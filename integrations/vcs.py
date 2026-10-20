from __future__ import annotations

import os

import gitlab
from fastapi import HTTPException
from github import Auth, Github

from config import settings


class VCSIntegration:
    def __init__(self):
        self.github = Github(auth=Auth.Token(settings.github_access_token or os.getenv("GITHUB_ACCESS_TOKEN", "")))
        self.gitlab = gitlab.Gitlab(
            "https://gitlab.com",
            private_token=settings.gitlab_access_token or os.getenv("GITLAB_ACCESS_TOKEN", ""),
        )

    async def connect_github(self, repo_url: str) -> Dict[str, Any]:
        try:
            # Extract owner and repo name from the URL
            parts = repo_url.strip("/").split("/")
            if len(parts) < 2:
                raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
            
            owner, repo_name = parts[-2], parts[-1]
            repo = self.github.get_repo(f"{owner}/{repo_name}")
            
            # Get repository contents
            contents = repo.get_contents("")
            file_tree = self._build_github_file_tree(contents)
            
            return {
                "tree": file_tree,
                "repo_info": {
                    "name": repo.name,
                    "description": repo.description,
                    "default_branch": repo.default_branch,
                    "stars": repo.stargazers_count
                }
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"GitHub Error: {str(e)}")

    async def connect_gitlab(self, repo_url: str) -> Dict[str, Any]:
        try:
            # Extract project ID or path from URL
            parts = repo_url.strip("/").split("/")
            if len(parts) < 2:
                raise HTTPException(status_code=400, detail="Invalid GitLab repository URL")
            
            project_path = "/".join(parts[-2:])
            project = self.gitlab.projects.get(project_path)
            
            # Get repository tree
            items = project.repository_tree(recursive=True)
            file_tree = self._build_gitlab_file_tree(items)
            
            return {
                "tree": file_tree,
                "repo_info": {
                    "name": project.name,
                    "description": project.description,
                    "default_branch": project.default_branch,
                    "stars": project.star_count
                }
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"GitLab Error: {str(e)}")

    def _build_github_file_tree(self, contents) -> Dict[str, Any]:
        tree = {"type": "directory", "name": "", "path": "", "children": []}
        
        for content in contents:
            if content.type == "dir":
                subtree = {
                    "type": "directory",
                    "name": content.name,
                    "path": content.path,
                    "children": self._build_github_file_tree(
                        self.github.get_repo(content.repository.full_name).get_contents(content.path)
                    )["children"]
                }
                tree["children"].append(subtree)
            else:
                tree["children"].append({
                    "type": "file",
                    "name": content.name,
                    "path": content.path
                })
        return tree

    def _build_gitlab_file_tree(self, items) -> Dict[str, Any]:
        tree = {"type": "directory", "name": "", "path": "", "children": []}
        
        for item in items:
            path_parts = item["path"].split("/")
            current = tree
            
            # Navigate through the path
            for i, part in enumerate(path_parts[:-1]):
                # Find or create directory
                found = False
                for child in current["children"]:
                    if child["name"] == part and child["type"] == "directory":
                        current = child
                        found = True
                        break
                
                if not found:
                    new_dir = {
                        "type": "directory",
                        "name": part,
                        "path": "/".join(path_parts[:i+1]),
                        "children": []
                    }
                    current["children"].append(new_dir)
                    current = new_dir
            
            # Add the file
            if item["type"] == "blob":
                current["children"].append({
                    "type": "file",
                    "name": path_parts[-1],
                    "path": item["path"]
                })
        
        return tree