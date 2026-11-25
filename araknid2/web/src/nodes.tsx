import { createContext, memo, useContext, useRef } from "react";
import { BaseEdge, Handle, Position, type EdgeProps, type NodeProps } from "@xyflow/react";
import type { Block, InsideBlock } from "./types";
import { displayTitle, humanTitle } from "./view";
import type { Card, Group, Stub } from "./levelview";

export interface CanvasActions {
  select: (id: string) => void;
  /** Single click on a card: open its trace (Trace first). */
  trace: (b: Block) => void;
  hover: (id: string | null) => void;
  toggleOpen: (b: Block) => void;
  drill: (b: Block) => void;
  showAll: (ownerId: string) => void;
  drillInside: (b: InsideBlock) => void;
}

export const Actions = createContext<CanvasActions | null>(null);
const useActions = () => useContext(Actions)!;

export const KIND_LABEL: Record<string, string> = {
  project: "Project", system: "System", module: "Module", file: "File", asset: "File", class: "Class",
  function: "Function", method: "Method", component: "Component", type: "Type", suggested_group: "Group",
  section: "Section", statement: "Statement", expression: "Expression",
};

export function Badges({ b }: { b: Block }) {
  return (
    <div className="badges">
      <span className={`badge kind kind-${b.kind}`}>{KIND_LABEL[b.kind] ?? b.kind}</span>
      {b.language && <span className="badge">{b.language === "tsx" ? "tsx" : b.language === "typescript" ? "ts" : b.language === "javascript" ? "js" : "py"}</span>}
      <span className="badge" title="Lines of code">{b.loc} loc</span>
      {b.tags.includes("route") && <span className="badge role">route</span>}
      {b.tags.includes("entry") && <span className="badge role">entry</span>}
      {b.tags.includes("hub") && <span className="badge muted" title="Called from almost everywhere; left out of importance ranking">hub</span>}
      {b.build_state === "partial" && <span className="badge warn" title="Stub: body is empty, pass, or raises NotImplementedError">partially built</span>}
      {b.health && <span className="badge warn" title={b.health === "parse_errors" ? "The parser hit syntax it could not read in this file" : "Large file with almost no blocks found"}>{b.health === "parse_errors" ? "parse errors" : "few blocks"}</span>}
      {b.is_test && <span className="badge muted">test</span>}
    </div>
  );
}

// ------------------------------------------------------------------ level view nodes

const KIND_ICON: Record<string, string> = {
  system: "◎", module: "▣", file: "▤", asset: "▢", class: "◇", function: "ƒ", method: "ƒ",
  component: "◈", type: "τ", project: "◎",
};

/** One block: a small card with its name and size. */
export const CardNode = memo(({ data }: NodeProps) => {
  const a = useActions();
  const c = data.card as Card;
  const b = c.block!;
  const timer = useRef<number | null>(null);
  const canOpen = b.kind !== "asset" && (b.children.length > 0 || ["function", "method", "component"].includes(b.kind));
  return (
    <div
      className={`card2 kind-${b.kind}`}
      onClick={(e) => {
        e.stopPropagation();
        if (timer.current) clearTimeout(timer.current);
        timer.current = window.setTimeout(() => a.trace(b), 220);
      }}
      onDoubleClick={(e) => {
        e.stopPropagation();
        if (timer.current) clearTimeout(timer.current);
        if (canOpen) a.drill(b);
      }}
      onMouseEnter={() => a.hover(b.id)}
      onMouseLeave={() => a.hover(null)}
      title={canOpen ? "Click to trace · double-click to open" : "Click to trace"}
    >
      <Handle type="target" position={Position.Left} className="h" isConnectable={false} />
      <span className="card2-icon" aria-hidden>{KIND_ICON[b.kind] ?? "•"}</span>
      <div className="card2-text">
        <div className="card2-title">{c.chain.length > 1 ? displayTitle(c.chain) : humanTitle(b)}</div>
        <div className="card2-sub">
          {KIND_LABEL[b.kind]} · {b.loc} loc
          {b.build_state === "partial" && <span className="warn-dot" title="Partially built (stub)"> · stub</span>}
          {b.health && <span className="warn-dot" title="Parse problem"> · ⚠</span>}
        </div>
      </div>
      {canOpen && <span className="card2-open" aria-hidden>›</span>}
      <Handle type="source" position={Position.Right} className="h" isConnectable={false} />
    </div>
  );
});

