from __future__ import annotations

import os
import sys

from loguru import logger


def setup_logger() -> None:
    level = os.environ.get("AGENT_LOG_LEVEL", "INFO").upper()
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
        level=level,
    )
