"""Tests for core utility functions."""

from __future__ import annotations

import os

from utils import (
    count_tokens,
    format_prompt_name,
    get_directory_tree,
    load_prompts_from_library,
    should_ignore,
)


def test_get_directory_tree_relative_paths(tmp_project):
    tree = get_directory_tree(str(tmp_project))
    files = [n for n in tree if n["type"] == "file"]
    assert any(n["name"] == "main.py" for n in files)
    for node in tree:
        if node["type"] == "file":
            assert not os.path.isabs(node["path"])


def test_should_ignore_pycache(tmp_project):
    patterns = {"__pycache__", "*.pyc"}
    assert should_ignore(str(tmp_project / "__pycache__"), str(tmp_project), patterns)


def test_count_tokens_nonempty():
    assert count_tokens("hello world") > 0
    assert count_tokens("") == 0


def test_format_prompt_name():
    assert (
        format_prompt_name("architecture_layer_identification.md")
        == "Architecture Layer Identification"
    )


def test_load_prompts_returns_dict():
    prompts = load_prompts_from_library()
    assert isinstance(prompts, dict)
