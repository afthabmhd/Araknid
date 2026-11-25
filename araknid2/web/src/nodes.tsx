import { createContext, memo, useContext } from "react";
import { BaseEdge, Handle, Position, type EdgeProps, type NodeProps } from "@xyflow/react";
import type { Block, InsideBlock } from "./types";
import { displayTitle, humanTitle, type DisplayNode } from "./view";
import type { WebPos } from "./radial";

export interface CanvasActions {
  select: (id: string) => void;
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

// ------------------------------------------------------------------ web nodes

const centred = { left: "50%", top: "50%", transform: "translate(-50%, -50%)" };

/** One block on the web: a dot sized by its code, with a label beside it. */
export const WebNode = memo(({ data }: NodeProps) => {
  const a = useActions();
  const n = data.node as DisplayNode;
  const p = data.pos as WebPos;
  const outer = data.outer as boolean;
  const minor = data.minor as boolean;
  const b = n.block;
  const isMore = n.kind === "more";
  const isGhost = n.kind === "ghost";
  const label = isMore ? `+${n.moreCount} more` : isGhost ? `↗ ${b!.code_name}` : displayTitle(n.chain);

  // Outer-ring labels run along their thread, like a radial dendrogram;
  // labels on the left half are flipped so they never read upside down.
  const deg = (p.angle * 180) / Math.PI;
  const left = Math.cos(p.angle) < 0;
  const labelStyle = outer
    ? {
        transform: `translate(-50%, -50%) rotate(${left ? deg + 180 : deg}deg) translateX(${left ? -(p.r + 6) : p.r + 6}px)`,
        transformOrigin: "50% 50%",
        justifyContent: left ? "flex-end" : "flex-start",
      }
    : undefined;

  return (
    <div
      className={`dot-wrap ${outer ? "outer" : "inner"} ${minor ? "minor" : ""} ${p.branch >= 0 ? `br-${p.branch % 8}` : "br-none"}`}
      onClick={(e) => { e.stopPropagation(); if (isMore) a.showAll(n.moreOf!); else if (b) a.select(b.id); }}
      onDoubleClick={(e) => {
        e.stopPropagation();
        if (!b || isMore) return;
        if (isGhost) return a.select(b.id);
        if (b.children.length && b.level < 4) a.toggleOpen(b);
        else if (b.kind === "class" && b.children.length) a.toggleOpen(b);
        else if (b.kind !== "asset") a.drill(b);
      }}
      onMouseEnter={() => b && a.hover(b.id)}
      onMouseLeave={() => a.hover(null)}
      title={b ? `${humanTitle(b)} · ${KIND_LABEL[b.kind]} · ${b.loc} loc` : undefined}
    >
      <Handle type="target" position={Position.Left} className="h" style={centred} isConnectable={false} />
      <div className={`dot dot-${isMore ? "more" : isGhost ? "ghost" : b!.kind} ${n.kind === "frame" ? "open" : ""} ${b?.build_state === "partial" ? "partial" : ""}`} />
      <div className={`lbl ${outer ? "lbl-outer" : "lbl-inner"}`} style={labelStyle}>
        <span>{label}</span>
      </div>
      <Handle type="source" position={Position.Right} className="h" style={centred} isConnectable={false} />
    </div>
  );
});

/** The silk: rings between the threads, drawn as a web behind the dots. */
export const RingsNode = memo(({ data }: NodeProps) => {
  const rings = data.rings as number[];
  const spokes = data.spokes as number[];
  const R = rings[rings.length - 1] + 60;
  const size = R * 2;
  const pt = (r: number, a: number) => [R + Math.cos(a) * r, R + Math.sin(a) * r];
  const paths: string[] = [];
  for (const r of rings.slice(1)) {
    // each ring sags slightly between spokes, like real silk
    let d = "";
    spokes.forEach((a, i) => {
      const b = spokes[(i + 1) % spokes.length] + (i + 1 === spokes.length ? 2 * Math.PI : 0);
      const [x0, y0] = pt(r, a);
      const [x1, y1] = pt(r, b);
      const [cx, cy] = pt(r * 0.94, (a + b) / 2);
      d += `${i === 0 ? `M${x0},${y0}` : ""} Q${cx},${cy} ${x1},${y1}`;
    });
    paths.push(d);
  }
  return (
    <svg width={size} height={size} className="silk" aria-hidden>
      {spokes.map((a, i) => {
        const [x, y] = pt(R - 40, a);
        return <line key={`s${i}`} x1={R} y1={R} x2={x} y2={y} />;
      })}
      {paths.map((d, i) => <path key={i} d={d} />)}
    </svg>
  );
});

/** The block at the centre of the web. */
export const HubNode = memo(({ data }: NodeProps) => {
  const a = useActions();
  const b = data.block as Block;
  return (
    <div className="hub" onClick={() => a.select(b.id)}>
      <Handle type="source" position={Position.Right} className="h" style={centred} isConnectable={false} />
      <div className="hub-dot" />
      <div className="hub-label">{b.kind === "project" ? b.code_name : displayTitle([b])}</div>
      <Handle type="target" position={Position.Left} className="h" style={centred} isConnectable={false} />
    </div>
  );
});

// ------------------------------------------------------------------ edges

/** A connection bundled towards the parent both ends share. */
export const BundledEdge = memo(({ id, sourceX, sourceY, targetX, targetY, data, style, markerEnd }: EdgeProps) => {
  const c = data as { cx: number; cy: number };
  const path = `M${sourceX},${sourceY} Q${c.cx},${c.cy} ${targetX},${targetY}`;
  return <BaseEdge id={id} path={path} style={style} markerEnd={markerEnd} />;
});

/** The thread from a block to its parent. */
export const ThreadEdge = memo(({ id, sourceX, sourceY, targetX, targetY, style }: EdgeProps) => (
  <BaseEdge id={id} path={`M${sourceX},${sourceY} L${targetX},${targetY}`} style={style} />
));

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

export const nodeTypes = { web: WebNode, rings: RingsNode, hub: HubNode, inside: InsideNode };
export const edgeTypes = { bundled: BundledEdge, thread: ThreadEdge };
