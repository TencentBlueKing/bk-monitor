from __future__ import annotations

import logging
from collections.abc import Callable
from functools import lru_cache

from apps.feature_toggle.handlers.toggle import FeatureToggleObject, Toggle
from apps.feature_toggle.plugins.constants import IAM_PERMISSION_MODE
from apps.iam.iam_engine.core.config import AuthMode
from apps.iam.iam_engine.core.requests import ResourceInstance

_VALID_MODES = frozenset({AuthMode.V3.value, AuthMode.V4.value, AuthMode.UNION.value})


class InvalidIAMPermissionModeError(Exception):
    """IAM 鉴权模式配置非法，调用方应拒绝鉴权。"""

    def __init__(self, mode_value: str, reason: str) -> None:
        self.mode_value = mode_value
        self.reason = reason
        super().__init__(reason)


class FeatureToggleModeProvider:
    """通过单个 Feature Toggle 配置解析 IAM 鉴权模式。"""

    def __init__(
        self,
        toggle_loader: Callable[[str], Toggle | None] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.toggle_loader = toggle_loader or FeatureToggleObject.toggle
        self.logger = logger or logging.getLogger("iam.mode")

    def get_mode(self, resources: tuple[ResourceInstance, ...] = ()) -> AuthMode:
        del resources
        return self._load_mode()

    def _load_mode(self) -> AuthMode:
        try:
            toggle = self.toggle_loader(IAM_PERMISSION_MODE)
        except Exception:  # pylint: disable=broad-except
            self.logger.exception("failed to load IAM permission mode toggle, fallback to v3")
            return AuthMode.V3

        if toggle is None:
            return AuthMode.V3

        if toggle.status == "off":
            reason = "IAM permission mode toggle is disabled"
            self.logger.error(reason)
            raise InvalidIAMPermissionModeError("off", reason)

        feature_config = toggle.feature_config or {}
        mode_value = feature_config.get("mode", AuthMode.V3.value)
        if not isinstance(mode_value, str):
            mode_value = str(mode_value)
        mode_value = mode_value.strip().lower()

        if mode_value not in _VALID_MODES:
            reason = f"invalid IAM permission mode configured: {mode_value}"
            self.logger.error(reason)
            raise InvalidIAMPermissionModeError(mode_value, reason)

        return AuthMode(mode_value)


@lru_cache(maxsize=1)
def get_mode_provider() -> FeatureToggleModeProvider:
    return FeatureToggleModeProvider()
