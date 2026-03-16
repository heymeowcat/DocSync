"""LLM-based analysis for DocSync."""

from __future__ import annotations

import logging
from typing import Any

from .providers import create_llm_client

logger = logging.getLogger(__name__)


def make_client(config) -> Any:
    """Create an LLM client based on config.provider."""
    return create_llm_client(config)


def analyze_drift(client, config, changed_files: list[str], diff: str, candidate_docs: dict[str, str], spec: str | None = None) -> str:
    """Ask the LLM which docs are affected and what should change."""
    if client is None:
        return _heuristic_report(changed_files, candidate_docs)

    docs_block = "\n\n".join(
        f"### {path}\n{content[:4000]}" for path, content in candidate_docs.items()
    )
    spec_block = ("Specification/ticket:\n" + spec + "\n\n") if spec else ""
    prompt = (
        "You are a documentation maintainer. Given a code diff and candidate "
        "documentation files, identify which docs are stale or need updates, "
        "and propose concrete edits.\n\n"
        + spec_block
        + "Changed files:\n" + "\n".join(f"- {p}" for p in changed_files) + "\n\n"
        + "Diff:\n```diff\n" + diff[:12000] + "\n```\n\n"
        + "Candidate docs:\n" + docs_block + "\n\n"
        + "Respond in Markdown with sections: 'Affected docs', 'Suggested updates', "
        + "'Risk level (low/medium/high)'."
    )
    try:
        response = client.chat.completions.create(
            model=config.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM analysis failed: %s", exc)
        return _heuristic_report(changed_files, candidate_docs)


def _heuristic_report(changed_files: list[str], candidate_docs: dict[str, str]) -> str:
    lines = ["## Affected docs", ""]
    if candidate_docs:
        for path in candidate_docs:
            lines.append(f"- `{path}` (heuristic match)")
    else:
        lines.append("- (none detected)")
    lines += ["", "## Suggested updates", ""]
    lines.append("Review the changed files and update the matched documentation accordingly.")
    lines += ["", "## Risk level", "", "medium (heuristic, no LLM)"]
    lines += ["", "### Changed files", ""]
    for p in changed_files:
        lines.append(f"- `{p}`")
    return "\n".join(lines)
