// Turns the stored block tree into what the canvas shows: which blocks are
// open frames, which are closed cards, what folds into "+ N more", and the
// edges rolled up onto whatever is visible. Pure functions, no React.

import type { Block, Edge, EdgeKind, GraphData } from "./types";

export const MAX_CHILDREN = 30; // [Guess] before "+ N more" folding kicks in
const COLLAPSIBLE = new Set(["project", "system", "module", "file"]);
const CONTAINERS = new Set(["project", "system", "module", "suggested_group", "file", "class"]);

export interface Filters {
  tests: boolean;
  assets: boolean;
  types: boolean;
  edgeKinds: Record<EdgeKind, boolean>;
  maybe: boolean;
}

export const defaultFilters: Filters = {
  tests: false,
  assets: false,
  types: false,
  edgeKinds: { imports: true, calls: true, inherits: true, instantiates: true, renders: true, next: true },
  maybe: true,
};

export interface ViewState {
  rootId: string; // drill root
  level: number; // slider, 1..4
  open: Record<string, boolean>; // per-block override (mixed detail)
  showAll: Record<string, boolean>; // containers with "+ N more" unfolded
  filters: Filters;
}

export type DisplayKind = "frame" | "card" | "more" | "ghost";

export interface DisplayNode {
  id: string; // block id, or synthetic id for more/ghost
  kind: DisplayKind;
  block?: Block;
  chain: Block[]; // pass-through collapsed blocks, outermost first, ending with block
  parent: string | null; // display parent id
  children: string[];
  moreCount?: number;
  moreOf?: string;
}

export interface DisplayEdge {
  id: string;
  source: string;
  target: string;
  kind: EdgeKind;
  count: number;
  maybe: boolean;
}

export interface Display {
  nodes: Map<string, DisplayNode>;
  roots: string[];
  edges: DisplayEdge[];
  /** the block whose inside is on screen after skipping pass-through roots */
  effectiveRoot: Block;
}

export class Index {
  blocks = new Map<string, Block>();
  out = new Map<string, Edge[]>();
  inc = new Map<string, Edge[]>();
  constructor(public g: GraphData) {
    for (const b of g.blocks) this.blocks.set(b.id, b);
    for (const e of g.edges) {
      (this.out.get(e.source) ?? this.out.set(e.source, []).get(e.source)!).push(e);
      (this.inc.get(e.target) ?? this.inc.set(e.target, []).get(e.target)!).push(e);
    }
  }
  get(id: string) {
    return this.blocks.get(id)!;
  }
  ancestors(id: string): Block[] {
    const out: Block[] = [];
    let b = this.blocks.get(id);
    while (b) {
      out.unshift(b);
      b = b.parent_id ? this.blocks.get(b.parent_id) : undefined;
    }
    return out;
  }
  isAncestor(a: string, b: string): boolean {
    let cur = this.blocks.get(b)?.parent_id;
    while (cur) {
      if (cur === a) return true;
      cur = this.blocks.get(cur)?.parent_id;
    }
    return false;
  }
}

export function isVisible(b: Block, f: Filters): boolean {
  if (b.is_test && !f.tests) return false;
  if (b.kind === "asset" && !f.assets) return false;
  if (b.kind === "type" && !f.types) return false;
  return true;
}

export function visibleChildren(ix: Index, b: Block, f: Filters): Block[] {
  return b.children.map((c) => ix.get(c)).filter((c) => isVisible(c, f));
}

/** Rule 2, pass-through collapse: a block with one child merges with it. */
export function collapseChain(ix: Index, b: Block, f: Filters): Block[] {
  const chain = [b];
  let cur = b;
  while (COLLAPSIBLE.has(cur.kind)) {
    const kids = visibleChildren(ix, cur, f);
    if (kids.length !== 1) break;
    cur = kids[0];
    chain.push(cur);
  }
  return chain;
}

export function defaultOpen(b: Block, level: number): boolean {
  if (b.kind === "project") return true;
  if (b.kind === "class") return level >= 4; // classes are frames holding their methods
  if (b.level >= 4) return false; // nested definitions open by drilling in
  return b.level < level;
}

export function displayTitle(chain: Block[]): string {
  return chain
    .filter((b) => b.kind !== "project")
    .map((b) => b.code_name)
    .join(" › ");
}

export function humanTitle(b: Block): string {
  if (b.human_name) return b.human_name;
  if (["file", "asset", "module", "system", "project"].includes(b.kind)) return b.code_name;
  const s = b.code_name.replace(/[_-]+/g, " ").replace(/([a-z0-9])([A-Z])/g, "$1 $2").trim();
  return s ? s[0].toUpperCase() + s.slice(1) : b.code_name;
}

