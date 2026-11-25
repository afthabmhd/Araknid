import type { GraphData, InsideResult, Project } from "./types";

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

export const api = {
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
