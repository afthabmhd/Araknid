"""Parser: turn one source file into definitions, imports and call sites.

Deterministic, no AI. Uses tree-sitter grammars for Python, JavaScript,
TypeScript and TSX. The tree is walked by hand rather than with queries so the
same code works across tree-sitter binding versions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

import tree_sitter_javascript as ts_js
import tree_sitter_python as ts_py
import tree_sitter_typescript as ts_ts
from tree_sitter import Language, Node, Parser

from .model import text_hash


@lru_cache(maxsize=None)
def get_language(lang: str) -> Language:
    if lang == "python":
        return Language(ts_py.language())
    if lang == "javascript":
        return Language(ts_js.language())
    if lang == "typescript":
        return Language(ts_ts.language_typescript())
    if lang == "tsx":
        return Language(ts_ts.language_tsx())
    raise ValueError(f"unsupported language {lang}")


def parse_bytes(lang: str, src: bytes):
    return Parser(get_language(lang)).parse(src)


# ---------------------------------------------------------------- data


@dataclass
class CallSite:
    name: str  # the called name: `f` in f(), `m` in obj.m()
    receiver: Optional[str] = None  # `obj` in obj.m(); "self"/"this" for own methods
    kind: str = "calls"  # calls | instantiates | renders


@dataclass
class Definition:
    name: str
    kind: str  # class | function | method | component | type
    node: Node
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    params: list[str] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    calls: list[CallSite] = field(default_factory=list)
    children: list["Definition"] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    is_stub: bool = False
    shape_hash: str = ""


@dataclass
class ImportBinding:
    """One local name made available by an import."""

    local: Optional[str]  # local name, None for side-effect imports
    source: str  # module specifier as written ("./x", "a.b", ".models")
    symbol: Optional[str]  # imported symbol; None means the whole module/namespace
    level: int = 0  # Python relative import dots
    certainty: str = "sure"
    reexport: bool = False


@dataclass
class FileParse:
    language: str
    definitions: list[Definition] = field(default_factory=list)
    imports: list[ImportBinding] = field(default_factory=list)
    top_calls: list[CallSite] = field(default_factory=list)
    exports: dict[str, str] = field(default_factory=dict)  # exported name -> local name; "default" too
    has_error: bool = False
    is_entry: bool = False
    line_count: int = 0


def _text(node: Optional[Node]) -> str:
    return node.text.decode("utf-8", errors="replace") if node is not None and node.text else ""


def shape_of(node: Node) -> str:
    """Hash of the syntax tree's node types, without names or literals."""
    parts: list[str] = []
    stack = [node]
    while stack:
        n = stack.pop()
        if n.is_named:
            parts.append(n.type)
        stack.extend(reversed(n.children))
    return text_hash(" ".join(parts).encode())


# ---------------------------------------------------------------- python

PY_COMPOUND = {
    "if_statement", "for_statement", "while_statement", "try_statement",
    "with_statement", "match_statement",
}
ROUTE_DECORATOR_HINTS = (".get", ".post", ".put", ".patch", ".delete", ".route", ".websocket", ".api_route")


def _py_params(params: Optional[Node]) -> list[str]:
    out: list[str] = []
    if params is None:
        return out
    for c in params.named_children:
        if c.type == "identifier":
            out.append(_text(c))
        else:
            ident = c.child_by_field_name("name") or next(
                (x for x in c.named_children if x.type == "identifier"), None
            )
            if ident is not None:
                prefix = "*" if c.type == "list_splat_pattern" else "**" if c.type == "dictionary_splat_pattern" else ""
                out.append(prefix + _text(ident))
    return [p for p in out if p not in ("self", "cls")]


def _py_is_stub(body: Optional[Node]) -> bool:
    if body is None:
        return False
    stmts = [c for c in body.named_children if c.type not in ("comment",)]
    # A docstring alone, pass, ..., or raise NotImplementedError
    stmts = [s for s in stmts if not (s.type == "expression_statement" and s.named_children and s.named_children[0].type == "string")]
    if not stmts:
        return True
    if len(stmts) == 1:
        s = stmts[0]
        t = _text(s).strip()
        if s.type == "pass_statement" or t == "...":
            return True
        if s.type == "raise_statement" and "NotImplementedError" in t:
            return True
    return False


