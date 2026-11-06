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

from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from iam_engine.mode import FeatureToggleModeProvider as SharedFeatureToggleModeProvider
from iam_engine.core.config import DEFAULT_DUAL_STACK, DualStackSpec
from iam_engine.core.exceptions import InvalidAuthModeError

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


class FeatureToggleModeProvider(SharedFeatureToggleModeProvider):
    """BKLog configuration-store adapter; all resolution rules live in the shared module."""

    def __init__(self, toggle_loader=None, logger=None, *, stack=None, env_loader=None):
        super().__init__(
            toggle_loader or FeatureToggleObject.toggle,
            logger,
            stack=stack,
            env_loader=env_loader or self._load_settings_mode,
        )

    @staticmethod
    def _load_settings_mode() -> str:
        """每次从 Django settings 读，不缓存，便于测试 override_settings。"""

        return str(getattr(settings, "BK_IAM_PERMISSION_MODE", "") or "").strip()


@lru_cache(maxsize=1)
def get_mode_provider() -> FeatureToggleModeProvider:
    """进程内单例。只缓存 Provider 实例。

    环境变量每次从 Django settings 读取；未设置时每次 get_mode 打 Toggle，不缓存读数。
    """

    return FeatureToggleModeProvider()


def get_deployment_mode_provider():
    """Deployments must not mistake an unreadable configuration table for V3."""

    def load_toggle(name):
        from apps.feature_toggle.models import FeatureToggle

        toggle = FeatureToggle.objects.filter(name=name).first()
        if toggle is not None:
            param = {
                key: getattr(toggle, key)
                for key in (
                    "name",
                    "status",
                    "alias",
                    "description",
                    "is_viewed",
                    "feature_config",
                    "biz_id_white_list",
                    "biz_id_black_list",
                )
            }
        else:
            status = settings.FEATURE_TOGGLE.get(name)
            if not status:
                return None
            param = {"name": name, "status": status, "feature_config": None}
        # Preserve the product's settings -> DB -> plugin precedence, but do not
        # swallow DB errors during deployment and silently synchronize V3.
        return FeatureToggleObject._format_result(FeatureToggleObject._load_plugins(name=name, param=param))

    return SharedFeatureToggleModeProvider(
        load_toggle,
        env_loader=FeatureToggleModeProvider._load_settings_mode,
        raise_on_load_error=True,
    )
