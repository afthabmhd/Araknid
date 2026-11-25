"""Plain-language summaries without AI.

Each block gets one short line saying what it does:
1. The author's own words first: a Python docstring, or the comment right
   above a JS/TS definition (JSDoc or // lines). First sentence only.
2. Otherwise a sentence built from code facts: what it sends requests to,
   what it uses, creates or shows, which scripts a page loads, and so on.

AI-written names and summaries (with the user's own key) can replace these
later; `summary_by` records where each line came from.
"""

from __future__ import annotations

import re
from typing import Optional

from .model import Block, Graph

MAX_LEN = 140

PY_DOC_RE = re.compile(r'^[ \t]*[rRuUbB]{0,2}("""|\'\'\')(.*?)\1', re.S | re.M)
JS_BLOCK_RE = re.compile(r"/\*\*?(.*?)\*/\s*$", re.S)


def _words(name: str) -> str:
    s = re.sub(r"[_\-]+", " ", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s).strip()
    return s.lower() if s else name


def _first_sentence(text: str) -> Optional[str]:
    lines = []
    for ln in text.strip().splitlines():
        ln = ln.strip().lstrip("*").strip()
        if not ln:
            if lines:
                break
            continue
        if ln.startswith("@") or ln.startswith(":param") or ln.startswith("Args:") or ln.startswith("Returns"):
            break
        lines.append(ln)
    s = " ".join(lines).strip()
    if not s or len(s) < 4:
        return None
    m = re.match(r"(.+?[.!?])(\s|$)", s)
    s = m.group(1) if m else s
    if len(s) > MAX_LEN:
        s = s[: MAX_LEN - 1].rsplit(" ", 1)[0] + "…"
    return s[:1].upper() + s[1:]


def author_doc(b: Block, src: bytes) -> Optional[str]:
    if b.start_byte is None or b.end_byte is None:
        return None
    text = src[b.start_byte:b.end_byte].decode("utf-8", errors="replace")
    if b.language == "python":
        if b.kind == "file":
            m = re.match(r'\s*(?:#[^\n]*\n\s*)*[rRuU]?("""|\'\'\')(.*?)\1', text, re.S)
            return _first_sentence(m.group(2)) if m else None
        # the body starts after the signature's colon line
        head_end = text.find(":\n")
        if head_end < 0:
            return None
        body = text[head_end + 2:]
        m = PY_DOC_RE.match(body)
        return _first_sentence(m.group(2)) if m else None
    if b.language in ("javascript", "typescript", "tsx"):
        if b.kind == "file":
            m = re.match(r"\s*(?:/\*\*?(.*?)\*/|((?://[^\n]*\n\s*)+))", text, re.S)
            if not m:
                return None
            raw = m.group(1) if m.group(1) is not None else re.sub(r"^\s*//", "", m.group(2), flags=re.M)
            return _first_sentence(raw)
        before = src[max(0, b.start_byte - 2000):b.start_byte].decode("utf-8", errors="replace").rstrip()
        before = re.sub(r"(export\s+(default\s+)?)$", "", before).rstrip()
        m = JS_BLOCK_RE.search(before)
        if m and before.endswith("*/"):
            return _first_sentence(m.group(1))
        lines = []
        for ln in reversed(before.splitlines()):
            if ln.strip().startswith("//"):
                lines.append(ln.strip()[2:])
            else:
                break
        if lines:
            return _first_sentence("\n".join(reversed(lines)))
    return None


def _list(items: list[str], limit: int = 3) -> str:
    items = list(dict.fromkeys(items))
    more = len(items) - limit
    items = items[:limit]
    if more > 0:
        return ", ".join(items) + f" and {more} more"
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def rules_summary(g: Graph, b: Block, out: dict[str, list], inc: dict[str, list]) -> Optional[str]:
    mine = out.get(b.id, [])
    name = lambda bid: _words(g.blocks[bid].code_name) if g.blocks[bid].kind not in ("file", "module", "system") else g.blocks[bid].code_name
    by_kind: dict[str, list[str]] = {}
    for e in mine:
        by_kind.setdefault(e.kind, []).append(e.target)
    parts: list[str] = []
    if b.route:
        parts.append(f"API endpoint for {b.route}")
    if "page" in b.tags:
        scripts = [g.blocks[t].code_name for t in by_kind.get("loads", []) if not g.blocks[t].code_name.endswith(".css")]
        parts.append("Web page" + (f" that runs {_list(scripts)}" if scripts else ""))
    if "requests" in by_kind:
        routes = [g.blocks[t].route or g.blocks[t].code_name for t in by_kind["requests"]]
        parts.append(f"Sends requests to {_list(routes, 2)}")
    if b.kind in ("function", "method", "component", "class") or b.kind == "file" and not parts:
        if "renders" in by_kind:
            parts.append(f"Shows {_list([name(t) for t in by_kind['renders']])}")
        if "instantiates" in by_kind:
            parts.append(f"Creates {_list([name(t) for t in by_kind['instantiates']], 2)}")
        if "calls" in by_kind:
            parts.append(f"Uses {_list([name(t) for t in by_kind['calls']])}")
        if "inherits" in by_kind:
            parts.append(f"Builds on {_list([name(t) for t in by_kind['inherits']], 2)}")
    if b.kind == "class" and not parts:
        methods = [g.blocks[c] for c in b.children if g.blocks[c].kind == "method"]
        if methods:
            parts.append(f"Groups {len(methods)} method{'s' if len(methods) != 1 else ''}: {_list([_words(m.code_name) for m in methods])}")
    if b.kind == "file" and not parts:
        defs = sorted((g.blocks[c] for c in b.children), key=lambda x: -x.importance)
        if defs:
            parts.append(f"Holds {_list([_words(d.code_name) for d in defs])}")
    if b.kind == "module" and not parts:
        files = [g.blocks[c] for c in b.children]
        parts.append(f"Folder with {len(files)} item{'s' if len(files) != 1 else ''}")
    if not parts:
        return None
    s = parts[0] + "".join(("; " + p[:1].lower() + p[1:]) for p in parts[1:3])
    users = len({e.source for e in inc.get(b.id, [])})
    if users and b.kind not in ("module", "system"):
        s += f". Used by {users} place{'s' if users != 1 else ''}"
    return s + "."


def summarise(g: Graph, sources: dict[str, bytes]) -> None:
    out: dict[str, list] = {}
    inc: dict[str, list] = {}
    for e in g.edges:
        if e.kind == "imports":
            continue
        out.setdefault(e.source, []).append(e)
        inc.setdefault(e.target, []).append(e)
    for b in g.blocks.values():
        if b.kind in ("project", "system", "asset"):
            continue
        src = sources.get(b.file or "")
        doc = author_doc(b, src) if src is not None and b.kind != "module" else None
        if doc:
            b.summary, b.summary_by = doc, "author"
            continue
        s = rules_summary(g, b, out, inc)
        if s:
            b.summary, b.summary_by = s, "rules"
