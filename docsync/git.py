"""Git helpers for DocSync."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ChangedFile:
    path: str
    status: str  # added/modified/deleted/renamed
    additions: int = 0
    deletions: int = 0


def _run(args: list[str], cwd: str | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def changed_files(base: str, head: str = "HEAD", cwd: str | None = None) -> list[ChangedFile]:
    """Return the list of files changed between base and head."""
    out = _run(["diff", "--name-status", f"{base}...{head}"], cwd=cwd)
    files: list[ChangedFile] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0][:1]
        path = parts[-1]
        label = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed"}.get(status, "modified")
        files.append(ChangedFile(path=path, status=label))
    return files


def diff_text(base: str, head: str = "HEAD", cwd: str | None = None, path: str | None = None) -> str:
    """Return the unified diff between base and head."""
    args = ["diff", f"{base}...{head}"]
    if path:
        args += ["--", path]
    return _run(args, cwd=cwd)


def is_git_repo(path: str | Path) -> bool:
    try:
        _run(["rev-parse", "--is-inside-work-tree"], cwd=str(path))
        return True
    except RuntimeError:
        return False
