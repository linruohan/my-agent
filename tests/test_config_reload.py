"""配置热重载。"""

from __future__ import annotations

from pathlib import Path

from src.infra.config import (
    invalidate_yaml_cache,
    load_app_config,
    reload_runtime_config,
)


def test_reload_runtime_config_picks_up_yaml_change(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    app_yaml = cfg_dir / "app.yaml"
    app_yaml.write_text(
        "app:\n  title: before\npaths:\n  checkpoints: data/checkpoints\n"
        "  workspace: data/workspace\n  vectorstore: data/vectorstore\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("src.infra.config.CONFIG_DIR", cfg_dir)
    monkeypatch.setattr("src.infra.config.INSTALL_ROOT", tmp_path)
    invalidate_yaml_cache()

    first = load_app_config()
    assert first["app"]["title"] == "before"

    app_yaml.write_text(
        "app:\n  title: after-hot-reload\npaths:\n  checkpoints: data/checkpoints\n"
        "  workspace: data/workspace\n  vectorstore: data/vectorstore\n",
        encoding="utf-8",
    )
    # 不依赖 mtime：显式热重载必须看到新值
    second = reload_runtime_config()
    assert second["app"]["title"] == "after-hot-reload"
    assert Path(second["paths"]["checkpoints"]).is_absolute()
