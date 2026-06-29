"""从 Provider 拉取可用模型列表。"""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from src.llm.factory import resolve_api_key
from src.llm.providers import ProviderConfig


def _normalize_base_url(base_url: str | None) -> str:
    return (base_url or "").rstrip("/")


def _openai_models_url(base_url: str) -> str:
    root = _normalize_base_url(base_url)
    if root.endswith("/v1"):
        return f"{root}/models"
    return f"{root}/v1/models"


def _parse_openai_models(payload: dict[str, Any]) -> list[str]:
    items = payload.get("data") or []
    models: list[str] = []
    for item in items:
        if isinstance(item, dict):
            model_id = item.get("id")
            if isinstance(model_id, str) and model_id.strip():
                models.append(model_id.strip())
    return models


def _parse_ollama_models(payload: dict[str, Any]) -> list[str]:
    items = payload.get("models") or []
    models: list[str] = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                models.append(name.strip())
    return models


def list_provider_models(provider: ProviderConfig, *, timeout: float = 15.0) -> list[str]:
    """拉取 Provider 可用模型；失败时抛出异常。"""
    if provider.type == "openai_compatible":
        base_url = _normalize_base_url(provider.base_url)
        if not base_url:
            raise ValueError("未配置 API Base URL")
        url = _openai_models_url(base_url)
        headers: dict[str, str] = {}
        api_key = resolve_api_key(provider)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            models = _parse_openai_models(resp.json())
    elif provider.type == "ollama":
        base_url = _normalize_base_url(provider.base_url) or "http://localhost:11434"
        url = f"{base_url}/api/tags"
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            models = _parse_ollama_models(resp.json())
    else:
        raise ValueError(f"不支持的 Provider 类型: {provider.type}")

    if provider.model and provider.model not in models:
        models.insert(0, provider.model)
    return sorted(set(models), key=str.lower)


def list_provider_models_safe(provider: ProviderConfig) -> tuple[list[str], str | None]:
    """拉取模型列表，失败时返回空列表与错误信息。"""
    try:
        return list_provider_models(provider), None
    except Exception as exc:
        logger.warning("拉取模型列表失败 ({}): {}", provider.name, exc)
        models = [provider.model] if provider.model else []
        return models, str(exc)
