"""Command-line interface for DocSync."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analyzer import analyze_drift, make_client
from .checks import (
    check_markdown_links,
    check_symbol_coverage,
    extract_documented_symbols,
    extract_symbols,
)
from .config import load_config
from .git import changed_files, diff_text, is_git_repo
from .matcher import filter_ignored, find_docs, heuristic_match
from .providers import list_llm_providers
from .report import build_report, write_report
from .vcs import list_vcs_providers


def cmd_init(args) -> int:
    path = Path(".docsync.yml")
    if path.exists() and not args.force:
        print(".docsync.yml already exists; use --force to overwrite", file=sys.stderr)
        return 1
    path.write_text(
        "docs_paths:\n  - docs\n  - README.md\n  - CHANGELOG.md\n"
        "ignore:\n  - '*.lock'\n  - node_modules\n  - .git\n"
        "threshold: 0.0\n",
        encoding="utf-8",
    )
    print("Created .docsync.yml")
    return 0


def cmd_review(args) -> int:
    repo = Path(args.repo).resolve()
    if not is_git_repo(repo):
        print(f"Not a git repository: {repo}", file=sys.stderr)
        return 2
    config = load_config(args.config)
    base = args.base
    head = args.head

    changed = changed_files(base, head, cwd=str(repo))
    changed_paths = [f.path for f in changed if f.status != "deleted"]
    changed_paths = filter_ignored(changed_paths, config.ignore)

    docs = find_docs(repo, config.docs_paths)
    docs = filter_ignored(docs, config.ignore)

    affected: dict[str, list[str]] = {}
    candidate_docs: dict[str, str] = {}
    for src in changed_paths:
        matches = heuristic_match(src, docs)
        if matches:
            affected[src] = matches
            for d in matches:
                full = repo / d
                if full.exists() and d not in candidate_docs:
                    try:
                        candidate_docs[d] = full.read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        pass

    diff = diff_text(base, head, cwd=str(repo))
    spec = None
    if args.spec:
        try:
            spec = Path(args.spec).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"Could not read spec: {exc}", file=sys.stderr)
    client = make_client(config)
    analysis = analyze_drift(client, config, changed_paths, diff, candidate_docs, spec=spec)

    report = build_report(changed_paths, affected, analysis)
    out = Path(args.output)
    write_report(out, report)
    print(f"Report written to {out}")
    print(f"Changed files: {len(changed_paths)}, affected docs: {len({d for v in affected.values() for d in v})}")

    if args.fail_on_drift and affected:
        return 1
    return 0


def cmd_providers(args) -> int:
    print("LLM providers:", ", ".join(list_llm_providers()))
    print("VCS providers:", ", ".join(list_vcs_providers()))
    return 0


def cmd_check(args) -> int:
    root = Path(args.repo).resolve()
    # symbol coverage for python files
    code_syms: set[str] = set()
    for py in root.rglob("*.py"):
        rel = py.relative_to(root)
        if any(part.startswith(".") or part in {"node_modules", "legacy"} for part in rel.parts):
            continue
        if ".venv" in str(py) or "site-packages" in str(py):
            continue
        code_syms |= extract_symbols(py)
    doc_syms: set[str] = set()
    for md in root.rglob("*.md"):
        if ".venv" in str(md) or "site-packages" in str(md):
            continue
        doc_syms |= extract_documented_symbols(md.read_text(encoding="utf-8", errors="ignore"))
    cov = check_symbol_coverage(code_syms, doc_syms)

    broken_links: list[dict[str, str]] = []
    for md in root.rglob("*.md"):
        if ".venv" in str(md) or "site-packages" in str(md):
            continue
        broken_links.extend(check_markdown_links(md, root))

    print(f"Symbol coverage: {cov['covered']}/{cov['total']} ({cov['coverage']*100:.1f}%)")
    if cov["undocumented"]:
        print("Undocumented:", ", ".join(cov["undocumented"][:20]))
    if cov["stale_references"]:
        print("Stale refs:", ", ".join(cov["stale_references"][:20]))
    print(f"Broken links: {len(broken_links)}")
    for b in broken_links[:20]:
        print(f"  {b['file']}: {b['link']}")

    if args.fail_on_issues and (cov["undocumented"] or broken_links):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="docsync", description="Keep docs in sync with code.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="Validate doc/code consistency and links")
    p_check.add_argument("--repo", default=".", help="Repository path")
    p_check.add_argument("--fail-on-issues", action="store_true")
    p_check.set_defaults(func=cmd_check)

    p_prov = sub.add_parser("providers", help="List supported providers")
    p_prov.set_defaults(func=cmd_providers)

    p_init = sub.add_parser("init", help="Create a default .docsync.yml")
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_review = sub.add_parser("review", help="Analyze a PR/diff for documentation drift")
    p_review.add_argument("--repo", default=".", help="Repository path")
    p_review.add_argument("--base", default="origin/main", help="Base ref")
    p_review.add_argument("--head", default="HEAD", help="Head ref")
    p_review.add_argument("--config", default=None, help="Config file path")
    p_review.add_argument("--output", default="docsync-report.md", help="Output report path")
    p_review.add_argument("--fail-on-drift", action="store_true", help="Exit non-zero if drift detected")
    p_review.add_argument("--spec", default=None, help="Path to a spec/ticket file for gap analysis")
    p_review.set_defaults(func=cmd_review)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