def _py_collect_calls(node: Node, out: list[CallSite]) -> None:
    """Collect call sites under node, without entering nested definitions."""
    stack = list(node.children)
    while stack:
        n = stack.pop()
        if n.type in ("function_definition", "class_definition", "decorated_definition"):
            continue
        if n.type == "call":
            fn = n.child_by_field_name("function")
            if fn is not None:
                if fn.type == "identifier":
                    name = _text(fn)
                    kind = "instantiates" if name[:1].isupper() else "calls"
                    out.append(CallSite(name=name, kind=kind))
                elif fn.type == "attribute":
                    obj = fn.child_by_field_name("object")
                    attr = fn.child_by_field_name("attribute")
                    recv = _text(obj) if obj is not None and obj.type == "identifier" else None
                    name = _text(attr)
                    kind = "instantiates" if name[:1].isupper() else "calls"
                    out.append(CallSite(name=name, receiver=recv or "?", kind=kind))
        stack.extend(n.children)


def _py_defs(node: Node, in_class: bool, out: list[Definition]) -> None:
    for child in node.children:
        target = child
        decorators: list[str] = []
        if child.type == "decorated_definition":
            decorators = [_text(d) for d in child.named_children if d.type == "decorator"]
            target = child.child_by_field_name("definition") or child.named_children[-1]
        if target.type in ("function_definition", "class_definition"):
            span = child  # include decorators
            name = _text(target.child_by_field_name("name"))
            body = target.child_by_field_name("body")
            if target.type == "class_definition":
                d = Definition(
                    name=name, kind="class", node=span,
                    start_line=span.start_point[0] + 1, end_line=span.end_point[0] + 1,
                    start_byte=span.start_byte, end_byte=span.end_byte,
                )
                sup = target.child_by_field_name("superclasses")
                if sup is not None:
                    for b in sup.named_children:
                        if b.type in ("identifier", "attribute"):
                            d.bases.append(_text(b).split(".")[-1])
                if body is not None:
                    _py_defs(body, True, d.children)
                    _py_collect_calls_top(body, d.calls)
            else:
                d = Definition(
                    name=name, kind="method" if in_class else "function", node=span,
                    start_line=span.start_point[0] + 1, end_line=span.end_point[0] + 1,
                    start_byte=span.start_byte, end_byte=span.end_byte,
                    params=_py_params(target.child_by_field_name("parameters")),
                )
                d.is_stub = _py_is_stub(body)
                if body is not None:
                    _py_collect_calls(body, d.calls)
                    _py_defs_nested(body, d.children)
            for dec in decorators:
                if any(h in dec for h in ROUTE_DECORATOR_HINTS) or dec.startswith("@app.") or dec.startswith("@router."):
                    if "route" not in d.tags:
                        d.tags.append("route")
                if "property" in dec:
                    d.tags.append("property")
            d.shape_hash = shape_of(target)
            out.append(d)
        elif child.type in PY_COMPOUND or child.type in ("block", "else_clause", "elif_clause", "except_clause", "finally_clause"):
            # definitions inside top-level if/try blocks (e.g. conditional imports/defs)
            _py_defs(child, in_class, out)


def _py_defs_nested(body: Node, out: list[Definition]) -> None:
    """Nested functions and classes inside a function body."""
    _py_defs(body, False, out)


def _py_collect_calls_top(class_body: Node, out: list[CallSite]) -> None:
    """Calls in a class body outside its methods (class attributes)."""
    for c in class_body.children:
        if c.type in ("function_definition", "decorated_definition", "class_definition"):
            continue
        _py_collect_calls(c, out)


