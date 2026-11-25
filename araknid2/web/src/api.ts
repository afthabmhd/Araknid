import type { GraphData, InsideResult, Project } from "./types";

/**
 * Static demo build (VITE_STATIC=1): no server. A pre-mapped repo is read from
 * demo.json next to the page, so the code web can be shared as a link.
 * Built with `npm run build:demo` after `python -m araknid.demo <repo>`.
 */
export const STATIC = import.meta.env.VITE_STATIC === "1";

interface DemoData {
  project: Project;
  graph: GraphData;
  files: Record<string, string>;
  inside: Record<string, InsideResult>;
}
let demo: Promise<DemoData> | null = null;
const loadDemo = () => (demo ??= fetch("./demo.json").then((r) => r.json() as Promise<DemoData>));
const enc = new TextEncoder();
const dec = new TextDecoder();
const notInDemo = () => Promise.reject(new Error("This is a demo with one repo already mapped. Run Araknid locally to import your own."));

const staticApi = {
  health: async () => ({ ok: true, allow_local: false }),
  projects: async () => [(await loadDemo()).project],
  importLocal: (_p: string) => notInDemo() as Promise<Project>,
  importGithub: (_u: string) => notInDemo() as Promise<Project>,
  importUpload: (_n: string, _f: { path: string; file: File }[]) => notInDemo() as Promise<Project>,
  remap: async (_id: string) => (await loadDemo()).project,
  remove: (_id: string) => notInDemo() as Promise<{ ok: boolean }>,
  graph: async (_id: string) => (await loadDemo()).graph,
  code: async (_id: string, file: string, start?: number | null, end?: number | null) => {
    const lines = ((await loadDemo()).files[file] ?? "").split("\n");
    const a = Math.max(1, start ?? 1);
    const b = Math.min(lines.length, end ?? lines.length);
    return { code: lines.slice(a - 1, b).join("\n"), start_line: a };
  },
  inside: async (_id: string, file: string, start: number, end: number, kind: string): Promise<InsideResult> => {
    const d = await loadDemo();
    const res = d.inside[`${file}:${start}:${end}:${kind}`] ?? { blocks: [], edges: [] };
    const bytes = enc.encode(d.files[file] ?? "");
    return { ...res, blocks: res.blocks.map((b) => ({ ...b, code: dec.decode(bytes.slice(b.start_byte, b.end_byte)) })) };
  },
};

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not json */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

const post = (url: string, body: unknown) =>
  fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

const serverApi = {
  health: () => fetch("/api/health").then((r) => j<{ ok: boolean; allow_local: boolean }>(r)),
  projects: () => fetch("/api/projects").then((r) => j<Project[]>(r)),
  importLocal: (path: string) => post("/api/projects/local", { path }).then((r) => j<Project>(r)),
  importGithub: (url: string) => post("/api/projects/github", { url }).then((r) => j<Project>(r)),
  importUpload: (name: string, files: { path: string; file: File }[]) => {
    const fd = new FormData();
    fd.append("name", name);
    for (const f of files) {
      fd.append("files", f.file);
      fd.append("paths", f.path);
    }
    return fetch("/api/projects/upload", { method: "POST", body: fd }).then((r) => j<Project>(r));
  },
  remap: (id: string) => fetch(`/api/projects/${id}/remap`, { method: "POST" }).then((r) => j<Project>(r)),
  remove: (id: string) => fetch(`/api/projects/${id}`, { method: "DELETE" }).then((r) => j<{ ok: boolean }>(r)),
  graph: (id: string) => fetch(`/api/projects/${id}/graph`).then((r) => j<GraphData>(r)),
  code: (id: string, file: string, start?: number | null, end?: number | null) => {
    const q = new URLSearchParams({ file });
    if (start) q.set("start_line", String(start));
    if (end) q.set("end_line", String(end));
    return fetch(`/api/projects/${id}/code?${q}`).then((r) => j<{ code: string; start_line: number }>(r));
  },
  inside: (id: string, file: string, start: number, end: number, kind: string) => {
    const q = new URLSearchParams({ file, start_byte: String(start), end_byte: String(end), kind });
    return fetch(`/api/projects/${id}/inside?${q}`).then((r) => j<InsideResult>(r));
  },
};

export const api: typeof serverApi = STATIC ? (staticApi as typeof serverApi) : serverApi;
