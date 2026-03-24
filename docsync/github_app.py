"""GitHub App authentication and webhook helpers."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any

import jwt
import requests
from github import Auth, Github

logger = logging.getLogger(__name__)


class GitHubApp:
    def __init__(
        self,
        app_id: str | None = None,
        private_key: str | None = None,
        webhook_secret: str | None = None,
    ):
        self.app_id = app_id or os.environ.get("GITHUB_APP_ID", "")
        self.private_key = (private_key or os.environ.get("GITHUB_PRIVATE_KEY", "")).replace("\\n", "\n")
        self.webhook_secret = webhook_secret or os.environ.get("GITHUB_WEBHOOK_SECRET", "")

    def is_configured(self) -> bool:
        return bool(self.app_id and self.private_key)

    def app_jwt(self) -> str:
        import time

        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 600, "iss": self.app_id}
        return jwt.encode(payload, self.private_key, algorithm="RS256")

    def installation_token(self, installation_id: int) -> str:
        headers = {"Authorization": f"Bearer {self.app_jwt()}", "Accept": "application/vnd.github+json"}
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        r = requests.post(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()["token"]

    def client_for_installation(self, installation_id: int) -> Github:
        token = self.installation_token(installation_id)
        return Github(auth=Auth.Token(token))

    @staticmethod
    def verify_signature(secret: str, body: bytes, signature: str) -> bool:
        if not secret or not signature:
            return False
        expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def handle_event(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        if event == "pull_request" and payload.get("action") in {"opened", "synchronize", "reopened"}:
            return {"status": "queued", "pr": payload["pull_request"]["number"]}
        return {"status": "ignored", "event": event}