def parse_python(src: bytes) -> FileParse:
    tree = parse_bytes("python", src)
    root = tree.root_node
    fp = FileParse(language="python", has_error=root.has_error, line_count=src.count(b"\n") + 1)
    _py_defs(root, False, fp.definitions)
    for n in root.children:
        if n.type == "import_statement":
            for c in n.named_children:
                if c.type == "dotted_name":
                    mod = _text(c)
                    fp.imports.append(ImportBinding(local=mod.split(".")[0], source=mod, symbol=None))
                    # also bind the full dotted path for attribute calls like a.b.f()
                elif c.type == "aliased_import":
                    mod = _text(c.child_by_field_name("name"))
                    alias = _text(c.child_by_field_name("alias"))
                    fp.imports.append(ImportBinding(local=alias, source=mod, symbol=None))
        elif n.type == "import_from_statement":
            modnode = n.child_by_field_name("module_name")
            level = 0
            mod = ""
            if modnode is not None:
                if modnode.type == "relative_import":
                    prefix = next((x for x in modnode.children if x.type == "import_prefix"), None)
                    level = len(_text(prefix)) if prefix is not None else 0
                    dn = next((x for x in modnode.named_children if x.type == "dotted_name"), None)
                    mod = _text(dn)
                else:
                    mod = _text(modnode)
            names = [c for c in n.named_children if c is not modnode]
            if any(c.type == "wildcard_import" for c in n.children):
                fp.imports.append(ImportBinding(local=None, source=mod, symbol="*", level=level, certainty="maybe"))
                continue
            for c in names:
                if c.type == "dotted_name":
                    sym = _text(c)
                    fp.imports.append(ImportBinding(local=sym.split(".")[-1], source=mod, symbol=sym, level=level))
                elif c.type == "aliased_import":
                    sym = _text(c.child_by_field_name("name"))
                    alias = _text(c.child_by_field_name("alias"))
                    fp.imports.append(ImportBinding(local=alias, source=mod, symbol=sym, level=level))
        elif n.type == "if_statement":
            cond = _text(n.child_by_field_name("condition"))
            if "__name__" in cond and "__main__" in cond:
                fp.is_entry = True
    # module level calls (outside definitions)
    for n in root.children:
        if n.type in ("function_definition", "class_definition", "decorated_definition", "import_statement", "import_from_statement"):
            continue
        _py_collect_calls(n, fp.top_calls)
    return fp


# ---------------------------------------------------------------- js / ts

JS_FUNC_VALUES = {"arrow_function", "function_expression", "function", "generator_function"}
JS_CLASS_DECL = {"class_declaration", "abstract_class_declaration"}
JS_TYPE_DECL = {"interface_declaration", "type_alias_declaration", "enum_declaration"}


def _js_params(params: Optional[Node]) -> list[str]:
    out: list[str] = []
    if params is None:
        return out
    if params.type == "identifier":  # x => ...
        return [_text(params)]
    for c in params.named_children:
        if c.type == "identifier":
            out.append(_text(c))
        elif c.type in ("required_parameter", "optional_parameter"):
            pat = c.child_by_field_name("pattern")
            out.append(_text(pat) if pat is not None and pat.type == "identifier" else "{…}")
        elif c.type == "assignment_pattern":
            left = c.child_by_field_name("left")
            out.append(_text(left) if left is not None and left.type == "identifier" else "{…}")
        elif c.type == "rest_pattern":
            out.append("..." + _text(c.named_children[0]) if c.named_children else "...")
        elif c.type in ("object_pattern", "array_pattern"):
            out.append("{…}" if c.type == "object_pattern" else "[…]")
    return out


def _contains_jsx(node: Node) -> bool:
    stack = [node]
    while stack:
        n = stack.pop()
        if n.type in ("jsx_element", "jsx_self_closing_element", "jsx_fragment"):
            return True
        if n is not node and n.type in ("function_declaration", "class_declaration"):
            continue
        stack.extend(n.children)
    return False


def _js_is_stub(body: Optional[Node]) -> bool:
    if body is None or body.type != "statement_block":
        return False
    stmts = [c for c in body.named_children if c.type != "comment"]
    if not stmts:
        return True
    if len(stmts) == 1 and stmts[0].type == "throw_statement" and "not implemented" in _text(stmts[0]).lower():
        return True
    return False


