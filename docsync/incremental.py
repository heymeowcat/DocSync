"""Incremental documentation regeneration."""

from __future__ import annotations

import re


def parse_sections(markdown: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, body) sections by H2/H3 headings."""
    lines = markdown.splitlines(keepends=True)
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_body: list[str] = []
    for line in lines:
        if re.match(r"^#{1,3}\s+", line):
            if current_heading or current_body:
                sections.append((current_heading, "".join(current_body)))
            current_heading = line.rstrip("\n")
            current_body = []
        else:
            current_body.append(line)
    if current_heading or current_body:
        sections.append((current_heading, "".join(current_body)))
    if not sections:
        sections = [("", markdown)]
    return sections


def reassemble(sections: list[tuple[str, str]]) -> str:
    out: list[str] = []
    for heading, body in sections:
        if heading:
            out.append(heading + "\n")
        out.append(body)
    return "".join(out)


def affected_section_indices(sections: list[tuple[str, str]], changed_files: list[str]) -> list[int]:
    """Heuristically determine which sections are affected by changed files."""
    stems = {f.split("/")[-1].split(".")[0].lower() for f in changed_files}
    affected: list[int] = []
    for i, (heading, body) in enumerate(sections):
        haystack = (heading + " " + body).lower()
        if any(stem and stem in haystack for stem in stems):
            affected.append(i)
    if not affected and sections:
        # Fall back to last section if nothing matched.
        affected = [len(sections) - 1]
    return affected


def regenerate_incremental(old: str, diff: str, changed_files: list[str], llm, cfg) -> str:
    """Regenerate only affected sections, preserving the rest."""
    sections = parse_sections(old)
    indices = affected_section_indices(sections, changed_files)
    if llm is None:
        return old
    new_sections = list(sections)
    for i in indices:
        heading, body = sections[i]
        prompt = (
            f"Rewrite the following documentation section to reflect the code changes. "
            f"Keep the same heading. Return only the section body.\n\n"
            f"Heading: {heading}\nCurrent body:\n{body}\n\nDiff:\n```diff\n{diff[:6000]}\n```\n"
        )
        try:
            resp = llm.chat.completions.create(model=cfg.model, messages=[{"role": "user", "content": prompt}])
            new_body = resp.choices[0].message.content.strip() + "\n"
            new_sections[i] = (heading, new_body)
        except Exception:  # noqa: BLE001
            pass
    return reassemble(new_sections)
