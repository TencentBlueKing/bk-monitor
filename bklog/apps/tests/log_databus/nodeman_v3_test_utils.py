from functools import wraps

from django.test import override_settings

from apps.feature_toggle.models import FeatureToggle
from apps.feature_toggle.plugins.constants import NODEMAN_V3_COLLECTOR


def set_nodeman_v3_toggle(
    status: str = "on",
    *,
    biz_ids: list[int] | None = None,
    biz_blacklist: list[int] | None = None,
    collector_ids: list[int] | None = None,
) -> FeatureToggle:
    """为单个事务内的测试设置 NodeMan V3 准入开关。"""
    toggle, _ = FeatureToggle.objects.update_or_create(
        name=NODEMAN_V3_COLLECTOR,
        defaults={
            "alias": "NodeMan V3 物理机采集",
            "status": status,
            "is_viewed": False,
            "feature_config": {"collector_config_ids": collector_ids or []},
            "biz_id_white_list": biz_ids or [],
            "biz_id_black_list": biz_blacklist or [],
        },
    )
    return toggle


def _env_settings(enabled: bool, env_value: str | None):
    """
    组装环境开关的 override。

    enabled 只表达「是否强制关闭」：True 表示不做强制、交给 DB 灰度，False 表示强制关闭。
    要验证 true / false 的强制语义，显式传 env_value。
    """
    if env_value is not None:
        return override_settings(ENABLE_NODEMAN_V3_VALUE=env_value)
    return override_settings(ENABLE_NODEMAN_V3_VALUE="" if enabled else "false")


def nodeman_v3_toggle(status: str = "on", *, enabled: bool = True, env_value: str | None = None, **config):
    """
    同时配置环境变量和数据库灰度开关，可装饰 TestCase 类或测试方法。

    env_value 用于覆盖环境变量档位（on / off / true / 非法值 / 空串）；
    不传时按 enabled 走历史口径。
    """

    def decorator(target):
        if isinstance(target, type):
            original_set_up = target.setUp

            @wraps(original_set_up)
            def set_up(test_case, *args, **kwargs):
                set_nodeman_v3_toggle(status, **config)
                return original_set_up(test_case, *args, **kwargs)

            target.setUp = set_up
            return _env_settings(enabled, env_value)(target)

        @wraps(target)
        def wrapped(*args, **kwargs):
            with _env_settings(enabled, env_value):
                set_nodeman_v3_toggle(status, **config)
                return target(*args, **kwargs)

        return wrapped

    return decorator
