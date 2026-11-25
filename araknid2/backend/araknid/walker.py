"""Find the files in a repo that belong on the map.

Generated and vendored code is hidden using .gitignore plus a built-in list.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import pathspec

BUILTIN_IGNORED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "bower_components", "__pycache__",
    ".venv", "venv", "env", ".env", ".tox", ".nox", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "dist", "build", "out", ".next", ".nuxt", ".svelte-kit",
    ".turbo", ".cache", ".parcel-cache", "coverage", ".coverage", "htmlcov",
    "site-packages", ".idea", ".vscode", "target", ".eggs", ".yarn", ".pnpm-store",
    "vendor", "third_party",
}
BUILTIN_IGNORED_FILE_RE = re.compile(
    r"(\.min\.(js|css)$|\.map$|\.lock$|-lock\.json$|\.pyc$|\.d\.ts$|\.(png|jpe?g|gif|ico|svg|webp|woff2?|ttf|eot|mp4|mp3|zip|gz|pdf|exe|dll|so|dylib)$)",
    re.IGNORECASE,
)

CODE_EXTENSIONS = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "tsx",
}
# Non-code files shown as opaque file blocks.
ASSET_EXTENSIONS = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".sql", ".html", ".css",
    ".scss", ".md", ".txt", ".sh", ".env.example", ".graphql", ".prisma",
}
ASSET_NAMES = {"Dockerfile", "Makefile", "Procfile", "docker-compose.yml", "docker-compose.yaml"}

MAX_FILE_BYTES = 1_000_000


@dataclass
class FoundFile:
    rel: str  # posix relative path
    language: str | None  # None for assets
    size: int


def _load_gitignore(root: Path) -> pathspec.PathSpec | None:
    gi = root / ".gitignore"
    if not gi.is_file():
        return None
    try:
        lines = gi.read_text(encoding="utf-8", errors="replace").splitlines()
        return pathspec.PathSpec.from_lines("gitwildmatch", lines)
    except Exception:
        return None


def walk(root: Path) -> list[FoundFile]:
    root = root.resolve()
    spec = _load_gitignore(root)
    found: list[FoundFile] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        rel_dir = "" if rel_dir == "." else rel_dir
        keep = []
        for d in sorted(dirnames):
            if d in BUILTIN_IGNORED_DIRS or d.endswith(".egg-info"):
                continue
            rel = f"{rel_dir}/{d}" if rel_dir else d
            if spec and spec.match_file(rel + "/"):
                continue
            if os.path.islink(os.path.join(dirpath, d)):
                continue
            keep.append(d)
        dirnames[:] = keep
        for f in sorted(filenames):
            rel = f"{rel_dir}/{f}" if rel_dir else f
            if BUILTIN_IGNORED_FILE_RE.search(f):
                continue
            if spec and spec.match_file(rel):
                continue
            full = os.path.join(dirpath, f)
            if os.path.islink(full):
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size > MAX_FILE_BYTES:
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in CODE_EXTENSIONS:
                found.append(FoundFile(rel, CODE_EXTENSIONS[ext], size))
            elif ext in ASSET_EXTENSIONS or f in ASSET_NAMES:
                found.append(FoundFile(rel, None, size))
    return found


TEST_FILE_RE = re.compile(
    r"(^|/)(test_[^/]*\.py|[^/]*_test\.py|conftest\.py|[^/]*\.(test|spec)\.[jt]sx?)$"
)
TEST_DIR_RE = re.compile(r"(^|/)(tests?|__tests__|spec|e2e)/")


def is_test_path(rel: str) -> bool:
    return bool(TEST_FILE_RE.search(rel) or TEST_DIR_RE.search(rel))
