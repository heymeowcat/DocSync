"""Shared pytest fixtures."""

from __future__ import annotations

import os
import tempfile

import pytest


@pytest.fixture
def tmp_project(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "utils.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "__init__.py").write_text("", encoding="utf-8")
    (sub / "mod.py").write_text("VALUE = 42\n", encoding="utf-8")
    return tmp_path
