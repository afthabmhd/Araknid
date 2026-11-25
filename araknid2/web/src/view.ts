// Shared helpers over the stored block tree: the index, filters, pass-through
// collapse, titles and search. What the canvas shows is built in levelview.ts.

import type { Block, Edge, EdgeKind, GraphData } from "./types";

const COLLAPSIBLE = new Set(["project", "system", "module", "file"]);

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
