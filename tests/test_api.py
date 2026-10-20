"""API-level tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_scan_project(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    r = client.post("/scan_project", json={"project_path": str(tmp_path)})
    assert r.status_code == 200
    data = r.json()
    assert "tree" in data
    assert "prompts" in data