export const MoreNode = memo(({ data }: NodeProps) => {
  const a = useActions();
  const c = data.card as Card;
  return (
    <div className="card2 more2" onClick={(e) => { e.stopPropagation(); a.showAll(c.id.slice(5)); }}>
      <Handle type="target" position={Position.Left} className="h" isConnectable={false} />
      + {c.more} more
      <Handle type="source" position={Position.Right} className="h" isConnectable={false} />
    </div>
  );
});

/** A frame: one child of the block you are in, holding its cards. */
export const FrameNode = memo(({ data }: NodeProps) => {
  const a = useActions();
  const g = data.group as Group;
  const timer = useRef<number | null>(null);
  return (
    <div className={`frame2 kind-${g.block.kind}`} onMouseEnter={() => a.hover(g.id)} onMouseLeave={() => a.hover(null)}>
      <Handle type="target" position={Position.Left} className="h" isConnectable={false} />
      <div
        className="frame2-head"
        onClick={(e) => {
          // wait briefly before selecting, so a double-click isn't broken by the re-render
          e.stopPropagation();
          if (timer.current) clearTimeout(timer.current);
          timer.current = window.setTimeout(() => a.select(g.block.id), 220);
        }}
        onDoubleClick={(e) => {
          e.stopPropagation();
          if (timer.current) clearTimeout(timer.current);
          a.drill(g.block);
        }}
      >
        <span className="card2-icon" aria-hidden>{KIND_ICON[g.block.kind] ?? "•"}</span>
        <span className="frame2-title">{displayTitle(g.chain)}</span>
        <span className="frame2-meta">{g.block.loc} loc</span>
        <button className="link" onClick={(e) => { e.stopPropagation(); a.drill(g.block); }}>Open ›</button>
      </div>
      <Handle type="source" position={Position.Right} className="h" isConnectable={false} />
    </div>
  );
});

/** Code outside the block you are in, with the number of links each way. */
export const StubNode = memo(({ data }: NodeProps) => {
  const a = useActions();
  const s = data.stub as Stub;
  return (
    <div className="stub2" onClick={(e) => { e.stopPropagation(); a.select(s.block.id); }}
      onMouseEnter={() => a.hover(s.id)} onMouseLeave={() => a.hover(null)}
      title="Outside the block you're in">
      <Handle type="target" position={Position.Left} className="h" isConnectable={false} />
      <div className="stub2-title">↗ {s.block.code_name}</div>
      <div className="card2-sub">outside · {s.incoming ? `${s.incoming} in` : ""}{s.incoming && s.outgoing ? " · " : ""}{s.outgoing ? `${s.outgoing} out` : ""}</div>
      <Handle type="source" position={Position.Right} className="h" isConnectable={false} />
    </div>
  );
});

/** Trace view: the block being traced. */
export const TraceCentreNode = memo(({ data }: NodeProps) => {
  const a = useActions();
  const b = data.block as Block;
  return (
    <div className="trace-centre" onClick={() => a.select(b.id)}>
      <Handle type="target" position={Position.Left} className="h" isConnectable={false} />
      <div className="card2-title">{humanTitle(b)}</div>
      <div className="card2-sub mono">{b.code_name}{b.params.length ? `(${b.params.join(", ")})` : ""}</div>
      <div className="card2-sub">{KIND_LABEL[b.kind]} · {b.file}</div>
      <Handle type="source" position={Position.Right} className="h" isConnectable={false} />
    </div>
  );
});

export const TraceGroupNode = memo(({ data }: NodeProps) => {
  const b = data.block as Block;
  return (
    <div className="frame2 trace-group">
      <div className="frame2-head"><span className="frame2-title">{b.path || b.code_name}</span></div>
    </div>
  );
});

// ------------------------------------------------------------------ inside levels

