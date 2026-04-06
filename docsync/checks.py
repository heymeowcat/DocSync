"""Documentation/code consistency checks for DocSync."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any


def extract_python_symbols(path: str | Path) -> set[str]:
    """Return public function/class names defined in a Python file."""
    try:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                names.add(node.name)
    return names


def extract_documented_symbols(markdown: str) -> set[str]:
    """Extract symbol names referenced in a markdown document."""
    # backtick-quoted identifiers and fenced code definitions
    symbols: set[str] = set()
    for m in re.finditer(r"`([A-Za-z_][A-Za-z0-9_]*)`", markdown):
        symbols.add(m.group(1))
    for m in re.finditer(r"^\s*(?:def|class|async def)\s+([A-Za-z_][A-Za-z0-9_]*)", markdown, re.MULTILINE):
        symbols.add(m.group(1))
    return symbols


def check_symbol_coverage(code_symbols: set[str], doc_symbols: set[str]) -> dict[str, Any]:
    """Compare code-defined public symbols against documented ones."""
    undocumented = sorted(code_symbols - doc_symbols)
    stale = sorted(doc_symbols - code_symbols)
    total = len(code_symbols)
    covered = total - len(undocumented)
    coverage = (covered / total) if total else 1.0
    return {
        "total": total,
        "covered": covered,
        "coverage": round(coverage, 3),
        "undocumented": undocumented,
        "stale_references": stale,
    }


def check_markdown_links(path: str | Path, root: str | Path) -> list[dict[str, str]]:
    """Return broken relative links in a markdown file."""
    root = Path(root)
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    broken: list[dict[str, str]] = []
    for m in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", text):
        target = m.group(1).split("#")[0].strip()
        if not target or target.startswith("http") or target.startswith("mailto:"):
            continue
        resolved = (Path(path).parent / target).resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            continue
        if not resolved.exists():
            broken.append({"file": str(path), "link": target})
    return broken
