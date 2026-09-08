from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("strategy", "0002_alter_actionconfig_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="StrategyIssueConfigModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "strategy_id",
                    models.IntegerField(
                        db_index=True,
                        unique=True,
                        verbose_name="策略 ID",
                    ),
                ),
                (
                    "bk_biz_id",
                    models.IntegerField(
                        db_index=True,
                        verbose_name="业务 ID",
                    ),
                ),
                (
                    "is_enabled",
                    models.BooleanField(
                        default=True,
                        verbose_name="是否启用",
                    ),
                ),
                (
                    "is_deleted",
                    models.BooleanField(
                        default=False,
                        verbose_name="是否删除",
                    ),
                ),
                (
                    "aggregate_dimensions",
                    models.JSONField(
                        blank=True,
                        default=list,
                        verbose_name="聚合维度",
                    ),
                ),
                (
                    "conditions",
                    models.JSONField(
                        blank=True,
                        default=list,
                        verbose_name="过滤条件",
                    ),
                ),
                (
                    "alert_levels",
                    models.JSONField(
                        blank=True,
                        default=list,
                        verbose_name="生效告警级别",
                    ),
                ),
                (
                    "create_user",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=32,
                        verbose_name="创建人",
                    ),
                ),
                (
                    "create_time",
                    models.DateTimeField(
                        auto_now_add=True,
                        blank=True,
                        verbose_name="创建时间",
                    ),
                ),
                (
                    "update_user",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=32,
                        verbose_name="最后修改人",
                    ),
                ),
                (
                    "update_time",
                    models.DateTimeField(
                        auto_now=True,
                        blank=True,
                        verbose_name="最后修改时间",
                    ),
                ),
            ],
            options={
                "verbose_name": "策略 Issue 聚合配置",
                "verbose_name_plural": "策略 Issue 聚合配置",
                "db_table": "bkmonitor_strategy_issue_config",
            },
        ),
    ]
