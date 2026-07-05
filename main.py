"""个人助理 Agent 入口。"""

from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

warnings.filterwarnings(
    "ignore", message=".*urllib3.*doesn't match a supported version.*", category=Warning
)

from src.infra.logger import setup_logger
from src.ui.app import run_app


def main() -> None:
    import multiprocessing

    multiprocessing.freeze_support()
    setup_logger()
    run_app()


if __name__ == "__main__":
    main()
