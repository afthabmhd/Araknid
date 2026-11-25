import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Project } from "./types";

// Same list as the backend walker, so uploads skip generated and vendored code.
const SKIP_DIRS = new Set([
  ".git", "node_modules", "__pycache__", ".venv", "venv", "env", "dist", "build", "out", ".next", ".nuxt",
  ".turbo", ".cache", "coverage", ".mypy_cache", ".pytest_cache", ".tox", "site-packages", ".idea", ".vscode",
  "target", "vendor", "third_party",
]);
const KEEP_EXT = /\.(py|pyi|js|mjs|cjs|jsx|ts|mts|cts|tsx|json|ya?ml|toml|ini|cfg|sql|html|css|scss|md|txt|sh|graphql|prisma)$/i;
const KEEP_NAMES = new Set(["Dockerfile", "Makefile", "Procfile", ".gitignore"]);

export function ImportScreen({ onOpen }: { onOpen: (p: Project) => void }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [github, setGithub] = useState("");
  const [local, setLocal] = useState("");
  const [allowLocal, setAllowLocal] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const folderInput = useRef<HTMLInputElement>(null);

  const refresh = () => api.projects().then(setProjects).catch((e) => setError(String(e.message ?? e)));
  useEffect(() => {
    refresh();
    api.health().then((h) => setAllowLocal(h.allow_local)).catch(() => setError("The Araknid server is not running. Start it with `uvicorn araknid.api:app`."));
    folderInput.current?.setAttribute("webkitdirectory", "");
  }, []);

  const run = async (label: string, fn: () => Promise<Project>) => {
    setBusy(label);
    setError(null);
    try {
      const p = await fn();
      onOpen(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const onFolder = (list: FileList | null) => {
    if (!list || !list.length) return;
    const files: { path: string; file: File }[] = [];
    for (const f of Array.from(list)) {
      const rel = (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name;
      const parts = rel.split("/");
      if (parts.slice(0, -1).some((p) => SKIP_DIRS.has(p))) continue;
      const name = parts[parts.length - 1];
      if (!KEEP_EXT.test(name) && !KEEP_NAMES.has(name)) continue;
      if (/\.min\.(js|css)$/.test(name) || /-lock\.json$/.test(name)) continue;
      files.push({ path: rel, file: f });
    }
    const name = (files[0]?.path.split("/")[0]) || "upload";
    run(`Uploading ${files.length} files`, () => api.importUpload(name, files));
  };

  return (
    <div className="import">
      <div className="import-inner">
        <h1>Araknid <span>2.0</span></h1>
        <p className="lead">Import a JavaScript, TypeScript or Python repo and read it as a web of blocks.</p>

        <section className="import-card">
          <h3>GitHub repo</h3>
          <form onSubmit={(e) => { e.preventDefault(); run("Cloning and mapping", () => api.importGithub(github)); }}>
            <input placeholder="https://github.com/owner/repo" value={github} onChange={(e) => setGithub(e.target.value)} />
            <button disabled={!github || !!busy}>Import</button>
          </form>
          <p className="muted small">Public repos for now. Private repos come with GitHub sign-in.</p>
        </section>

        <section className="import-card">
          <h3>Folder from this computer</h3>
          <div className="row">
            <button disabled={!!busy} onClick={() => folderInput.current?.click()}>Choose folder…</button>
            <input ref={folderInput} type="file" multiple style={{ display: "none" }} onChange={(e) => onFolder(e.target.files)} />
            <span className="muted small">Uploads code files only. node_modules and build output are skipped.</span>
          </div>
          {allowLocal && (
            <form onSubmit={(e) => { e.preventDefault(); run("Mapping folder", () => api.importLocal(local)); }}>
              <input placeholder="Or a path on the server, e.g. /home/me/project" value={local} onChange={(e) => setLocal(e.target.value)} />
              <button disabled={!local || !!busy}>Map path</button>
            </form>
          )}
        </section>

        {busy && <div className="status">{busy}…</div>}
        {error && <div className="error">{error}</div>}

        {projects.length > 0 && (
          <section className="projects">
            <h3>Projects</h3>
            <ul>
              {projects.map((p) => (
                <li key={p.id}>
                  <button className="proj" onClick={() => onOpen(p)}>
                    <b>{p.name}</b>
                    <span className="muted small">
                      {p.source} · {p.stats ? `${p.stats.files} files, ${Number(p.stats.lines ?? 0).toLocaleString()} lines` : "not mapped"}
                    </span>
                  </button>
                  <button className="icon" title="Delete project" onClick={() => api.remove(p.id).then(refresh)}>×</button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
