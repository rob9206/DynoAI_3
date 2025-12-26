from __future__ import annotations

import logging
import sys
from typing import Iterable


def get_stdout_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Return a logger that always emits to stdout in a deterministic format.

    Modules in this package avoid global logging configuration; instead they
    attach a stdout stream handler the first time they are imported.
    """
    logger = logging.getLogger(name)
    has_stream = any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
    if not has_stream:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


__all__: Iterable[str] = ["get_stdout_logger"]
