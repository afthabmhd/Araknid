"""Resolver: link imports and calls across files.

Rules:
- Imports are resolved to files: Python dotted names against every package
  root in the repo; JS/TS relative paths with extension and index lookup,
  plus tsconfig/jsconfig `paths` aliases.
- Calls are resolved through the file's own definitions and its import
  bindings. A call on an unknown receiver (`obj.save()`) is linked only when
  the method name is unique in the repo, and then it is marked "maybe".
- Bare package imports (`react`, `requests`) are external. They belong to the
  Dependencies store, which comes later.
"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Optional

from .parsers import CallSite, FileParse, ImportBinding

JS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
# Method names too common to link by name alone.
COMMON_NAMES = {
    "get", "set", "add", "put", "post", "delete", "remove", "update", "push", "pop", "map", "filter",
    "reduce", "find", "forEach", "keys", "values", "items", "append", "extend", "join", "split", "format",
    "then", "catch", "finally", "run", "start", "stop", "close", "open", "read", "write", "send", "emit",
    "on", "off", "call", "apply", "bind", "toString", "init", "__init__", "render", "load", "save", "parse",
    "copy", "clear", "has", "includes", "indexOf", "slice", "splice", "replace", "strip", "lower", "upper",
    "log", "error", "warn", "info", "debug", "next", "resolve", "reject", "use", "create", "execute", "handle",
    "process", "validate", "length", "size", "name", "id", "type", "value", "data", "fetch", "json", "test",
}


def _strip_json_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(^|[^:\"'])//[^\n]*", r"\1", text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return text


class Resolver:
    def __init__(
        self,
        root: Path,
        code_files: list[str],
        systems: list[str],
        parses: dict[str, FileParse],
        defs_by_file: dict[str, dict[str, str]],
    ):
        self.root = root
        self.files = set(code_files)
        self.parses = parses
        self.defs_by_file = defs_by_file
        self._bindings: dict[str, dict[str, tuple[Optional[str], Optional[str], str]]] = {}
        self._py_index: dict[str, list[str]] = {}
        self._build_py_index()
        self.systems = systems
        self._aliases = self._load_ts_aliases(systems)
        # unique top-level/method names across the repo -> block id
        name_count: dict[str, list[str]] = {}
        for rel, defs in defs_by_file.items():
            for qual, bid in defs.items():
                short = qual.split(".")[-1].split("#")[0]
                name_count.setdefault(short, []).append(bid)
        self._unique = {n: ids[0] for n, ids in name_count.items() if len(ids) == 1}

    # ------------------------------------------------------------ python

    def _build_py_index(self) -> None:
        for rel in self.files:
            if not rel.endswith((".py", ".pyi")):
                continue
            p = PurePosixPath(rel)
            parts = list(p.with_suffix("").parts)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            # every suffix of the path is a candidate dotted name (covers src/ layouts)
            for i in range(len(parts)):
                dotted = ".".join(parts[i:])
                if dotted:
                    self._py_index.setdefault(dotted, []).append(rel)

    def _py_lookup(self, dotted: str, from_rel: str) -> Optional[str]:
        cands = self._py_index.get(dotted)
        if not cands:
            return None
        if len(cands) == 1:
            return cands[0]
        # prefer the candidate whose package root is closest to the importer
        def score(c: str) -> tuple[int, int]:
            common = 0
            for a, b in zip(PurePosixPath(c).parts, PurePosixPath(from_rel).parts):
                if a != b:
                    break
                common += 1
            return (-common, len(c))
        return sorted(cands, key=score)[0]

    def _py_package_of(self, rel: str, level: int) -> str:
        p = PurePosixPath(rel)
        pkg = p.parent
        for _ in range(level - 1):
            pkg = pkg.parent
        return "" if str(pkg) == "." else str(pkg)

    def _py_resolve(self, from_rel: str, imp: ImportBinding) -> tuple[Optional[str], Optional[str]]:
        """Return (file, symbol) for a Python import binding."""
        if imp.level:
            base = self._py_package_of(from_rel, imp.level)
            mod_path = "/".join(x for x in [base, imp.source.replace(".", "/") if imp.source else ""] if x)
            if imp.symbol and imp.symbol != "*":
                sub = f"{mod_path}/{imp.symbol.replace('.', '/')}" if mod_path else imp.symbol.replace(".", "/")
                for cand in (sub + ".py", sub + "/__init__.py"):
                    if cand in self.files:
                        return cand, None
            for cand in (mod_path + ".py", mod_path + "/__init__.py", (mod_path + "/__init__.py").lstrip("/")):
                if cand in self.files:
                    return cand, imp.symbol if imp.symbol != "*" else None
            return None, None
        if imp.symbol and imp.symbol != "*":
            f = self._py_lookup(f"{imp.source}.{imp.symbol}", from_rel)
            if f:
                return f, None
            f = self._py_lookup(imp.source, from_rel)
            return (f, imp.symbol) if f else (None, None)
        # import a.b.c  -> bound as `a`; resolve the deepest file we know
        parts = imp.source.split(".")
        for i in range(len(parts), 0, -1):
            f = self._py_lookup(".".join(parts[:i]), from_rel)
            if f:
                return f, None
        return None, None

    # ------------------------------------------------------------ js / ts

    def _load_ts_aliases(self, systems: list[str]) -> list[tuple[str, str, str]]:
        """(system dir, alias prefix, target dir) from tsconfig/jsconfig paths."""
        out: list[tuple[str, str, str]] = []
        for s in systems:
            for name in ("tsconfig.json", "jsconfig.json", "tsconfig.base.json", "tsconfig.app.json"):
                cfg = self.root / s / name if s else self.root / name
                if not cfg.is_file():
                    continue
                try:
                    data = json.loads(_strip_json_comments(cfg.read_text(encoding="utf-8")))
                except Exception:
                    continue
                co = data.get("compilerOptions") or {}
                base = co.get("baseUrl", ".")
                for alias, targets in (co.get("paths") or {}).items():
                    if not targets:
                        continue
                    a = alias.rstrip("*")
                    t = str(PurePosixPath(s or ".") / base / targets[0].rstrip("*"))
                    t = t.lstrip("./") if t.startswith("./") else t
                    out.append((s, a, t.rstrip("/")))
        return out

    def _js_file(self, base: str) -> Optional[str]:
        base = str(PurePosixPath(base))
        if base.startswith("./"):
            base = base[2:]
        cands = [base]
        stem, ext = (base.rsplit(".", 1) + [""])[:2] if "." in PurePosixPath(base).name else (base, "")
        if ext in ("js", "jsx", "mjs", "cjs"):
            cands += [stem + e for e in (".ts", ".tsx")]  # TS ESM imports with .js extension
        cands += [base + e for e in JS_EXTS] + [f"{base}/index{e}" for e in JS_EXTS]
        for c in cands:
            if c in self.files:
                return c
        return None

    def _norm(self, path: str) -> str:
        parts: list[str] = []
        for p in path.split("/"):
            if p in ("", "."):
                continue
            if p == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(p)
        return "/".join(parts)

    def _js_resolve_spec(self, from_rel: str, spec: str) -> tuple[Optional[str], str]:
        if spec.startswith("."):
            d = str(PurePosixPath(from_rel).parent)
            d = "" if d == "." else d
            return self._js_file(self._norm(f"{d}/{spec}")), "sure"
        for _sys, alias, target in self._aliases:
            if alias and spec.startswith(alias):
                return self._js_file(self._norm(f"{target}/{spec[len(alias):]}")), "sure"
        if spec.startswith("@/") or spec.startswith("~/"):
            # common convention without tsconfig: guess src/
            sysdir = next((s for s in sorted(self.systems, key=len, reverse=True)
                           if not s or from_rel.startswith(s + "/")), "")
            f = self._js_file(self._norm(f"{sysdir}/src/{spec[2:]}"))
            return f, "maybe"
        return None, "sure"  # external package

    # ------------------------------------------------------------ public

    def resolve_module(self, from_rel: str, imp: ImportBinding) -> Optional[str]:
        if from_rel.endswith((".py", ".pyi")):
            return self._py_resolve(from_rel, imp)[0]
        return self._js_resolve_spec(from_rel, imp.source)[0]

    def bindings_for(self, rel: str) -> dict[str, tuple[Optional[str], Optional[str], str]]:
        """local name -> (file, symbol or None for namespace, certainty)."""
        if rel in self._bindings:
            return self._bindings[rel]
        out: dict[str, tuple[Optional[str], Optional[str], str]] = {}
        fp = self.parses.get(rel)
        if fp:
            for imp in fp.imports:
                if not imp.local:
                    continue
                if fp.language == "python":
                    f, sym = self._py_resolve(rel, imp)
                    cert = imp.certainty
                else:
                    f, cert = self._js_resolve_spec(rel, imp.source)
                    sym = imp.symbol
                    cert = "maybe" if imp.certainty == "maybe" else cert
                if f:
                    out[imp.local] = (f, sym, cert)
        self._bindings[rel] = out
        return out

    def _def_in_file(self, rel: str, name: str, depth: int = 0) -> Optional[str]:
        """Find a top-level definition `name` in a file, following re-exports."""
        defs = self.defs_by_file.get(rel, {})
        fp = self.parses.get(rel)
        if fp and name in fp.exports:
            local = fp.exports[name]
            if local in defs:
                return defs[local]
            name = local
        if name in defs:
            return defs[name]
        if depth > 3 or not fp:
            return None
        # re-exports and barrel files: export { x } from './x', export * from './y'
        b = self.bindings_for(rel)
        if name in b and b[name][0]:
            f, sym, _ = b[name]
            return self._def_in_file(f, sym or name, depth + 1) if f else None
        for imp in fp.imports:
            if imp.reexport and imp.symbol == "*":
                f, _ = self._js_resolve_spec(rel, imp.source)
                if f:
                    hit = self._def_in_file(f, name, depth + 1)
                    if hit:
                        return hit
        if name == "default" and fp:
            tops = [k for k in defs if "." not in k]
            if len(tops) == 1:
                return defs[tops[0]]
        return None

    def resolve_name(self, rel: str, name: str, bindings) -> tuple[Optional[str], str]:
        defs = self.defs_by_file.get(rel, {})
        if name in defs:
            return defs[name], "sure"
        if name in bindings:
            f, sym, cert = bindings[name]
            if f is None:
                return None, cert
            if sym is None:
                return None, cert  # namespace: the call name decides
            hit = self._def_in_file(f, sym)
            return (hit, cert) if hit else (None, cert)
        return None, "sure"

    def resolve_call(self, rel: str, call: CallSite, bindings, class_id: Optional[str]) -> tuple[Optional[str], str]:
        if call.receiver is None:
            return self.resolve_name(rel, call.name, bindings)
        defs = self.defs_by_file.get(rel, {})
        if call.receiver in ("self", "this", "cls") and class_id:
            # own method: find a method with this name in the enclosing class
            for qual, bid in defs.items():
                if bid == class_id:
                    cand = defs.get(f"{qual}.{call.name}")
                    if cand:
                        return cand, "sure"
            hit = self._unique.get(call.name)
            if hit and call.name not in COMMON_NAMES:
                return hit, "maybe"  # probably inherited
            return None, "sure"
        if call.receiver in bindings:
            f, sym, cert = bindings[call.receiver]
            if f and sym is None:  # namespace / module import: mod.f()
                hit = self._def_in_file(f, call.name)
                if hit:
                    return hit, cert
            elif f and sym:  # imported class: Cls.static()
                cls = self._def_in_file(f, sym)
                if cls:
                    fdefs = self.defs_by_file.get(f, {})
                    for qual, bid in fdefs.items():
                        if bid == cls and f"{qual}.{call.name}" in fdefs:
                            return fdefs[f"{qual}.{call.name}"], cert
        if call.receiver in defs:  # local class: Cls.method()
            cand = defs.get(f"{call.receiver}.{call.name}")
            if cand:
                return cand, "sure"
        hit = self._unique.get(call.name)
        if hit and call.name not in COMMON_NAMES and len(call.name) > 3:
            return hit, "maybe"
        return None, "sure"
