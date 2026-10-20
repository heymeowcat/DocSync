"""TecDocAuto application entrypoint."""

from __future__ import annotations

import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from github import Auth, Github, GithubException

from config import settings
from integrations.vcs import VCSIntegration
from routes import auth, dashboard, generate_lld, scan_project

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TecDocAuto",
    description="AI-powered Low-Level Design (LLD) document generator for codebases.",
    version="0.1.0",
)

vcs = VCSIntegration()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan_project.router)
app.include_router(generate_lld.router)
app.include_router(auth.router)
app.include_router(dashboard.router)


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/connect_github")
async def connect_github(repo_url: str):
    """Connect to a GitHub repository and fetch its top-level contents."""
    try:
        parts = repo_url.strip("/").split("/")
        if len(parts) < 2:
            raise HTTPException(status_code=400, detail="Invalid GitHub repository URL.")
        owner, repo_name = parts[-2], parts[-1]

        g = Github(auth=Auth.Token(settings.github_access_token))
        repo = g.get_repo(f"{owner}/{repo_name}")
        contents = repo.get_contents("")
        file_tree = build_github_file_tree(contents)
        return JSONResponse({"tree": file_tree, "prompts": {}})
    except GithubException as exc:
        raise HTTPException(status_code=400, detail=f"GitHub API error: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("connect_github failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/connect_repository")
async def connect_repository(request: Request):
    """Connect to a GitHub or GitLab repository."""
    try:
        data = await request.json()
        repo_url = data.get("repo_url")
        if not repo_url:
            raise HTTPException(status_code=400, detail="Repository URL is required")

        if "github.com" in repo_url:
            result = await vcs.connect_github(repo_url)
        elif "gitlab.com" in repo_url:
            result = await vcs.connect_gitlab(repo_url)
        else:
            raise HTTPException(status_code=400, detail="Unsupported repository host")
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("connect_repository failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/download/{file_path:path}")
async def download_file(file_path: str):
    """Download a generated document."""
    path = Path(file_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)


def build_github_file_tree(contents):
    """Build a file tree structure from GitHub repository contents."""
    file_tree = {"type": "directory", "name": "", "path": "", "children": []}
    for content in contents:
        if content.type == "dir":
            file_tree["children"].append(
                {"type": "directory", "name": content.name, "path": content.path, "children": []}
            )
        elif content.type == "file":
            file_tree["children"].append(
                {"type": "file", "name": content.name, "path": content.path}
            )
    return file_tree


def cli() -> None:
    """Console entrypoint."""
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    cli()
