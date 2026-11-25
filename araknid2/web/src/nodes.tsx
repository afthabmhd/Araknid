import { createContext, memo, useContext, useEffect, useState } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { Block, InsideBlock } from "./types";
import { displayTitle, humanTitle, type DisplayNode } from "./view";

export interface CanvasActions {
  projectId: string;
  selected: string | null;
  highlighted: Set<string>;
  expanded: Record<string, boolean>;
  select: (id: string) => void;
  toggleOpen: (b: Block) => void;
  toggleCode: (id: string) => void;
  drill: (b: Block) => void;
  showAll: (ownerId: string) => void;
  drillInside: (b: InsideBlock) => void;
  loadCode: (b: Block) => Promise<string>;
}

export const Actions = createContext<CanvasActions | null>(null);
const useActions = () => useContext(Actions)!;

const KIND_LABEL: Record<string, string> = {
  system: "System", module: "Module", file: "File", asset: "File", class: "Class", function: "Function",
  method: "Method", component: "Component", type: "Type", suggested_group: "Group",
  section: "Section", statement: "Statement", expression: "Expression",
};

function Badges({ b }: { b: Block }) {
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

export const FrameNode = memo(({ data }: NodeProps) => {
  const a = useActions();
  const n = data.node as DisplayNode;
  const b = n.block!;
  const sel = a.selected === b.id;
  return (
    <div className={`frame frame-${b.kind} ${sel ? "selected" : ""} ${a.highlighted.has(b.id) ? "hl" : ""}`}>
      <Handle type="target" position={Position.Left} className="h" />
      <div className="frame-head" onClick={(e) => { e.stopPropagation(); a.select(b.id); }}>
        <button className="icon" title="Close this block" onClick={(e) => { e.stopPropagation(); a.toggleOpen(b); }}>▾</button>
        <span className="frame-title">{displayTitle(n.chain)}</span>
        <span className="frame-meta">{KIND_LABEL[b.kind]} · {b.loc} loc</span>
        <button className="link" title="Open this block on its own canvas" onClick={(e) => { e.stopPropagation(); a.drill(b); }}>Drill in →</button>
      </div>
      <Handle type="source" position={Position.Right} className="h" />
    </div>
  );
});

export const CardNode = memo(({ data }: NodeProps) => {
  const a = useActions();
  const n = data.node as DisplayNode;
  const b = n.block!;
  const showCode = a.expanded[b.id];
  const chainTitle = n.chain.length > 1 ? displayTitle(n.chain) : null;
  const canOpen = b.children.length > 0;
  const isDef = b.level >= 4;
  return (
    <div
      className={`card card-${b.kind} ${a.selected === b.id ? "selected" : ""} ${a.highlighted.has(b.id) ? "hl" : ""} ${showCode ? "with-code" : ""}`}
      onClick={() => a.select(b.id)}
      onDoubleClick={(e) => { e.stopPropagation(); if (canOpen && !isDef) a.toggleOpen(b); else if (b.kind !== "asset") a.drill(b); }}
    >
      <Handle type="target" position={Position.Left} className="h" />
      <div className="card-title" title={b.human_name ? "AI-written name" : "Name taken from the code"}>{humanTitle(b)}</div>
      <div className="card-code-name">{chainTitle ?? b.code_name}{b.params.length > 0 && isDef ? `(${b.params.join(", ")})` : isDef && b.kind !== "class" && b.kind !== "type" ? "()" : ""}</div>
      <Badges b={b} />
      <div className="card-actions">
        {b.kind !== "asset" && b.kind !== "project" && b.start_line != null && (
          <button onClick={(e) => { e.stopPropagation(); a.toggleCode(b.id); }}>{showCode ? "Hide code" : "Expand"}</button>
        )}
        {canOpen && !isDef && <button onClick={(e) => { e.stopPropagation(); a.toggleOpen(b); }} title="Open one level deeper here">Open ▸</button>}
        {(b.kind !== "asset") && <button onClick={(e) => { e.stopPropagation(); a.drill(b); }} title="Show this block's inner web">Drill in →</button>}
        <button disabled title="Explain needs your AI key (next step of phase one)">Explain</button>
        <button disabled title="Instruct needs your AI key and the gates (next step)">Instruct</button>
      </div>
      {showCode && <InlineCode b={b} />}
      <Handle type="source" position={Position.Right} className="h" />
    </div>
  );
});

function InlineCode({ b }: { b: Block }) {
  const a = useActions();
  const [code, setCode] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    a.loadCode(b).then((c) => live && setCode(c)).catch((e) => live && setErr(String(e)));
    return () => { live = false; };
  }, [b.id]); // eslint-disable-line react-hooks/exhaustive-deps
  if (err) return <div className="inline-code error">{err}</div>;
  if (code === null) return <div className="inline-code">Loading…</div>;
  return <CodeLines code={code} start={b.start_line ?? 1} className="inline-code nowheel nodrag" />;
}

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

export const MoreNode = memo(({ data }: NodeProps) => {
  const a = useActions();
  const n = data.node as DisplayNode;
  return (
    <div className="more" onClick={() => a.showAll(n.moreOf!)} title="Show every block in this frame">
      <Handle type="target" position={Position.Left} className="h" />
      + {n.moreCount} more
      <div className="more-sub">less connected blocks</div>
      <Handle type="source" position={Position.Right} className="h" />
    </div>
  );
});

export const GhostNode = memo(({ data }: NodeProps) => {
  const a = useActions();
  const n = data.node as DisplayNode;
  const b = n.block!;
  return (
    <div className="ghost" onClick={() => a.select(b.id)} title="Outside the block you drilled into">
      <Handle type="target" position={Position.Left} className="h" />
      ↗ {b.code_name}
      <div className="more-sub">outside</div>
      <Handle type="source" position={Position.Right} className="h" />
    </div>
  );
});

export const InsideNode = memo(({ data }: NodeProps) => {
  const a = useActions();
  const ib = data.inside as InsideBlock;
  const sel = a.selected === ib.id;
  return (
    <div className={`card inside inside-${ib.kind} ${sel ? "selected" : ""}`} onClick={() => a.select(ib.id)}
      onDoubleClick={() => ib.has_children && a.drillInside(ib)}>
      <Handle type="target" position={Position.Top} className="h" />
      <div className="inside-head">
        <span className={`badge kind kind-${ib.kind}`}>{KIND_LABEL[ib.kind]}</span>
        <span className="inside-label" title={ib.named_by === "placeholder" ? "Placeholder name: AI names sections later" : undefined}>
          {ib.kind === "section" ? ib.label : ib.node_type.replace(/_/g, " ")}
        </span>
        <span className="badge">L{ib.start_line}{ib.end_line !== ib.start_line ? `–${ib.end_line}` : ""}</span>
        {ib.has_children && <button className="link" onClick={(e) => { e.stopPropagation(); a.drillInside(ib); }}>Open →</button>}
      </div>
      <CodeLines code={ib.code} start={ib.start_line} className="inline-code small nowheel nodrag" />
      <Handle type="source" position={Position.Bottom} className="h" />
    </div>
  );
});

export const nodeTypes = { frame: FrameNode, card: CardNode, more: MoreNode, ghost: GhostNode, inside: InsideNode };
