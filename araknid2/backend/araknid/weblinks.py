"""Links that cross the network or the page: front-end code calling API routes,
and HTML pages loading their scripts and styles.

These connections are real but no import shows them, so the plain resolver
misses them (a vanilla JS site calling a Python API is the common case).

- Routes come from decorators (@app.get("/users/{id}")) and from file-based
  routing: Vercel and Netlify style `api/...` files, Next.js `pages/api/...`
  and app router `app/.../route.ts`.
- Requests come from fetch(), axios.get() and friends in JS, and from
  requests/httpx in Python, when the first argument is a URL string.
- Pages: <script src> and <link href> in .html files.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Optional

PARAM_RE = re.compile(r"\[\.\.\.[^\]]+\]|\[[^\]]+\]|\{[^}]*\}|:[A-Za-z_]\w*|<[^>]+>")
SCRIPT_RE = re.compile(r"<script\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)
STYLE_RE = re.compile(r"<link\b[^>]*\bhref\s*=\s*[\"']([^\"']+\.css)(?:\?[^\"']*)?[\"']", re.I)
CODE_EXT = (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".mts")


@dataclass
class Route:
    path: str  # "/api/admin/events/[slug]"
    method: Optional[str]
    block_id: str
    pattern: re.Pattern
    from_file: bool  # file-based routes are full paths; decorator routes may sit under a prefix


def _pattern(path: str) -> re.Pattern:
    out = ""
    pos = 0
    for m in PARAM_RE.finditer(path):
        out += re.escape(path[pos:m.start()])
        out += ".+" if m.group(0).startswith("[...") else "[^/]+"
        pos = m.end()
    out += re.escape(path[pos:])
    return re.compile(out.rstrip("/") + "/?$")


def file_route(rel: str, system_root: str) -> Optional[str]:
    """URL path served by a file under file-based routing, or None."""
    if not rel.endswith(CODE_EXT):
        return None
    inner = rel[len(system_root) + 1:] if system_root and rel.startswith(system_root + "/") else rel
    parts = list(PurePosixPath(inner).parts)
    stem = PurePosixPath(parts[-1]).name
    for ext in CODE_EXT:
        if stem.endswith(ext):
            stem = stem[: -len(ext)]
            break
    parts[-1] = stem
    if parts[0] == "api":  # Vercel / Netlify functions
        segs = parts
    elif parts[:2] == ["pages", "api"] or parts[:3] == ["src", "pages", "api"]:
        segs = parts[parts.index("api"):]
    elif "app" in parts and stem == "route":  # Next.js app router
        i = parts.index("app")
        segs = [p for p in parts[i + 1:-1] if not (p.startswith("(") and p.endswith(")"))]
    else:
        return None
    if segs and segs[-1] == "index":
        segs = segs[:-1]
    if any(s.startswith("_") for s in segs):  # private helpers, not routes
        return None
    return "/" + "/".join(segs)


def build_routes(files: list[str], systems: list[str], system_for, file_ids: dict[str, str],
                 decorated: list[tuple[str, str, Optional[str]]]) -> list[Route]:
    routes: list[Route] = []
    for rel in files:
        path = file_route(rel, system_for(rel))
        if path is not None and rel in file_ids:
            routes.append(Route(path, None, file_ids[rel], _pattern(path), True))
    for bid, path, method in decorated:
        if path.startswith("/") or path == "":
            routes.append(Route(path or "/", method, bid, _pattern(path or "/"), False))
    return routes


def url_path(url: str) -> str:
    u = re.sub(r"^https?://[^/]+", "", url)
    u = u.split("?")[0].split("#")[0]
    return u or "/"


def match_request(url: str, method: Optional[str], routes: list[Route]) -> tuple[Optional[Route], str]:
    """Best route for a request URL, with certainty."""
    path = url_path(url).replace("{}", "x")
    exact = [r for r in routes if r.pattern.match(path)]
    if exact:
        same = [r for r in exact if r.method is None or method is None or r.method == method]
        pick = (same or exact)
        # prefer the most specific (longest literal path)
        pick.sort(key=lambda r: -len(PARAM_RE.sub("", r.path)))
        return pick[0], "sure" if len(pick) == 1 or same else "maybe"
    # decorator routes under a router prefix: match on the tail
    tail = [r for r in routes if not r.from_file and r.path not in ("", "/")
            and re.search(r.pattern.pattern.lstrip("^"), path) and (r.method is None or method is None or r.method == method)]
    if tail:
        # the most specific route wins (/users/me over /users/{id}); a tie stays unlinked
        lit = lambda r: len(PARAM_RE.sub("", r.path))
        tail.sort(key=lambda r: -lit(r))
        if len(tail) == 1 or lit(tail[0]) > lit(tail[1]):
            return tail[0], "maybe"
    return None, "sure"


def page_links(rel: str, html: str, system_root: str, known: set[str]) -> list[tuple[str, str]]:
    """(target file, kind) for each script and stylesheet an HTML page loads."""
    out: list[tuple[str, str]] = []
    base = PurePosixPath(rel).parent
    for rx in (SCRIPT_RE, STYLE_RE):
        for m in rx.finditer(html):
            ref = m.group(1).split("?")[0].split("#")[0]
            if re.match(r"^(https?:)?//", ref):
                continue
            if ref.startswith("/"):
                cands = [f"{system_root}/{ref.lstrip('/')}" if system_root else ref.lstrip("/")]
                # static folders served at the site root
                for d in ("public", "static", "www"):
                    cands.append(f"{system_root + '/' if system_root else ''}{d}/{ref.lstrip('/')}")
            else:
                cands = [str(PurePosixPath(base, ref))]
            for c in cands:
                c = posixpath.normpath(c)
                if c in known:
                    out.append((c, "loads"))
                    break
    return out
