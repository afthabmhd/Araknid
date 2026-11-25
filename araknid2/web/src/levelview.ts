// What the canvas shows, kept simple on purpose.
//
// Rules (from Sourcetrail, CodeSee and the edge-compression research):
// 1. One block at a time. The canvas shows what is inside the block you are
//    in, at the level the slider picks. Everything else is one click away.
// 2. At most one layer of frames. Cards are grouped by the child of the
//    current block they live in. Frames never nest inside frames.
// 3. Connections are summed. At rest only frame-to-frame lines are drawn, one
//    per pair, with a count. A card's own lines appear when you point at it.
// 4. Nothing is cut off. A connection to code outside the current block is
//    counted on a stub for the outside block it goes to.

import type { Block, EdgeKind } from "./types";
import { collapseChain, isVisible, visibleChildren, type Filters, type Index } from "./view";

export const MAX_CARDS_PER_GROUP = 24; // [Guess]
export const MAX_GROUPS = 16; // [Guess]

export interface Card {
  id: string; // block id, or "more:<group>"
  block?: Block;
  chain: Block[]; // pass-through collapsed blocks ending with block
  group: string | null; // frame id, null when the card is loose at the top level
  more?: number; // for "+ N more"
}

export interface Group {
  id: string; // block id of the frame
  block: Block;
  chain: Block[];
  cards: string[];
  hidden: number;
}

export interface Stub {
  id: string; // "out:<block id>"
  block: Block;
  incoming: number; // connections from this outside block into the current one
  outgoing: number;
}

export interface Link {
  id: string;
  source: string;
  target: string;
  count: number;
  kinds: Partial<Record<EdgeKind, number>>;
  maybe: boolean;
}

export interface LevelView {
  root: Block; // effective root after skipping pass-through wrappers
  rootChain: Block[];
  level: number; // the level actually shown
  groups: Group[];
  cards: Map<string, Card>;
  loose: string[]; // cards not inside a frame
  stubs: Stub[];
  groupLinks: Link[]; // between frames, loose cards and stubs
  cardLinks: Link[]; // between cards (shown on focus)
  repOf: (blockId: string) => string | undefined; // card (or frame/stub) that stands for a block
}

function addLink(map: Map<string, Link>, s: string, t: string, kind: EdgeKind, count: number, maybe: boolean) {
  const id = `${s}>${t}`;
  const l = map.get(id) ?? map.set(id, { id, source: s, target: t, count: 0, kinds: {}, maybe: true }).get(id)!;
  l.count += count;
  l.kinds[kind] = (l.kinds[kind] ?? 0) + count;
  l.maybe = l.maybe && maybe;
}

