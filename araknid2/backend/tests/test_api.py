from pathlib import Path

from fastapi.testclient import TestClient

FIX = Path(__file__).parent / "fixtures" / "mixed"


def test_import_graph_code_inside(tmp_path, monkeypatch):
    from araknid import api
    from araknid.store import Store

    monkeypatch.setattr(api, "store", Store(tmp_path))
    c = TestClient(api.app)
    p = c.post("/api/projects/local", json={"path": str(FIX)}).json()
    g = c.get(f"/api/projects/{p['id']}/graph").json()
    assert g["schema_version"] == 1 and len(g["blocks"]) > 10
    fn = next(b for b in g["blocks"] if b["path"].endswith("payments.py/PaymentService.validate"))
    code = c.get(f"/api/projects/{p['id']}/code", params={"file": fn["file"], "start_line": fn["start_line"], "end_line": fn["end_line"]}).json()
    assert code["code"].strip().startswith("def validate")
    ins = c.get(f"/api/projects/{p['id']}/inside", params={
        "file": fn["file"], "start_byte": fn["start_byte"], "end_byte": fn["end_byte"], "kind": "method"}).json()
    assert ins["blocks"]
    # path traversal is refused
    assert c.get(f"/api/projects/{p['id']}/code", params={"file": "../../etc/passwd"}).status_code == 404


def test_upload_strips_traversal(tmp_path, monkeypatch):
    from araknid import api
    from araknid.store import Store

    monkeypatch.setattr(api, "store", Store(tmp_path))
    c = TestClient(api.app)
    files = [("files", ("a.py", b"def a():\n    return 1\n")), ("files", ("b.py", b"x = 1\n"))]
    r = c.post("/api/projects/upload", data={"name": "up", "paths": ["repo/a.py", "repo/../../evil.py"]}, files=files)
    assert r.status_code == 200
    root = Path(r.json()["root"])
    assert (root / "a.py").is_file()
    assert not (tmp_path / "evil.py").exists()
