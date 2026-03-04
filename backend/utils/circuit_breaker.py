"""
Circuit Breaker Utility
========================
Wraps async external API calls with open/half-open/closed state machine.
When a source fails repeatedly it opens the circuit and returns cached data
instead of hammering a dead endpoint or accumulating timeout delays.

Usage
-----
    cb = CircuitBreaker("acled", failure_threshold=3, recovery_timeout=120)

    @cb.call
    async def fetch():
        return await client.get(url)

    result = await fetch()
    if result is None:
        # circuit is open — use fallback
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Optional
from enum import Enum

logger = logging.getLogger("circuit_breaker")


class CircuitState(str, Enum):
    CLOSED    = "closed"       # Normal operation
    OPEN      = "open"         # Failing — reject calls fast
    HALF_OPEN = "half_open"    # Testing recovery


class CircuitBreaker:
    """
    Async circuit breaker with exponential backoff.

    Parameters
    ----------
    name              : Human-readable label for logging
    failure_threshold : Consecutive failures before opening circuit
    recovery_timeout  : Seconds to wait before trying HALF_OPEN
    success_threshold : Consecutive successes in HALF_OPEN before closing
    cache_ttl         : Seconds to cache last good result for fallback
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 120.0,
        success_threshold: int = 2,
        cache_ttl: float = 900.0,
    ):
        self.name              = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout  = recovery_timeout
        self.success_threshold = success_threshold
        self.cache_ttl         = cache_ttl

        self._state            = CircuitState.CLOSED
        self._failure_count    = 0
        self._success_count    = 0
        self._last_failure_at: Optional[float] = None
        self._cached_result: Any = None
        self._cache_timestamp: Optional[float] = None
        self._lock             = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if self._last_failure_at and (time.monotonic() - self._last_failure_at) >= self.recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def cached_result(self) -> Any:
        """Return cached result if still fresh, else None."""
        if self._cached_result is not None and self._cache_timestamp is not None:
            if (time.monotonic() - self._cache_timestamp) < self.cache_ttl:
                return self._cached_result
        return None

    async def _on_success(self, result: Any):
        async with self._lock:
            self._cached_result  = result
            self._cache_timestamp = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state         = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(f"[CB:{self.name}] Circuit CLOSED — recovery confirmed")
            else:
                self._failure_count = 0

    async def _on_failure(self, exc: Exception):
        async with self._lock:
            self._failure_count  += 1
            self._last_failure_at = time.monotonic()
            self._success_count   = 0

            if self._failure_count >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        f"[CB:{self.name}] Circuit OPEN after {self._failure_count} failures. "
                        f"Recovery in {self.recovery_timeout}s. Last error: {exc}"
                    )

    def call(self, func: Callable) -> Callable:
        """Decorator — wraps an async function with circuit breaker logic."""
        async def wrapper(*args, **kwargs):
            current_state = self.state

            if current_state == CircuitState.OPEN:
                cached = self.cached_result
                if cached is not None:
                    logger.debug(f"[CB:{self.name}] Circuit OPEN — returning cached result")
                    return cached
                logger.debug(f"[CB:{self.name}] Circuit OPEN — no cache, returning None")
                return None

            if current_state == CircuitState.HALF_OPEN:
                logger.info(f"[CB:{self.name}] Circuit HALF_OPEN — testing with live call")

            try:
                result = await func(*args, **kwargs)
                await self._on_success(result)
                return result
            except Exception as exc:
                await self._on_failure(exc)
                cached = self.cached_result
                if cached is not None:
                    logger.debug(f"[CB:{self.name}] Failure — returning cached result")
                    return cached
                return None

        return wrapper

    def status(self) -> dict:
        return {
            "name":           self.name,
            "state":          self.state.value,
            "failure_count":  self._failure_count,
            "has_cache":      self.cached_result is not None,
            "recovery_in_s":  max(0, self.recovery_timeout - (time.monotonic() - self._last_failure_at))
                              if self._last_failure_at else None,
        }
