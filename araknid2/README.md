# Araknid 2.0

Araknid 2.0 turns a codebase into a web of nested blocks that you can read at any depth. This folder holds the new
version. Araknid v1 (the PyQt5 block editor for C) stays in the repo root, untouched.

This first slice is the **code web**: it covers the Phase 0 graph engine spike and the map part of Phase 1 in the requirements doc.

- Import a JavaScript, TypeScript or Python repo from GitHub, from a folder upload in the browser, or from a path on
  the machine running the server.
- Araknid's own graph engine maps it with tree-sitter into the unified block model: one record type with a parent,
  a level, hashes and line ranges, plus edges (imports, calls, instantiates, inherits, renders).
- The web client (React Flow + ELK) keeps the map simple with four rules, taken from Sourcetrail, CodeSee and
  research on compound graphs and edge compression:
  1. **One block at a time.** The canvas shows what is inside the block you're in, at the level the slider picks.
     Double-click a card to go inside, and use the breadcrumb to come back out.
  2. **At most one layer of frames.** Cards are grouped by the child of the current block they live in. Frames
     never nest.
  3. **Lines go around cards, never across them.** ELK lays each frame out by flow (users on the left, what they use
     on the right) and routes every line with right-angle bends; one line per pair of cards, with a count. Pointing at
     a card or frame lights its lines and fades the rest. Only a very busy level (over 160 lines) falls back to one
     summed line per pair of frames. Cards with no lines are packed in a small grid, and unrelated frames sit side by
     side.
  4. **Nothing is cut off.** A connection to code outside the current block is counted on an "outside" stub.
  **Trace** is the main way to explore: click any card to see it in the middle, what uses it on the left and what it uses on the right,
  grouped by file. Functions open into the inside levels 5 to 7 (sections, statements, expressions).

## Run it

Requirements: Python 3.11+, Node 20+, git.

```bash
# backend
cd araknid2/backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn araknid.api:app --port 8000

# web client (second terminal)
cd araknid2/web
npm install
npm run dev          # http://localhost:5173, proxies /api to :8000
```

For a single server, run `npm run build` in `web/`. The backend then serves `web/dist` at http://localhost:8000.

**Static demo** (no server, one pre-mapped repo, shareable as a link):

```bash
cd araknid2/backend && python -m araknid.demo /path/to/repo ../web/public/demo.json "repo name"
cd ../web && npm run build:demo     # output in web/dist-demo, serve it with any static host
```

Tests: `cd araknid2/backend && pytest`. Type check: `cd araknid2/web && npm run typecheck`.

Settings (environment variables):

| Variable | Default | Meaning |
| --- | --- | --- |
| `ARAKNID_DATA` | `backend/data` | Where projects, uploaded copies and `graph.json` files are kept |
| `ARAKNID_ALLOW_LOCAL` | `1` | Allow importing a folder by server path. Turn this off on any shared or online server |

## Layout

```
araknid2/
  backend/araknid/
    model.py     the unified block data model (Block, Edge, Graph, schema version)
    walker.py    finds files; hides generated and vendored code (.gitignore + built-in list)
    parsers.py   tree-sitter parser: definitions, imports, call sites, stubs, routes
    resolver.py  links imports and calls across files ("sure" or "maybe")
    engine.py    builds levels 0 to 4, edges, importance and hub exclusion, parse health
    inside.py    levels 5 to 7 on demand: sections, statements, expressions
    store.py     project store on disk (a stand-in for Postgres)
    api.py       FastAPI endpoints
  web/src/
    view.ts      display tree: slider, pass-through collapse, "+ N more", edge roll-up, ghost stubs
    levelview.ts what is on screen: cards, frames, summed links, outside stubs, trace
    canvasLayout.ts  ELK layered layout with routed lines, row packing of unrelated frames, trace columns
    ProjectView.tsx, nodes.tsx, Panel.tsx, ImportScreen.tsx
```

## How the doc's rules are applied

| Doc rule | Where |
| --- | --- |
| Level 1 systems come from manifests (`package.json`, `pyproject.toml`, Dockerfile, ...); files outside every unit go to a root unit | `engine._detect_systems` |
| One parent per block; ids are stable because they're derived from the path | `model.block_id` |
| Pass-through collapse (`src/` wrappers, a file holding one class) and skipping empty levels | `view.collapseChain` |
| A class is one card at level 4; open it to see its methods | `levelview.buildLevelView` |
| Importance = in-degree + entry points/routes + exported, with super-hubs left out of the ranking; the rest folds into "+ N more" | `engine.build_graph`, `levelview.buildLevelView` |
| Edges roll up to whatever is visible, with counts; edges leaving the current block show as outside stubs | `levelview.buildLevelView` |
| Tests stay beside the code and are hidden by default | `walker.is_test_path`, filters |
| Stub detection ("partially built") | `parsers._py_is_stub`, `_js_is_stub` |
| Parse-health check | `engine.build_graph` (`parse_errors`, `few_blocks`) |
| Sections: software finds the boundaries, and the developer's comment headers win | `inside._sections` |

## Guesses and gaps (to confirm)

- **[Guess]** At most 24 cards per frame and 16 frames before "+ N more". Over 160 lines on a level, lines are summed per frame.
- **[Guess]** "+ N more" folds after 30 children, sections start at 40 lines or more than 3 control structures, and a
  file counts as `few_blocks` when it has over 300 lines and no definitions.
- **[Guess]** Level 0 "project" is an extra root above the System blocks, so the tree has a single root.
- Block ids come from the path. Keeping ids across renames and moves by `shape_hash` comes with the incremental updater.
- The calls resolver is our own import resolution. It doesn't use Pyright or the TypeScript server yet. A call on an
  unknown object links only when the method name is unique in the repo, and that link is marked "maybe".
- The TypeScript grammar (tree-sitter-typescript 0.23) can't read a few newer TS constructs. Those files are flagged
  `parse errors` and are still mapped.
- Not in this slice: Leiden suggested groups for big folders, the comparison against Graphify on 10 repos (Phase 0
  gate), Explain and Instruct (they need the context engine and the user's AI key), the code drawer, Postgres,
  incremental updates, private repos.

Measured on this machine: fastapi/fastapi (137k lines, 1,237 code files) maps in about 2.3 s, and
full-stack-fastapi-template (14k lines) maps in 0.2 s.
