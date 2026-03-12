# DocSync

**Keep documentation in sync with code.** DocSync is a CI-native tool that
analyzes pull requests, detects documentation drift, and proposes updates.

## Why

Documentation rots the moment code changes. DocSync runs on every PR, maps
changed source files to affected docs, and posts a reviewable report (or opens a
draft PR with suggested edits). No more "docs updated in a follow-up."

## Quick start

```bash
pip install -e .
docsync init          # creates .docsync.yml
docsync review --base origin/main --head HEAD --output docsync-report.md
```

## GitHub Action

```yaml
- uses: actions/checkout@v4
  with: { fetch-depth: 0 }
- run: pip install -e .
- run: docsync review --base origin/${{ github.base_ref }} --head HEAD --output docsync-report.md --fail-on-drift
```

See `.github/workflows/docsync.yml`.

## Configuration (`.docsync.yml`)

```yaml
docs_paths:
  - docs
  - README.md
  - CHANGELOG.md
ignore:
  - '*.lock'
  - node_modules
threshold: 0.0
```

Set `OPENROUTER_API_KEY` for LLM-powered analysis; otherwise DocSync falls back
to heuristic matching.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
```

## License

MIT
