// Mirrors araknid/model.py (the unified block data model).

export type BlockKind =
  | "project" | "system" | "module" | "suggested_group" | "file" | "asset"
  | "class" | "function" | "method" | "component" | "type"
  | "section" | "statement" | "expression";

export type EdgeKind = "imports" | "calls" | "inherits" | "instantiates" | "renders" | "requests" | "loads" | "next";

export interface Block {
  id: string;
  parent_id: string | null;
  path: string;
  level: number;
  kind: BlockKind;
  code_name: string;
  human_name: string | null;
  summary?: string | null;
  summary_by?: "author" | "rules" | "ai" | null;
  route?: string | null;
  language: string | null;
  file: string | null;
  start_line: number | null;
  end_line: number | null;
  start_byte: number | null;
  end_byte: number | null;
  loc: number;
  content_hash: string | null;
  shape_hash: string | null;
  build_state: "built" | "partial" | "not_built";
  pinned: boolean;
  status: string;
  params: string[];
  tags: string[];
  is_test: boolean;
  importance: number;
  health: string | null;
  children: string[];
}

export interface Edge {
  source: string;
  target: string;
  kind: EdgeKind;
  certainty: "sure" | "maybe";
  origin: "extracted" | "inferred" | "user";
  count: number;
}

export interface GraphData {
  schema_version: number;
  project_id: string;
  name: string;
  root_id: string;
  blocks: Block[];
  edges: Edge[];
  stats: Record<string, unknown> & { lines?: number; files?: number; map_seconds?: number };
}

export interface Project {
  id: string;
  name: string;
  source: "local" | "github" | "upload";
  origin: string;
  root: string;
  created_at: number;
  mapped_at: number | null;
  stats: GraphData["stats"] | null;
}

/** A block from the inside levels (5 to 7), built on demand. */
export interface InsideBlock {
  id: string;
  level: number;
  kind: "definition" | "section" | "statement" | "expression";
  node_type: string;
  label: string;
  file: string;
  start_byte: number;
  end_byte: number;
  start_line: number;
  end_line: number;
  has_children: boolean;
  code: string;
  named_by?: "comment" | "placeholder";
  statements?: number;
}

export interface InsideResult {
  blocks: InsideBlock[];
  edges: { source: string; target: string; kind: "next" }[];
}
