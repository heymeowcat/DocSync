"""DocSync GitHub App / SaaS entrypoint."""

from __future__ import annotations

import logging
import os

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from docsync.analyzer import analyze_drift, make_client
from docsync.config import load_config
from docsync.github_app import GitHubApp
from docsync.matcher import filter_ignored, heuristic_match
from docsync.report import build_report

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(title="DocSync", version="0.3.0")
REPORTS: list[dict] = []
gh_app = GitHubApp()


async def process_pull_request(payload: dict) -> None:
    pr = payload["pull_request"]
    repo_full = payload["repository"]["full_name"]
    installation_id = payload["installation"]["id"]
    base = pr["base"]["ref"]
    head_sha = pr["head"]["sha"]
    pr_number = pr["number"]

    try:
        client_gh = gh_app.client_for_installation(installation_id)
        repo = client_gh.get_repo(repo_full)

        # Clone is not available in webhook context; fetch changed files via API.
        # Use GitHub compare API to get changed file paths.
        comparison = repo.compare(base, head_sha)
        changed_paths = [f.filename for f in comparison.files if f.status != "removed"]
        cfg = load_config(None)
        changed_paths = filter_ignored(changed_paths, cfg.ignore)

        # Fetch docs content from the repo (default branch tree not full; best-effort).
        docs: list[str] = []
        try:
            contents = repo.get_contents("")
            docs = [c.path for c in (contents if isinstance(contents, list) else [contents]) if c.type == "file"]
        except Exception:  # noqa: BLE001
            docs = []

        affected: dict[str, list[str]] = {}
        candidate_docs: dict[str, str] = {}
        for src in changed_paths:
            matches = heuristic_match(src, docs)
            if matches:
                affected[src] = matches
                for d in matches:
                    if d not in candidate_docs:
                        try:
                            f = repo.get_contents(d, ref=head_sha)
                            candidate_docs[d] = base64_decode(f.content) if hasattr(f, "content") else ""
                        except Exception:  # noqa: BLE001
                            candidate_docs[d] = ""

        # Diff text via compare patch
        diff = "\n".join(f.patch or "" for f in comparison.files)

        llm = make_client(cfg)
        analysis = analyze_drift(llm, cfg, changed_paths, diff, candidate_docs)

        report = build_report(changed_paths, affected, analysis)

        # Post as PR comment
        repo.get_issue(pr_number).create_comment(report[:65000])
        conclusion = "success" if not affected else "neutral"
        gh_app.create_check_run(repo, head_sha, "DocSync", conclusion, report[:65000])
        REPORTS.insert(0, {"repo": repo_full, "pr": pr_number, "report": report[:5000]})
        REPORTS[:] = REPORTS[:50]
        logger.info("Posted DocSync report to %s#%s", repo_full, pr_number)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to process PR %s#%s: %s", repo_full, pr_number, exc)


def base64_decode(content: str) -> str:
    import base64

    try:
        return base64.b64decode(content).decode("utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return ""


@app.get("/health")
async def health():
    return {"status": "ok", "configured": gh_app.is_configured()}


@app.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
):
    body = await request.body()
    if gh_app.webhook_secret and not GitHubApp.verify_signature(gh_app.webhook_secret, body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")
    payload = await request.json()
    result = gh_app.handle_event(x_github_event, payload)
    if result.get("status") == "queued":
        background_tasks.add_task(process_pull_request, payload)
    return JSONResponse(result)


@app.get("/reports")
async def reports():
    return {"reports": REPORTS}

@app.get("/")
async def root():
    return {"name": "DocSync", "docs": "/docs", "reports": "/reports"}