export function CodeLines({ code, start, className }: { code: string; start: number; className?: string }) {
  const lines = code.split("\n");
  return (
    <pre className={className ?? "code"}>
      {lines.map((l, i) => (
        <div key={i} className="ln">
          <span className="no">{start + i}</span>
          <span className="tx">{l || " "}</span>
        </div>
      ))}
    </pre>
  );
}

export const InsideNode = memo(({ data, selected }: NodeProps) => {
  const a = useActions();
  const ib = data.inside as InsideBlock;
  return (
    <div className={`card inside inside-${ib.kind} ${selected || data.sel ? "selected" : ""}`} onClick={() => a.select(ib.id)}
      onDoubleClick={() => ib.has_children && a.drillInside(ib)}>
      <Handle type="target" position={Position.Top} className="h" isConnectable={false} />
      <div className="inside-head">
        <span className={`badge kind kind-${ib.kind}`}>{KIND_LABEL[ib.kind]}</span>
        <span className="inside-label" title={ib.named_by === "placeholder" ? "Placeholder name: AI names sections later" : undefined}>
          {ib.kind === "section" ? ib.label : ib.node_type.replace(/_/g, " ")}
        </span>
        <span className="badge">L{ib.start_line}{ib.end_line !== ib.start_line ? `–${ib.end_line}` : ""}</span>
        {ib.has_children && <button className="link" onClick={(e) => { e.stopPropagation(); a.drillInside(ib); }}>Open →</button>}
      </div>
      <CodeLines code={ib.code} start={ib.start_line} className="inline-code small nowheel nodrag" />
      <Handle type="source" position={Position.Bottom} className="h" isConnectable={false} />
    </div>
  );
});

export const nodeTypes = {
  card: CardNode, more: MoreNode, frame: FrameNode, stub: StubNode,
  traceCentre: TraceCentreNode, traceGroup: TraceGroupNode, inside: InsideNode,
};

// ------------------------------------------------------------------ edges

type Pt = { x: number; y: number };

/** A line drawn along the route ELK picked, with rounded corners. */
export function RoutedEdge(p: EdgeProps) {
  const pts = (p.data?.points as Pt[] | undefined) ?? [{ x: p.sourceX, y: p.sourceY }, { x: p.targetX, y: p.targetY }];
  const r = 6;
  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 1; i < pts.length; i++) {
    const cur = pts[i];
    const next = pts[i + 1];
    if (!next) { d += ` L ${cur.x} ${cur.y}`; break; }
    const prev = pts[i - 1];
    const inLen = Math.hypot(cur.x - prev.x, cur.y - prev.y);
    const outLen = Math.hypot(next.x - cur.x, next.y - cur.y);
    const k = Math.min(r, inLen / 2, outLen / 2);
    const ax = cur.x - ((cur.x - prev.x) / (inLen || 1)) * k;
    const ay = cur.y - ((cur.y - prev.y) / (inLen || 1)) * k;
    const bx = cur.x + ((next.x - cur.x) / (outLen || 1)) * k;
    const by = cur.y + ((next.y - cur.y) / (outLen || 1)) * k;
    d += ` L ${ax} ${ay} Q ${cur.x} ${cur.y} ${bx} ${by}`;
  }
  // label on the longest straight piece
  let best = 0, lx = pts[0].x, ly = pts[0].y;
  for (let i = 1; i < pts.length; i++) {
    const len = Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y);
    if (len > best) { best = len; lx = (pts[i].x + pts[i - 1].x) / 2; ly = (pts[i].y + pts[i - 1].y) / 2; }
  }
  return (
    <BaseEdge
      id={p.id} path={d} markerEnd={p.markerEnd} style={p.style} interactionWidth={0}
      label={p.label} labelX={lx} labelY={ly} labelStyle={p.labelStyle}
      labelShowBg={p.labelShowBg} labelBgStyle={p.labelBgStyle} labelBgPadding={p.labelBgPadding} labelBgBorderRadius={p.labelBgBorderRadius}
    />
  );
}

export const edgeTypes = { routed: RoutedEdge };
