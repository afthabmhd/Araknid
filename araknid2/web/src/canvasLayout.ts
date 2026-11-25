// Layout for the level view and the trace view.
//
// Level view: ELK's layered layout places every card, frame and outside stub
// at once (frames are compound nodes), so code that uses something sits to
// its left and lines flow left to right. ELK also routes each line around the
// cards with right-angle bends, and we draw exactly those routes, so lines
// never run across a card. Cards with no lines at all are packed into a small
// grid inside their frame so they don't make the frame a long column.

import ELK from "elkjs/lib/elk.bundled.js";
import type { LevelView, Trace } from "./levelview";

export const CARD_W = 210;
export const CARD_H = 58;
const GAP = 10;
const FRAME_PAD = 14;
const FRAME_HEAD = 34;
export const STUB_W = 180;
export const STUB_H = 44;

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
  parent?: string;
}

export interface Point { x: number; y: number }

export interface LevelLayout {
  boxes: Map<string, Box>;
  routes: Map<string, Point[]>; // link id -> points in flow coordinates
}

const elk = new ELK();

const SPACING = {
  "elk.spacing.nodeNode": "22",
  "elk.spacing.edgeEdge": "7",
  "elk.spacing.edgeNode": "14",
  "elk.layered.spacing.nodeNodeBetweenLayers": "64",
  "elk.layered.spacing.edgeNodeBetweenLayers": "18",
  "elk.layered.spacing.edgeEdgeBetweenLayers": "7",
};

interface ElkNode {
  id: string;
  width?: number;
  height?: number;
  x?: number;
  y?: number;
  children?: ElkNode[];
  layoutOptions?: Record<string, string>;
}

