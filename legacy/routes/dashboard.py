"""Dashboard API routes for browsing GitHub repositories."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from github import Github, GithubException

from .auth import get_current_user

router = APIRouter()


def build_file_tree(contents) -> list[dict]:
    """Convert GitHub contents into a nested tree structure."""
    tree = []
    for content in contents:
        if content.type == "dir":
            tree.append(
                {"type": "directory", "name": content.name, "path": content.path, "children": []}
            )
        elif content.type == "file":
            tree.append({"type": "file", "name": content.name, "path": content.path})
    return tree


@router.get("/api/repositories")
async def list_repositories(user: dict = Depends(get_current_user)):
    try:
        g = Github(user["access_token"])
        repos = []
        for repo in g.get_user().get_repos():
            repos.append(
                {
                    "id": repo.id,
                    "name": repo.name,
                    "description": repo.description,
                    "stars": repo.stargazers_count,
                    "default_branch": repo.default_branch,
                }
            )
        return repos
    except GithubException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/repository/{repo_id}/files")
async def get_repository_files(repo_id: int, user: dict = Depends(get_current_user)):
    try:
        g = Github(user["access_token"])
        repo = g.get_repo(repo_id)
        return build_file_tree(repo.get_contents(""))
    except GithubException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/process")
async def process_files(data: dict, user: dict = Depends(get_current_user)):
    return {"id": "unique_id_for_result"}