def _js_collect_calls(node: Node, out: list[CallSite]) -> None:
    # Start at the node itself: an arrow function body can be a bare call.
    stack = [node] if node.type not in ("statement_block", "program") else list(node.children)
    while stack:
        n = stack.pop()
        if n.type in ("function_declaration", "class_declaration", "method_definition", "generator_function_declaration"):
            continue
        if n.type == "variable_declarator":
            v = n.child_by_field_name("value")
            if v is not None and v.type in JS_FUNC_VALUES:
                # named nested function: its calls belong to its own block
                continue
        if n.type == "call_expression":
            fn = n.child_by_field_name("function")
            if fn is not None:
                if fn.type == "identifier":
                    out.append(CallSite(name=_text(fn)))
                elif fn.type == "member_expression":
                    obj = fn.child_by_field_name("object")
                    prop = fn.child_by_field_name("property")
                    recv = "?"
                    if obj is not None:
                        if obj.type == "this":
                            recv = "this"
                        elif obj.type == "identifier":
                            recv = _text(obj)
                    out.append(CallSite(name=_text(prop), receiver=recv))
        elif n.type == "new_expression":
            ctor = n.child_by_field_name("constructor")
            if ctor is not None and ctor.type == "identifier":
                out.append(CallSite(name=_text(ctor), kind="instantiates"))
            elif ctor is not None and ctor.type == "member_expression":
                obj = ctor.child_by_field_name("object")
                out.append(CallSite(name=_text(ctor.child_by_field_name("property")),
                                    receiver=_text(obj) if obj is not None and obj.type == "identifier" else "?",
                                    kind="instantiates"))
        elif n.type in ("jsx_opening_element", "jsx_self_closing_element"):
            nm = n.child_by_field_name("name")
            if nm is not None:
                t = _text(nm)
                if t[:1].isupper():
                    if "." in t:
                        recv, _, prop = t.rpartition(".")
                        out.append(CallSite(name=prop, receiver=recv, kind="renders"))
                    else:
                        out.append(CallSite(name=t, kind="renders"))
        stack.extend(n.children)


def _js_make_func(name: str, span: Node, fn: Node, in_class: bool, out: list[Definition], tags: list[str]) -> None:
    body = fn.child_by_field_name("body")
    params = fn.child_by_field_name("parameters") or fn.child_by_field_name("parameter")
    kind = "method" if in_class else "function"
    if not in_class and name[:1].isupper() and _contains_jsx(fn):
        kind = "component"
    d = Definition(
        name=name, kind=kind, node=span,
        start_line=span.start_point[0] + 1, end_line=span.end_point[0] + 1,
        start_byte=span.start_byte, end_byte=span.end_byte,
        params=_js_params(params), tags=list(tags),
    )
    d.is_stub = _js_is_stub(body)
    if body is not None:
        _js_collect_calls(body, d.calls)
        if body.type == "statement_block":
            _js_defs(body, False, d.children, [])
    d.shape_hash = shape_of(fn)
    out.append(d)


def _js_defs(node: Node, in_class: bool, out: list[Definition], tags: list[str], fp: Optional[FileParse] = None) -> None:
    for child in node.children:
        t = child.type
        if t == "export_statement":
            decl = child.child_by_field_name("declaration")
            is_default = any(c.type == "default" for c in child.children)
            etags = tags + ["exported"]
            if decl is not None:
                before = len(out)
                _js_defs_one(decl, child, in_class, out, etags)
                if fp is not None:
                    for d in out[before:]:
                        fp.exports["default" if is_default else d.name] = d.name
            else:
                value = child.child_by_field_name("value")
                if is_default and value is not None:
                    if value.type == "identifier" and fp is not None:
                        fp.exports["default"] = _text(value)
                    elif value.type in JS_FUNC_VALUES or value.type in ("class",):
                        if value.type == "class":
                            continue
                        _js_make_func("default", child, value, False, out, etags)
                        if fp is not None:
                            fp.exports["default"] = "default"
                # export { a as b }
                if fp is not None:
                    for c in child.named_children:
                        if c.type == "export_clause":
                            for spec in c.named_children:
                                if spec.type == "export_specifier":
                                    nm = _text(spec.child_by_field_name("name"))
                                    al = spec.child_by_field_name("alias")
                                    fp.exports[_text(al) if al is not None else nm] = nm
            continue
        _js_defs_one(child, child, in_class, out, tags)


