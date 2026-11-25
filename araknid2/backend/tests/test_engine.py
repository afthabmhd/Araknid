from pathlib import Path

import pytest

from araknid.engine import build_graph
from araknid.inside import inside
from araknid.model import block_id

FIX = Path(__file__).parent / "fixtures" / "mixed"


@pytest.fixture(scope="module")
def g():
    return build_graph(FIX, "p_test", "mixed")


def by_path(g, path):
    return g.blocks[block_id(path)]


def edge(g, src, dst, kind):
    s, d = block_id(src), block_id(dst)
    return next((e for e in g.edges if e.source == s and e.target == d and e.kind == kind), None)


def test_systems_from_manifests(g):
    systems = sorted(b.code_name for b in g.blocks.values() if b.kind == "system")
    assert systems == ["billing-api", "billing-web"]


def test_tree_has_one_parent_and_levels(g):
    for b in g.blocks.values():
        if b.parent_id:
            assert b.id in g.blocks[b.parent_id].children
            assert g.blocks[b.parent_id].level <= b.level


def test_python_definitions(g):
    cls = by_path(g, "api/app/services/payments.py/PaymentService")
    assert cls.kind == "class"
    m = by_path(g, "api/app/services/payments.py/PaymentService.charge_card")
    assert m.kind == "method" and m.parent_id == cls.id and m.params == ["amount"]
    assert "route" in by_path(g, "api/app/main.py/charge").tags
    assert by_path(g, "api/app/services/payments.py/refund").build_state == "partial"
    assert "entry" in by_path(g, "api/app/main.py").tags


def test_python_edges(g):
    assert edge(g, "api/app/main.py", "api/app/services/payments.py", "imports")
    assert edge(g, "api/app/main.py/charge", "api/app/services/payments.py/PaymentService", "instantiates")
    assert edge(g, "api/app/main.py/do_refund", "api/app/services/payments.py/refund", "calls")
    assert edge(g, "api/app/services/payments.py/PaymentService.charge_card",
                "api/app/services/payments.py/PaymentService.validate", "calls").certainty == "sure"
    assert edge(g, "api/app/services/payments.py/PaymentService", "api/app/services/payments.py/Base", "inherits")


def test_js_definitions_and_edges(g):
    assert by_path(g, "web/src/App.tsx/App").kind == "component"
    assert by_path(g, "web/src/components/Button.tsx/Button").kind == "component"
    assert by_path(g, "web/src/lib/api.ts/Charge").kind == "type"
    assert edge(g, "web/src/main.tsx", "web/src/App.tsx/App", "renders")
    assert edge(g, "web/src/App.tsx/App", "web/src/components/Button.tsx/Button", "renders")  # default import
    assert edge(g, "web/src/App.tsx/App.onClick", "web/src/lib/api.ts/charge", "calls")  # namespace import, nested arrow fn
    assert edge(g, "web/src/App.tsx", "web/src/lib/api.ts", "imports")
    assert by_path(g, "web/src/lib/render.ts/render").build_state == "partial"


def test_ids_are_stable(g):
    g2 = build_graph(FIX, "p_other", "mixed")
    assert set(g.blocks) == set(g2.blocks)


def test_inside_levels():
    src = (FIX / "api/app/services/payments.py").read_bytes()
    g = build_graph(FIX, "p", "m")
    b = by_path(g, "api/app/services/payments.py/PaymentService.validate")
    res = inside("python", b.file, src, b.start_byte, b.end_byte, "method")
    assert [x["kind"] for x in res["blocks"]] == ["statement"]
    stmt = res["blocks"][0]
    res2 = inside("python", b.file, src, stmt["start_byte"], stmt["end_byte"], "statement")
    assert res2["blocks"] and "raise" in res2["blocks"][0]["code"]


def test_files_outside_units_get_root_system(tmp_path):
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "package.json").write_text('{"name": "w"}')
    (tmp_path / "web" / "a.js").write_text("export function a() {}")
    (tmp_path / "tool.py").write_text("def t():\n    pass\n")
    g = build_graph(tmp_path, "p", "repo")
    assert sorted(b.path for b in g.blocks.values() if b.kind == "system") == [".", "web"]
