"""LLM and VCS provider abstractions for DocSync."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM providers
# ---------------------------------------------------------------------------

LLM_PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {"base_url": "https://api.openai.com/v1", "env": "OPENAI_API_KEY", "compat": "openai"},
    "anthropic": {"base_url": "https://api.anthropic.com/v1", "env": "ANTHROPIC_API_KEY", "compat": "anthropic"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "env": "GEMINI_API_KEY", "compat": "openai"},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "env": "GROQ_API_KEY", "compat": "openai"},
    "mistral": {"base_url": "https://api.mistral.ai/v1", "env": "MISTRAL_API_KEY", "compat": "openai"},
    "ollama": {"base_url": "http://localhost:11434/v1", "env": "", "compat": "openai"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "env": "OPENROUTER_API_KEY", "compat": "openai"},
    "together": {"base_url": "https://api.together.xyz/v1", "env": "TOGETHER_API_KEY", "compat": "openai"},
    "perplexity": {"base_url": "https://api.perplexity.ai", "env": "PERPLEXITY_API_KEY", "compat": "openai"},
    "cohere": {"base_url": "https://api.cohere.com/compatibility/v1", "env": "COHERE_API_KEY", "compat": "openai"},
    "azure": {"base_url": None, "env": "AZURE_OPENAI_API_KEY", "compat": "azure"},
    "huggingface": {"base_url": "https://router.huggingface.co/v1", "env": "HF_TOKEN", "compat": "openai"},
}


@dataclass
class _Message:
    content: str


@dataclass
class _Choice:
    message: _Message


@dataclass
class _Response:
    choices: list[_Choice]


class _AnthropicCompletions:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def create(self, model: str, messages: list[dict], **kwargs):
        import requests

        system = ""
        msgs = []
        for m in messages:
            if m.get("role") == "system":
                system = m.get("content", "")
            else:
                msgs.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={"model": model, "max_tokens": kwargs.get("max_tokens", 4096), "system": system, "messages": msgs},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        return _Response([_Choice(_Message(text))])


class _AnthropicChat:
    def __init__(self, api_key: str):
        self.completions = _AnthropicCompletions(api_key)


class AnthropicClient:
    def __init__(self, api_key: str):
        self.chat = _AnthropicChat(api_key)


def create_llm_client(config) -> Any:
    """Create an LLM client based on config.provider."""
    provider_name = getattr(config, "provider", "openrouter") or "openrouter"
    spec = LLM_PROVIDERS.get(provider_name)
    if spec is None:
        logger.warning("Unknown LLM provider %s; falling back to openrouter", provider_name)
        spec = LLM_PROVIDERS["openrouter"]
        provider_name = "openrouter"

    api_key = getattr(config, "resolved_api_key", "") or getattr(config, "api_key", "")
    # config may carry a generic api_key field
    if not api_key:
        api_key = getattr(config, "resolved_api_key", "") or ""

    compat = spec["compat"]
    if compat == "anthropic":
        if not api_key:
            return None
        return AnthropicClient(api_key)

    if compat == "azure":
        try:
            from openai import AzureOpenAI
        except Exception:  # noqa: BLE001
            return None
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", getattr(config, "base_url", "") or "")
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01")
        if not api_key or not endpoint:
            return None
        return AzureOpenAI(api_key=api_key, azure_endpoint=endpoint, api_version=api_version)

    base_url = getattr(config, "base_url", None) or spec["base_url"]
    if spec["base_url"] and not getattr(config, "base_url", None):
        base_url = spec["base_url"]
    # allow config override
    if getattr(config, "base_url", None):
        base_url = config.base_url

    if not api_key and spec["env"]:
        api_key = os.environ.get(spec["env"], "")

    if not api_key and provider_name != "ollama":
        return None

    try:
        from openai import OpenAI

        return OpenAI(base_url=base_url, api_key=api_key or "ollama")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not create LLM client: %s", exc)
        return None


def list_llm_providers() -> list[str]:
    return sorted(LLM_PROVIDERS.keys())
