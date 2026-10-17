"""
Logging setup.

Ansible reads the inventory JSON from stdout, so log output only ever goes to
stderr (and optionally a file). Logging never exits the process.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from .config import Config

LOGGER_NAME = "xo_inventory"

logger = logging.getLogger(LOGGER_NAME)
logger.addHandler(logging.NullHandler())


class _StderrHandler(logging.StreamHandler):
    """Writes to whatever sys.stderr is at the time of each message."""

    def __init__(self):
        super().__init__(sys.stderr)

    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stderr
        super().emit(record)


def configure_logging(config: Config) -> None:
    """Attach stderr (and optional file) handlers according to the config."""
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    logger.setLevel(config.log_level)
    logger.propagate = False
    formatter = logging.Formatter(config.log_format, datefmt=config.log_timestamp_format)

    console = _StderrHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    if config.enable_file_logging and config.log_file_path:
        try:
            config.log_file_path.parent.mkdir(parents=True, exist_ok=True)
            if config.enable_log_rotation:
                file_handler: logging.Handler = RotatingFileHandler(
                    config.log_file_path,
                    maxBytes=config.log_file_max_size,
                    backupCount=config.log_file_backup_count,
                    encoding="utf-8",
                )
            else:
                file_handler = logging.FileHandler(config.log_file_path, encoding="utf-8")
        except OSError as exc:
            # A log file we cannot write must not break the inventory.
            logger.warning("File logging disabled, cannot open %s: %s", config.log_file_path, exc)
        else:
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    for message in config.warnings:
        logger.warning("%s", message)
