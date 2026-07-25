"""Gateway http_token 强制校验。"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.gateway.config import http_token_required, validate_http_token
from src.gateway.inbox import GatewayInbox
from src.gateway.service import GatewayService


def test_validate_http_token_ok_when_gateway_disabled():
    cfg = {"enabled": False, "http_enabled": True, "http_token": ""}
    assert http_token_required(cfg) is False
    assert validate_http_token(cfg) is None


def test_validate_http_token_ok_when_http_disabled():
    cfg = {"enabled": True, "http_enabled": False, "http_token": ""}
    assert validate_http_token(cfg) is None


def test_validate_http_token_requires_non_empty():
    cfg = {"enabled": True, "http_enabled": True, "http_token": ""}
    err = validate_http_token(cfg)
    assert err is not None
    assert "http_token" in err


def test_validate_http_token_passes_with_token():
    cfg = {"enabled": True, "http_enabled": True, "http_token": "secret"}
    assert validate_http_token(cfg) is None


def test_gateway_start_skips_http_without_token(tmp_path, monkeypatch):
    inbox = GatewayInbox(db_path=tmp_path / "gw.db")
    svc = GatewayService(inbox)

    monkeypatch.setattr(
        "src.gateway.service.load_gateway_config",
        lambda: {
            "enabled": True,
            "http_enabled": True,
            "http_host": "127.0.0.1",
            "http_port": 8765,
            "http_token": "",
            "http_webhook_url": "",
            "telegram": {"enabled": False},
            "discord": {"enabled": False},
            "slack": {"enabled": False},
        },
    )
    http_cls = MagicMock()
    monkeypatch.setattr("src.gateway.service.GatewayHttpServer", http_cls)

    svc.start()
    http_cls.assert_not_called()
    assert svc._http is None


def test_gateway_start_http_with_token(tmp_path, monkeypatch):
    inbox = GatewayInbox(db_path=tmp_path / "gw2.db")
    svc = GatewayService(inbox)

    monkeypatch.setattr(
        "src.gateway.service.load_gateway_config",
        lambda: {
            "enabled": True,
            "http_enabled": True,
            "http_host": "127.0.0.1",
            "http_port": 8765,
            "http_token": "secret",
            "http_webhook_url": "",
            "telegram": {"enabled": False},
            "discord": {"enabled": False},
            "slack": {"enabled": False},
        },
    )
    instance = MagicMock()
    http_cls = MagicMock(return_value=instance)
    monkeypatch.setattr("src.gateway.service.GatewayHttpServer", http_cls)

    svc.start()
    http_cls.assert_called_once()
    instance.start.assert_called_once()
    assert svc._http is instance
