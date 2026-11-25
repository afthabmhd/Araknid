"""Graph engine: build the nested block web (levels 0 to 4) for a repo.

Pipeline (from the doc's "Mapping pipeline"):
  1. Parse every supported file (parsers.py)
  2. Resolve imports and calls across files (resolver.py)
  3. Build blocks: systems > modules > files > definitions, with hashes
  4. (later) Cluster large folders with Leiden
  5. Check parse health
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path, PurePosixPath
from typing import Optional

from . import parsers
from .model import (
    LEVEL_DEFINITION, LEVEL_FILE, LEVEL_MODULE, LEVEL_PROJECT, LEVEL_SYSTEM,
    Block, Edge, Graph, block_id, text_hash,
)
from .resolver import Resolver
from .walker import FoundFile, is_test_path, walk

MANIFESTS = ("package.json", "pyproject.toml", "setup.py", "setup.cfg", "Dockerfile", "docker-compose.yml", "docker-compose.yaml")


def _detect_systems(files: list[FoundFile]) -> list[str]:
    """Return system root directories ("" is the repo root).

    A deployable or runnable unit is a folder with its own manifest. A root
    package.json that only declares workspaces is a container, not a unit.
    """
    dirs: set[str] = set()
    for f in files:
        p = PurePosixPath(f.rel)
        if p.name in MANIFESTS:
            d = str(p.parent) if str(p.parent) != "." else ""
            dirs.add(d)
    if not dirs:
        return [""]
    # Nested manifests within one unit (e.g. a Dockerfile next to package.json) collapse.
    roots = sorted(dirs, key=lambda d: (d.count("/"), d))
    # Keep the shallowest manifest dirs, but allow siblings below a root workspace.
    result: list[str] = []
    for d in roots:
        if any(d != r and (r == "" or d.startswith(r + "/")) for r in result if r != ""):
            continue  # nested inside a non-root system
        result.append(d)
    # Files outside every unit belong to a root unit.
    if "" not in result and any(_system_for(f.rel, result) == "" for f in files):
        result.insert(0, "")
    return result


def _system_for(rel: str, systems: list[str]) -> str:
    best = ""
    for s in systems:
        if s and (rel == s or rel.startswith(s + "/")) and len(s) > len(best):
            best = s
    return best


def _code_title(name: str) -> str:
    """A readable fallback title from a code name (not AI-written)."""
    s = re.sub(r"[_\-]+", " ", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s).strip()
    return s[:1].upper() + s[1:] if s else name


def _system_name(root: Path, sysdir: str, repo_name: str) -> str:
    base = root / sysdir if sysdir else root
    pj = base / "package.json"
    if pj.is_file():
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
            if isinstance(data.get("name"), str):
                return data["name"]
        except Exception:
            pass
    pp = base / "pyproject.toml"
    if pp.is_file():
        m = re.search(r'^\s*name\s*=\s*"([^"]+)"', pp.read_text(encoding="utf-8", errors="replace"), re.M)
        if m:
            return m.group(1)
    return sysdir.split("/")[-1] if sysdir else repo_name


def build_graph(root: Path, project_id: str, name: str) -> Graph:
    t0 = time.time()
    root = root.resolve()
    files = walk(root)
    systems = _detect_systems(files)

    g = Graph(project_id=project_id, name=name, root_id=block_id(""))
    g.add(Block(id=g.root_id, parent_id=None, path="", level=LEVEL_PROJECT, kind="project", code_name=name))

    sys_ids: dict[str, str] = {}
    for s in systems:
        bid = block_id(f"@system/{s}")
        g.add(Block(
            id=bid, parent_id=g.root_id, path=s or ".", level=LEVEL_SYSTEM, kind="system",
            code_name=_system_name(root, s, name), file=s or None,
        ))
        sys_ids[s] = bid

    module_ids: dict[str, str] = {}

    def module_for(dir_rel: str, sysdir: str) -> str:
        """Block id of the module (folder) holding a file, creating parents."""
        if dir_rel == sysdir:
            return sys_ids[sysdir]
        if dir_rel in module_ids:
            return module_ids[dir_rel]
        parent_dir = str(PurePosixPath(dir_rel).parent)
        parent_dir = "" if parent_dir == "." else parent_dir
        parent = module_for(parent_dir, sysdir)
        bid = block_id(dir_rel + "/")
        is_pkg = (root / dir_rel / "__init__.py").is_file()
        g.add(Block(
            id=bid, parent_id=parent, path=dir_rel, level=LEVEL_MODULE, kind="module",
            code_name=PurePosixPath(dir_rel).name, file=dir_rel,
            tags=["python_package"] if is_pkg else [],
            is_test=is_test_path(dir_rel + "/"),
        ))
        module_ids[dir_rel] = bid
        return bid

    parses: dict[str, parsers.FileParse] = {}
    file_ids: dict[str, str] = {}
    # definition lookup: file rel -> {qualified name: block id}
    defs_by_file: dict[str, dict[str, str]] = {}
    def_nodes: dict[str, parsers.Definition] = {}
    def_file: dict[str, str] = {}
    def_class: dict[str, Optional[str]] = {}  # method block id -> class block id
    total_lines = 0

    for f in files:
        sysdir = _system_for(f.rel, systems)
        parent_dir = str(PurePosixPath(f.rel).parent)
        parent_dir = "" if parent_dir == "." else parent_dir
        parent = module_for(parent_dir, sysdir)
        full = root / f.rel
        try:
            src = full.read_bytes()
        except OSError:
            continue
        lines = src.count(b"\n") + (0 if src.endswith(b"\n") else 1) if src else 0
        total_lines += lines if f.language else 0
        fid = block_id(f.rel)
        fb = Block(
            id=fid, parent_id=parent, path=f.rel, level=LEVEL_FILE,
            kind="file" if f.language else "asset", code_name=PurePosixPath(f.rel).name,
            language=f.language, file=f.rel, start_line=1, end_line=max(lines, 1),
            start_byte=0, end_byte=len(src), loc=lines, content_hash=text_hash(src),
            is_test=is_test_path(f.rel),
        )
        g.add(fb)
        file_ids[f.rel] = fid
        if not f.language:
            continue
        try:
            fp = parsers.parse_file(f.language, src)
        except Exception:
            fb.health = "parse_failed"
            continue
        parses[f.rel] = fp
        if fp.is_entry:
            fb.tags.append("entry")
        if PurePosixPath(f.rel).stem in ("main", "index", "app", "server", "cli", "__main__", "manage", "wsgi", "asgi"):
            fb.tags.append("entry")
        if fp.has_error:
            fb.health = "parse_errors"
        defs_by_file[f.rel] = {}

        def add_defs(defs: list[parsers.Definition], parent_id: str, prefix: str, class_id: Optional[str]) -> int:
            n = 0
            seen: dict[str, int] = {}
            for d in defs:
                seen[d.name] = seen.get(d.name, 0) + 1
                qual = d.name if seen[d.name] == 1 else f"{d.name}#{seen[d.name]}"
                path = f"{f.rel}/{prefix}{qual}"
                bid = block_id(path)
                body = src[d.start_byte:d.end_byte]
                b = Block(
                    id=bid, parent_id=parent_id, path=path, level=LEVEL_DEFINITION, kind=d.kind,
                    code_name=d.name, language=f.language, file=f.rel,
                    start_line=d.start_line, end_line=d.end_line,
                    start_byte=d.start_byte, end_byte=d.end_byte,
                    loc=d.end_line - d.start_line + 1, content_hash=text_hash(body),
                    shape_hash=d.shape_hash, params=d.params, tags=list(dict.fromkeys(d.tags)),
                    build_state="partial" if d.is_stub else "built", is_test=fb.is_test,
                )
                g.add(b)
                defs_by_file[f.rel][prefix + qual] = bid
                def_nodes[bid] = d
                def_file[bid] = f.rel
                def_class[bid] = class_id if d.kind == "method" else None
                n += 1
                n += add_defs(d.children, bid, prefix + qual + ".", bid if d.kind == "class" else None)
            return n

        ndefs = add_defs(fp.definitions, fid, "", None)
        # Parse health: big code files that produce almost no blocks.
        if ndefs == 0 and lines > 300 and not fb.health:
            fb.health = "few_blocks"

    # ---------------------------------------------------------- resolve
    resolver = Resolver(root, [f.rel for f in files if f.language], systems, parses, defs_by_file)
    edges: dict[tuple[str, str, str], Edge] = {}

    def add_edge(src_id: str, dst_id: str, kind: str, certainty: str, origin: str) -> None:
        if src_id == dst_id:
            return
        key = (src_id, dst_id, kind)
        e = edges.get(key)
        if e:
            e.count += 1
            if certainty == "sure":
                e.certainty = "sure"
        else:
            edges[key] = Edge(src_id, dst_id, kind, certainty, origin)  # type: ignore[arg-type]

    for rel, fp in parses.items():
        fid = file_ids[rel]
        bindings = resolver.bindings_for(rel)
        for imp in fp.imports:
            target = resolver.resolve_module(rel, imp)
            if target and target in file_ids:
                add_edge(fid, file_ids[target], "imports", imp.certainty, "extracted")
        for call in fp.top_calls:
            dst, cert = resolver.resolve_call(rel, call, bindings, None)
            if dst:
                add_edge(fid, dst, call.kind, cert, "inferred")

    for bid, d in def_nodes.items():
        rel = def_file[bid]
        bindings = resolver.bindings_for(rel)
        for call in d.calls:
            dst, cert = resolver.resolve_call(rel, call, bindings, def_class.get(bid) or (bid if d.kind == "class" else None))
            if dst:
                add_edge(bid, dst, call.kind, cert, "inferred")
        for base in d.bases:
            dst, cert = resolver.resolve_name(rel, base, bindings)
            if dst:
                add_edge(bid, dst, "inherits", cert, "inferred")

    g.edges = list(edges.values())

    # ---------------------------------------------------------- importance
    indeg: dict[str, int] = {}
    for e in g.edges:
        if e.kind in ("calls", "instantiates", "renders", "inherits"):
            indeg[e.target] = indeg.get(e.target, 0) + e.count
        elif e.kind == "imports":
            indeg[e.target] = indeg.get(e.target, 0) + 1
    degrees = sorted(indeg.values())
    hub_cut = max(15, degrees[int(len(degrees) * 0.98)] if degrees else 0)
    for b in g.blocks.values():
        d = indeg.get(b.id, 0)
        score = float(d)
        if "entry" in b.tags or "route" in b.tags:
            score += 5
        if "exported" in b.tags:
            score += 1
        if d > hub_cut and len(degrees) > 50:
            b.tags.append("hub")
            score = 2.0  # hub exclusion: keep super-hubs from crowding the view
        b.importance = score
    # containers: importance is the sum of their children (computed bottom-up)
    order = sorted(g.blocks.values(), key=lambda b: -b.level)
    for b in order:
        if b.children and b.level <= LEVEL_FILE:
            b.importance += sum(g.blocks[c].importance for c in b.children) * 0.5
            b.loc = b.loc or sum(g.blocks[c].loc for c in b.children)

    # Tests stay beside: a module is a test module if every child is a test.
    for b in order:
        if b.kind in ("module",) and b.children and all(g.blocks[c].is_test for c in b.children):
            b.is_test = True

    counts: dict[str, int] = {}
    for b in g.blocks.values():
        counts[b.kind] = counts.get(b.kind, 0) + 1
    g.stats = {
        "files": len(files),
        "code_files": len(parses),
        "lines": total_lines,
        "blocks": len(g.blocks),
        "edges": len(g.edges),
        "kinds": counts,
        "systems": len(systems),
        "map_seconds": round(time.time() - t0, 2),
        "health_flags": sum(1 for b in g.blocks.values() if b.health),
    }
    return g
