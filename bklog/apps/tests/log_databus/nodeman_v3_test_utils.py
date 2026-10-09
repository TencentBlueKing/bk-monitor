from functools import wraps

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


def nodeman_v3_toggle(status: str = "on", **config):
    """可装饰 TestCase 类或测试方法，替代基于 settings 的旧开关装饰器。"""

    def decorator(target):
        if isinstance(target, type):
            original_set_up = target.setUp

            @wraps(original_set_up)
            def set_up(test_case, *args, **kwargs):
                set_nodeman_v3_toggle(status, **config)
                return original_set_up(test_case, *args, **kwargs)

            target.setUp = set_up
            return target

        @wraps(target)
        def wrapped(*args, **kwargs):
            set_nodeman_v3_toggle(status, **config)
            return target(*args, **kwargs)

        return wrapped

    return decorator
