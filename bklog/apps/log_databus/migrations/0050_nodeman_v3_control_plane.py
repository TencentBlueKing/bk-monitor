import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("log_databus", "0049_collectorconfig_storage_cluster_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="NodeManV3Binding",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                (
                    "resource_type",
                    models.CharField(default="collector_config", max_length=64, verbose_name="资源类型"),
                ),
                ("resource_key", models.CharField(db_index=True, max_length=255, verbose_name="资源标识")),
                ("bk_biz_id", models.IntegerField(db_index=True, verbose_name="业务ID")),
                ("bk_tenant_id", models.CharField(default="", max_length=64, verbose_name="租户ID")),
                ("collector_config_id", models.IntegerField(db_index=True, verbose_name="采集项ID")),
                ("deploy_policy_id", models.BigIntegerField(default=None, null=True, verbose_name="部署策略ID")),
                ("policy_name", models.CharField(default="", max_length=255, verbose_name="部署策略名称")),
                ("policy_fingerprint", models.CharField(default="", max_length=64, verbose_name="期望态指纹")),
                ("generation", models.IntegerField(default=0, verbose_name="期望态版本")),
                ("is_enabled", models.BooleanField(default=True, verbose_name="采集项是否启用")),
            ],
            options={
                "verbose_name": "节点管理V3绑定",
                "verbose_name_plural": "节点管理V3绑定",
                "unique_together": {("resource_type", "bk_tenant_id", "bk_biz_id", "resource_key")},
            },
        ),
        migrations.CreateModel(
            name="NodeManV3Operation",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name="操作ID"
                    ),
                ),
                (
                    "operation_type",
                    models.CharField(
                        choices=[("reconcile", "期望态收敛"), ("remove", "子配置清理")],
                        max_length=32,
                        verbose_name="动作类型",
                    ),
                ),
                ("generation", models.IntegerField(default=0, verbose_name="期望态版本")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "待派发"),
                            ("dispatching", "派发中"),
                            ("running", "执行中"),
                            ("success", "成功"),
                            ("partial_failed", "部分失败"),
                            ("failed", "失败"),
                            ("unknown", "未知"),
                        ],
                        default="pending",
                        max_length=32,
                        verbose_name="状态",
                    ),
                ),
                (
                    "result_state",
                    models.CharField(
                        choices=[("unsupported", "能力未提供"), ("write_result_unknown", "写结果未知")],
                        default=None,
                        max_length=32,
                        null=True,
                        verbose_name="结果标记",
                    ),
                ),
                ("request_summary", models.JSONField(default=None, null=True, verbose_name="请求摘要")),
                ("error_message", models.TextField(default="", verbose_name="错误信息")),
                (
                    "binding",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="operations",
                        to="log_databus.nodemanv3binding",
                        verbose_name="绑定",
                    ),
                ),
            ],
            options={
                "verbose_name": "节点管理V3操作",
                "verbose_name_plural": "节点管理V3操作",
            },
        ),
        migrations.CreateModel(
            name="NodeManV3Workflow",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                ("trigger_id", models.CharField(default="", max_length=128, verbose_name="触发器ID")),
                ("workflow_id", models.CharField(default="", max_length=128, verbose_name="工作流ID")),
                (
                    "dispatch_status",
                    models.CharField(
                        choices=[
                            ("prepared", "已落库未提交"),
                            ("submitting", "提交中"),
                            ("submitted", "已提交"),
                            ("definite_failed", "确定失败"),
                            ("unknown", "结果未知"),
                        ],
                        default="prepared",
                        max_length=32,
                        verbose_name="派发状态",
                    ),
                ),
                (
                    "normalized_status",
                    models.CharField(
                        choices=[
                            ("pending", "待派发"),
                            ("dispatching", "派发中"),
                            ("running", "执行中"),
                            ("success", "成功"),
                            ("partial_failed", "部分失败"),
                            ("failed", "失败"),
                            ("unknown", "未知"),
                        ],
                        default="pending",
                        max_length=32,
                        verbose_name="归一状态",
                    ),
                ),
                ("status_summary", models.JSONField(default=None, null=True, verbose_name="状态摘要")),
                (
                    "operation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workflows",
                        to="log_databus.nodemanv3operation",
                        verbose_name="操作",
                    ),
                ),
            ],
            options={
                "verbose_name": "节点管理V3工作流",
                "verbose_name_plural": "节点管理V3工作流",
                "unique_together": {("operation", "trigger_id")},
            },
        ),
        migrations.CreateModel(
            name="NodeManV3SubConfigTarget",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")),
                ("created_by", models.CharField(default="", max_length=32, verbose_name="创建者")),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True, null=True, verbose_name="更新时间")),
                ("updated_by", models.CharField(blank=True, default="", max_length=32, verbose_name="修改者")),
                ("bk_host_id", models.IntegerField(db_index=True, verbose_name="主机ID")),
                ("config_file_name", models.CharField(max_length=255, verbose_name="子配置文件名")),
                ("generation", models.IntegerField(default=0, verbose_name="期望态版本")),
                ("desired_md5", models.CharField(default="", max_length=64, verbose_name="期望内容MD5")),
                ("applied_md5", models.CharField(default="", max_length=64, verbose_name="已生效内容MD5")),
                ("applied_at", models.DateTimeField(default=None, null=True, verbose_name="生效时间")),
                ("is_desired", models.BooleanField(default=True, verbose_name="是否仍在期望范围内")),
                (
                    "binding",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="targets",
                        to="log_databus.nodemanv3binding",
                        verbose_name="绑定",
                    ),
                ),
            ],
            options={
                "verbose_name": "节点管理V3子配置目标",
                "verbose_name_plural": "节点管理V3子配置目标",
                "unique_together": {("binding", "bk_host_id", "config_file_name")},
            },
        ),
        migrations.AddIndex(
            model_name="nodemanv3operation",
            index=models.Index(fields=["binding", "generation"], name="idx_nmv3_oper_binding_gen"),
        ),
        migrations.AddIndex(
            model_name="nodemanv3operation",
            index=models.Index(fields=["status", "updated_at"], name="idx_nmv3_oper_status"),
        ),
    ]
