import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background, Controls, MarkerType, MiniMap, ReactFlow, ReactFlowProvider, useReactFlow,
  type Edge as RFEdge, type Node as RFNode,
} from "@xyflow/react";
import { api } from "./api";
import { CARD_H, CARD_W, CODE_W, layout } from "./layout";
import { Actions, nodeTypes, type CanvasActions } from "./nodes";
import { Panel } from "./Panel";
import type { Block, EdgeKind, GraphData, InsideBlock, InsideResult } from "./types";
import { buildDisplay, defaultFilters, displayTitle, Index, search, type Filters } from "./view";
import ELK from "elkjs/lib/elk.bundled.js";

const LEVELS = [
  { n: 1, name: "System" },
  { n: 2, name: "Modules" },
  { n: 3, name: "Files" },
  { n: 4, name: "Definitions" },
  { n: 5, name: "Sections" },
  { n: 6, name: "Statements" },
  { n: 7, name: "Expressions" },
];

export const EDGE_COLORS: Record<EdgeKind, string> = {
  imports: "#8a94a6",
  calls: "#3b82f6",
  instantiates: "#14b8a6",
  inherits: "#a855f7",
  renders: "#f59e0b",
  next: "#8a94a6",
};

type Crumb = { kind: "block"; id: string } | { kind: "inside"; item: InsideBlock; title: string };

export function ProjectView({ graph, onBack, onRemap }: { graph: GraphData; onBack: () => void; onRemap: () => void }) {
  return (
    <ReactFlowProvider>
      <Inner graph={graph} onBack={onBack} onRemap={onRemap} />
    </ReactFlowProvider>
  );
}

