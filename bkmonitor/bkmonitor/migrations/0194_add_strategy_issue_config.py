# Generated manually for Issues module

from django.db import migrations, models

import bkmonitor.utils.db.fields


class Migration(migrations.Migration):
    dependencies = [
        ("bkmonitor", "0193_update_20251303"),
    ]

    operations = [
        migrations.CreateModel(
            name="StrategyIssueConfig",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(default=True, verbose_name="是否启用")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("create_user", models.CharField(blank=True, default="", max_length=32, verbose_name="创建人")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("update_user", models.CharField(blank=True, default="", max_length=32, verbose_name="更新人")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("strategy_id", models.IntegerField(db_index=True, unique=True, verbose_name="策略 ID")),
                ("bk_biz_id", models.IntegerField(db_index=True, verbose_name="业务 ID")),
                (
                    "aggregate_dimensions",
                    bkmonitor.utils.db.fields.JsonField(default=list, verbose_name="聚合维度"),
                ),
                ("conditions", bkmonitor.utils.db.fields.JsonField(default=list, verbose_name="过滤条件")),
                ("alert_levels", bkmonitor.utils.db.fields.JsonField(default=list, verbose_name="生效告警级别")),
            ],
            options={
                "verbose_name": "策略 Issue 聚合配置",
                "db_table": "bkmonitor_strategy_issue_config",
            },
        ),
    ]
