# DocSync

**DocSync is a SaaS GitHub App that keeps documentation in sync with code.**

On every pull request, DocSync analyzes the diff, detects documentation drift,
and posts a reviewable report as a PR comment — optionally opening a draft PR
with suggested edits. No local installation required: install the GitHub App
and you're done.

## Features

- GitHub App webhook integration (no CI YAML needed)
- Diff-aware documentation drift detection
- Spec-vs-code gap analysis (`--spec`)
- Multi-provider LLM support (OpenAI, Anthropic, Gemini, Groq, Mistral,
  Ollama, OpenRouter, Together, Perplexity, Cohere, Azure OpenAI, Hugging Face)
- Multi-VCS support (GitHub, GitLab, Bitbucket, Gitea)
- Heuristic fallback when no LLM key is configured

## Self-hosting

```bash
cp .env.example .env
# fill in GITHUB_APP_ID, GITHUB_PRIVATE_KEY, GITHUB_WEBHOOK_SECRET, and an LLM key
docker compose up
```

Or run directly:

```bash
pip install -e .
uvicorn main:app --host 0.0.0.0 --port 8000
```

Point your GitHub App's webhook URL to `https://your-host/webhook`.

## Configuration

Environment variables (see `.env.example`):

- `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET`
- `OPENROUTER_API_KEY` (or any provider key)
- `DOCSYNC_PROVIDER`, `DOCSYNC_MODEL`

## Local CLI (for development)

```bash
docsync review --base origin/main --head HEAD --output report.md
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
```

## License

MIT
