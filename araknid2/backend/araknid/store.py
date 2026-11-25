"""Project store.

Phase one keeps each project as a folder on disk: the source copy (for
GitHub and uploaded imports) and graph.json. The doc's target is Postgres
with pgvector for the seven context stores; this is a stand-in until then.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from .engine import build_graph
from .model import SCHEMA_VERSION

DATA_DIR = Path(os.environ.get("ARAKNID_DATA", Path(__file__).resolve().parent.parent / "data"))
GITHUB_RE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(\.git)?/?$")


@dataclass
class Project:
    id: str
    name: str
    source: str  # local | github | upload
    origin: str  # path or URL as given
    root: str  # folder that is mapped
    created_at: float
    mapped_at: Optional[float] = None
    stats: Optional[dict] = None


class Store:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.dir = Path(data_dir)
        (self.dir / "projects").mkdir(parents=True, exist_ok=True)

    def _pdir(self, pid: str) -> Path:
        if not re.fullmatch(r"p_[0-9a-f]{12}", pid):
            raise KeyError(pid)
        return self.dir / "projects" / pid

    def list(self) -> list[Project]:
        out = []
        for d in sorted((self.dir / "projects").iterdir()):
            meta = d / "project.json"
            if meta.is_file():
                out.append(Project(**json.loads(meta.read_text())))
        return sorted(out, key=lambda p: -p.created_at)

    def get(self, pid: str) -> Project:
        meta = self._pdir(pid) / "project.json"
        if not meta.is_file():
            raise KeyError(pid)
        return Project(**json.loads(meta.read_text()))

    def _save(self, p: Project) -> None:
        d = self._pdir(p.id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "project.json").write_text(json.dumps(asdict(p), indent=2))

    def _new(self, name: str, source: str, origin: str, root: Optional[Path] = None) -> Project:
        pid = "p_" + uuid.uuid4().hex[:12]
        root = root or (self._pdir(pid) / "src")
        p = Project(id=pid, name=name, source=source, origin=origin, root=str(root), created_at=time.time())
        self._save(p)
        return p

    # ------------------------------------------------------------ imports

    def import_local(self, path: str) -> Project:
        root = Path(path).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"Folder not found: {path}")
        p = self._new(root.name, "local", str(root), root)
        return self.map(p.id)

    def import_github(self, url: str) -> Project:
        m = GITHUB_RE.match(url.strip())
        if not m:
            raise ValueError("Use a public GitHub URL like https://github.com/owner/repo")
        p = self._new(m.group(2), "github", url.strip())
        dest = Path(p.root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        res = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", f"https://github.com/{m.group(1)}/{m.group(2)}.git", str(dest)],
            capture_output=True, text=True, timeout=300,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        if res.returncode != 0:
            self.delete(p.id)
            raise ValueError("Could not clone the repo. Is it public? " + res.stderr.strip()[-300:])
        return self.map(p.id)

    def import_upload(self, name: str, files: list[tuple[str, bytes]]) -> Project:
        p = self._new(name or "upload", "upload", "browser upload")
        dest = Path(p.root).resolve()
        dest.mkdir(parents=True, exist_ok=True)
        # Drop a shared top folder ("myrepo/src/a.py" -> "src/a.py")
        tops = {f[0].replace("\\", "/").lstrip("/").split("/")[0] for f in files}
        strip = len(tops) == 1 and all("/" in f[0].replace("\\", "/").lstrip("/") for f in files)
        for rel, data in files:
            rel = rel.replace("\\", "/").lstrip("/")
            if strip:
                rel = rel.split("/", 1)[1]
            target = (dest / rel).resolve()
            if not str(target).startswith(str(dest) + os.sep):
                continue  # path traversal
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return self.map(p.id)

    # ------------------------------------------------------------ mapping

    def map(self, pid: str) -> Project:
        p = self.get(pid)
        g = build_graph(Path(p.root), p.id, p.name)
        (self._pdir(pid) / "graph.json").write_text(json.dumps(g.to_dict()))
        p.mapped_at = time.time()
        p.stats = g.stats
        self._save(p)
        return p

    def graph(self, pid: str) -> dict:
        f = self._pdir(pid) / "graph.json"
        if not f.is_file():
            self.map(pid)
        data = json.loads(f.read_text())
        if data.get("schema_version") != SCHEMA_VERSION:
            self.map(pid)
            data = json.loads(f.read_text())
        return data

    def read_file(self, pid: str, rel: str) -> bytes:
        p = self.get(pid)
        root = Path(p.root).resolve()
        target = (root / rel).resolve()
        if not str(target).startswith(str(root) + os.sep):
            raise KeyError(rel)
        return target.read_bytes()

    def delete(self, pid: str) -> None:
        shutil.rmtree(self._pdir(pid), ignore_errors=True)