export function buildLevelView(ix: Index, rootId: string, level: number, f: Filters, showAll: Record<string, boolean>): LevelView {
  const rootChain = collapseChain(ix, ix.get(rootId), f);
  let root = rootChain[rootChain.length - 1];
  if (!visibleChildren(ix, root, f).length) root = ix.get(rootId);

  const cards = new Map<string, Card>();
  const groups: Group[] = [];
  const loose: string[] = [];
  const rep = new Map<string, string>();
  for (const b of rootChain) rep.set(b.id, "__root__");

  // Blocks at the chosen level inside `b` (not nested inside each other).
  const atLevel = (b: Block, out: Block[]) => {
    for (const c of visibleChildren(ix, b, f)) {
      if (c.level >= level || !c.children.length || c.kind === "class") out.push(c);
      else atLevel(c, out);
    }
  };

  const byImportance = (a: Block, b: Block) => Number(b.pinned) - Number(a.pinned) || b.importance - a.importance || b.loc - a.loc;

  const tops = visibleChildren(ix, root, f).map((c) => collapseChain(ix, c, f));
  // Is the slider asking for anything deeper than the current block's children?
  const deeper = tops.some((ch) => {
    const last = ch[ch.length - 1];
    return last.level < level && last.kind !== "class" && visibleChildren(ix, last, f).length > 0;
  });

  const addCard = (chain: Block[], group: string | null) => {
    const b = chain[chain.length - 1];
    cards.set(b.id, { id: b.id, block: b, chain, group });
    for (const c of chain) rep.set(c.id, b.id);
    return b.id;
  };

  if (!deeper) {
    // flat: the children themselves are the cards
    const sorted = tops.slice().sort((a, b) => byImportance(a[a.length - 1], b[b.length - 1]));
    const limit = showAll[root.id] ? Infinity : MAX_CARDS_PER_GROUP * 2;
    sorted.slice(0, limit).forEach((ch) => loose.push(addCard(ch, null)));
    if (sorted.length > limit) {
      const id = `more:${root.id}`;
      cards.set(id, { id, chain: [], group: null, more: sorted.length - limit });
      for (const ch of sorted.slice(limit)) for (const b of ch) rep.set(b.id, id);
      loose.push(id);
    }
  } else {
    const sortedTops = tops.slice().sort((a, b) => byImportance(a[a.length - 1], b[b.length - 1]));
    for (const chain of sortedTops) {
      const top = chain[chain.length - 1];
      const inner: Block[] = [];
      if (top.level < level && top.kind !== "class") atLevel(top, inner);
      if (!inner.length || groups.length >= MAX_GROUPS) {
        loose.push(addCard(chain, null));
        continue;
      }
      const g: Group = { id: top.id, block: top, chain, cards: [], hidden: 0 };
      for (const c of chain) rep.set(c.id, g.id);
      const sorted = inner.map((c) => collapseChain(ix, c, f)).sort((a, b) => byImportance(a[a.length - 1], b[b.length - 1]));
      const limit = showAll[top.id] ? Infinity : MAX_CARDS_PER_GROUP;
      sorted.slice(0, limit).forEach((ch) => g.cards.push(addCard(ch, g.id)));
      if (sorted.length > limit) {
        const id = `more:${top.id}`;
        g.hidden = sorted.length - limit;
        cards.set(id, { id, chain: [], group: g.id, more: g.hidden });
        for (const ch of sorted.slice(limit)) for (const b of ch) rep.set(b.id, id);
        g.cards.push(id);
      }
      groups.push(g);
    }
  }

  // Every block maps to the card, frame or root that contains it.
  const resolve = (id: string): string | undefined => {
    const hit = rep.get(id);
    if (hit !== undefined) return hit;
    const b = ix.blocks.get(id);
    if (!b?.parent_id) return undefined;
    const r = resolve(b.parent_id);
    if (r !== undefined) rep.set(id, r);
    return r;
  };

  // Outside blocks: summarised at the child of the common ancestor.
  const rootPath = ix.ancestors(root.id).map((b) => b.id);
  const stubs = new Map<string, Stub>();
  const stubFor = (id: string): Stub | undefined => {
    const path = ix.ancestors(id);
    let i = 0;
    while (i < path.length && i < rootPath.length && path[i].id === rootPath[i]) i++;
    const top = path[i];
    if (!top) return undefined;
    const sid = `out:${top.id}`;
    return stubs.get(sid) ?? stubs.set(sid, { id: sid, block: top, incoming: 0, outgoing: 0 }).get(sid)!;
  };

  const groupOf = (cardId: string) => cards.get(cardId)?.group ?? cardId;
  const groupLinks = new Map<string, Link>();
  const cardLinks = new Map<string, Link>();
  for (const e of ix.g.edges) {
    if (!f.edgeKinds[e.kind]) continue;
    if (e.certainty === "maybe" && !f.maybe) continue;
    const sb = ix.blocks.get(e.source);
    const tb = ix.blocks.get(e.target);
    if (!sb || !tb || !isVisible(sb, f) || !isVisible(tb, f)) continue;
    let s = resolve(e.source);
    let t = resolve(e.target);
    if (s === "__root__" || t === "__root__") continue;
    if (s === undefined && t === undefined) continue;
    const maybe = e.certainty === "maybe";
    if (s === undefined) {
      const st = stubFor(e.source);
      if (!st) continue;
      st.incoming += e.count;
      s = st.id;
    }
    if (t === undefined) {
      const st = stubFor(e.target);
      if (!st) continue;
      st.outgoing += e.count;
      t = st.id;
    }
    if (s === t) continue;
    // card level (both ends known); a frame id here means "somewhere in that frame"
    addLink(cardLinks, s, t, e.kind, e.count, maybe);
    const gs = s.startsWith("out:") ? s : groupOf(s);
    const gt = t.startsWith("out:") ? t : groupOf(t);
    if (gs !== gt) addLink(groupLinks, gs, gt, e.kind, e.count, maybe);
  }

  return {
    root,
    rootChain,
    level,
    groups,
    cards,
    loose,
    stubs: [...stubs.values()].sort((a, b) => b.incoming + b.outgoing - (a.incoming + a.outgoing)),
    groupLinks: [...groupLinks.values()],
    cardLinks: [...cardLinks.values()],
    repOf: (id) => resolve(id),
  };
}

/** Sourcetrail-style trace: who uses this block, and what it uses. */
export interface Trace {
  centre: Block;
  callers: { group: Block; items: { block: Block; kinds: EdgeKind[]; count: number }[] }[];
  callees: { group: Block; items: { block: Block; kinds: EdgeKind[]; count: number }[] }[];
}

export function buildTrace(ix: Index, id: string, f: Filters): Trace {
  const centre = ix.get(id);
  // include connections of everything inside the block (a file's functions, a class's methods)
  const inside = new Set<string>([id]);
  const stack = [id];
  while (stack.length) {
    const cur = ix.get(stack.pop()!);
    for (const c of cur.children) {
      inside.add(c);
      stack.push(c);
    }
  }
  const side = (dir: "in" | "out") => {
    const items = new Map<string, { block: Block; kinds: Set<EdgeKind>; count: number }>();
    for (const bid of inside) {
      const list = (dir === "in" ? ix.inc : ix.out).get(bid) ?? [];
      for (const e of list) {
        if (!f.edgeKinds[e.kind] || (e.certainty === "maybe" && !f.maybe)) continue;
        const other = ix.blocks.get(dir === "in" ? e.source : e.target);
        if (!other || inside.has(other.id) || !isVisible(other, f)) continue;
        const it = items.get(other.id) ?? items.set(other.id, { block: other, kinds: new Set(), count: 0 }).get(other.id)!;
        it.kinds.add(e.kind);
        it.count += e.count;
      }
    }
    // group by the file (or, for files, the module) they live in
    const groups = new Map<string, { group: Block; items: { block: Block; kinds: EdgeKind[]; count: number }[] }>();
    for (const it of items.values()) {
      let g = it.block.parent_id ? ix.get(it.block.parent_id) : it.block;
      while (g.level > 3 && g.parent_id) g = ix.get(g.parent_id);
      const entry = groups.get(g.id) ?? groups.set(g.id, { group: g, items: [] }).get(g.id)!;
      entry.items.push({ block: it.block, kinds: [...it.kinds], count: it.count });
    }
    return [...groups.values()].sort((a, b) => b.items.length - a.items.length);
  };
  return { centre, callers: side("in"), callees: side("out") };
}
