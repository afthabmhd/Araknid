"""The unified block data model.

Every block, from a whole system down to one expression, is the same kind of
record with a parent. The web is a tree of blocks (nesting) plus a graph of
edges between them (imports, calls, inherits, instantiates).

See "Data model for nested blocks" in the requirements doc.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Literal, Optional

# Bump when the serialized graph format changes in an incompatible way.
SCHEMA_VERSION = 1

# Level numbers from the doc. Level 0 (project) is an addition: it is the
# single root that holds every level 1 System block, so the tree has one root.
LEVEL_PROJECT = 0
LEVEL_SYSTEM = 1
LEVEL_MODULE = 2
LEVEL_FILE = 3
LEVEL_DEFINITION = 4
LEVEL_SECTION = 5
LEVEL_STATEMENT = 6
LEVEL_EXPRESSION = 7

BlockKind = Literal[
    "project",
    "system",
    "module",
    "suggested_group",
    "file",
    "asset",  # non-code file, shown as an opaque file block
    "class",
    "function",
    "method",
    "component",
    "type",
    "section",
    "statement",
    "expression",
]

EdgeKind = Literal["imports", "calls", "inherits", "instantiates", "renders", "next"]
Certainty = Literal["sure", "maybe"]
Origin = Literal["extracted", "inferred", "user"]


def block_id(path: str) -> str:
    """Stable id derived from the block's path.

    Phase one: the id survives re-imports as long as the path does not change.
    Matching renamed or moved blocks by shape_hash comes with the incremental
    updater.
    """
    return "blk_" + hashlib.sha1(path.encode("utf-8")).hexdigest()[:12]


def text_hash(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()[:16]


@dataclass
class Block:
    id: str
    parent_id: Optional[str]
    path: str
    level: int
    kind: BlockKind
    code_name: str
    # Plain-language title. AI-written later; None until then. The client
    # shows a title derived from code_name meanwhile and marks it as such.
    human_name: Optional[str] = None
    language: Optional[str] = None
    file: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    start_byte: Optional[int] = None
    end_byte: Optional[int] = None
    loc: int = 0
    content_hash: Optional[str] = None
    shape_hash: Optional[str] = None
    arch_node_id: Optional[str] = None
    build_state: Literal["built", "partial", "not_built"] = "built"
    pinned: bool = False
    status: Literal["synced", "changed", "needs_review", "unplanned"] = "synced"
    # Extras used by the map.
    params: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)  # route, entry, exported, test, hub, ...
    is_test: bool = False
    importance: float = 0.0
    health: Optional[str] = None  # e.g. "parse_errors", "few_blocks"
    children: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Edge:
    source: str
    target: str
    kind: EdgeKind
    certainty: Certainty = "sure"
    origin: Origin = "extracted"
    count: int = 1

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.source, self.target, self.kind)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Graph:
    project_id: str
    name: str
    root_id: str
    blocks: dict[str, Block] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    def add(self, block: Block) -> Block:
        self.blocks[block.id] = block
        if block.parent_id and block.parent_id in self.blocks:
            self.blocks[block.parent_id].children.append(block.id)
        return block

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "name": self.name,
            "root_id": self.root_id,
            "blocks": [b.to_dict() for b in self.blocks.values()],
            "edges": [e.to_dict() for e in self.edges],
            "stats": self.stats,
        }
