"""HTTP API for the web client.

Run:  uvicorn araknid.api:app --reload   (from araknid2/backend)
"""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .inside import inside
from .store import Store
from .walker import CODE_EXTENSIONS

app = FastAPI(title="Araknid 2.0", version="0.1.0")
store = Store()

# Importing a folder by server path only makes sense when the server runs on
# the user's own machine (local dev, or the desktop wrapper later).
ALLOW_LOCAL = os.environ.get("ARAKNID_ALLOW_LOCAL", "1") == "1"
MAX_UPLOAD_BYTES = 200 * 1024 * 1024


class LocalImport(BaseModel):
    path: str


class GithubImport(BaseModel):
    url: str


def _not_found(e: Exception):
    raise HTTPException(404, f"Not found: {e}")


@app.get("/api/health")
def health():
    return {"ok": True, "allow_local": ALLOW_LOCAL}


@app.get("/api/projects")
def list_projects():
    return [asdict(p) for p in store.list()]


@app.post("/api/projects/local")
def import_local(body: LocalImport):
    if not ALLOW_LOCAL:
        raise HTTPException(403, "Local folder import is off on this server. Upload the folder instead.")
    try:
        return asdict(store.import_local(body.path))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/projects/github")
def import_github(body: GithubImport):
    try:
        return asdict(store.import_github(body.url))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/projects/upload")
async def import_upload(name: str = Form(""), files: list[UploadFile] = File(...), paths: list[str] = Form(...)):
    if len(paths) != len(files):
        raise HTTPException(400, "Each file needs a path")
    total = 0
    items = []
    for f, rel in zip(files, paths):
        data = await f.read()
        total += len(data)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Upload is over 200 MB. Leave out node_modules and build folders.")
        items.append((rel, data))
    return asdict(store.import_upload(name, items))


@app.post("/api/projects/{pid}/remap")
def remap(pid: str):
    try:
        return asdict(store.map(pid))
    except KeyError as e:
        _not_found(e)


@app.delete("/api/projects/{pid}")
def delete_project(pid: str):
    try:
        store.get(pid)
    except KeyError as e:
        _not_found(e)
    store.delete(pid)
    return {"ok": True}


@app.get("/api/projects/{pid}/graph")
def get_graph(pid: str):
    try:
        return store.graph(pid)
    except KeyError as e:
        _not_found(e)


@app.get("/api/projects/{pid}/code")
def get_code(pid: str, file: str, start_line: Optional[int] = None, end_line: Optional[int] = None):
    try:
        data = store.read_file(pid, file).decode("utf-8", "replace")
    except (KeyError, FileNotFoundError, IsADirectoryError) as e:
        _not_found(e)
    lines = data.splitlines()
    a = max(1, start_line or 1)
    b = min(len(lines), end_line or len(lines))
    return {"file": file, "start_line": a, "end_line": b, "code": "\n".join(lines[a - 1:b])}


@app.get("/api/projects/{pid}/inside")
def get_inside(pid: str, file: str, start_byte: int, end_byte: int, kind: str):
    ext = os.path.splitext(file)[1].lower()
    lang = CODE_EXTENSIONS.get(ext)
    if not lang:
        raise HTTPException(400, "Not a supported code file")
    try:
        src = store.read_file(pid, file)
    except (KeyError, FileNotFoundError) as e:
        _not_found(e)
    return inside(lang, file, src, start_byte, end_byte, kind)


# Serve the built web client when it exists (araknid2/web/dist).
WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        return FileResponse(WEB_DIST / "index.html")