export async function layoutLevel(v: LevelView): Promise<LevelLayout> {
  // which top-level box (frame, loose card or stub) each id lives in
  const owner = new Map<string, string | null>();
  for (const g of v.groups) {
    owner.set(g.id, null);
    for (const c of g.cards) owner.set(c, g.id);
  }
  for (const id of v.loose) owner.set(id, null);
  for (const s of v.stubs) owner.set(s.id, null);

  // links ELK can route: both ends on screen, and neither end inside the other
  // ("+ N more" cards get no lines: they would pull every hidden card's lines into one fan)
  const links = v.cardLinks.filter((l) => {
    if (!owner.has(l.source) || !owner.has(l.target)) return false;
    if (l.source.startsWith("more:") || l.target.startsWith("more:")) return false;
    return owner.get(l.source) !== l.target && owner.get(l.target) !== l.source;
  });
  const linked = new Set<string>();
  for (const l of links) { linked.add(l.source); linked.add(l.target); }

  const pack = (ids: string[], parent: string): { node: ElkNode; place: (x: number, y: number, out: Map<string, Box>) => void } => {
    const cols = Math.max(1, Math.min(4, Math.ceil(Math.sqrt(ids.length / 1.6))));
    const rows = Math.ceil(ids.length / cols);
    const node = { id: `iso:${parent}`, width: cols * CARD_W + (cols - 1) * GAP, height: rows * CARD_H + (rows - 1) * GAP };
    return {
      node,
      place: (x, y, out) => ids.forEach((id, i) => {
        out.set(id, { x: x + (i % cols) * (CARD_W + GAP), y: y + Math.floor(i / cols) * (CARD_H + GAP), w: CARD_W, h: CARD_H, parent: parent === "root" ? undefined : parent });
      }),
    };
  };

  const packs = new Map<string, ReturnType<typeof pack>>();
  const childrenOf = (ids: string[], parent: string): ElkNode[] => {
    const loneCards = ids.filter((id) => !linked.has(id) && !id.startsWith("out:") && !v.groups.some((g) => g.id === id));
    const nodes: ElkNode[] = [];
    for (const id of ids) {
      if (loneCards.length > 1 && loneCards.includes(id)) continue;
      const g = v.groups.find((x) => x.id === id);
      if (g) {
        nodes.push({
          id,
          layoutOptions: { ...SPACING, "elk.padding": `[top=${FRAME_HEAD},left=${FRAME_PAD},bottom=${FRAME_PAD},right=${FRAME_PAD}]` },
          children: childrenOf(g.cards, g.id),
        });
      } else if (id.startsWith("out:")) nodes.push({ id, width: STUB_W, height: STUB_H });
      else nodes.push({ id, width: CARD_W, height: CARD_H });
    }
    if (loneCards.length > 1) {
      const p = pack(loneCards, parent);
      packs.set(p.node.id, p);
      nodes.push(p.node);
    }
    return nodes;
  };

  const top = [...v.groups.map((g) => g.id), ...v.loose, ...v.stubs.map((s) => s.id)];
  const res = (await elk.layout({
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
      "elk.hierarchyHandling": "INCLUDE_CHILDREN",
      "elk.edgeRouting": "ORTHOGONAL",
      ...SPACING,
      "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
      "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
      "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
      "elk.separateConnectedComponents": "true",
      "elk.spacing.componentComponent": "40",
      "elk.aspectRatio": "1.6",
    },
    children: childrenOf(top, "root"),
    edges: links.map((l) => ({ id: l.id, sources: [l.source], targets: [l.target] })),
  } as never)) as unknown as ElkNode & { edges?: { id: string; container?: string; sections?: { startPoint: Point; endPoint: Point; bendPoints?: Point[] }[] }[] };

  const boxes = new Map<string, Box>();
  const abs = new Map<string, Point>([["root", { x: 0, y: 0 }]]);
  const walk = (n: ElkNode, parent: string, origin: Point) => {
    for (const c of n.children ?? []) {
      const x = c.x ?? 0, y = c.y ?? 0;
      abs.set(c.id, { x: origin.x + x, y: origin.y + y });
      const p = packs.get(c.id);
      if (p) { p.place(x, y, boxes); continue; }
      boxes.set(c.id, { x, y, w: c.width ?? CARD_W, h: c.height ?? CARD_H, parent: parent === "root" ? undefined : parent });
      if (c.children?.length) walk(c, c.id, { x: origin.x + x, y: origin.y + y });
    }
  };
  walk(res, "root", { x: 0, y: 0 });

  const routes = new Map<string, Point[]>();
  for (const e of res.edges ?? []) {
    const sec = e.sections?.[0];
    if (!sec) continue;
    const o = abs.get(e.container ?? "root") ?? { x: 0, y: 0 };
    const pts = [sec.startPoint, ...(sec.bendPoints ?? []), sec.endPoint].map((p) => ({ x: p.x + o.x, y: p.y + o.y }));
    routes.set(e.id, pts);
  }
  packComponents(res, links, owner, boxes, routes);
  return { boxes, routes };
}

