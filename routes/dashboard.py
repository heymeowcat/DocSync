from fastapi import APIRouter, Depends, HTTPException
from github import Github
from typing import List
from .auth import get_current_user

router = APIRouter()

@router.get("/api/repositories")
async def list_repositories(user = Depends(get_current_user)):
    g = Github(user["access_token"])
    repos = []
    for repo in g.get_user().get_repos():
        repos.append({
            "id": repo.id,
            "name": repo.name,
            "description": repo.description,
            "stars": repo.stargazers_count,
            "default_branch": repo.default_branch
        })
    return repos

@router.get("/api/repository/{repo_id}/files")
async def get_repository_files(repo_id: int, user = Depends(get_current_user)):
    g = Github(user["access_token"])
    repo = g.get_repo(repo_id)
    return build_file_tree(repo.get_contents(""))

@router.post("/api/process")
async def process_files(data: dict, user = Depends(get_current_user)):
    # Reuse your existing processing logic here
    return {"id": "unique_id_for_result"}