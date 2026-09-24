"""初始化分片异步导出灰度开关和动态策略。"""

from django.db import migrations


FEATURE_NAME = "feature_async_export_sharded"

DEFAULT_CONFIG = {
    "target_rows": 30000,
    "target_bytes": 67108864,
    "split_factor": 2.0,
    "merge_factor": 1.5,
    "max_rows": 10000000,
    "max_parts": 500,
    "sample_rows": 100,
    "bucket_seconds": 30,
    "split_step_ms": 1000,
    "max_buckets": 500,
    "fallback_row_bytes": 1024,
    "default_parallelism": 4,
    "max_parallelism": 8,
    "index_parallelism": 4,
    # 0 表示环境容量未配置：调度器会拒绝投递并告警，避免多 Pod 下预算被按 Pod 相乘
    "global_parallelism": 0,
    "part_max_attempts": 3,
    "planning_attempts": 3,
    "artifact_retention_seconds": 86400,
    "signed_url_seconds": 600,
}


def forwards_func(apps, schema_editor):
    feature_toggle = apps.get_model("feature_toggle", "FeatureToggle")
    feature_toggle.objects.update_or_create(
        name=FEATURE_NAME,
        defaults={
            "alias": "分片异步日志导出",
            "status": "off",
            "is_viewed": False,
            "description": "控制新建日志导出是否进入 ExportJob 分片链路；关闭不影响存量任务收尾。",
            "feature_config": DEFAULT_CONFIG,
            "biz_id_white_list": None,
            "biz_id_black_list": None,
        },
    )


def backwards_func(apps, schema_editor):
    feature_toggle = apps.get_model("feature_toggle", "FeatureToggle")
    feature_toggle.objects.filter(name=FEATURE_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [("feature_toggle", "0011_init_iam_permission_toggle")]

    operations = [migrations.RunPython(forwards_func, backwards_func)]
