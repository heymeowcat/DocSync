# TecDocAuto

AI-powered **Low-Level Design (LLD) document generator** for codebases.

TecDocAuto scans a project, summarizes each selected file with an LLM, and
produces a structured LLD document (Markdown, with optional DOCX/HTML/JSON
export) covering project overview, architecture, detailed design, data design,
interfaces, algorithms, and testing.

## Features

- **Local project scanning** - browse and select files from any local directory.
- **GitHub / GitLab integration** - connect a remote repository and pick files.
- **Prompt library** - 60+ reusable analysis prompts (architecture, quality,
  performance, security, learning, ...).
- **Multiple output formats** - Markdown, DOCX, HTML, JSON.
- **Git history awareness** - commit history is fed to the model for context.
- **Web UI + REST API** - FastAPI backend with a browser interface.

## Quick start

### Prerequisites

- Python 3.10+
- [Pandoc](https://pandoc.org/) (for DOCX export)
- An [OpenRouter](https://openrouter.ai/) API key (or any OpenAI-compatible endpoint)

### Install

```bash
git clone https://github.com/heymeowcat/TecDocAuto.git
cd TecDocAuto
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# edit .env and set OPENROUTER_API_KEY
```

### Run

```bash
tecdocauto
# or
uvicorn main:app --reload
```

Open <http://localhost:8000>.

### Run tests

```bash
pytest
```

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Description |
| --- | --- |
| `OPENROUTER_API_KEY` | LLM provider API key |
| `OPENROUTER_MODEL` | Model id (default free model) |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | GitHub OAuth (optional) |
| `GITHUB_ACCESS_TOKEN` | GitHub personal access token (optional) |
| `GITLAB_ACCESS_TOKEN` | GitLab personal access token (optional) |
| `JWT_SECRET` | Secret for signing auth cookies |

## Project layout

```
.
├── main.py              # FastAPI app + CLI entrypoint
├── config.py            # Pydantic settings
├── utils.py             # Scanning, generation, export logic
├── routes/              # API routers
├── integrations/        # VCS (GitHub/GitLab) integration
├── templates/           # Jinja2/HTML templates
├── static/              # Static assets
├── prompt_library/      # Reusable LLM prompts
├── tests/               # pytest suite
└── pyproject.toml
```

## API

- `POST /scan_project` - scan a local directory, returns file tree + prompts.
- `POST /generate_lld` - generate an LLD document.
- `GET /health` - health check.
- `GET /download/{path}` - download a generated file.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and PRs are welcome.

## License

[MIT](LICENSE)
