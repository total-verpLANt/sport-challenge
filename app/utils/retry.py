"""Retry-Decorator für Garmin-Rate-Limit-Fehler.

Retryt ausschliesslich bei ``GarminConnectTooManyRequestsError`` mit
exponentiellem Backoff.  Alle anderen Exceptions werden sofort
weitergegeben.
"""
from __future__ import annotations

import functools
import logging
import time
from typing import Callable, TypeVar

from garminconnect.exceptions import GarminConnectTooManyRequestsError

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable)


def retry_on_rate_limit(max_retries: int = 2, base_delay: float = 60) -> Callable[[F], F]:
    """Decorator: Wiederholt den Aufruf bei ``GarminConnectTooManyRequestsError``.

    Args:
        max_retries: Maximale Anzahl Wiederholungsversuche (Standard: 2).
        base_delay:  Basis-Wartezeit in Sekunden (Standard: 60).
                     1. Retry wartet ``base_delay``, 2. Retry wartet ``2 * base_delay``.

    Nach Ausschöpfen aller Versuche wird die Exception hart weitergegeben.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except GarminConnectTooManyRequestsError as exc:
                    if attempt >= max_retries:
                        logger.error(
                            "Rate-Limit-Fehler nach %d Versuchen in %s – gebe auf.",
                            attempt + 1,
                            func.__qualname__,
                        )
                        raise
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "Rate-Limit-Fehler in %s (Versuch %d/%d) – warte %.0fs.",
                        func.__qualname__,
                        attempt + 1,
                        max_retries,
                        delay,
                    )
                    time.sleep(delay)

        return wrapper  # type: ignore[return-value]

    return decorator
