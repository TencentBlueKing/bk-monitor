from __future__ import annotations

# ---------------------------------------------------------------------------
# 鉴权模式解析：环境变量优先，否则 Feature Toggle
#
# BKAPP_IAM_PERMISSION_MODE 是运维主入口。非空则只认这一层：合法则不再读 Toggle，
# 非法则 fail-closed，不跨层回退。这是有意取舍：env 一旦设置，改 DB Toggle 无效，
# 灰度回滚必须改 values / 环境变量后重新发布，不能把 Toggle 当逃生阀。
# 未设置或空白时才读 iam_permission_mode Toggle；缺 Toggle / 读库失败回退 stack.legacy。
# 不要把拓扑对象写进 Toggle，也不要把 mode 塞进 settings.FEATURE_TOGGLE
# （那是 on/off，且 FeatureToggleObject 会用 DB 行覆盖 settings）。
# 对外取值来自 DualStackSpec.valid_mode_values（当前默认 v3 / v4 / union）。
# status 必须是 on；debug / off 一律拒绝，IAM 鉴权不做业务级白名单灰度。
# ---------------------------------------------------------------------------

import logging
from collections.abc import Callable, Mapping
from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.feature_toggle.handlers.toggle import FeatureToggleObject, Toggle
from apps.feature_toggle.plugins.constants import IAM_PERMISSION_MODE
from apps.iam.iam_engine.core.config import AuthMode, DEFAULT_DUAL_STACK, DualStackSpec
from apps.iam.iam_engine.core.exceptions import InvalidAuthModeError
from apps.iam.iam_engine.core.requests import ResourceInstance

InvalidIAMPermissionModeError = InvalidAuthModeError


def validate_configured_permission_mode(
    mode_value: str | None = None,
    *,
    stack: DualStackSpec | None = None,
) -> None:
    """校验进程级 BKAPP_IAM_PERMISSION_MODE / settings.BK_IAM_PERMISSION_MODE。

    空白表示未配置，留给 Feature Toggle；非空必须属于 ``stack.valid_mode_values``。
    与 ``FeatureToggleModeProvider._require_valid_mode`` 共用同一取值集合，
    但启动失败抛 ``ImproperlyConfigured``，避免非法环境变量拖到第一次鉴权才全量 403。
    """

    stack = stack or DEFAULT_DUAL_STACK
    if mode_value is None:
        mode_value = str(getattr(settings, "BK_IAM_PERMISSION_MODE", "") or "").strip().lower()
    else:
        mode_value = str(mode_value).strip().lower()
    if not mode_value:
        return
    if mode_value not in stack.valid_mode_values:
        allowed = ", ".join(sorted(stack.valid_mode_values))
        raise ImproperlyConfigured(f"BKAPP_IAM_PERMISSION_MODE={mode_value!r} is invalid; expected one of: {allowed}")


class FeatureToggleModeProvider:
    """解析运行时鉴权模式：显式环境变量优先，否则 Feature Toggle。

    resources 参数是 ModeProvider 协议预留的按空间灰度钩子；当前实现忽略它，
    全平台共用一个 mode。若以后要按空间切流，在这里读 resources，不要改 Router。
    """

    def __init__(
        self,
        toggle_loader: Callable[[str], Toggle | None] | None = None,
        logger: logging.Logger | None = None,
        *,
        stack: DualStackSpec | None = None,
        env_loader: Callable[[], str | None] | None = None,
    ) -> None:
        self.toggle_loader = toggle_loader or FeatureToggleObject.toggle
        self.env_loader = env_loader or self._load_settings_mode
        self.logger = logger or logging.getLogger("iam.mode")
        self.stack = stack or DEFAULT_DUAL_STACK
        self._logged_env_override = False

    @staticmethod
    def _load_settings_mode() -> str:
        """每次从 Django settings 读，不缓存，便于测试 override_settings。"""

        return str(getattr(settings, "BK_IAM_PERMISSION_MODE", "") or "").strip()

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


@lru_cache(maxsize=1)
def get_mode_provider() -> FeatureToggleModeProvider:
    """进程内单例。只缓存 Provider 实例。

    环境变量每次从 Django settings 读取；未设置时每次 get_mode 打 Toggle，不缓存读数。
    """

    return FeatureToggleModeProvider()
