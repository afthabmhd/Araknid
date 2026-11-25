import { useEffect, useState } from "react";
import { Badges, CodeLines } from "./nodes";
import type { Block, Edge, InsideBlock } from "./types";
import { humanTitle, type Index } from "./view";

type Tab = "code" | "connections" | "details" | "explain";

export function Panel(props: {
  ix: Index;
  block: Block | null;
  inside: InsideBlock | null;
  loadCode: (b: Block) => Promise<string>;
  onTrace: (b: Block) => void;
  onSelect: (id: string) => void;
  onDrill: (b: Block) => void;
  onClose: () => void;
}) {
  const { ix, block, inside } = props;
  const [tab, setTab] = useState<Tab>("code");
  const [code, setCode] = useState<string | null>(null);

  useEffect(() => {
    setCode(null);
    if (block && block.start_line != null && block.kind !== "project" && block.kind !== "system" && block.kind !== "module") {
      props.loadCode(block).then(setCode).catch((e) => setCode(`// ${e}`));
    }
  }, [block?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!block && !inside) {
    return (
      <aside className="panel empty-panel">
        <p>Select a block to see its code, connections and details.</p>
      </aside>
    );
  }

  if (inside) {
    return (
      <aside className="panel">
        <div className="panel-head">
          <div>
            <div className="panel-title">{inside.kind === "section" ? inside.label : inside.node_type.replace(/_/g, " ")}</div>
            <div className="muted small">{inside.file} · lines {inside.start_line}–{inside.end_line}</div>
          </div>
          <button className="icon" onClick={props.onClose}>×</button>
        </div>
        {inside.named_by === "placeholder" && <p className="note">Section boundaries come from the code. Names are placeholders until the AI names them.</p>}
        <CodeLines code={inside.code} start={inside.start_line} />
      </aside>
    );
  }

  const b = block!;
  const out = ix.out.get(b.id) ?? [];
  const inc = ix.inc.get(b.id) ?? [];

  return (
    <aside className="panel">
      <div className="panel-head">
        <div>
          <div className="panel-title">{humanTitle(b)}</div>
          <div className="mono small">{b.code_name}{b.params.length ? `(${b.params.join(", ")})` : ""}</div>
          <div className="muted small">{b.path || "(project root)"}{b.start_line ? ` · lines ${b.start_line}–${b.end_line}` : ""}</div>
        </div>
        <button className="icon" onClick={props.onClose}>×</button>
      </div>
      <div className="panel-meta">
        <Badges b={b} />
        <div className="panel-actions">
          {b.kind !== "asset" && b.kind !== "project" && (b.children.length > 0 || ["function", "method", "component"].includes(b.kind)) && (
            <button onClick={() => props.onDrill(b)}>Open ›</button>
          )}
          {b.kind !== "project" && <button onClick={() => props.onTrace(b)} title="Who uses this block, and what it uses">Trace connections</button>}
        </div>
      </div>
      <div className="tabs">
        {(["code", "connections", "details", "explain"] as Tab[]).map((t) => (
          <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
            {t === "connections" ? `Connections (${out.length + inc.length})` : t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      <div className="panel-body">
        {tab === "code" && (
          b.kind === "module" || b.kind === "system" || b.kind === "project" ? (
            <div>
              <p className="muted">{b.children.length} blocks inside. Drill in to see them.</p>
              <button onClick={() => props.onDrill(b)}>Drill in →</button>
            </div>
          ) : code === null ? <p className="muted">Loading…</p> : <CodeLines code={code} start={b.start_line ?? 1} />
        )}
        {tab === "connections" && (
          <div>
            <EdgeList title="Uses" edges={out} ix={ix} side="target" onSelect={props.onSelect} />
            <EdgeList title="Used by" edges={inc} ix={ix} side="source" onSelect={props.onSelect} />
            {out.length + inc.length === 0 && <p className="muted">No direct connections. Its children may have some; open it to see them rolled up.</p>}
          </div>
        )}
        {tab === "details" && (
          <dl className="details">
            <dt>Kind</dt><dd>{b.kind}</dd>
            <dt>Level</dt><dd>{b.level}</dd>
            <dt>Language</dt><dd>{b.language ?? "–"}</dd>
            <dt>Lines of code</dt><dd>{b.loc}</dd>
            <dt>Build state</dt><dd>{b.build_state}</dd>
            <dt>Tags</dt><dd>{b.tags.join(", ") || "–"}</dd>
            <dt>Importance</dt><dd>{b.importance.toFixed(1)}</dd>
            <dt>Parse health</dt><dd>{b.health ?? "ok"}</dd>
            <dt>Block id</dt><dd className="mono">{b.id}</dd>
            <dt>Content hash</dt><dd className="mono">{b.content_hash ?? "–"}</dd>
            <dt>Shape hash</dt><dd className="mono">{b.shape_hash ?? "–"}</dd>
          </dl>
        )}
        {tab === "explain" && (
          <div className="note">
            Explain and Instruct come next. They need your own AI key (Claude, OpenAI, Gemini, Ollama or any
            OpenAI-compatible endpoint) and go through the context engine, so the AI only sees this block and
            what it connects to.
          </div>
        )}
      </div>
    </aside>
  );
}

function EdgeList({ title, edges, ix, side, onSelect }: {
  title: string; edges: Edge[]; ix: Index; side: "source" | "target"; onSelect: (id: string) => void;
}) {
  if (!edges.length) return null;
  const sorted = [...edges].sort((a, b) => a.kind.localeCompare(b.kind));
  return (
    <div className="edge-list">
      <h5>{title}</h5>
      <ul>
        {sorted.map((e, i) => {
          const other = ix.blocks.get(e[side]);
          if (!other) return null;
          return (
            <li key={i} onClick={() => onSelect(other.id)}>
              <span className={`badge edge-${e.kind}`}>{e.kind}</span>
              <span className="mono">{other.code_name}</span>
              {e.certainty === "maybe" && <span className="badge muted" title="Linked by name only">maybe</span>}
              {e.count > 1 && <span className="muted"> ×{e.count}</span>}
              <div className="muted small">{other.path}</div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
