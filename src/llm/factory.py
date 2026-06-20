from __future__ import annotations

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from loguru import logger

from src.infra.config import get_env_or_keyring
from src.llm.providers import ProviderConfig


def resolve_api_key(provider: ProviderConfig) -> str | None:
    if not provider.api_key_env:
        return None
    return get_env_or_keyring(provider.api_key_env)


def create_llm(provider: ProviderConfig) -> BaseChatModel:
    """根据 Provider 配置创建 LangChain ChatModel。"""
    logger.info("创建 LLM: provider={} model={}", provider.name, provider.model)

    if provider.type == "openai_compatible":
        api_key = resolve_api_key(provider)
        if not api_key:
            logger.warning("未找到 API Key: {}", provider.api_key_env)
        return init_chat_model(
            model=provider.model,
            model_provider="openai",
            base_url=provider.base_url,
            api_key=api_key or "not-set",
            temperature=provider.temperature,
            timeout=provider.timeout,
        )

    if provider.type == "ollama":
        return init_chat_model(
            model=f"ollama:{provider.model}",
            base_url=provider.base_url,
            temperature=provider.temperature,
            timeout=provider.timeout,
        )

    raise ValueError(f"不支持的 Provider 类型: {provider.type}")


def create_llm_with_fallback(
    providers: dict[str, ProviderConfig],
    chain: list[str],
) -> tuple[BaseChatModel, str]:
    last_error: Exception | None = None
    for name in chain:
        if name not in providers:
            continue
        try:
            llm = create_llm(providers[name])
            return llm, name
        except Exception as exc:
            logger.warning("Provider {} 初始化失败: {}", name, exc)
            last_error = exc
    raise RuntimeError(f"所有 LLM Provider 均不可用: {last_error}")
