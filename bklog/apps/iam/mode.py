from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from functools import lru_cache

from apps.feature_toggle.handlers.toggle import FeatureToggleObject, Toggle
from apps.feature_toggle.plugins.constants import IAM_PERMISSION_MODE
from apps.iam.iam_engine.core.config import AuthMode
from apps.iam.iam_engine.core.exceptions import InvalidAuthModeError
from apps.iam.iam_engine.core.requests import ResourceInstance

_VALID_MODES = frozenset({AuthMode.V3.value, AuthMode.V4.value, AuthMode.UNION.value})

InvalidIAMPermissionModeError = InvalidAuthModeError


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

        # IAM 鉴权模式不按业务灰度，因此不复用 FeatureToggle 通用的 debug 白名单/黑名单语义，
        # 只认可显式的 "on"；其余任何状态（包括 "off"、"debug"、未知值）都必须安全拒绝鉴权，
        # 不能被当作已开启继续读取 feature_config.mode。
        if toggle.status != "on":
            status_value = str(toggle.status or "")
            reason = f"IAM permission mode toggle status is not enabled: {status_value!r}"
            self.logger.error(reason)
            raise InvalidAuthModeError(status_value or "off", reason)

        # feature_config 是普通 JSONField，可以存任意 JSON 值（字符串、数组、数字……），
        # 不能假设它一定是字典；类型不对时必须安全拒绝，不能让 AttributeError 泄漏到调用方。
        feature_config = toggle.feature_config
        if feature_config is None:
            feature_config = {}
        if not isinstance(feature_config, Mapping):
            reason = (
                f"IAM permission mode toggle feature_config is not a mapping: "
                f"type={type(feature_config).__name__!r} value={feature_config!r}"
            )
            self.logger.error(reason)
            raise InvalidAuthModeError("invalid_feature_config", reason)

        mode_value = feature_config.get("mode", AuthMode.V3.value)
        if not isinstance(mode_value, str):
            mode_value = str(mode_value)
        mode_value = mode_value.strip().lower()

        if mode_value not in _VALID_MODES:
            reason = f"invalid IAM permission mode configured: {mode_value}"
            self.logger.error(reason)
            raise InvalidAuthModeError(mode_value, reason)

        return AuthMode(mode_value)


@lru_cache(maxsize=1)
def get_mode_provider() -> FeatureToggleModeProvider:
    return FeatureToggleModeProvider()
