"""Report generation for DocSync."""

from __future__ import annotations

from pathlib import Path


def build_report(changed: list[str], affected: dict[str, list[str]], analysis: str) -> str:
    """Build a Markdown drift report."""
    lines = ["# DocSync report", "", "## Changed files", ""]
    for p in changed:
        lines.append(f"- `{p}`")
    lines += ["", "## Affected documentation", ""]
    if affected:
        for src, docs in affected.items():
            lines.append(f"### `{src}`")
            for d in docs:
                lines.append(f"- `{d}`")
            lines.append("")
    else:
        lines.append("_No documentation files matched._")
    lines += ["", "## Analysis", "", analysis, ""]
    return "\n".join(lines)


def write_report(path: str | Path, content: str) -> Path:
    p = Path(path)
    p.write_text(content, encoding="utf-8")
    return p