function Inner({ graph, onBack, onRemap }: { graph: GraphData; onBack: () => void; onRemap: () => void }) {
  const ix = useMemo(() => new Index(graph), [graph]);
  const [level, setLevel] = useState(2);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [showAll, setShowAll] = useState<Record<string, boolean>>({});
  const [filters, setFilters] = useState<Filters>(defaultFilters);
  const [crumbs, setCrumbs] = useState<Crumb[]>([{ kind: "block", id: graph.root_id }]);
  const [selected, setSelected] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [highlighted, setHighlighted] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [nodes, setNodes] = useState<RFNode[]>([]);
  const [edges, setEdges] = useState<RFEdge[]>([]);
  const [busy, setBusy] = useState(false);
  const [insideData, setInsideData] = useState<InsideResult | null>(null);
  const codeCache = useRef(new Map<string, string>());
  const rf = useReactFlow();
  const fitPending = useRef(true);

  // the innermost structural crumb, and the inside path after it
  const blockCrumbs = crumbs.filter((c): c is Extract<Crumb, { kind: "block" }> => c.kind === "block");
  const rootId = blockCrumbs[blockCrumbs.length - 1].id;
  const insideTop = crumbs[crumbs.length - 1];
  const insideMode = insideTop.kind === "inside";

  const display = useMemo(
    () => buildDisplay(ix, { rootId, level, open, showAll, filters }),
    [ix, rootId, level, open, showAll, filters],
  );

  // ------------------------------------------------------------- actions
  const drill = useCallback((b: Block) => {
    fitPending.current = true;
    if (["function", "method", "component"].includes(b.kind) && b.start_byte != null && b.file) {
      const item: InsideBlock = {
        id: b.id, level: 4, kind: "definition", node_type: b.kind, label: b.code_name, file: b.file,
        start_byte: b.start_byte, end_byte: b.end_byte!, start_line: b.start_line!, end_line: b.end_line!,
        has_children: true, code: "",
      };
      setCrumbs((c) => [...c, { kind: "inside", item, title: `${b.code_name}()` }]);
    } else {
      setCrumbs((c) => [...c, { kind: "block", id: b.id }]);
    }
    setOpen({});
    setShowAll({});
  }, []);

  const drillInside = useCallback((ib: InsideBlock) => {
    fitPending.current = true;
    setCrumbs((c) => [...c, { kind: "inside", item: ib, title: ib.kind === "section" ? ib.label : ib.node_type.replace(/_/g, " ") }]);
  }, []);

  const loadCode = useCallback(async (b: Block) => {
    const hit = codeCache.current.get(b.id);
    if (hit !== undefined) return hit;
    const res = await api.code(graph.project_id, b.file!, b.start_line, b.end_line);
    codeCache.current.set(b.id, res.code);
    return res.code;
  }, [graph.project_id]);

  const actions: CanvasActions = useMemo(() => ({
    projectId: graph.project_id,
    selected,
    highlighted,
    expanded,
    select: (id) => setSelected(id),
    toggleOpen: (b) => setOpen((o) => ({ ...o, [b.id]: !(display.nodes.get(b.id)?.kind === "frame") })),
    toggleCode: (id) => setExpanded((e) => ({ ...e, [id]: !e[id] })),
    drill,
    showAll: (owner) => setShowAll((s) => ({ ...s, [owner]: true })),
    drillInside,
    loadCode,
  }), [graph.project_id, selected, highlighted, expanded, display, drill, drillInside, loadCode]);

  // ------------------------------------------------------------- inside levels
  useEffect(() => {
    if (insideTop.kind !== "inside") {
      setInsideData(null);
      return;
    }
    const it = insideTop.item;
    let live = true;
    setBusy(true);
    api.inside(graph.project_id, it.file, it.start_byte, it.end_byte, it.kind)
      .then((r) => live && setInsideData(r))
      .catch(() => live && setInsideData({ blocks: [], edges: [] }))
      .finally(() => live && setBusy(false));
    return () => { live = false; };
  }, [insideTop, graph.project_id]);

  // ------------------------------------------------------------- layout
  useEffect(() => {
    let live = true;
    const run = async () => {
      setBusy(true);
      if (insideMode) {
        if (!insideData) return;
        const elk = new ELK();
        const sized = insideData.blocks.map((b) => {
          const lines = Math.min(b.code.split("\n").length, 14);
          return { id: b.id, width: 520, height: 46 + lines * 16 + 14 };
        });
        const res = await elk.layout({
          id: "root",
          layoutOptions: { "elk.algorithm": "layered", "elk.direction": "DOWN", "elk.spacing.nodeNode": "24", "elk.layered.spacing.nodeNodeBetweenLayers": "30" },
          children: sized,
          edges: insideData.edges.map((e, i) => ({ id: `e${i}`, sources: [e.source], targets: [e.target] })),
        });
        if (!live) return;
        const byId = new Map(insideData.blocks.map((b) => [b.id, b]));
        setNodes((res.children ?? []).map((c) => ({
          id: c.id, type: "inside", position: { x: c.x ?? 0, y: c.y ?? 0 },
          data: { inside: byId.get(c.id) }, style: { width: c.width, height: c.height },
        })));
        setEdges(insideData.edges.map((e, i) => ({
          id: `ie${i}`, source: e.source, target: e.target, type: "smoothstep",
          style: { stroke: EDGE_COLORS.next }, markerEnd: { type: MarkerType.ArrowClosed, color: EDGE_COLORS.next },
        })));
      } else {
        const sizeOf = (id: string) => {
          const n = display.nodes.get(id)!;
          if (n.kind === "more" || n.kind === "ghost") return { w: 170, h: 56 };
          const b = n.block!;
          if (expanded[b.id]) {
            const lines = Math.min((b.end_line ?? 1) - (b.start_line ?? 1) + 1, 24);
            return { w: CODE_W, h: CARD_H + 16 + lines * 16 + 16 };
          }
          return { w: CARD_W, h: CARD_H };
        };
        const placed = await layout(display, sizeOf);
        if (!live) return;
        const rfNodes: RFNode[] = [];
        const visit = (id: string) => {
          const n = display.nodes.get(id)!;
          const p = placed.get(id);
          if (!p) return;
          rfNodes.push({
            id,
            type: n.kind,
            position: { x: p.x, y: p.y },
            parentId: n.parent ?? undefined,
            data: { node: n },
            style: { width: p.w, height: p.h },
            draggable: true,
            selectable: false,
            zIndex: n.kind === "frame" ? 0 : 1,
          });
          for (const c of n.children) visit(c);
        };
        for (const r of display.roots) visit(r);
        setNodes(rfNodes);
        setEdges(display.edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.count > 1 ? String(e.count) : undefined,
          style: {
            stroke: EDGE_COLORS[e.kind],
            strokeWidth: Math.min(1 + Math.log2(e.count + 1) * 0.7, 4),
            strokeDasharray: e.kind === "imports" ? "5 4" : e.maybe ? "2 4" : undefined,
            opacity: e.maybe ? 0.6 : 0.9,
          },
          markerEnd: { type: MarkerType.ArrowClosed, color: EDGE_COLORS[e.kind], width: 14, height: 14 },
          zIndex: 2,
          data: { kind: e.kind },
        })));
      }
      setBusy(false);
    };
    run();
    return () => { live = false; };
  }, [display, expanded, insideMode, insideData, rf]);

  // A new canvas starts empty so the fit below waits for its own nodes.
  useEffect(() => {
    setNodes([]);
    setEdges([]);
    fitPending.current = true;
  }, [crumbs, level]);

  // Fit the view after a new canvas has rendered (drill, level change).
  useEffect(() => {
    if (!fitPending.current || nodes.length === 0) return;
    fitPending.current = false;
    const t = setTimeout(() => rf.fitView({ padding: 0.12, duration: 300, maxZoom: 1.1 }), 60);
    return () => clearTimeout(t);
  }, [nodes, rf]);

  // ------------------------------------------------------------- search
  const results = useMemo(() => search(ix, query, filters), [ix, query, filters]);
  const reveal = (b: Block) => {
    // open every ancestor so the block is visible, then focus it
    const anc = ix.ancestors(b.id).slice(0, -1);
    const root = ix.ancestors(rootId);
    const inRoot = root.every((r, i) => anc[i]?.id === r.id) || b.id === rootId;
    if (!inRoot || insideMode) {
      setCrumbs([{ kind: "block", id: graph.root_id }]);
    }
    setOpen((o) => {
      const n = { ...o };
      for (const a of anc) n[a.id] = true;
      return n;
    });
    setShowAll((s) => {
      const n = { ...s };
      for (const a of anc) n[a.id] = true;
      return n;
    });
    setSelected(b.id);
    setHighlighted(new Set([b.id]));
    setQuery("");
    setTimeout(() => {
      const node = rf.getNode(b.id) ?? anc.reverse().map((a) => rf.getNode(a.id)).find(Boolean);
      if (node) rf.fitView({ nodes: [{ id: node.id }], padding: 0.6, duration: 400, maxZoom: 1.2 });
    }, 350);
  };

  // ------------------------------------------------------------- ui
  const setLevelReset = (n: number) => {
    setLevel(n);
    setOpen({});
    setShowAll({});
    fitPending.current = true;
  };

  const crumbTitle = (c: Crumb, i: number) => {
    if (c.kind === "inside") return c.title;
    const b = ix.get(c.id);
    if (i === 0) return graph.name;
    return displayTitle([b]);
  };

  const currentLevel = insideMode ? (insideData?.blocks[0]?.level ?? 5) : level;
  const selectedBlock = selected ? ix.blocks.get(selected) ?? null : null;
  const selectedInside = !selectedBlock && insideData ? insideData.blocks.find((b) => b.id === selected) ?? null : null;
  const stats = graph.stats;

  return (
    <Actions.Provider value={actions}>
      <div className="app">
        <header className="topbar">
          <button className="ghost-btn" onClick={onBack} title="All projects">◂ Projects</button>
          <div className="brand">Araknid <span>2.0</span></div>
          <div className="slider" role="group" aria-label="Detail level">
            <span className="slider-label">Detail</span>
            {LEVELS.map((l) => {
              const inside = l.n >= 5;
              const active = currentLevel === l.n;
              return (
                <button
                  key={l.n}
                  className={`lvl ${active ? "active" : ""} ${inside ? "inside" : ""}`}
                  disabled={inside || insideMode}
                  title={inside ? "Inside levels open one block at a time: drill into a function" : `Level ${l.n}: ${l.name}`}
                  onClick={() => setLevelReset(l.n)}
                >
                  <b>{l.n}</b> {l.name}
                </button>
              );
            })}
          </div>
          <div className="search">
            <input placeholder="Search blocks by name or file" value={query} onChange={(e) => setQuery(e.target.value)} />
            {results.length > 0 && (
              <ul className="results">
                {results.map((b) => (
                  <li key={b.id} onClick={() => reveal(b)}>
                    <b>{b.code_name}</b> <span className="muted">{b.kind}</span>
                    <div className="muted small">{b.path}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <button className="ghost-btn" onClick={onRemap} title="Parse the files again">Re-map</button>
        </header>

        <nav className="crumbs">
          {crumbs.map((c, i) => (
            <span key={i}>
              {i > 0 && <span className="sep">›</span>}
              <button
                className={i === crumbs.length - 1 ? "current" : ""}
                onClick={() => { fitPending.current = true; setCrumbs(crumbs.slice(0, i + 1)); setOpen({}); setShowAll({}); }}
              >
                {crumbTitle(c, i)}
              </button>
            </span>
          ))}
          <span className="stats">
            {String(stats.files ?? "?")} files · {Number(stats.lines ?? 0).toLocaleString()} lines · {graph.blocks.length} blocks · mapped in {String(stats.map_seconds ?? "?")}s
            {busy && " · laying out…"}
          </span>
        </nav>

        <div className="main">
          <aside className="filters">
            <h4>Show</h4>
            <Check label="Tests" v={filters.tests} on={(v) => setFilters({ ...filters, tests: v })} />
            <Check label="Other files (config, docs)" v={filters.assets} on={(v) => setFilters({ ...filters, assets: v })} />
            <Check label="Type declarations" v={filters.types} on={(v) => setFilters({ ...filters, types: v })} />
            <h4>Connections</h4>
            {(["calls", "imports", "renders", "instantiates", "inherits"] as EdgeKind[]).map((k) => (
              <Check key={k} label={k} color={EDGE_COLORS[k]} v={filters.edgeKinds[k]}
                on={(v) => setFilters({ ...filters, edgeKinds: { ...filters.edgeKinds, [k]: v } })} />
            ))}
            <Check label="Maybe links (guessed by name)" v={filters.maybe} on={(v) => setFilters({ ...filters, maybe: v })} />
            <p className="hint">
              Double-click a card to open it in place. <b>Drill in</b> gives a block its own canvas. Functions drill into
              sections and statements.
            </p>
          </aside>
          <div className="canvas">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={(changes) => {
                // positions only: we own the layout
                if (!changes.some((c) => c.type === "position")) return;
                setNodes((ns) => ns.map((n) => {
                  const ch = changes.find((c) => c.type === "position" && c.id === n.id) as { position?: { x: number; y: number } } | undefined;
                  return ch?.position ? { ...n, position: ch.position } : n;
                }));
              }}
              onPaneClick={() => { setSelected(null); setHighlighted(new Set()); }}
              minZoom={0.05}
              maxZoom={2}
              proOptions={{ hideAttribution: true }}
              onlyRenderVisibleElements
            >
              <Background gap={24} size={1} />
              <Controls showInteractive={false} />
              <MiniMap pannable zoomable nodeStrokeWidth={2} />
            </ReactFlow>
            {!busy && nodes.length === 0 && <div className="empty">Nothing to show here with the current filters.</div>}
          </div>
          <Panel
            projectId={graph.project_id}
            ix={ix}
            block={selectedBlock}
            inside={selectedInside}
            loadCode={loadCode}
            onSelect={(id) => { const b = ix.blocks.get(id); if (b) reveal(b); }}
            onDrill={drill}
            onClose={() => setSelected(null)}
          />
        </div>
      </div>
    </Actions.Provider>
  );
}

function Check({ label, v, on, color }: { label: string; v: boolean; on: (v: boolean) => void; color?: string }) {
  return (
    <label className="check">
      <input type="checkbox" checked={v} onChange={(e) => on(e.target.checked)} />
      {color && <span className="swatch" style={{ background: color }} />}
      {label}
    </label>
  );
}
