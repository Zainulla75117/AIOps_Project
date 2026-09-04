"""Retry utilities with exponential backoff."""

from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable, TypeVar

from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def retry_sync(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable:
    """Decorator for synchronous functions with exponential backoff retry.

    Args:
        max_attempts: Maximum number of attempts (including first try).
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay cap.
        exceptions: Exception types to retry on.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    if attempt == max_attempts:
                        logger.warning(
                            "retry_exhausted",
                            function=func.__name__,
                            attempts=max_attempts,
                            error=str(exc),
                        )
                        raise
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    logger.debug(
                        "retrying",
                        function=func.__name__,
                        attempt=attempt,
                        delay=delay,
                        error=str(exc),
                    )
                    import time
                    time.sleep(delay)
            raise last_exception  # type: ignore[misc]  # unreachable but satisfies mypy
        return wrapper
    return decorator


def retry_async(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable:
    """Decorator for async functions with exponential backoff retry."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    if attempt == max_attempts:
                        logger.warning(
                            "retry_exhausted",
                            function=func.__name__,
                            attempts=max_attempts,
                            error=str(exc),
                        )
                        raise
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    logger.debug(
                        "retrying_async",
                        function=func.__name__,
                        attempt=attempt,
                        delay=delay,
                        error=str(exc),
                    )
                    await asyncio.sleep(delay)
            raise last_exception  # type: ignore[misc]
        return wrapper
    return decorator
