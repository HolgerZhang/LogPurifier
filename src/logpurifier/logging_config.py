"""Project logging configuration (loguru).

setup_logging() initializes console + file sinks. redirect_stdout_to_logger()
forwards stdout (e.g. vendored loglizer prints) to DEBUG without editing its source.
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

from loguru import logger

_CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
)
_configured = False


def setup_logging(level: str = "INFO", log_dir: str = "logs") -> None:
    """Init console (colored) + rotating file sinks. Safe to call repeatedly."""
    global _configured
    logger.remove()
    logger.add(sys.stderr, level=level, format=_CONSOLE_FORMAT, enqueue=True)
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logger.add(
        Path(log_dir) / "logpurifier_{time:YYYYMMDD_HHmmss}.log",
        level="DEBUG",
        rotation="50 MB",
        retention=5,
        encoding="utf-8",
        enqueue=True,
    )
    _configured = True


@contextlib.contextmanager
def redirect_stdout_to_logger(prefix: str = "loglizer"):
    """Forward stdout written inside the block to logger.debug, line by line."""
    buffer = io.StringIO()
    old = sys.stdout
    sys.stdout = buffer
    try:
        yield
    finally:
        sys.stdout = old
        for line in buffer.getvalue().splitlines():
            if line.strip():
                logger.debug("[{}] {}", prefix, line.strip())


__all__ = ["logger", "setup_logging", "redirect_stdout_to_logger"]
