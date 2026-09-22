"""分片异步导出的功能开关与动态策略配置。"""

from dataclasses import asdict, dataclass

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
    # 0 表示环境容量未配置：调度器会拒绝投递并告警，必须由运维按真实容量显式配置
    global_parallelism: int = 0
    part_max_attempts: int = 3
    planning_attempts: int = 3
    artifact_retention_seconds: int = 86_400
    signed_url_seconds: int = 600

    def snapshot(self):
        return asdict(self)


# 策略字段取值范围；FeatureConfig 是无 Schema 的 JSONField，非法值逐项回退默认值。
# 键值为 (允许类型, 最小值, 最大值)，float 字段同时接受 int，运维可以直接写 2 这样的值。
_BOUNDS = {
    "target_rows": (int, 1, 100_000_000),
    "target_bytes": (int, 1, 10 * 1024 * 1024 * 1024),
    "split_factor": ((int, float), 1.0, 100.0),
    "merge_factor": ((int, float), 1.0, 100.0),
    "max_rows": (int, 1, 100_000_000),
    "max_parts": (int, 1, 10_000),
    "sample_rows": (int, 1, 10_000),
    "bucket_seconds": (int, 1, 86_400),
    "max_buckets": (int, 1, 10_000),
    "fallback_row_bytes": (int, 1, 10 * 1024 * 1024),
    "default_parallelism": (int, 1, 64),
    "max_parallelism": (int, 1, 64),
    "index_parallelism": (int, 1, 10_000),
    # 0 是「未配置」的哨兵值，调度器据此拒绝投递
    "global_parallelism": (int, 0, 10_000),
    "part_max_attempts": (int, 1, 20),
    "planning_attempts": (int, 1, 20),
    "artifact_retention_seconds": (int, 1, 365 * 86_400),
    "signed_url_seconds": (int, 1, 86_400),
}


def _validated_policy(raw):
    """按 _BOUNDS 逐项校验并回退默认值。"""
    defaults = ExportPolicy()
    if not isinstance(raw, dict):
        if raw is not None:
            logger.warning("[sharded_export_config] feature_config is not a mapping, using defaults")
        return defaults

    values = defaults.snapshot()
    for name, (types, minimum, maximum) in _BOUNDS.items():
        value = raw.get(name, values[name])
        # bool 是 int 的子类，需要显式排除
        if isinstance(value, bool) or not isinstance(value, types) or not minimum <= value <= maximum:
            logger.warning("[sharded_export_config] invalid %s=%r, using default=%r", name, value, values[name])
            continue
        values[name] = float(value) if types is not int else value

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
