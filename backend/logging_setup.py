import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler
from typing import Optional

_INITIALIZED = False

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _get_log_dir() -> str:
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Aragoz Lite", "logs")
        return os.path.join(os.path.dirname(sys.executable), "logs")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")


def setup_logging(level: int = logging.INFO, log_file: Optional[str] = None) -> logging.Logger:
    global _INITIALIZED
    root = logging.getLogger("aragoz")

    if _INITIALIZED:
        return root

    root.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    log_dir = _get_log_dir()
    os.makedirs(log_dir, exist_ok=True)

    if log_file is None:
        log_file = os.path.join(log_dir, "aragoz.log")

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _INITIALIZED = True
    root.info("Logging initialized (level=%s, file=%s)", logging.getLevelName(level), log_file)
    return root


def get_logger(name: str) -> logging.Logger:
    if not _INITIALIZED:
        setup_logging()
    return logging.getLogger(f"aragoz.{name}")
