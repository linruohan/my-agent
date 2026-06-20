"""个人助理 Agent 入口。"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# langchain / paddle 等依赖链会触发 requests 版本提示，不影响运行
warnings.filterwarnings("ignore", message=".*urllib3.*doesn't match a supported version.*", category=Warning)

from src.infra.logger import setup_logger
from src.ui.app import run_app


def main() -> None:
    setup_logger()
    run_app()


if __name__ == "__main__":
    main()