/** ELK stacks unconnected parts in one tall column; lay them out in rows instead. */
function packComponents(res: ElkNode, links: { id: string; source: string; target: string }[], owner: Map<string, string | null>, boxes: Map<string, Box>, routes: Map<string, Point[]>) {
  const tops = (res.children ?? []).map((c) => c.id);
  if (tops.length < 2) return;
  const parent = new Map(tops.map((t) => [t, t]));
  const find = (x: string): string => (parent.get(x) === x ? x : find(parent.get(x)!));
  const topOf = (id: string) => owner.get(id) ?? (id.startsWith("iso:") ? null : id) ?? id;
  const topFor = (id: string) => (parent.has(id) ? id : topOf(id) ?? id);
  for (const l of links) {
    const a = find(topFor(l.source)), b = find(topFor(l.target));
    if (a !== b) parent.set(a, b);
  }
  // top-level boxes (an "iso:root" pack has no box of its own; use its cards)
  const comps = new Map<string, { ids: string[]; x0: number; y0: number; x1: number; y1: number }>();
  const add = (root: string, id: string, b: Box) => {
    const c = comps.get(root) ?? comps.set(root, { ids: [], x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity }).get(root)!;
    c.ids.push(id);
    c.x0 = Math.min(c.x0, b.x); c.y0 = Math.min(c.y0, b.y);
    c.x1 = Math.max(c.x1, b.x + b.w); c.y1 = Math.max(c.y1, b.y + b.h);
  };
  for (const t of tops) {
    if (t === "iso:root") {
      for (const [id, b] of boxes) if (!b.parent && !tops.includes(id)) add(`iso-root`, id, b);
    } else if (boxes.has(t)) add(find(t), t, boxes.get(t)!);
  }
  if (comps.size < 2) return;
  const list = [...comps.entries()].sort((a, b) => (b[1].y1 - b[1].y0) - (a[1].y1 - a[1].y0));
  const area = list.reduce((s, [, c]) => s + (c.x1 - c.x0) * (c.y1 - c.y0), 0);
  const maxW = Math.max(...list.map(([, c]) => c.x1 - c.x0));
  void area;
  const GAPC = 40;
  // shelf packing; try a few row widths and keep the one closest to a wide screen
  const shelf = (rowW: number) => {
    let x = 0, y = 0, rowH = 0, w = 0;
    const at = new Map<string, Point>();
    for (const [root, c] of list) {
      const cw = c.x1 - c.x0, ch = c.y1 - c.y0;
      if (x > 0 && x + cw > rowW) { x = 0; y += rowH + GAPC; rowH = 0; }
      at.set(root, { x: x - c.x0, y: y - c.y0 });
      x += cw + GAPC;
      w = Math.max(w, x - GAPC);
      rowH = Math.max(rowH, ch);
    }
    return { at, ratio: w / (y + rowH) };
  };
  let best = shelf(maxW);
  for (const m of [1.5, 2, 2.5, 3, 4, 6]) {
    const t = shelf(maxW * m);
    if (Math.abs(Math.log(t.ratio / 1.7)) < Math.abs(Math.log(best.ratio / 1.7))) best = t;
  }
  const shift = best.at;
  for (const [root, c] of list) {
    const d = shift.get(root)!;
    for (const id of c.ids) {
      const b = boxes.get(id)!;
      boxes.set(id, { ...b, x: b.x + d.x, y: b.y + d.y });
    }
  }
  for (const l of links) {
    const pts = routes.get(l.id);
    const t = topFor(l.source);
    const d = parent.has(t) ? shift.get(find(t)) : shift.get("iso-root");
    if (pts && d) routes.set(l.id, pts.map((p) => ({ x: p.x + d.x, y: p.y + d.y })));
  }
}

/** Trace: callers in a column on the left, the block in the middle, callees on the right. */
export function layoutTrace(t: Trace): Map<string, Box> {
  const out = new Map<string, Box>();
  const COL_GAP = 140;
  const column = (groups: Trace["callers"], x: number, side: string) => {
    let y = 0;
    for (const g of groups) {
      const gid = `${side}:${g.group.id}`;
      const h = FRAME_HEAD + g.items.length * (CARD_H + GAP) - GAP + FRAME_PAD;
      out.set(gid, { x, y, w: CARD_W + FRAME_PAD * 2, h });
      g.items.forEach((it, i) => {
        out.set(`${side}:${it.block.id}`, { x: FRAME_PAD, y: FRAME_HEAD + i * (CARD_H + GAP), w: CARD_W, h: CARD_H, parent: gid });
      });
      y += h + 24;
    }
    return y;
  };
  const leftH = column(t.callers, 0, "in");
  const midX = CARD_W + FRAME_PAD * 2 + COL_GAP;
  const rightX = midX + CARD_W + 40 + COL_GAP;
  const rightH = column(t.callees, rightX, "out");
  const tallest = Math.max(leftH, rightH, CARD_H);
  out.set(`mid:${t.centre.id}`, { x: midX, y: Math.max(0, tallest / 2 - 40), w: CARD_W + 40, h: 80 });
  return out;
}
