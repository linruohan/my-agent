#!/usr/bin/env python3
"""构建后组装 Windows 发布目录（exe + 配置/主题/Web/数据 等外部资源）。"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DATA = Path(__file__).resolve().parent / "release-data"

# 与 exe 同目录拷贝的静态资源
COPY_DIRS = ("config", "web")

# data/ 下需预创建的子目录
DATA_SUBDIRS = (
    "checkpoints",
    "workspace",
    "workspace/knowledge",
    "vectorstore",
    "temp/input",
)

# 默认不从开发 data/ 拷贝的敏感或运行时文件
SKIP_DATA_NAMES = frozenset({
    "secrets.json",
    "user_settings.yaml",
    "metrics.db",
    "metrics.db-shm",
    "metrics.db-wal",
    "sessions.db",
    "sessions.db-shm",
    "sessions.db-wal",
    "task.db",
    "task.db-shm",
    "task.db-wal",
    "note.db",
    "note.db-shm",
    "note.db-wal",
    "search_cache.db",
    "search_cache.db-shm",
    "search_cache.db-wal",
    "gateway.db",
    "gateway.db-shm",
    "gateway.db-wal",
    "cron_jobs.db",
    "cron_jobs.db-shm",
    "cron_jobs.db-wal",
    "conversation_index.db",
    "conversation_index.db-shm",
    "conversation_index.db-wal",
    "learning.db",
    "learning.db-shm",
    "learning.db-wal",
    "metrics_export.csv",
    "temp",
})


def _ignore_copy(_dir: str, names: list[str]) -> set[str]:
    ignored = {n for n in names if n in {"__pycache__", ".pytest_cache", ".git"}}
    ignored.update(n for n in names if n.endswith((".pyc", ".pyo")))
    return ignored


def copy_dir(src: Path, dst: Path) -> None:
    if not src.is_dir():
        raise FileNotFoundError(f"目录不存在: {src}")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=_ignore_copy)


def stage_static_dirs(project_root: Path, release_dir: Path) -> list[str]:
    copied: list[str] = []
    for name in COPY_DIRS:
        src = project_root / name
        dst = release_dir / name
        copy_dir(src, dst)
        copied.append(name)
    return copied


def stage_data_dir(
    project_root: Path,
    release_dir: Path,
    *,
    include_dev_data: bool,
    init_databases: bool,
) -> None:
    data_dir = release_dir / "data"
    template = RELEASE_DATA / "data"
    if template.is_dir():
        copy_dir(template, data_dir)
    else:
        data_dir.mkdir(parents=True, exist_ok=True)

    for sub in DATA_SUBDIRS:
        (data_dir / sub).mkdir(parents=True, exist_ok=True)

    history = data_dir / "input_history.json"
    if not history.is_file():
        history.write_text("[]\n", encoding="utf-8")

    if include_dev_data:
        src_data = project_root / "data"
        if src_data.is_dir():
            for item in src_data.iterdir():
                if item.name in SKIP_DATA_NAMES:
                    continue
                target = data_dir / item.name
                if item.is_dir():
                    if target.exists():
                        shutil.rmtree(target)
                    shutil.copytree(item, target, ignore=_ignore_copy)
                elif item.is_file():
                    shutil.copy2(item, target)

    if init_databases:
        _init_sqlite_databases(data_dir)


def _init_sqlite_databases(data_dir: Path) -> None:
    sys.path.insert(0, str(ROOT))
    from src.database import close_database, ensure_database

    ensure_database(data_dir)
    close_database()


def stage_release(
    project_root: Path,
    release_dir: Path,
    *,
    exe_name: str = "my-agent.exe",
    include_dev_data: bool = False,
    init_databases: bool = True,
) -> dict[str, object]:
    exe_src = project_root / "dist" / exe_name
    if not exe_src.is_file():
        raise FileNotFoundError(f"未找到 exe，请先运行 PyInstaller: {exe_src}")

    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True)

    shutil.copy2(exe_src, release_dir / exe_name)
    copied_dirs = stage_static_dirs(project_root, release_dir)
    stage_data_dir(
        project_root,
        release_dir,
        include_dev_data=include_dev_data,
        init_databases=init_databases,
    )

    readme_src = Path(__file__).resolve().parent / "RELEASE.txt"
    if readme_src.is_file():
        shutil.copy2(readme_src, release_dir / "README.txt")

    manifest = {
        "exe": exe_name,
        "copied_dirs": copied_dirs,
        "data_subdirs": list(DATA_SUBDIRS),
        "include_dev_data": include_dev_data,
        "init_databases": init_databases,
    }
    (release_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="组装 my-agent Windows 发布目录")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=ROOT,
        help="项目根目录",
    )
    parser.add_argument(
        "--release-dir",
        type=Path,
        default=ROOT / "dist" / "my-agent",
        help="发布目录输出路径",
    )
    parser.add_argument(
        "--include-dev-data",
        action="store_true",
        help="从开发环境 data/ 拷贝数据库等（跳过 secrets/user_settings）",
    )
    parser.add_argument(
        "--no-init-databases",
        action="store_true",
        help="不预初始化空 SQLite 数据库",
    )
    args = parser.parse_args()

    manifest = stage_release(
        args.project_root.resolve(),
        args.release_dir.resolve(),
        include_dev_data=args.include_dev_data,
        init_databases=not args.no_init_databases,
    )
    print(f"发布目录: {args.release_dir.resolve()}")
    print(f"已拷贝: {', '.join(manifest['copied_dirs'])}")
    print("data/ 目录结构与数据库已就绪")


if __name__ == "__main__":
    main()
