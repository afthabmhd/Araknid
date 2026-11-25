import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Controls, MarkerType, MiniMap, ReactFlow, ReactFlowProvider, useReactFlow,
  type Edge as RFEdge, type Node as RFNode,
} from "@xyflow/react";
import ELK from "elkjs/lib/elk.bundled.js";
import { api } from "./api";
import { Actions, edgeTypes, nodeTypes, type CanvasActions } from "./nodes";
import { Panel } from "./Panel";
import { bundlePoint, webLayout } from "./radial";
import type { Block, EdgeKind, GraphData, InsideBlock, InsideResult } from "./types";
import { buildDisplay, defaultFilters, displayTitle, Index, search, type Filters } from "./view";

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
  imports: "var(--e-imports)",
  calls: "var(--e-calls)",
  instantiates: "var(--e-instantiates)",
  inherits: "var(--e-inherits)",
  renders: "var(--e-renders)",
  next: "var(--e-imports)",
};

const MAJOR_LABELS = 36; // [Guess] how many outer labels stay visible when zoomed out
const ZOOM_LABELS = 0.85; // below this zoom, minor labels hide

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
  const [hovered, setHovered] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [zoomedOut, setZoomedOut] = useState(true);
  const [insideNodes, setInsideNodes] = useState<RFNode[]>([]);
  const [insideEdges, setInsideEdges] = useState<RFEdge[]>([]);
  const [busy, setBusy] = useState(false);
  const [insideData, setInsideData] = useState<InsideResult | null>(null);
  const codeCache = useRef(new Map<string, string>());
  const rf = useReactFlow();
  const fitPending = useRef(true);

  const blockCrumbs = crumbs.filter((c): c is Extract<Crumb, { kind: "block" }> => c.kind === "block");
  const rootId = blockCrumbs[blockCrumbs.length - 1].id;
  const insideTop = crumbs[crumbs.length - 1];
  const insideMode = insideTop.kind === "inside";

  const display = useMemo(
    () => buildDisplay(ix, { rootId, level, open, showAll, filters }),
    [ix, rootId, level, open, showAll, filters],
  );
  const web = useMemo(() => webLayout(display), [display]);

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
    setSelected(null);
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

  const isOpen = useCallback((id: string) => display.nodes.get(id)?.kind === "frame", [display]);
  const toggleOpen = useCallback((b: Block) => setOpen((o) => ({ ...o, [b.id]: !isOpen(b.id) })), [isOpen]);

  const actions: CanvasActions = useMemo(() => ({
    select: (id) => setSelected(id),
    hover: (id) => setHovered(id),
    toggleOpen,
    drill,
    showAll: (owner) => setShowAll((s) => ({ ...s, [owner]: true })),
    drillInside,
  }), [toggleOpen, drill, drillInside]);

  // ------------------------------------------------------------- the web
  const base = useMemo(() => {
    const nodes: RFNode[] = [];
    const edges: RFEdge[] = [];
    const lastRing = web.rings[web.rings.length - 1] ?? 0;
    // the silk: spokes at each first-ring block (at least 8) and rings between them
    const firstRing = [...web.pos.values()].filter((p) => p.depth === 1).map((p) => p.angle);
    let spokes = [...firstRing].sort((a, b) => a - b);
    if (spokes.length < 8) spokes = Array.from({ length: 12 }, (_, i) => -Math.PI / 2 + (i / 12) * 2 * Math.PI);
    if (web.rings.length > 1) {
      nodes.push({
        id: "__rings__", type: "rings", position: { x: -(lastRing + 60), y: -(lastRing + 60) },
        data: { rings: web.rings, spokes }, draggable: false, selectable: false, focusable: false, zIndex: -1,
        style: { pointerEvents: "none" },
      });
    }
    nodes.push({
      id: "__hub__", type: "hub", position: { x: -16, y: -16 }, data: { block: display.effectiveRoot },
      draggable: false, selectable: false, style: { width: 32, height: 32, pointerEvents: "all" },
    });

    // label budget: inner rings always, outer leaves only the most important
    const leaves = [...display.nodes.values()].filter((n) => n.kind === "card" && n.block);
    const major = new Set(
      [...leaves].sort((a, b) => (b.block!.importance - a.block!.importance) || (b.block!.loc - a.block!.loc))
        .slice(0, MAJOR_LABELS).map((n) => n.id),
    );

    for (const [id, p] of web.pos) {
      const n = display.nodes.get(id)!;
      const outer = n.kind !== "frame";
      nodes.push({
        id, type: "web",
        position: { x: p.x - p.r, y: p.y - p.r },
        data: { node: n, pos: p, outer, minor: outer && !major.has(id) && p.depth > 1 },
        // React Flow turns pointer events off on nodes it can't drag or select
        style: { width: p.r * 2, height: p.r * 2, pointerEvents: "all" },
        draggable: false, selectable: false,
      });
      edges.push({
        id: `t:${id}`, source: n.parent ?? "__hub__", target: id, type: "thread",
        className: "thread", selectable: false, focusable: false,
      });
    }

    for (const e of display.edges) {
      if (!web.pos.has(e.source) || !web.pos.has(e.target)) continue;
      const c = bundlePoint(display, web, e.source, e.target);
      edges.push({
        id: e.id, source: e.source, target: e.target, type: "bundled",
        data: { cx: c.x, cy: c.y, kind: e.kind },
        className: `conn conn-${e.kind} ${e.maybe ? "maybe" : ""}`,
        style: { strokeWidth: Math.min(0.7 + Math.log2(e.count + 1) * 0.5, 3) },
        selectable: false, focusable: false,
      });
    }
    return { nodes, edges };
  }, [web, display]);

  // Focus mode: hovering or selecting a block lights it, its connections and
  // its parents, and fades everything else back into the web.
  const focusId = hovered ?? selected;
  const { nodes, edges } = useMemo(() => {
    if (insideMode) return { nodes: insideNodes, edges: insideEdges };
    const focus = focusId ? (display.nodes.has(focusId) ? focusId : resolveShown(ix, display, focusId)) : null;
    if (!focus) return base;
    const lit = new Set<string>([focus]);
    let cur = display.nodes.get(focus)?.parent ?? null;
    while (cur) { lit.add(cur); cur = display.nodes.get(cur)?.parent ?? null; }
    const hotEdges = new Set<string>();
    for (const e of display.edges) {
      if (e.source === focus || e.target === focus) {
        hotEdges.add(e.id);
        lit.add(e.source);
        lit.add(e.target);
      }
    }
    return {
      nodes: base.nodes.map((n) => n.type !== "web" ? n : {
        ...n, className: n.id === focus ? "focus" : lit.has(n.id) ? "lit" : "faded",
      }),
      edges: base.edges.map((e) => {
        if (e.type === "thread") return lit.has(e.target) ? { ...e, className: "thread lit" } : e;
        if (!hotEdges.has(e.id)) return { ...e, className: `${e.className} faded` };
        const kind = (e.data as { kind: EdgeKind }).kind;
        return {
          ...e,
          className: `${e.className} hot`,
          style: { ...e.style, stroke: EDGE_COLORS[kind], strokeWidth: Number(e.style?.strokeWidth ?? 1) + 0.6 },
          markerEnd: { type: MarkerType.ArrowClosed, color: EDGE_COLORS[kind], width: 12, height: 12 },
          zIndex: 5,
        };
      }),
    };
  }, [base, focusId, display, ix, insideMode, insideNodes, insideEdges]);

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

  useEffect(() => {
    if (!insideMode || !insideData) {
      setInsideNodes([]);
      setInsideEdges([]);
      return;
    }
    let live = true;
    const elk = new ELK();
    const sized = insideData.blocks.map((b) => {
      const lines = Math.min(b.code.split("\n").length, 14);
      return { id: b.id, width: 520, height: 46 + lines * 16 + 14 };
    });
    elk.layout({
      id: "root",
      layoutOptions: { "elk.algorithm": "layered", "elk.direction": "DOWN", "elk.spacing.nodeNode": "24", "elk.layered.spacing.nodeNodeBetweenLayers": "30" },
      children: sized,
      edges: insideData.edges.map((e, i) => ({ id: `e${i}`, sources: [e.source], targets: [e.target] })),
    }).then((res) => {
      if (!live) return;
      const byId = new Map(insideData.blocks.map((b) => [b.id, b]));
      setInsideNodes((res.children ?? []).map((c) => ({
        id: c.id, type: "inside", position: { x: c.x ?? 0, y: c.y ?? 0 },
        data: { inside: byId.get(c.id) }, style: { width: c.width, height: c.height, pointerEvents: "all" }, draggable: false,
      })));
      setInsideEdges(insideData.edges.map((e, i) => ({
        id: `ie${i}`, source: e.source, target: e.target, type: "smoothstep",
        style: { stroke: EDGE_COLORS.next }, markerEnd: { type: MarkerType.ArrowClosed },
      })));
    });
    return () => { live = false; };
  }, [insideMode, insideData]);

  // ------------------------------------------------------------- fitting the view
  useEffect(() => {
    fitPending.current = true;
  }, [crumbs, level]);
  useEffect(() => {
    if (!fitPending.current || nodes.length === 0) return;
    if (insideMode && !insideNodes.length) return;
    fitPending.current = false;
    const t = setTimeout(() => rf.fitView({ padding: 0.08, duration: 350, maxZoom: 1.2 }), 150);
    return () => clearTimeout(t);
  }, [nodes, rf, insideMode, insideNodes.length]);

  // ------------------------------------------------------------- search
  const results = useMemo(() => search(ix, query, filters), [ix, query, filters]);
  const pendingCentre = useRef<string | null>(null);
  const reveal = (b: Block) => {
    const anc = ix.ancestors(b.id).slice(0, -1);
    const root = ix.ancestors(rootId);
    const inRoot = root.every((r, i) => anc[i]?.id === r.id) || b.id === rootId;
    if (!inRoot || insideMode) setCrumbs([{ kind: "block", id: graph.root_id }]);
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
    setQuery("");
    fitPending.current = false;
    pendingCentre.current = b.id;
  };
  useEffect(() => {
    const id = pendingCentre.current;
    if (!id) return;
    const p = web.pos.get(id);
    if (!p) return;
    pendingCentre.current = null;
    setTimeout(() => rf.setCenter(p.x, p.y, { zoom: 1.1, duration: 450 }), 40);
  }, [web, rf]);

  // ------------------------------------------------------------- ui
  const setLevelReset = (n: number) => {
    setLevel(n);
    setOpen({});
    setShowAll({});
  };

  const crumbTitle = (c: Crumb, i: number) => {
    if (c.kind === "inside") return c.title;
    if (i === 0) return graph.name;
    return displayTitle([ix.get(c.id)]);
  };

  const currentLevel = insideMode ? (insideData?.blocks[0]?.level ?? 5) : level;
  const selectedBlock = selected ? ix.blocks.get(selected) ?? null : null;
  const selectedInside = !selectedBlock && insideData ? insideData.blocks.find((b) => b.id === selected) ?? null : null;
  const stats = graph.stats;
  const shownCount = web.pos.size;

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
                onClick={() => { setCrumbs(crumbs.slice(0, i + 1)); setOpen({}); setShowAll({}); setSelected(null); }}
              >
                {crumbTitle(c, i)}
              </button>
            </span>
          ))}
          <span className="stats">
            {insideMode ? "" : `${shownCount} of ${graph.blocks.length} blocks shown · `}
            {String(stats.files ?? "?")} files · {Number(stats.lines ?? 0).toLocaleString()} lines
            {busy && " · loading…"}
          </span>
        </nav>

        <div className="main">
          <aside className="filters">
            <h4>Show</h4>
            <Check id="f-tests" label="Tests" v={filters.tests} on={(v) => setFilters({ ...filters, tests: v })} />
            <Check id="f-assets" label="Other files (config, docs)" v={filters.assets} on={(v) => setFilters({ ...filters, assets: v })} />
            <Check id="f-types" label="Type declarations" v={filters.types} on={(v) => setFilters({ ...filters, types: v })} />
            <h4>Connections</h4>
            {(["calls", "imports", "renders", "instantiates", "inherits"] as EdgeKind[]).map((k) => (
              <Check key={k} id={`f-${k}`} label={k} color={EDGE_COLORS[k]} v={filters.edgeKinds[k]}
                on={(v) => setFilters({ ...filters, edgeKinds: { ...filters.edgeKinds, [k]: v } })} />
            ))}
            <Check id="f-maybe" label="Maybe links (guessed by name)" v={filters.maybe} on={(v) => setFilters({ ...filters, maybe: v })} />
            <h4>Reading the web</h4>
            <p className="hint">
              The block you're in sits at the centre. Each ring is one level deeper, and each block hangs on a thread
              from its parent. Bigger dots hold more code.
            </p>
            <p className="hint">
              Hover or click a dot to see its connections. Double-click to open it on the next ring, or to drill
              into a function. Zoom in to read every label.
            </p>
          </aside>
          <div
            className={`canvas ${zoomedOut ? "zoomed-out" : ""} ${focusId ? "has-focus" : ""}`}
            // the more connections on screen, the fainter each one rests
            style={{ ["--idle-alpha" as string]: String(Math.max(0.25, Math.min(1, 120 / Math.max(1, display.edges.length)))) }}
          >
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              onPaneClick={() => setSelected(null)}
              onMove={(_, vp) => { const far = vp.zoom < ZOOM_LABELS; if (far !== zoomedOut) setZoomedOut(far); }}
              minZoom={0.05}
              maxZoom={2.5}
              fitView
              fitViewOptions={{ padding: 0.08, maxZoom: 1.2 }}
              zoomOnDoubleClick={false}
              nodesDraggable={false}
              nodesConnectable={false}
              proOptions={{ hideAttribution: true }}
            >
              <Controls showInteractive={false} />
              {insideMode && <MiniMap pannable zoomable />}
            </ReactFlow>
            {!busy && nodes.length === 0 && <div className="empty">Nothing to show here with the current filters.</div>}
            {!insideMode && (
              <div className="legend" aria-hidden>
                {(["calls", "imports", "renders", "instantiates", "inherits"] as EdgeKind[]).filter((k) => filters.edgeKinds[k]).map((k) => (
                  <span key={k}><i style={{ background: EDGE_COLORS[k] }} />{k}</span>
                ))}
              </div>
            )}
          </div>
          <Panel
            ix={ix}
            block={selectedBlock}
            inside={selectedInside}
            isOpen={selectedBlock ? isOpen(selectedBlock.id) : false}
            loadCode={loadCode}
            onSelect={(id) => { const b = ix.blocks.get(id); if (b) reveal(b); }}
            onDrill={drill}
            onToggleOpen={toggleOpen}
            onClose={() => setSelected(null)}
          />
        </div>
      </div>
    </Actions.Provider>
  );
}

/** The dot that stands for a block that is folded inside another one. */
function resolveShown(ix: Index, display: ReturnType<typeof buildDisplay>, id: string): string | null {
  let cur = ix.blocks.get(id);
  while (cur) {
    if (display.nodes.has(cur.id)) return cur.id;
    cur = cur.parent_id ? ix.blocks.get(cur.parent_id) : undefined;
  }
  return null;
}

function Check({ id, label, v, on, color }: { id: string; label: string; v: boolean; on: (v: boolean) => void; color?: string }) {
  return (
    <label className="check" htmlFor={id}>
      <input id={id} type="checkbox" checked={v} onChange={(e) => on(e.target.checked)} />
      {color && <span className="swatch" style={{ background: color }} />}
      {label}
    </label>
  );
}
