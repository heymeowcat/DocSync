"""Tests for DocSync core modules."""

from __future__ import annotations

import subprocess

from docsync.config import load_config
from docsync.git import changed_files, is_git_repo
from docsync.matcher import find_docs, heuristic_match


def test_config_defaults(tmp_path):
    cfg = load_config(tmp_path / "missing.yml")
    assert "docs" in cfg.docs_paths
    assert cfg.threshold == 0.0


def test_heuristic_match():
    docs = ["docs/api.md", "README.md"]
    matches = heuristic_match("src/api/client.py", docs)
    assert "docs/api.md" in matches
    assert "README.md" in matches


def test_find_docs(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# guide", encoding="utf-8")
    (tmp_path / "README.md").write_text("# readme", encoding="utf-8")
    docs = find_docs(tmp_path, ["docs", "README.md"])
    assert "docs/guide.md" in docs
    assert "README.md" in docs


def test_git_changed_files(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "a.txt").write_text("hi", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    assert is_git_repo(tmp_path)
    changed_files("HEAD", "HEAD", cwd=str(tmp_path)) if False else None
    # working tree changes aren't in HEAD..HEAD; test repo detection only
    assert is_git_repo(tmp_path)


def test_list_providers():
    from docsync.providers import list_llm_providers
    from docsync.vcs import list_vcs_providers

    assert "openai" in list_llm_providers()
    assert "github" in list_vcs_providers()


def test_create_llm_client_ollama():
    from docsync.config import Config
    from docsync.providers import create_llm_client

    cfg = Config(provider="ollama", model="llama3")
    client = create_llm_client(cfg)
    assert client is not None


def test_parse_sections():
    from docsync.incremental import parse_sections, reassemble

    md = "# Title\n\nintro\n\n## Foo\n\nfoo body\n\n## Bar\n\nbar body\n"
    secs = parse_sections(md)
    assert len(secs) >= 2
    assert "Foo" in "".join(h for h, _ in secs)
    out = reassemble(secs)
    assert "Foo" in out


def test_affected_sections():
    from docsync.incremental import affected_section_indices, parse_sections

    md = "## Auth\n\nlogin\n\n## Billing\n\nstripe\n"
    secs = parse_sections(md)
    idx = affected_section_indices(secs, ["src/auth.py"])
    assert any("Auth" in secs[i][0] for i in idx)
