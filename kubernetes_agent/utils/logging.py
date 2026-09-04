"""Structured logging setup using structlog.

Provides JSON-formatted structured logging for production and
coloured console output for development.
"""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(*, debug: bool = False, json_output: bool = True) -> None:
    """Configure structlog and stdlib logging.

    Args:
        debug: Enable DEBUG level if True, else INFO.
        json_output: Use JSON renderer (production). False uses coloured console.
    """
    log_level = logging.DEBUG if debug else logging.INFO

    # stdlib logging config (captures third-party library logs)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
        force=True,
    )

    # structlog processors
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Apply structured formatting to the root handler
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    for handler in logging.root.handlers:
        handler.setFormatter(formatter)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named structured logger."""
    return structlog.get_logger(name)
