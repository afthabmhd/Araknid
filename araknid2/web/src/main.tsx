import { StrictMode, useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "@xyflow/react/dist/style.css";
import "./styles.css";
import { api } from "./api";
import { ImportScreen } from "./ImportScreen";
import { ProjectView } from "./ProjectView";
import type { GraphData, Project } from "./types";

function App() {
  const [projectId, setProjectId] = useState<string | null>(() => new URLSearchParams(location.search).get("p"));
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((id: string) => {
    setGraph(null);
    setError(null);
    api.graph(id).then(setGraph).catch((e) => setError(String(e.message ?? e)));
  }, []);

  useEffect(() => {
    const url = new URL(location.href);
    if (projectId) {
      url.searchParams.set("p", projectId);
      load(projectId);
    } else url.searchParams.delete("p");
    history.replaceState(null, "", url);
  }, [projectId, load]);

  if (!projectId) return <ImportScreen onOpen={(p: Project) => setProjectId(p.id)} />;
  if (error) return <div className="center error">{error} <button onClick={() => setProjectId(null)}>Back</button></div>;
  if (!graph) return <div className="center">Loading the map…</div>;
  return (
    <ProjectView
      key={graph.project_id + String(graph.stats.map_seconds) + graph.blocks.length}
      graph={graph}
      onBack={() => setProjectId(null)}
      onRemap={() => api.remap(projectId).then(() => load(projectId))}
    />
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
