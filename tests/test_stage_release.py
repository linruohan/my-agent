"""发布目录组装测试。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_stage_release():
    spec = importlib.util.spec_from_file_location(
        "my_agent_stage_release",
        ROOT / "packaging" / "stage_release.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


stage_release = _load_stage_release().stage_release


@pytest.fixture
def mini_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    for name in ("config", "web"):
        d = project / name
        d.mkdir(parents=True)
        (d / f"{name}.txt").write_text(name, encoding="utf-8")
    (project / "web" / "themes").mkdir(parents=True)
    (project / "web" / "themes" / "default.json").write_text("{}", encoding="utf-8")
    dist = project / "dist"
    dist.mkdir()
    (dist / "my-agent.exe").write_bytes(b"MZ")
    data = project / "data"
    data.mkdir()
    (data / "sessions.db").write_bytes(b"db")
    (data / "secrets.json").write_text("{}", encoding="utf-8")
    return project


def test_stage_release_copies_resources_and_inits_data(mini_project: Path, tmp_path: Path):
    release = tmp_path / "release"
    manifest = stage_release(mini_project, release, init_databases=False)

    assert (release / "my-agent.exe").is_file()
    assert (release / "config" / "config.txt").read_text(encoding="utf-8") == "config"
    assert (release / "web" / "web.txt").read_text(encoding="utf-8") == "web"
    assert (release / "web" / "themes" / "default.json").is_file()
    assert (release / "data" / "checkpoints").is_dir()
    assert (release / "data" / "workspace" / "knowledge").is_dir()
    assert (release / "data" / "input_history.json").is_file()
    assert (release / "manifest.json").is_file()
    assert manifest["copied_dirs"] == ["config", "web"]


def test_stage_release_skips_secrets_when_include_dev_data(mini_project: Path, tmp_path: Path):
    release = tmp_path / "release"
    stage_release(mini_project, release, include_dev_data=True, init_databases=False)

    assert (release / "data" / "sessions.db").is_file()
    assert not (release / "data" / "secrets.json").exists()


def test_stage_release_init_databases(mini_project: Path, tmp_path: Path):
    release = tmp_path / "release"
    stage_release(mini_project, release, init_databases=True)

    for name in ("sessions.db", "task.db", "note.db", "search_cache.db", "metrics.db"):
        db = release / "data" / name
        assert db.is_file()
        assert db.stat().st_size > 0
