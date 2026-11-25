from pathlib import Path

import pytest

from araknid.engine import build_graph
from araknid.model import block_id

FIX = Path(__file__).parent / "fixtures" / "site"


@pytest.fixture(scope="module")
def g():
    return build_graph(FIX, "p_site", "site")


def edge(g, src, dst, kind):
    s, d = block_id(src), block_id(dst)
    return next((e for e in g.edges if e.source == s and e.target == d and e.kind == kind), None)


def test_iife_functions_are_found(g):
    names = {b.code_name for b in g.blocks.values() if b.file == "src/app.js" and b.level == 4}
    assert {"loadItems", "api", "save"} <= names


def test_fetch_links_to_file_route(g):
    e = edge(g, "src/app.js/loadItems", "api/items.py", "requests")
    assert e is not None and e.certainty == "sure"
    assert g.blocks[block_id("api/items.py")].route == "/api/items"


def test_helper_call_links_to_dynamic_route(g):
    assert edge(g, "src/app.js/save", "api/items/[id].py", "requests") is not None


def test_page_loads_scripts_and_styles(g):
    assert "page" in g.blocks[block_id("index.html")].tags
    assert edge(g, "index.html", "src/app.js", "loads") is not None
    assert edge(g, "index.html", "styles.css", "loads") is not None


def test_build_copy_folder_is_hidden(g):
    assert not any(b.path.startswith("public/") for b in g.blocks.values())


def test_summaries(g):
    assert g.blocks[block_id("service.py")].summary == "Shared logic for the site's API."
    assert g.blocks[block_id("service.py")].summary_by == "author"
    assert g.blocks[block_id("src/app.js/loadItems")].summary == "Ask the server for every item."
    s = g.blocks[block_id("src/app.js/save")].summary
    assert s.startswith("Sends requests to /api/items/[id]")
