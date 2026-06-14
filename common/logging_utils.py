"""Structured logging shared by every pipeline stage (CLAUDE.md §11).

``get_logger`` returns a logger that writes to the console and to a per-stage log
file. Each stage also emits machine-readable records via :mod:`common.metrics`.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_FMT = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")


def get_logger(name: str, log_file: Path | None = None) -> logging.Logger:
    """Return an idempotently-configured logger (console + optional file)."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger

    console = logging.StreamHandler(stream=sys.stdout)
    console.setFormatter(_FMT)
    logger.addHandler(console)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(_FMT)
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger
