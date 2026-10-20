"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for TecDocAuto."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM provider (OpenRouter by default)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "cognitivecomputations/dolphin3.0-r1-mistral-24b:free"

    # GitHub OAuth (optional)
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/auth/github/callback"
    github_access_token: str = ""

    # GitLab (optional)
    gitlab_access_token: str = ""

    # App
    jwt_secret: str = "change-me-in-production"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"


settings = Settings()
