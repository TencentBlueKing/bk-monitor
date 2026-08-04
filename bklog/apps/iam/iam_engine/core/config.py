from __future__ import annotations

import logging
import time
from collections.abc import Callable
from enum import Enum
from threading import Lock


class AuthMode(str, Enum):
    V3 = "v3"
    V4 = "v4"
    UNION = "union"


class DynamicModeConfigProvider:
    """Load the authorization mode periodically without rebuilding the process."""

    def __init__(
        self,
        loader: Callable[[], object],
        ttl_seconds: float = 30,
        clock: Callable[[], float] = time.monotonic,
        logger: logging.Logger | None = None,
    ) -> None:
        self.loader = loader
        self.ttl_seconds = max(ttl_seconds, 0)
        self.clock = clock
        self.logger = logger or logging.getLogger("iam.mode")
        self._cached_mode: AuthMode | None = None
        self._expires_at = 0.0
        self._lock = Lock()

    def get_mode(self) -> AuthMode:
        with self._lock:
            now = self.clock()
            if self._cached_mode is not None and now < self._expires_at:
                return self._cached_mode

            self._cached_mode = self._load_mode()
            self._expires_at = now + self.ttl_seconds
            return self._cached_mode

    def _load_mode(self) -> AuthMode:
        try:
            raw_mode = self.loader()
        except Exception:  # pylint: disable=broad-except
            self.logger.exception("failed to load IAM permission mode, fallback to v3")
            return AuthMode.V3

        if isinstance(raw_mode, AuthMode):
            return raw_mode
        try:
            return AuthMode(str(raw_mode).strip().lower())
        except ValueError:
            self.logger.error("invalid IAM permission mode %r, fallback to v3", raw_mode)
            return AuthMode.V3
