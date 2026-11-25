// Layout for the level view and the trace view.
//
// Level view: cards sit in a tidy grid inside their frame (sorted by
// importance, so the busiest blocks come first). Frames, loose cards and
// outside stubs are then placed left to right by ELK's layered layout using
// only the summed frame-to-frame links, so the main flow of the code reads
// left to right with few crossings.

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

const elk = new ELK();

export async function layoutLevel(v: LevelView): Promise<Map<string, Box>> {
  const out = new Map<string, Box>();
  const frameSize = new Map<string, { w: number; h: number }>();
  for (const g of v.groups) {
    const n = g.cards.length;
    const cols = Math.max(1, Math.min(4, Math.ceil(Math.sqrt(n / 1.6))));
    const rows = Math.ceil(n / cols);
    g.cards.forEach((id, i) => {
      const c = i % cols;
      const r = Math.floor(i / cols);
      out.set(id, { x: FRAME_PAD + c * (CARD_W + GAP), y: FRAME_HEAD + r * (CARD_H + GAP), w: CARD_W, h: CARD_H, parent: g.id });
    });
    frameSize.set(g.id, {
      w: Math.max(240, FRAME_PAD * 2 + cols * CARD_W + (cols - 1) * GAP),
      h: FRAME_HEAD + rows * CARD_H + (rows - 1) * GAP + FRAME_PAD,
    });
  }

  const children = [
    ...v.groups.map((g) => ({ id: g.id, width: frameSize.get(g.id)!.w, height: frameSize.get(g.id)!.h })),
    ...v.loose.map((id) => ({ id, width: CARD_W, height: CARD_H })),
    ...v.stubs.map((s) => ({ id: s.id, width: STUB_W, height: STUB_H })),
  ];
  const ids = new Set(children.map((c) => c.id));
  const edges = v.groupLinks
    .filter((l) => ids.has(l.source) && ids.has(l.target))
    .map((l) => ({ id: l.id, sources: [l.source], targets: [l.target] }));

  // a single row of loose cards wraps better with rectangle packing
  const layered = edges.length > 0;
  const res = await elk.layout({
    id: "root",
    layoutOptions: layered
      ? {
          "elk.algorithm": "layered",
          "elk.direction": "RIGHT",
          "elk.spacing.nodeNode": "36",
          "elk.layered.spacing.nodeNodeBetweenLayers": "90",
          "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
          "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
          "elk.separateConnectedComponents": "true",
          "elk.spacing.componentComponent": "60",
        }
      : { "elk.algorithm": "rectpacking", "elk.aspectRatio": "1.8", "elk.spacing.nodeNode": "28" },
    children,
    edges,
  });
  for (const c of res.children ?? []) {
    out.set(c.id, { x: c.x ?? 0, y: c.y ?? 0, w: c.width ?? CARD_W, h: c.height ?? CARD_H });
  }
  return out;
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