export function buildDisplay(ix: Index, v: ViewState): Display {
  const f = v.filters;
  const nodes = new Map<string, DisplayNode>();
  const rep = new Map<string, string>(); // block id -> display node id

  // Skip pass-through roots: a project with one system opens straight at its modules.
  let root = ix.get(v.rootId);
  const rootChain = collapseChain(ix, root, f);
  root = rootChain[rootChain.length - 1];
  if (!CONTAINERS.has(root.kind) || visibleChildren(ix, root, f).length === 0) root = ix.get(v.rootId);
  for (const b of rootChain) rep.set(b.id, "__root__");

  const place = (b: Block, parent: string | null): string => {
    const chain = collapseChain(ix, b, f);
    const last = chain[chain.length - 1];
    const kids = visibleChildren(ix, last, f);
    const open = (v.open[last.id] ?? defaultOpen(last, v.level)) && kids.length > 0;
    const node: DisplayNode = { id: last.id, kind: open ? "frame" : "card", block: last, chain, parent, children: [] };
    nodes.set(node.id, node);
    for (const c of chain) rep.set(c.id, node.id);
    if (open) node.children = placeChildren(last, kids, node.id);
    return node.id;
  };

  const placeChildren = (owner: Block, kids: Block[], parentId: string | null): string[] => {
    let shown = kids;
    let hidden: Block[] = [];
    if (kids.length > MAX_CHILDREN && !v.showAll[owner.id]) {
      const sorted = [...kids].sort((a, b) => Number(b.pinned) - Number(a.pinned) || b.importance - a.importance);
      const keep = new Set(sorted.slice(0, MAX_CHILDREN).map((b) => b.id));
      shown = kids.filter((k) => keep.has(k.id));
      hidden = kids.filter((k) => !keep.has(k.id));
    }
    const ids = shown.map((k) => place(k, parentId));
    if (hidden.length) {
      const id = `more:${owner.id}`;
      nodes.set(id, { id, kind: "more", chain: [], parent: parentId, children: [], moreCount: hidden.length, moreOf: owner.id });
      for (const h of hidden) rep.set(h.id, id);
      ids.push(id);
    }
    return ids;
  };

  const roots = placeChildren(root, visibleChildren(ix, root, f), null);

  // Every block maps to its nearest displayed ancestor.
  const resolve = (id: string): string | undefined => {
    const hit = rep.get(id);
    if (hit !== undefined) return hit;
    const b = ix.blocks.get(id);
    if (!b || !b.parent_id) return undefined;
    const r = resolve(b.parent_id);
    if (r !== undefined) rep.set(id, r);
    return r;
  };

  // Edges leaving the drill root become stubs to ghost nodes.
  const ghostFor = (id: string): string | undefined => {
    const path = ix.ancestors(id);
    const rootPath = ix.ancestors(root.id).map((b) => b.id);
    let i = 0;
    while (i < path.length && i < rootPath.length && path[i].id === rootPath[i]) i++;
    const top = path[i];
    if (!top) return undefined;
    const gid = `ghost:${top.id}`;
    if (!nodes.has(gid)) {
      nodes.set(gid, { id: gid, kind: "ghost", block: top, chain: [top], parent: null, children: [] });
      roots.push(gid);
    }
    return gid;
  };

  const agg = new Map<string, DisplayEdge>();
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
    if (s === undefined) s = ghostFor(e.source);
    if (t === undefined) t = ghostFor(e.target);
    if (!s || !t || s === t) continue;
    // skip edges between a frame and something inside it
    if (isDisplayAncestor(nodes, s, t) || isDisplayAncestor(nodes, t, s)) continue;
    const key = `${s}|${t}|${e.kind}`;
    const cur = agg.get(key);
    if (cur) {
      cur.count += e.count;
      cur.maybe = cur.maybe && e.certainty === "maybe";
    } else {
      agg.set(key, { id: key, source: s, target: t, kind: e.kind, count: e.count, maybe: e.certainty === "maybe" });
    }
  }
  return { nodes, roots, edges: [...agg.values()], effectiveRoot: root };
}

function isDisplayAncestor(nodes: Map<string, DisplayNode>, a: string, b: string): boolean {
  let cur = nodes.get(b)?.parent;
  while (cur) {
    if (cur === a) return true;
    cur = nodes.get(cur)?.parent ?? null;
  }
  return false;
}

export function search(ix: Index, q: string, f: Filters, limit = 12): Block[] {
  const s = q.trim().toLowerCase();
  if (!s) return [];
  const scored: [number, Block][] = [];
  for (const b of ix.blocks.values()) {
    if (b.kind === "project" || !isVisible(b, f)) continue;
    const name = b.code_name.toLowerCase();
    let score = -1;
    if (name === s) score = 100;
    else if (name.startsWith(s)) score = 60;
    else if (name.includes(s)) score = 40;
    else if (b.path.toLowerCase().includes(s)) score = 10;
    if (score >= 0) scored.push([score + Math.min(b.importance, 20) + (b.level === 4 ? 5 : 0), b]);
  }
  return scored.sort((a, b) => b[0] - a[0]).slice(0, limit).map((x) => x[1]);
}
