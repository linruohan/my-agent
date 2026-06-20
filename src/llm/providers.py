from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ProviderConfig:
    name: str
    type: str
    base_url: str | None = None
    model: str = ""
    api_key_env: str | None = None
    temperature: float = 0.7
    timeout: int = 60
    supports_tool_call: bool = True
    extra: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> ProviderConfig:
        known = {
            "type",
            "base_url",
            "model",
            "api_key_env",
            "temperature",
            "timeout",
            "supports_tool_call",
        }
        extra = {k: v for k, v in data.items() if k not in known}
        return cls(
            name=name,
            type=data["type"],
            base_url=data.get("base_url"),
            model=data.get("model", ""),
            api_key_env=data.get("api_key_env"),
            temperature=float(data.get("temperature", 0.7)),
            timeout=int(data.get("timeout", 60)),
            supports_tool_call=bool(data.get("supports_tool_call", True)),
            extra=extra or None,
        )


def parse_providers(raw: dict[str, Any]) -> tuple[str, dict[str, ProviderConfig]]:
    default = raw.get("default_provider", "deepseek")
    providers_raw = raw.get("providers", {})
    providers = {
        name: ProviderConfig.from_dict(name, cfg)
        for name, cfg in providers_raw.items()
    }
    return default, providers
