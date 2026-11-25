"""Inside levels (5 Sections, 6 Statements, 7 Expressions), built on demand.

These are computed when the user drills into a definition and are not stored
in the main graph, so a 20k-line repo does not become hundreds of thousands
of records. Section boundaries are found by software. Section names here are
placeholders; plain-language names come from the AI later.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from tree_sitter import Node

from .model import LEVEL_EXPRESSION, LEVEL_SECTION, LEVEL_STATEMENT
from .parsers import parse_bytes

SECTION_MIN_LINES = 40  # [Guess] from the doc: about 40 lines
SECTION_MIN_CONTROL = 3
MAX_SECTIONS = 8

CONTROL = {
    "if_statement", "for_statement", "for_in_statement", "while_statement", "do_statement",
    "try_statement", "with_statement", "match_statement", "switch_statement",
}
BODY_FIELDS = ("body", "consequence", "alternative", "handler", "finalizer")
CLAUSE_TYPES = {
    "else_clause", "elif_clause", "except_clause", "finally_clause", "case_clause", "catch_clause",
    "switch_case", "switch_default", "switch_body", "case_block",
}
HEADER_RE = re.compile(r"^\s*(#|//)\s*(-{2,}|={2,}|\*{2,}|#{2,})?\s*(.+?)\s*(-{2,}|={2,}|\*{2,}|#{2,})?\s*$")


def _iid(file: str, a: int, b: int, kind: str) -> str:
    return "in_" + hashlib.sha1(f"{file}:{a}:{b}:{kind}".encode()).hexdigest()[:12]


def _find_node(root: Node, start: int, end: int) -> Optional[Node]:
    """Smallest named node covering exactly [start, end), or the closest cover."""
    node = root.named_descendant_for_byte_range(start, max(start, end - 1))
    while node is not None and node.parent is not None and (node.start_byte > start or node.end_byte < end):
        node = node.parent
    # prefer an exact match among ancestors
    cur = node
    while cur is not None:
        if cur.start_byte == start and cur.end_byte == end:
            return cur
        cur = cur.parent
    return node


def _def_body(node: Node) -> Optional[Node]:
    """The statement block of a function/class/decorated definition."""
    if node.type == "decorated_definition":
        node = node.child_by_field_name("definition") or node
    if node.type == "export_statement":
        decl = node.child_by_field_name("declaration")
        if decl is not None:
            node = decl
    if node.type in ("lexical_declaration", "variable_declaration"):
        vd = next((c for c in node.named_children if c.type == "variable_declarator"), None)
        v = vd.child_by_field_name("value") if vd is not None else None
        if v is not None:
            node = v
    body = node.child_by_field_name("body")
    return body if body is not None else node


def _statements(container: Node) -> list[Node]:
    return [c for c in container.named_children if c.type != "comment" and not c.type.startswith("type_")]


def _label(src: bytes, node: Node) -> str:
    first = src[node.start_byte:node.end_byte].decode("utf-8", "replace").strip().splitlines()
    t = first[0] if first else node.type
    return (t[:77] + "…") if len(t) > 80 else t


def _block(file: str, src: bytes, node: Node, level: int, kind: str, label: str, start: Optional[int] = None,
           end: Optional[int] = None, has_children: bool = True, extra: Optional[dict] = None) -> dict:
    a = node.start_byte if start is None else start
    b = node.end_byte if end is None else end
    d = {
        "id": _iid(file, a, b, kind),
        "level": level,
        "kind": kind,
        "node_type": node.type,
        "label": label,
        "file": file,
        "start_byte": a,
        "end_byte": b,
        "start_line": src.count(b"\n", 0, a) + 1,
        "end_line": src.count(b"\n", 0, b) + 1,
        "has_children": has_children,
        "code": src[a:b].decode("utf-8", "replace"),
    }
    if extra:
        d.update(extra)
    return d


def _sections(src: bytes, stmts: list[Node], comments: list[Node]) -> list[tuple[int, int, Optional[str]]]:
    """Split a body into (start index, end index, header) groups of statements."""
    if not stmts:
        return []
    header_at: dict[int, str] = {}
    for i, s in enumerate(stmts):
        prev_end = stmts[i - 1].end_byte if i else -1
        for c in comments:
            if prev_end < c.start_byte < s.start_byte:
                m = HEADER_RE.match(src[c.start_byte:c.end_byte].decode("utf-8", "replace"))
                if m:
                    header_at[i] = m.group(3)[:60]
    groups: list[list[int]] = [[0]]
    headers: list[Optional[str]] = [header_at.get(0)]
    for i in range(1, len(stmts)):
        gap = src[stmts[i - 1].end_byte:stmts[i].start_byte].count(b"\n") >= 2
        if i in header_at or gap or stmts[i].type in CONTROL:
            groups.append([i])
            headers.append(header_at.get(i))
        else:
            groups[-1].append(i)
    # merge groups until there are at most MAX_SECTIONS, never merging away a written header
    def lines(g: list[int]) -> int:
        return src.count(b"\n", stmts[g[0]].start_byte, stmts[g[-1]].end_byte) + 1
    while len(groups) > MAX_SECTIONS:
        best = None
        for j in range(len(groups) - 1):
            if headers[j + 1] is not None:
                continue
            size = lines(groups[j]) + lines(groups[j + 1])
            if best is None or size < best[0]:
                best = (size, j)
        if best is None:
            break
        j = best[1]
        groups[j] = groups[j] + groups[j + 1]
        del groups[j + 1]
        del headers[j + 1]
    return [(g[0], g[-1], h) for g, h in zip(groups, headers)]


def _children_of_statement(node: Node) -> list[Node]:
    """Sub-statements of a compound statement. Clauses (else, except, case) open as their own blocks."""
    out: list[Node] = []
    for c in node.named_children:
        if c.type in ("block", "statement_block", "switch_body"):
            out.extend(x for x in c.named_children if x.type != "comment")
        elif c.type in CLAUSE_TYPES:
            out.append(c)
    return out


def _is_compound(node: Node) -> bool:
    return node.type in CONTROL or node.type in CLAUSE_TYPES or node.type in ("block", "statement_block")


def _expr_children(node: Node) -> list[Node]:
    out = []
    for c in node.named_children:
        if c.type in ("comment",):
            continue
        out.append(c)
    return out


def inside(lang: str, file: str, src: bytes, start: int, end: int, kind: str) -> dict:
    """Children of one block one level down, plus 'next' edges between siblings."""
    tree = parse_bytes(lang, src)
    root = tree.root_node
    blocks: list[dict] = []

    if kind in ("function", "method", "component", "definition"):
        node = _find_node(root, start, end)
        if node is None:
            return {"blocks": [], "edges": []}
        body = _def_body(node)
        stmts = _statements(body) if body is not None and body.type in ("block", "statement_block") else []
        if not stmts and body is not None:  # arrow function with expression body
            blocks.append(_block(file, src, body, LEVEL_EXPRESSION, "expression", _label(src, body),
                                 has_children=bool(body.named_children)))
        else:
            n_lines = src.count(b"\n", start, end) + 1
            n_control = sum(1 for s in stmts if s.type in CONTROL)
            comments = [c for c in body.named_children if c.type == "comment"] if body is not None else []
            if n_lines > SECTION_MIN_LINES or n_control > SECTION_MIN_CONTROL:
                for i, (a, b, header) in enumerate(_sections(src, stmts, comments)):
                    s0, s1 = stmts[a], stmts[b]
                    label = header or f"Section {i + 1}"
                    blocks.append(_block(
                        file, src, s0, LEVEL_SECTION, "section", label,
                        start=s0.start_byte, end=s1.end_byte,
                        extra={"named_by": "comment" if header else "placeholder", "statements": b - a + 1},
                    ))
            else:
                for s in stmts:
                    blocks.append(_block(file, src, s, LEVEL_STATEMENT, "statement", _label(src, s),
                                         has_children=_is_compound(s) or bool(_expr_children(s))))
    elif kind == "section":
        node = _find_node(root, start, end)
        # the section's statements are the body children within the range
        container = node
        while container is not None and container.type not in ("block", "statement_block"):
            container = container.parent
        if container is None:
            return {"blocks": [], "edges": []}
        for s in _statements(container):
            if s.start_byte >= start and s.end_byte <= end:
                blocks.append(_block(file, src, s, LEVEL_STATEMENT, "statement", _label(src, s),
                                     has_children=_is_compound(s) or bool(_expr_children(s))))
    elif kind == "statement":
        node = _find_node(root, start, end)
        if node is None:
            return {"blocks": [], "edges": []}
        if _is_compound(node):
            for s in _children_of_statement(node):
                blocks.append(_block(file, src, s, LEVEL_STATEMENT, "statement", _label(src, s),
                                     has_children=_is_compound(s) or bool(_expr_children(s))))
        if not blocks:
            for e in _expr_children(node):
                blocks.append(_block(file, src, e, LEVEL_EXPRESSION, "expression",
                                     f"{e.type.replace('_', ' ')} · {_label(src, e)}",
                                     has_children=bool(e.named_children)))
    elif kind == "expression":
        node = _find_node(root, start, end)
        if node is not None:
            for e in _expr_children(node):
                blocks.append(_block(file, src, e, LEVEL_EXPRESSION, "expression",
                                     f"{e.type.replace('_', ' ')} · {_label(src, e)}",
                                     has_children=bool(e.named_children)))

    edges = []
    if blocks and blocks[0]["kind"] in ("section", "statement"):
        edges = [{"source": a["id"], "target": b["id"], "kind": "next", "certainty": "sure", "count": 1}
                 for a, b in zip(blocks, blocks[1:])]
    return {"blocks": blocks, "edges": edges}
