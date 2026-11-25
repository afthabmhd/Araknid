"""Export one mapped repo as demo.json for the static demo build.

    python -m araknid.demo <repo folder> <out.json> [name]

The static web build (npm run build:demo) reads it instead of calling the
API. Inside levels are precomputed for every non-test function, so the demo
can drill down to expressions without a server.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from .engine import build_graph
from .inside import inside
from .walker import CODE_EXTENSIONS

MAX_DEPTH = 6


def export(root: Path, name: str) -> dict:
    g = build_graph(root, "demo", name).to_dict()
    files: dict[str, str] = {}
    for b in g["blocks"]:
        if b["kind"] in ("file", "asset") and b["file"]:
            files[b["file"]] = (root / b["file"]).read_text(encoding="utf-8", errors="replace")
    ins: dict[str, dict] = {}

    def walk(lang: str, file: str, src: bytes, a: int, z: int, kind: str, depth: int) -> None:
        key = f"{file}:{a}:{z}:{kind}"
        if key in ins or depth > MAX_DEPTH:
            return
        res = inside(lang, file, src, a, z, kind)
        for blk in res["blocks"]:
            blk.pop("code", None)  # the client slices it from files
        ins[key] = res
        for blk in res["blocks"]:
            if blk["has_children"]:
                walk(lang, file, src, blk["start_byte"], blk["end_byte"], blk["kind"], depth + 1)

    for b in g["blocks"]:
        if b["kind"] in ("function", "method", "component") and not b["is_test"]:
            lang = CODE_EXTENSIONS[os.path.splitext(b["file"])[1].lower()]
            walk(lang, b["file"], (root / b["file"]).read_bytes(), b["start_byte"], b["end_byte"], "definition", 0)

    project = {
        "id": "demo", "name": name, "source": "github", "origin": name, "root": "",
        "created_at": time.time(), "mapped_at": time.time(), "stats": g["stats"],
    }
    return {"project": project, "graph": g, "files": files, "inside": ins}


if __name__ == "__main__":
    root, out = Path(sys.argv[1]), Path(sys.argv[2])
    name = sys.argv[3] if len(sys.argv) > 3 else root.name
    data = export(root, name)
    out.write_text(json.dumps(data, separators=(",", ":")))
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB, {len(data['inside'])} inside entries)")
