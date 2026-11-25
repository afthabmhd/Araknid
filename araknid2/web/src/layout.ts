// Auto layout with ELK. Each frame is laid out on its own (children first),
// using edges rolled up to siblings in that frame. Frames with internal
// connections use a layered left-to-right layout; frames without use
// rectangle packing so they stay compact.

import ELK, { type ElkNode, type ElkExtendedEdge } from "elkjs/lib/elk.bundled.js";
import type { Display } from "./view";

const elk = new ELK();

export const CARD_W = 250;
export const CARD_H = 92;
export const CODE_W = 560;
export const FRAME_HEADER = 40;

export interface Size {
  w: number;
  h: number;
}

export interface Placed {
  x: number; // relative to parent
  y: number;
  w: number;
  h: number;
}

export async function layout(d: Display, sizeOf: (id: string) => Size): Promise<Map<string, Placed>> {
  const parentOf = (id: string) => d.nodes.get(id)?.parent ?? null;
  const chainOf = (id: string) => {
    const out: (string | null)[] = [];
    let cur: string | null = id;
    while (cur) {
      out.unshift(cur);
      cur = parentOf(cur);
    }
    out.unshift(null);
    return out;
  };

  // Layout-only edges between siblings, keyed by container (null = top level)
  const sib = new Map<string | null, Set<string>>();
  for (const e of d.edges) {
    const a = chainOf(e.source);
    const b = chainOf(e.target);
    let i = 0;
    while (i < a.length && i < b.length && a[i] === b[i]) i++;
    const container = a[i - 1];
    const s = a[i];
    const t = b[i];
    if (!s || !t || s === t) continue;
    const set = sib.get(container) ?? sib.set(container, new Set()).get(container)!;
    set.add(`${s}>${t}`);
  }

  const build = (id: string): ElkNode => {
    const n = d.nodes.get(id)!;
    if (n.kind !== "frame") {
      const s = sizeOf(id);
      return { id, width: s.w, height: s.h };
    }
    return container(id, n.children);
  };

  const container = (id: string, children: string[]): ElkNode => {
    const edges = [...(sib.get(id === "__top__" ? null : id) ?? [])].map((k, i): ElkExtendedEdge => {
      const [s, t] = k.split(">");
      return { id: `${id}-e${i}`, sources: [s], targets: [t] };
    });
    const layered = edges.length > 0;
    return {
      id,
      layoutOptions: layered
        ? {
            "elk.algorithm": "layered",
            "elk.direction": "RIGHT",
            "elk.layered.spacing.nodeNodeBetweenLayers": "70",
            "elk.spacing.nodeNode": "28",
            "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
            "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
            "elk.padding": `[top=${id === "__top__" ? 20 : FRAME_HEADER + 14},left=18,bottom=18,right=18]`,
          }
        : {
            "elk.algorithm": "rectpacking",
            "elk.aspectRatio": "1.6",
            "elk.spacing.nodeNode": "22",
            "elk.padding": `[top=${id === "__top__" ? 20 : FRAME_HEADER + 14},left=18,bottom=18,right=18]`,
          },
      children: children.map(build),
      edges,
    };
  };

  const graph = container("__top__", d.roots);
  const res = await elk.layout(graph);
  const out = new Map<string, Placed>();
  const walk = (n: ElkNode) => {
    for (const c of n.children ?? []) {
      out.set(c.id, { x: c.x ?? 0, y: c.y ?? 0, w: c.width ?? CARD_W, h: c.height ?? CARD_H });
      walk(c);
    }
  };
  walk(res);
  return out;
}
