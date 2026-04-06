"""Link validation helpers."""

from __future__ import annotations

from pathlib import Path

from .checks import check_markdown_links


def check_all_links(root: str | Path) -> list[dict[str, str]]:
    root = Path(root)
    broken: list[dict[str, str]] = []
    for md in root.rglob("*.md"):
        broken.extend(check_markdown_links(md, root))
    return broken
