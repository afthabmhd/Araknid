import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Controls, MarkerType, ReactFlow, ReactFlowProvider, useReactFlow,
  type Edge as RFEdge, type Node as RFNode,
} from "@xyflow/react";
import ELK from "elkjs/lib/elk.bundled.js";
import { api } from "./api";
import { layoutLevel, layoutTrace, type Box } from "./canvasLayout";
import { buildLevelView, buildTrace, type Link } from "./levelview";
import { Actions, nodeTypes, type CanvasActions } from "./nodes";
import { Panel } from "./Panel";
import type { Block, EdgeKind, GraphData, InsideBlock, InsideResult } from "./types";
import { defaultFilters, displayTitle, Index, search, type Filters } from "./view";

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

type Crumb =
  | { kind: "block"; id: string }
  | { kind: "inside"; item: InsideBlock; title: string }
  | { kind: "trace"; id: string };

const mainKind = (l: Link): EdgeKind =>
  (Object.entries(l.kinds).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))[0]?.[0] as EdgeKind) ?? "calls";

const pe = { pointerEvents: "all" as const }; // React Flow turns pointer events off on nodes it can't drag or select

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
  const [showAll, setShowAll] = useState<Record<string, boolean>>({});
  const [filters, setFilters] = useState<Filters>(defaultFilters);
  const [crumbs, setCrumbs] = useState<Crumb[]>([{ kind: "block", id: graph.root_id }]);
  const [selected, setSelected] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [base, setBase] = useState<{ nodes: RFNode[]; edges: RFEdge[]; cardLinks: Link[] }>({ nodes: [], edges: [], cardLinks: [] });
  const [busy, setBusy] = useState(false);
  const [insideData, setInsideData] = useState<InsideResult | null>(null);
  const codeCache = useRef(new Map<string, string>());
  const rf = useReactFlow();
  const fitPending = useRef(true);

  const top = crumbs[crumbs.length - 1];
  const blockCrumbs = crumbs.filter((c): c is Extract<Crumb, { kind: "block" }> => c.kind === "block");
  const rootId = blockCrumbs[blockCrumbs.length - 1].id;
  const mode: "level" | "inside" | "trace" = top.kind === "block" ? "level" : top.kind;

  const view = useMemo(
    () => (mode === "level" ? buildLevelView(ix, rootId, level, filters, showAll) : null),
    [ix, rootId, level, filters, showAll, mode],
  );
  const trace = useMemo(() => (top.kind === "trace" ? buildTrace(ix, top.id, filters) : null), [ix, top, filters]);

  // ------------------------------------------------------------- actions
  const drill = useCallback((b: Block) => {
    if (["function", "method", "component"].includes(b.kind) && b.start_byte != null && b.file) {
      const item: InsideBlock = {
        id: b.id, level: 4, kind: "definition", node_type: b.kind, label: b.code_name, file: b.file,
        start_byte: b.start_byte, end_byte: b.end_byte!, start_line: b.start_line!, end_line: b.end_line!,
        has_children: true, code: "",
      };
      setCrumbs((c) => [...c.filter((x) => x.kind !== "trace"), { kind: "inside", item, title: `${b.code_name}()` }]);
    } else {
      setCrumbs((c) => [...c.filter((x) => x.kind !== "trace"), { kind: "block", id: b.id }]);
    }
    setShowAll({});
    setSelected(null);
    setHovered(null);
  }, []);

  const traceBlock = useCallback((b: Block) => {
    setCrumbs((c) => [...c.filter((x) => x.kind !== "trace" && x.kind !== "inside"), { kind: "trace", id: b.id }]);
    setSelected(b.id);
    setHovered(null);
  }, []);

  const drillInside = useCallback((ib: InsideBlock) => {
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
    select: (id) => setSelected(id),
    trace: (b) => (b.kind === "project" ? setSelected(b.id) : traceBlock(b)),
    hover: (id) => setHovered(id),
    toggleOpen: (b) => drill(b),
    drill,
    showAll: (owner) => setShowAll((s) => ({ ...s, [owner]: true })),
    drillInside,
  }), [drill, drillInside, traceBlock]);

  // ------------------------------------------------------------- level view
  useEffect(() => {
    if (!view) return;
    let live = true;
    setBusy(true);
    layoutLevel(view).then((boxes) => {
      if (!live) return;
      const nodes: RFNode[] = [];
      const put = (id: string, type: string, box: Box, data: Record<string, unknown>, z = 1) =>
        nodes.push({
          id, type, data, position: { x: box.x, y: box.y }, parentId: box.parent,
          style: { width: box.w, height: box.h, ...pe }, draggable: false, selectable: false, zIndex: z,
        });
      for (const g of view.groups) {
        const gb = boxes.get(g.id);
        if (!gb) continue;
        put(g.id, "frame", gb, { group: g }, 0);
        for (const cid of g.cards) {
          const cb = boxes.get(cid);
          const card = view.cards.get(cid)!;
          if (cb) put(cid, card.more ? "more" : "card", cb, { card }, 1);
        }
      }
      for (const id of view.loose) {
        const b = boxes.get(id);
        const card = view.cards.get(id)!;
        if (b) put(id, card.more ? "more" : "card", b, { card }, 1);
      }
      for (const s of view.stubs) {
        const b = boxes.get(s.id);
        if (b) put(s.id, "stub", b, { stub: s }, 1);
      }
      const edges: RFEdge[] = view.groupLinks.filter((l) => boxes.has(l.source) && boxes.has(l.target)).map((l) => summedEdge(l, "group"));
      setBase({ nodes, edges, cardLinks: view.cardLinks });
      setBusy(false);
    });
    return () => { live = false; };
  }, [view]);

  // ------------------------------------------------------------- trace view
  useEffect(() => {
    if (!trace) return;
    const boxes = layoutTrace(trace);
    const nodes: RFNode[] = [];
    const edges: RFEdge[] = [];
    const cid = `mid:${trace.centre.id}`;
    const cb = boxes.get(cid)!;
    nodes.push({ id: cid, type: "traceCentre", data: { block: trace.centre }, position: { x: cb.x, y: cb.y }, style: { width: cb.w, height: cb.h, ...pe }, draggable: false, selectable: false });
    for (const [side, groups] of [["in", trace.callers], ["out", trace.callees]] as const) {
      for (const g of groups) {
        const gid = `${side}:${g.group.id}`;
        const gb = boxes.get(gid)!;
        nodes.push({ id: gid, type: "traceGroup", data: { block: g.group }, position: { x: gb.x, y: gb.y }, style: { width: gb.w, height: gb.h }, draggable: false, selectable: false, zIndex: 0 });
        for (const it of g.items) {
          const id = `${side}:${it.block.id}`;
          const b = boxes.get(id)!;
          nodes.push({
            id, type: "card", parentId: gid, data: { card: { id: it.block.id, block: it.block, chain: [it.block], group: gid } },
            position: { x: b.x, y: b.y }, style: { width: b.w, height: b.h, ...pe }, draggable: false, selectable: false, zIndex: 1,
          });
          const kind = it.kinds[0];
          edges.push({
            id: `te:${id}`, source: side === "in" ? id : cid, target: side === "in" ? cid : id,
            className: `sum sum-${kind}`,
            style: { stroke: EDGE_COLORS[kind], strokeWidth: 1.4 },
            markerEnd: { type: MarkerType.ArrowClosed, color: EDGE_COLORS[kind], width: 12, height: 12 },
            label: it.count > 1 ? `${it.kinds.join(", ")} ×${it.count}` : it.kinds.join(", "),
            labelBgPadding: [4, 2], labelBgBorderRadius: 4,
            selectable: false, focusable: false,
          });
        }
      }
    }
    setBase({ nodes, edges, cardLinks: [] });
  }, [trace]);

  // ------------------------------------------------------------- inside levels
  useEffect(() => {
    if (top.kind !== "inside") {
      setInsideData(null);
      return;
    }
    const it = top.item;
    let live = true;
    setBusy(true);
    api.inside(graph.project_id, it.file, it.start_byte, it.end_byte, it.kind)
      .then((r) => live && setInsideData(r))
      .catch(() => live && setInsideData({ blocks: [], edges: [] }))
      .finally(() => live && setBusy(false));
    return () => { live = false; };
  }, [top, graph.project_id]);

  useEffect(() => {
    if (mode !== "inside" || !insideData) return;
    let live = true;
    const elk = new ELK();
    const sized = insideData.blocks.map((b) => ({ id: b.id, width: 520, height: 46 + Math.min(b.code.split("\n").length, 14) * 16 + 14 }));
    elk.layout({
      id: "root",
      layoutOptions: { "elk.algorithm": "layered", "elk.direction": "DOWN", "elk.spacing.nodeNode": "24", "elk.layered.spacing.nodeNodeBetweenLayers": "30" },
      children: sized,
      edges: insideData.edges.map((e, i) => ({ id: `e${i}`, sources: [e.source], targets: [e.target] })),
    }).then((res) => {
      if (!live) return;
      const byId = new Map(insideData.blocks.map((b) => [b.id, b]));
      setBase({
        nodes: (res.children ?? []).map((c) => ({
          id: c.id, type: "inside", position: { x: c.x ?? 0, y: c.y ?? 0 },
          data: { inside: byId.get(c.id) }, style: { width: c.width, height: c.height, ...pe }, draggable: false, selectable: false,
        })),
        edges: insideData.edges.map((e, i) => ({
          id: `ie${i}`, source: e.source, target: e.target, type: "smoothstep",
          style: { stroke: EDGE_COLORS.next }, markerEnd: { type: MarkerType.ArrowClosed },
        })),
        cardLinks: [],
      });
    });
    return () => { live = false; };
  }, [mode, insideData]);

  // ------------------------------------------------------------- focus on demand
  // At rest: only summed frame-to-frame lines. Pointing at a card swaps in that
  // card's own connections and fades the cards it has nothing to do with.
  const focusId = hovered ?? selected;
  const { nodes, edges } = useMemo(() => {
    if (mode !== "level" || !view || !focusId) return base;
    const rep = view.cards.has(focusId) || view.groups.some((g) => g.id === focusId) || focusId.startsWith("out:")
      ? focusId : view.repOf(focusId);
    if (!rep || rep === "__root__") return base;
    const isGroup = view.groups.some((g) => g.id === rep) || rep.startsWith("out:");
    const lit = new Set<string>([rep]);
    let extra: RFEdge[] = [];
    let groupEdges = base.edges;
    if (isGroup) {
      groupEdges = base.edges.map((e) => (e.source === rep || e.target === rep ? { ...e, className: `${e.className} hot` } : { ...e, className: `${e.className} faded` }));
      for (const e of base.edges) if (e.source === rep || e.target === rep) { lit.add(e.source); lit.add(e.target); }
    } else {
      const mine = base.cardLinks.filter((l) => l.source === rep || l.target === rep);
      for (const l of mine) { lit.add(l.source); lit.add(l.target); }
      extra = mine.map((l) => ({ ...summedEdge(l, "card"), zIndex: 10 }));
      groupEdges = base.edges.map((e) => ({ ...e, className: `${e.className} faded` }));
      const g = view.cards.get(rep)?.group;
      if (g) lit.add(g);
    }
    const litGroups = new Set([...lit].map((id) => view.cards.get(id)?.group).filter(Boolean) as string[]);
    return {
      nodes: base.nodes.map((n) => {
        const on = lit.has(n.id) || (n.type === "frame" && litGroups.has(n.id));
        return { ...n, className: n.id === rep ? "focus" : on ? "lit" : "faded" };
      }),
      edges: [...groupEdges, ...extra],
    };
  }, [base, focusId, mode, view]);

  // ------------------------------------------------------------- fitting the view
  useEffect(() => {
    fitPending.current = true;
  }, [crumbs, level]);
  useEffect(() => {
    if (!fitPending.current || base.nodes.length === 0) return;
    fitPending.current = false;
    const t = setTimeout(() => rf.fitView({ padding: 0.1, duration: 300, maxZoom: 1.15 }), 80);
    return () => clearTimeout(t);
  }, [base, rf]);

  // ------------------------------------------------------------- search
  const results = useMemo(() => search(ix, query, filters), [ix, query, filters]);
  const reveal = (b: Block) => {
    // open the block that holds it, at a level where it is a card
    const parent = b.parent_id ? ix.get(b.parent_id) : ix.get(graph.root_id);
    const home = parent.level >= 3 ? ix.ancestors(b.id).find((x) => x.level === 3 && x.kind !== "file") ?? parent : parent;
    const holder = b.level >= 4 ? ix.ancestors(b.id).filter((x) => x.level <= 3).pop()! : home;
    setCrumbs([{ kind: "block", id: graph.root_id }, ...(holder.id !== graph.root_id ? [{ kind: "block" as const, id: holder.id }] : [])]);
    setLevel(Math.max(b.level, Math.min(4, holder.level + 1)));
    setShowAll({ [holder.id]: true });
    setSelected(b.id);
    setQuery("");
  };

  // ------------------------------------------------------------- ui
  const crumbTitle = (c: Crumb, i: number) => {
    if (c.kind === "inside") return c.title;
    if (c.kind === "trace") return `Trace: ${ix.get(c.id).code_name}`;
    if (i === 0) return graph.name;
    return displayTitle([ix.get(c.id)]);
  };

  const currentLevel = mode === "inside" ? (insideData?.blocks[0]?.level ?? 5) : level;
  const selectedBlock = selected ? ix.blocks.get(selected) ?? null : null;
  const selectedInside = !selectedBlock && insideData ? insideData.blocks.find((b) => b.id === selected) ?? null : null;
  const stats = graph.stats;
  const shown = view ? view.cards.size : 0;

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
              const disabled = inside || mode !== "level" || (view ? l.n <= view.root.level : false);
              return (
                <button
                  key={l.n}
                  className={`lvl ${currentLevel === l.n ? "active" : ""} ${inside ? "inside" : ""}`}
                  disabled={disabled}
                  title={inside ? "Inside levels open one block at a time: double-click a function" : `Level ${l.n}: ${l.name}`}
                  onClick={() => { setLevel(l.n); setShowAll({}); }}
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
                onClick={() => { setCrumbs(crumbs.slice(0, i + 1)); setShowAll({}); setSelected(null); setHovered(null); }}
              >
                {crumbTitle(c, i)}
              </button>
            </span>
          ))}
          <span className="stats">
            {mode === "level" ? `${shown} blocks on screen · ` : ""}
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
            <h4>How to read it</h4>
            <p className="hint">
              You see one block at a time. Lines between boxes are totals: the number says how many connections run
              that way.
            </p>
            <p className="hint">
              Click a card to trace it: who uses it on the left, what it uses on the right. Click any card in a
              trace to follow it. Point at a card to see its links, and double-click to go inside.
            </p>
          </aside>
          <div className={`canvas ${focusId ? "has-focus" : ""}`}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onPaneClick={() => setSelected(null)}
              minZoom={0.1}
              maxZoom={2}
              zoomOnDoubleClick={false}
              nodesDraggable={false}
              nodesConnectable={false}
              proOptions={{ hideAttribution: true }}
            >
              <Controls showInteractive={false} />
            </ReactFlow>
            {!busy && nodes.length === 0 && (
              <div className="empty">{mode === "trace" ? "No connections for this block with the current filters." : "Nothing to show here with the current filters."}</div>
            )}
            {mode === "trace" && trace && (
              <div className="trace-legend">
                <span>Used by · {trace.callers.reduce((s, g) => s + g.items.length, 0)}</span>
                <span>Uses · {trace.callees.reduce((s, g) => s + g.items.length, 0)}</span>
              </div>
            )}
          </div>
          <Panel
            ix={ix}
            block={selectedBlock}
            inside={selectedInside}
            loadCode={loadCode}
            onSelect={(id) => { const b = ix.blocks.get(id); if (b) reveal(b); }}
            onDrill={drill}
            onTrace={traceBlock}
            onClose={() => setSelected(null)}
          />
        </div>
      </div>
    </Actions.Provider>
  );
}

function summedEdge(l: Link, scope: "group" | "card"): RFEdge {
  const kind = mainKind(l);
  const width = Math.min(1 + Math.log2(l.count + 1) * (scope === "group" ? 0.9 : 0.6), 5);
  return {
    id: `${scope}:${l.id}`,
    source: l.source,
    target: l.target,
    className: `sum sum-${kind} ${scope} ${l.maybe ? "maybe" : ""}`,
    style: { stroke: EDGE_COLORS[kind], strokeWidth: width },
    markerEnd: { type: MarkerType.ArrowClosed, color: EDGE_COLORS[kind], width: 12, height: 12 },
    label: l.count > 1 ? String(l.count) : undefined,
    labelBgPadding: [4, 2],
    labelBgBorderRadius: 8,
    selectable: false,
    focusable: false,
    data: { kinds: l.kinds },
  };
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

