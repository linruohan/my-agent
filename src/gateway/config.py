"""Gateway 配置读取。"""

from __future__ import annotations

from typing import Any

from src.infra.user_settings import get_stored_api_key, load_user_settings


def _channel_ids(raw: Any) -> set[str]:
    if isinstance(raw, (int, str)):
        raw = [raw]
    if not isinstance(raw, list):
        return set()
    return {str(x).strip() for x in raw if str(x).strip()}


def _merge_section(app: dict, user: dict) -> dict[str, Any]:
    return {**app, **user}


def load_gateway_config() -> dict[str, Any]:
    from src.infra.config import load_app_config

    app_gw = load_app_config().get("gateway", {}) or {}
    settings = load_user_settings()
    gw = _merge_section(app_gw, settings.get("gateway", {}) or {})

    tg = _merge_section(app_gw.get("telegram", {}) or {}, gw.get("telegram", {}) or {})
    tg_token = str(tg.get("bot_token") or "").strip() or get_stored_api_key("TELEGRAM_BOT_TOKEN") or ""

    dc = _merge_section(app_gw.get("discord", {}) or {}, gw.get("discord", {}) or {})
    dc_token = str(dc.get("bot_token") or "").strip() or get_stored_api_key("DISCORD_BOT_TOKEN") or ""

    sk = _merge_section(app_gw.get("slack", {}) or {}, gw.get("slack", {}) or {})
    sk_bot = str(sk.get("bot_token") or "").strip() or get_stored_api_key("SLACK_BOT_TOKEN") or ""
    sk_app = str(sk.get("app_token") or "").strip() or get_stored_api_key("SLACK_APP_TOKEN") or ""

    cron_default = _merge_section(app_gw.get("cron_default") or {}, gw.get("cron_default") or {})

    enabled = bool(gw.get("enabled", False))
    http_enabled = bool(gw.get("http_enabled", True))
    http_token = str(gw.get("http_token") or "").strip()

    return {
        "enabled": enabled,
        "http_enabled": http_enabled,
        "http_host": str(gw.get("http_host") or "127.0.0.1"),
        "http_port": int(gw.get("http_port") or 8765),
        "http_token": http_token,
        # 出站 webhook：有值时优先 POST 推送，失败再落入 outbound 轮询队列
        "http_webhook_url": str(gw.get("http_webhook_url") or "").strip(),
        "remote_hitl": str(gw.get("remote_hitl") or "auto_reject").strip().lower(),
        "cron_default": {
            "source": str(cron_default.get("source") or "").strip(),
            "chat_id": str(cron_default.get("chat_id") or "").strip(),
        },
        "telegram": {
            "enabled": bool(tg.get("enabled", False)) and bool(tg_token),
            "bot_token": tg_token,
            "allowed_chat_ids": _channel_ids(tg.get("allowed_chat_ids")),
            "poll_interval": float(tg.get("poll_interval") or 2.0),
        },
        "discord": {
            "enabled": bool(dc.get("enabled", False)) and bool(dc_token),
            "bot_token": dc_token,
            "allowed_channel_ids": _channel_ids(dc.get("allowed_channel_ids")),
        },
        "slack": {
            "enabled": bool(sk.get("enabled", False)) and bool(sk_bot and sk_app),
            "bot_token": sk_bot,
            "app_token": sk_app,
            "allowed_channel_ids": _channel_ids(sk.get("allowed_channel_ids")),
        },
    }


def http_token_required(cfg: dict[str, Any] | None = None) -> bool:
    """Gateway 启用且开启 HTTP 时必须配置非空 http_token。"""
    data = cfg if cfg is not None else load_gateway_config()
    return bool(data.get("enabled")) and bool(data.get("http_enabled"))


def validate_http_token(cfg: dict[str, Any] | None = None) -> str | None:
    """校验 HTTP 鉴权配置。返回错误信息；通过则返回 None。"""
    data = cfg if cfg is not None else load_gateway_config()
    if not http_token_required(data):
        return None
    if str(data.get("http_token") or "").strip():
        return None
    return (
        "Gateway HTTP 已启用但 http_token 为空；"
        "请在 config/app.yaml 或 user_settings 中设置非空 token，否则拒绝启动 HTTP 服务"
    )