def _js_defs_one(decl: Node, span: Node, in_class: bool, out: list[Definition], tags: list[str]) -> None:
    t = decl.type
    if t in ("function_declaration", "generator_function_declaration"):
        _js_make_func(_text(decl.child_by_field_name("name")), span, decl, in_class, out, tags)
    elif t in JS_CLASS_DECL:
        name = _text(decl.child_by_field_name("name"))
        d = Definition(
            name=name, kind="class", node=span,
            start_line=span.start_point[0] + 1, end_line=span.end_point[0] + 1,
            start_byte=span.start_byte, end_byte=span.end_byte, tags=list(tags),
        )
        heritage = next((c for c in decl.named_children if c.type == "class_heritage"), None)
        if heritage is not None:
            for c in heritage.named_children:
                if c.type == "extends_clause":
                    v = c.child_by_field_name("value") or (c.named_children[0] if c.named_children else None)
                    if v is not None:
                        d.bases.append(_text(v).split(".")[-1].split("<")[0])
                elif c.type in ("identifier", "member_expression"):  # javascript grammar
                    d.bases.append(_text(c).split(".")[-1])
        body = decl.child_by_field_name("body")
        if body is not None:
            for m in body.named_children:
                if m.type == "method_definition":
                    mname = _text(m.child_by_field_name("name"))
                    _js_make_func(mname, m, m, True, d.children, [])
                elif m.type in ("public_field_definition", "field_definition"):
                    v = m.child_by_field_name("value")
                    nm = m.child_by_field_name("name") or m.child_by_field_name("property")
                    if v is not None and v.type in JS_FUNC_VALUES and nm is not None:
                        _js_make_func(_text(nm), m, v, True, d.children, [])
        if any(c.kind == "method" and c.name == "render" for c in d.children) or _contains_jsx(decl):
            if any(b in ("Component", "PureComponent") for b in d.bases):
                d.kind = "component"
        d.shape_hash = shape_of(decl)
        out.append(d)
    elif t in ("lexical_declaration", "variable_declaration"):
        declarators = [c for c in decl.named_children if c.type == "variable_declarator"]
        for vd in declarators:
            name_node = vd.child_by_field_name("name")
            value = vd.child_by_field_name("value")
            if name_node is None or value is None or name_node.type != "identifier":
                continue
            # unwrap memo(...)/forwardRef(...)/styled wrappers: memo(() => ...)
            inner = value
            if value.type == "call_expression":
                args = value.child_by_field_name("arguments")
                if args is not None and args.named_children and args.named_children[0].type in JS_FUNC_VALUES:
                    inner = args.named_children[0]
            if inner.type in JS_FUNC_VALUES:
                use_span = span if len(declarators) == 1 else vd
                _js_make_func(_text(name_node), use_span, inner, in_class, out, tags)
            elif inner.type == "class":
                d = Definition(
                    name=_text(name_node), kind="class", node=span,
                    start_line=span.start_point[0] + 1, end_line=span.end_point[0] + 1,
                    start_byte=span.start_byte, end_byte=span.end_byte, tags=list(tags),
                )
                d.shape_hash = shape_of(inner)
                out.append(d)
    elif t in JS_TYPE_DECL:
        name = _text(decl.child_by_field_name("name"))
        d = Definition(
            name=name, kind="type", node=span,
            start_line=span.start_point[0] + 1, end_line=span.end_point[0] + 1,
            start_byte=span.start_byte, end_byte=span.end_byte, tags=list(tags),
        )
        d.shape_hash = shape_of(decl)
        out.append(d)


