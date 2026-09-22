"""分片异步导出的功能开关与动态策略配置。"""

from dataclasses import asdict, dataclass

from django.conf import settings

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.utils.log import logger


FEATURE_ASYNC_EXPORT_SHARDED = "feature_async_export_sharded"

PLAN_TASK_NAME = "apps.log_search.tasks.sharded_export.plan_sharded_export"
PART_TASK_NAME = "apps.log_search.tasks.sharded_export.execute_sharded_export_part"
FINALIZE_TASK_NAME = "apps.log_search.tasks.sharded_export.finalize_sharded_export"


@dataclass(frozen=True)
class ExportPolicy:
    """会影响任务行为的策略；创建任务时需完整保存为快照。"""

    target_rows: int = 30_000
    target_bytes: int = 64 * 1024 * 1024
    split_factor: float = 2.0
    merge_factor: float = 1.5
    max_rows: int = 10_000_000
    max_parts: int = 500
    sample_rows: int = 100
    bucket_seconds: int = 30
    max_buckets: int = 500
    fallback_row_bytes: int = 1024
    default_parallelism: int = 4
    max_parallelism: int = 8
    index_parallelism: int = 4
    global_parallelism: int = 4
    part_max_attempts: int = 3
    planning_attempts: int = 3
    artifact_retention_seconds: int = 86_400
    signed_url_seconds: int = 600

    def snapshot(self):
        return asdict(self)


_INTEGER_RANGES = {
    "target_rows": (1, 100_000_000),
    "target_bytes": (1, 10 * 1024 * 1024 * 1024),
    "max_rows": (1, 100_000_000),
    "max_parts": (1, 10_000),
    "sample_rows": (1, 10_000),
    "bucket_seconds": (1, 86_400),
    "max_buckets": (1, 10_000),
    "fallback_row_bytes": (1, 10 * 1024 * 1024),
    "default_parallelism": (1, 64),
    "max_parallelism": (1, 64),
    "index_parallelism": (0, 10_000),
    "global_parallelism": (0, 10_000),
    "part_max_attempts": (1, 20),
    "planning_attempts": (1, 20),
    "artifact_retention_seconds": (1, 365 * 86_400),
    "signed_url_seconds": (1, 86_400),
}
_FLOAT_RANGES = {"split_factor": (1.0, 100.0), "merge_factor": (1.0, 100.0)}


def _validated_policy(raw):
    """FeatureConfig 是无 Schema 的 JSONField，非法值逐项回退默认值。"""
    defaults = ExportPolicy()
    values = defaults.snapshot()
    if raw is None:
        return defaults
    if not isinstance(raw, dict):
        logger.warning("[sharded_export_config] feature_config is not a mapping, using defaults")
        return defaults

    for name, (minimum, maximum) in _INTEGER_RANGES.items():
        value = raw.get(name, values[name])
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            logger.warning("[sharded_export_config] invalid %s=%r, using default=%r", name, value, values[name])
            continue
        values[name] = value
    for name, (minimum, maximum) in _FLOAT_RANGES.items():
        value = raw.get(name, values[name])
        if isinstance(value, bool) or not isinstance(value, int | float) or not minimum <= value <= maximum:
            logger.warning("[sharded_export_config] invalid %s=%r, using default=%r", name, value, values[name])
            continue
        values[name] = float(value)

    values["max_parallelism"] = max(values["default_parallelism"], values["max_parallelism"])
    values["signed_url_seconds"] = min(values["signed_url_seconds"], values["artifact_retention_seconds"])
    return ExportPolicy(**values)


def current_policy():
    """读取当前动态策略；开关关闭时仍供存量任务和调度器读取。"""
    toggle = FeatureToggleObject.toggle(FEATURE_ASYNC_EXPORT_SHARDED)
    return _validated_policy(toggle.feature_config if toggle else None)


def policy_from_snapshot(snapshot):
    """恢复任务创建时的策略；旧任务缺少快照时使用当前默认策略。"""
    return _validated_policy(snapshot)


def is_enabled(bk_biz_id=None):
    """仅用于决定新请求是否进入分片导出链路。"""
    return FeatureToggleObject.switch(FEATURE_ASYNC_EXPORT_SHARDED, biz_id=bk_biz_id, default=False)


def scheduler_limits():
    """动态软限制不得超过环境容量硬上限。"""
    policy = current_policy()
    return (
        min(policy.index_parallelism, settings.ASYNC_EXPORT_INDEX_HARD_LIMIT),
        min(policy.global_parallelism, settings.ASYNC_EXPORT_GLOBAL_HARD_LIMIT),
    )
