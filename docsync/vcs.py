"""VCS provider abstractions (GitHub, GitLab, Bitbucket, Gitea)."""

from __future__ import annotations

import base64
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class VCSProvider:
    name: str = "base"

    def __init__(self, token: str = "", base_url: str | None = None):
        self.token = token
        self.base_url = base_url

    def list_files(self, repo: str, path: str = "") -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_file(self, repo: str, path: str) -> str:
        raise NotImplementedError


class GitHubProvider(VCSProvider):
    name = "github"

    def __init__(self, token: str = "", base_url: str | None = None):
        super().__init__(token, base_url or "https://api.github.com")

    def _headers(self):
        h = {"Accept": "application/vnd.github+json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def list_files(self, repo, path=""):
        url = f"{self.base_url}/repos/{repo}/contents/{path}".rstrip("/")
        r = requests.get(url, headers=self._headers(), timeout=30)
        r.raise_for_status()
        data = r.json()
        items = data if isinstance(data, list) else [data]
        return [{"path": i["path"], "type": "dir" if i["type"] == "dir" else "file", "name": i["name"]} for i in items]

    def get_file(self, repo, path):
        url = f"{self.base_url}/repos/{repo}/contents/{path}"
        r = requests.get(url, headers=self._headers(), timeout=30)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        return ""


class GitLabProvider(VCSProvider):
    name = "gitlab"

    def __init__(self, token: str = "", base_url: str | None = None):
        super().__init__(token, base_url or "https://gitlab.com/api/v4")

    def _headers(self):
        h = {}
        if self.token:
            h["PRIVATE-TOKEN"] = self.token
        return h

    def list_files(self, repo, path=""):
        project = repo.replace("/", "%2F")
        url = f"{self.base_url}/projects/{project}/repository/tree"
        params = {"path": path, "per_page": 100} if path else {"per_page": 100}
        r = requests.get(url, headers=self._headers(), params=params, timeout=30)
        r.raise_for_status()
        return [{"path": i["path"], "type": "directory" if i["type"] == "tree" else "file", "name": i["name"]} for i in r.json()]

    def get_file(self, repo, path):
        project = repo.replace("/", "%2F")
        url = f"{self.base_url}/projects/{project}/repository/files/{path.replace('/', '%2F')}/raw"
        r = requests.get(url, headers=self._headers(), params={"ref": "main"}, timeout=30)
        r.raise_for_status()
        return r.text


class BitbucketProvider(VCSProvider):
    name = "bitbucket"

    def __init__(self, token: str = "", base_url: str | None = None, username: str = ""):
        super().__init__(token, base_url or "https://api.bitbucket.org/2.0")
        self.username = username

    def _auth(self):
        if self.username and self.token:
            return (self.username, self.token)
        return None

    def list_files(self, repo, path=""):
        url = f"{self.base_url}/repositories/{repo}/src/HEAD/{path}".rstrip("/")
        r = requests.get(url, auth=self._auth(), timeout=30)
        r.raise_for_status()
        data = r.json()
        return [{"path": v["path"], "type": "directory" if v["type"] == "commit_directory" else "file", "name": v["path"].split("/")[-1]} for v in data.get("values", [])]

    def get_file(self, repo, path):
        url = f"{self.base_url}/repositories/{repo}/src/HEAD/{path}"
        r = requests.get(url, auth=self._auth(), timeout=30)
        r.raise_for_status()
        return r.text


class GiteaProvider(VCSProvider):
    name = "gitea"

    def __init__(self, token: str = "", base_url: str | None = None):
        super().__init__(token, base_url or "https://gitea.com/api/v1")

    def _headers(self):
        h = {}
        if self.token:
            h["Authorization"] = f"token {self.token}"
        return h

    def list_files(self, repo, path=""):
        url = f"{self.base_url}/repos/{repo}/contents/{path}".rstrip("/")
        r = requests.get(url, headers=self._headers(), timeout=30)
        r.raise_for_status()
        data = r.json()
        items = data if isinstance(data, list) else [data]
        return [{"path": i.get("path", i.get("name")), "type": "dir" if i.get("type") == "dir" else "file", "name": i["name"]} for i in items]

    def get_file(self, repo, path):
        url = f"{self.base_url}/repos/{repo}/contents/{path}"
        r = requests.get(url, headers=self._headers(), timeout=30)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        return data.get("content", "") if isinstance(data, dict) else ""


VCS_PROVIDERS = {
    "github": GitHubProvider,
    "gitlab": GitLabProvider,
    "bitbucket": BitbucketProvider,
    "gitea": GiteaProvider,
}


def create_vcs_provider(name: str, token: str = "", base_url: str | None = None, **kwargs) -> VCSProvider:
    cls = VCS_PROVIDERS.get(name.lower())
    if cls is None:
        raise ValueError(f"Unknown VCS provider: {name}")
    return cls(token=token, base_url=base_url, **kwargs)


def list_vcs_providers() -> list[str]:
    return sorted(VCS_PROVIDERS.keys())
