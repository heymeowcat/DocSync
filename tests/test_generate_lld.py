"""Tests for LLD generation (LLM calls mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _mock_client():
    mock = MagicMock()
    mock.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Generated content."))
    ]
    return mock


def test_generate_lld(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")

    with patch("utils.client", _mock_client()):
        r = client.post(
            "/generate_lld",
            json={
                "project_path": str(tmp_path),
                "selected_files": ["a.py"],
                "enabled_prompts": {"generate_lld_document": True},
                "output_format": "markdown",
            },
        )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "markdown_output" in data
    assert "Project Summary" in data["markdown_output"]
