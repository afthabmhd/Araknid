// The spiderweb layout.
//
// The block you are looking at sits at the centre. Each level of the tree is
// a ring around it, and every block hangs on a thread (spoke) from its parent.
// A block gets a slice of the circle in proportion to how much it holds, so
// siblings never overlap and the whole map stays round and balanced.
// Connections (calls, imports) are drawn as curves pulled towards their
// common parent, which bundles them into a few clean strands instead of a
// hairball. Deterministic: the same map always lands in the same place.

import type { Display, DisplayNode } from "./view";

export interface WebPos {
  x: number; // centre of the dot
  y: number;
  r: number; // dot radius
  angle: number; // radians, 0 = right, clockwise (screen coords)
  depth: number; // 0 = centre, 1 = first ring, ...
  branch: number; // index of the first-ring ancestor, for colour
}

export interface WebLayout {
  pos: Map<string, WebPos>;
  rings: number[]; // radius of each ring, index = depth
  centre: { x: number; y: number; r: number };
}

const DOT_SPACING = 30; // [Guess] minimum arc length between dots on a ring, px
const RING_GAP = 170; // minimum distance between rings, px
const FIRST_RING = 190;
const WEDGE_PAD = 0.12; // fraction of a wedge kept empty between siblings

export function dotRadius(n: DisplayNode, depth: number): number {
  if (n.kind === "more" || n.kind === "ghost") return 9;
  const loc = n.block?.loc ?? 1;
  const size = 4 + Math.min(11, Math.sqrt(loc) / 2.2);
  if (n.kind === "frame") return Math.max(size, 13 - depth);
  return size;
}

export function webLayout(d: Display): WebLayout {
  const weight = new Map<string, number>();
  const w = (id: string): number => {
    const hit = weight.get(id);
    if (hit !== undefined) return hit;
    const n = d.nodes.get(id)!;
    // a frame weighs its children; a closed dot weighs a little more when big
    const v = n.children.length ? n.children.reduce((s, c) => s + w(c), 0) : 1;
    weight.set(id, v);
    return v;
  };

  // nodes per depth, to size the rings
  const perDepth: number[] = [];
  const angles = new Map<string, { a: number; depth: number; branch: number }>();
  const roots = d.roots.filter((id) => d.nodes.get(id)!.kind !== "ghost");
  const ghosts = d.roots.filter((id) => d.nodes.get(id)!.kind === "ghost");

  const place = (ids: string[], a0: number, a1: number, depth: number, branch: number | null) => {
    const total = ids.reduce((s, id) => s + w(id), 0) || 1;
    let a = a0;
    const span = a1 - a0;
    ids.forEach((id, i) => {
      const share = (w(id) / total) * span;
      const pad = ids.length > 1 ? share * WEDGE_PAD * 0.5 : 0;
      const b = branch ?? i;
      angles.set(id, { a: a + share / 2, depth, branch: b });
      perDepth[depth] = (perDepth[depth] ?? 0) + 1;
      const n = d.nodes.get(id)!;
      if (n.children.length) place(n.children, a + pad, a + share - pad, depth + 1, b);
      a += share;
    });
  };
  // start at the top and go clockwise
  place(roots, -Math.PI / 2, (3 * Math.PI) / 2, 1, null);

  const rings: number[] = [0];
  for (let depth = 1; depth < perDepth.length; depth++) {
    const need = ((perDepth[depth] ?? 0) * DOT_SPACING) / (2 * Math.PI);
    const prev = rings[depth - 1];
    rings[depth] = Math.max(depth === 1 ? FIRST_RING : prev + RING_GAP, need, prev + RING_GAP * 0.8);
  }

  const pos = new Map<string, WebPos>();
  for (const [id, { a, depth, branch }] of angles) {
    const R = rings[depth];
    const n = d.nodes.get(id)!;
    pos.set(id, { x: Math.cos(a) * R, y: Math.sin(a) * R, r: dotRadius(n, depth), angle: a, depth, branch });
  }

  // blocks outside a drilled-in block orbit beyond the outermost ring
  if (ghosts.length) {
    const R = (rings[rings.length - 1] ?? FIRST_RING) + RING_GAP;
    ghosts.forEach((id, i) => {
      const a = -Math.PI / 2 + ((i + 0.5) / ghosts.length) * 2 * Math.PI;
      pos.set(id, { x: Math.cos(a) * R, y: Math.sin(a) * R, r: 9, angle: a, depth: rings.length, branch: -1 });
    });
    rings.push(R);
  }

  return { pos, rings, centre: { x: 0, y: 0, r: 16 } };
}

/** Control point that bends an edge towards the parent both ends share. */
export function bundlePoint(
  d: Display,
  layout: WebLayout,
  source: string,
  target: string,
  beta = 0.85,
): { x: number; y: number } {
  const chain = (id: string) => {
    const out: string[] = [];
    let cur: string | null = id;
    while (cur) {
      out.unshift(cur);
      cur = d.nodes.get(cur)?.parent ?? null;
    }
    return out;
  };
  const a = chain(source);
  const b = chain(target);
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i++;
  const lca = i > 0 ? layout.pos.get(a[i - 1]) : undefined;
  const anchor = lca ?? layout.centre;
  const s = layout.pos.get(source)!;
  const t = layout.pos.get(target)!;
  const mx = (s.x + t.x) / 2;
  const my = (s.y + t.y) / 2;
  return { x: mx + (anchor.x - mx) * beta, y: my + (anchor.y - my) * beta };
}
