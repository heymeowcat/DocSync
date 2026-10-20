# Usage

## `docsync init`

Creates a `.docsync.yml` in the current directory.

## `docsync review`

Analyzes the diff between `--base` and `--head`.

Options:
- `--repo` repository path (default `.`)
- `--base` base ref (default `origin/main`)
- `--head` head ref (default `HEAD`)
- `--config` config file path
- `--output` report path (default `docsync-report.md`)
- `--fail-on-drift` exit non-zero when drift is detected
