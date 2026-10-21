"""Shared mode resolution; platform configuration stores are injected."""

import logging
from collections.abc import Callable, Mapping
from typing import Any

from iam_engine.core.config import AuthMode, DEFAULT_DUAL_STACK, DualStackSpec
from iam_engine.core.exceptions import InvalidAuthModeError
from iam_engine.core.requests import ResourceInstance

IAM_PERMISSION_MODE = "iam_permission_mode"


class FeatureToggleModeProvider:
    """解析运行时鉴权模式：显式环境变量优先，否则 Feature Toggle。

    resources 参数是 ModeProvider 协议预留的按空间灰度钩子；当前实现忽略它，
    全平台共用一个 mode。若以后要按空间切流，在这里读 resources，不要改 Router。
    """

    def __init__(
        self,
        toggle_loader: Callable[[str], Any],
        logger: logging.Logger | None = None,
        *,
        stack: DualStackSpec | None = None,
        env_loader: Callable[[], str | None],
        raise_on_load_error: bool = False,
    ) -> None:
        self.toggle_loader = toggle_loader
        self.env_loader = env_loader
        self.logger = logger or logging.getLogger("iam.mode")
        self.stack = stack or DEFAULT_DUAL_STACK
        self.raise_on_load_error = raise_on_load_error
        self._logged_env_override = False

    def get_mode(self, resources: tuple[ResourceInstance, ...] = ()) -> AuthMode:
        del resources
        return self._load_mode()

    def _load_mode(self) -> AuthMode:
        env_mode = self._env_mode_value()
        if env_mode is not None:
            mode = self._require_valid_mode(
                env_mode,
                reason=f"invalid IAM permission mode configured via BKAPP_IAM_PERMISSION_MODE: {env_mode}",
            )
            self._log_env_override_once(mode.value)
            return mode
        return self._load_toggle_mode()

    def _env_mode_value(self) -> str | None:
        """环境变量未设置或空白视为未配置，让 Toggle 接手；非空字符串即使非法也要返回给校验层。"""

        raw = self.env_loader()
        if raw is None:
            return None
        if not isinstance(raw, str):
            raw = str(raw)
        raw = raw.strip().lower()
        return raw or None

    def _require_valid_mode(self, mode_value: str, *, reason: str) -> AuthMode:
        if mode_value not in self.stack.valid_mode_values:
            self.logger.error(reason)
            raise InvalidAuthModeError(mode_value, reason)
        return AuthMode(mode_value)

    def _log_env_override_once(self, mode_value: str) -> None:
        if self._logged_env_override:
            return
        self._logged_env_override = True
        self.logger.warning(
            "IAM permission mode uses BKAPP_IAM_PERMISSION_MODE=%s; Feature Toggle %s is ignored",
            mode_value,
            IAM_PERMISSION_MODE,
        )

    def _load_toggle_mode(self) -> AuthMode:
        fallback = self.stack.fallback_mode
        try:
            toggle = self.toggle_loader(IAM_PERMISSION_MODE)
        except Exception:  # pylint: disable=broad-except
            if self.raise_on_load_error:
                raise
            self.logger.exception("failed to load IAM permission mode toggle, fallback to %s", fallback.value)
            return fallback

        if toggle is None:
            return fallback

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

        mode_value = feature_config.get("mode", fallback.value)
        if not isinstance(mode_value, str):
            mode_value = str(mode_value)
        mode_value = mode_value.strip().lower()

        return self._require_valid_mode(
            mode_value,
            reason=f"invalid IAM permission mode configured: {mode_value}",
        )
