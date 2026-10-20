"""Map changed source files to documentation files."""

from __future__ import annotations

import fnmatch
from pathlib import Path


def find_docs(root: str | Path, docs_paths: list[str]) -> list[str]:
    """Collect documentation file paths under the configured docs paths."""
    root = Path(root)
    result: list[str] = []
    for entry in docs_paths:
        p = root / entry
        if p.is_file():
            result.append(str(p.relative_to(root)))
        elif p.is_dir():
            for child in p.rglob("*"):
                if child.is_file() and child.suffix.lower() in {".md", ".rst", ".adoc", ".txt"}:
                    result.append(str(child.relative_to(root)))
    return sorted(set(result))


def heuristic_match(changed: str, docs: list[str]) -> list[str]:
    """Heuristically match a changed source file to documentation files."""
    matches: list[str] = []
    stem = Path(changed).stem.lower()
    parent = Path(changed).parent.name.lower()
    for doc in docs:
        low = doc.lower()
        if stem and stem in low:
            matches.append(doc)
            continue
        if parent and parent not in {"", "."} and parent in low:
            matches.append(doc)
    # Always consider top-level README as potentially affected.
    for doc in docs:
        if doc.lower().endswith("readme.md"):
            if doc not in matches:
                matches.append(doc)
    return matches


def filter_ignored(paths: list[str], ignore: list[str]) -> list[str]:
    out = []
    for p in paths:
        if any(fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(Path(p).name, pat) for pat in ignore):
            continue
        out.append(p)
    return out
