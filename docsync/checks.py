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


def extract_js_symbols(path: str | Path) -> set[str]:
    """Return exported function/class/const names from a JS/TS file (regex-based)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return set()
    names: set[str] = set()
    for m in re.finditer(r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][\w]*)", text):
        names.add(m.group(1))
    for m in re.finditer(r"(?:export\s+)?class\s+([A-Za-z_][\w]*)", text):
        names.add(m.group(1))
    for m in re.finditer(r"export\s+const\s+([A-Za-z_][\w]*)", text):
        names.add(m.group(1))
    for m in re.finditer(r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z_][\w]*)\s*=\s*(?:async\s*)?\(", text):
        names.add(m.group(1))
    return {n for n in names if not n.startswith("_")}


def extract_go_symbols(path: str | Path) -> set[str]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return set()
    names: set[str] = set()
    for m in re.finditer(r"^func\s+(?:\([^)]*\)\s+)?([A-Z][\w]*)", text, re.MULTILINE):
        names.add(m.group(1))
    for m in re.finditer(r"^type\s+([A-Z][\w]*)", text, re.MULTILINE):
        names.add(m.group(1))
    return names


def extract_rust_symbols(path: str | Path) -> set[str]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return set()
    names: set[str] = set()
    for m in re.finditer(r"pub\s+(?:async\s+)?fn\s+([A-Za-z_][\w]*)", text):
        names.add(m.group(1))
    for m in re.finditer(r"pub\s+struct\s+([A-Za-z_][\w]*)", text):
        names.add(m.group(1))
    for m in re.finditer(r"pub\s+enum\s+([A-Za-z_][\w]*)", text):
        names.add(m.group(1))
    for m in re.finditer(r"pub\s+trait\s+([A-Za-z_][\w]*)", text):
        names.add(m.group(1))
    return names


def extract_java_symbols(path: str | Path) -> set[str]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return set()
    names: set[str] = set()
    for m in re.finditer(r"(?:public|protected)\s+(?:static\s+)?(?:class|interface|enum)\s+([A-Za-z_][\w]*)", text):
        names.add(m.group(1))
    for m in re.finditer(r"(?:public|protected)\s+(?:static\s+)?[\w<>\[\], ?]+\s+([A-Za-z_][\w]*)\s*\(", text):
        names.add(m.group(1))
    return {n for n in names if n not in {"if", "for", "while", "switch", "catch"}}


def extract_symbols(path: str | Path) -> set[str]:
    """Dispatch symbol extraction by file extension."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".py":
        return extract_python_symbols(p)
    if ext in {".js", ".jsx", ".ts", ".tsx", ".mjs"}:
        return extract_js_symbols(p)
    if ext == ".go":
        return extract_go_symbols(p)
    if ext == ".rs":
        return extract_rust_symbols(p)
    if ext == ".java":
        return extract_java_symbols(p)
    return set()


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