def _string_value(node: Optional[Node]) -> Optional[str]:
    if node is None:
        return None
    if node.type == "string":
        frag = next((c for c in node.named_children if c.type == "string_fragment"), None)
        return _text(frag) if frag is not None else ""
    if node.type == "template_string" and not any(c.type == "template_substitution" for c in node.named_children):
        return _text(node)[1:-1]
    return None


def parse_js(src: bytes, lang: str) -> FileParse:
    tree = parse_bytes(lang, src)
    root = tree.root_node
    fp = FileParse(language=lang, has_error=root.has_error, line_count=src.count(b"\n") + 1)
    _js_defs(root, False, fp.definitions, [], fp)
    for n in root.children:
        if n.type == "import_statement":
            source = _string_value(n.child_by_field_name("source"))
            if source is None:
                continue
            clause = next((c for c in n.named_children if c.type == "import_clause"), None)
            if clause is None:
                fp.imports.append(ImportBinding(local=None, source=source, symbol=None))
                continue
            for c in clause.named_children:
                if c.type == "identifier":
                    fp.imports.append(ImportBinding(local=_text(c), source=source, symbol="default"))
                elif c.type == "namespace_import":
                    ident = next((x for x in c.named_children if x.type == "identifier"), None)
                    fp.imports.append(ImportBinding(local=_text(ident), source=source, symbol=None))
                elif c.type == "named_imports":
                    for spec in c.named_children:
                        if spec.type == "import_specifier":
                            nm = _text(spec.child_by_field_name("name"))
                            al = spec.child_by_field_name("alias")
                            fp.imports.append(ImportBinding(local=_text(al) if al is not None else nm, source=source, symbol=nm))
        elif n.type == "export_statement":
            source = _string_value(n.child_by_field_name("source"))
            if source is not None:
                clause = next((c for c in n.named_children if c.type == "export_clause"), None)
                if clause is None:
                    fp.imports.append(ImportBinding(local=None, source=source, symbol="*", reexport=True))
                else:
                    for spec in clause.named_children:
                        if spec.type == "export_specifier":
                            nm = _text(spec.child_by_field_name("name"))
                            al = spec.child_by_field_name("alias")
                            local = _text(al) if al is not None else nm
                            fp.imports.append(ImportBinding(local=local, source=source, symbol=nm, reexport=True))
                            fp.exports[local] = local
    # require() and dynamic import() anywhere in the file
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type == "call_expression":
            fn = n.child_by_field_name("function")
            args = n.child_by_field_name("arguments")
            if fn is not None and args is not None and args.named_children:
                spec = _string_value(args.named_children[0])
                if spec is not None and (fn.type == "import" or _text(fn) == "require"):
                    local = None
                    parent = n.parent
                    if parent is not None and parent.type == "variable_declarator":
                        nm = parent.child_by_field_name("name")
                        if nm is not None and nm.type == "identifier":
                            local = _text(nm)
                    fp.imports.append(ImportBinding(
                        local=local, source=spec, symbol=None,
                        certainty="sure" if _text(fn) == "require" else "maybe",
                    ))
        stack.extend(n.children)
    for n in root.children:
        if n.type in ("function_declaration", "class_declaration", "import_statement", "export_statement",
                      "lexical_declaration", "variable_declaration", "interface_declaration", "type_alias_declaration"):
            if n.type in ("lexical_declaration", "variable_declaration"):
                # calls in initialisers of non-function constants
                for vd in n.named_children:
                    v = vd.child_by_field_name("value") if vd.type == "variable_declarator" else None
                    if v is not None and v.type not in JS_FUNC_VALUES:
                        _js_collect_calls(vd, fp.top_calls)
            continue
        _js_collect_calls(n, fp.top_calls)
    return fp


def parse_file(lang: str, src: bytes) -> FileParse:
    if lang == "python":
        return parse_python(src)
    return parse_js(src, lang)
