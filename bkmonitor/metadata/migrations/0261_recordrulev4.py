# Generated manually on 2026-05-16

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0260_basereportsinkconfig"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecordRuleV4",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creator", models.CharField(max_length=64, verbose_name="创建者")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updater", models.CharField(max_length=64, verbose_name="更新者")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("space_type", models.CharField(max_length=64, verbose_name="空间类型")),
                ("space_id", models.CharField(max_length=128, verbose_name="空间ID")),
                ("bk_tenant_id", models.CharField(default="system", max_length=256, null=True, verbose_name="租户ID")),
                ("group_name", models.CharField(max_length=128, verbose_name="预计算组名称")),
                ("flow_name", models.CharField(max_length=128, verbose_name="V4 Flow 名称")),
                ("table_id", models.CharField(max_length=128, verbose_name="结果表名")),
                ("dst_vm_table_id", models.CharField(max_length=128, verbose_name="VM 结果表RT")),
                (
                    "dst_vm_storage_name",
                    models.CharField(blank=True, default="", max_length=128, verbose_name="目标 VM 存储名称"),
                ),
                ("generation", models.IntegerField(default=0, verbose_name="用户声明版本")),
                ("desired_status", models.CharField(default="running", max_length=32, verbose_name="期望状态")),
                (
                    "applied_desired_status",
                    models.CharField(default="running", max_length=32, verbose_name="最近成功生效的期望状态"),
                ),
                ("status", models.CharField(default="created", max_length=32, verbose_name="聚合阶段")),
                ("conditions", models.JSONField(default=dict, verbose_name="当前状态条件")),
                ("auto_refresh", models.BooleanField(default=True, verbose_name="是否自动刷新")),
                ("last_check_time", models.DateTimeField(blank=True, null=True, verbose_name="最近检查时间")),
                ("last_refresh_time", models.DateTimeField(blank=True, null=True, verbose_name="最近刷新时间")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="删除完成时间")),
                (
                    "operation_lock_token",
                    models.CharField(blank=True, default="", max_length=64, verbose_name="操作锁 Token"),
                ),
                (
                    "operation_lock_owner",
                    models.CharField(blank=True, default="", max_length=128, verbose_name="操作锁持有者"),
                ),
                (
                    "operation_lock_reason",
                    models.CharField(blank=True, default="", max_length=64, verbose_name="操作锁原因"),
                ),
                (
                    "operation_lock_expires_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="操作锁过期时间"),
                ),
            ],
            options={
                "verbose_name": "V4 预计算规则组",
                "verbose_name_plural": "V4 预计算规则组",
                "unique_together": {("bk_tenant_id", "table_id"), ("bk_tenant_id", "dst_vm_table_id")},
            },
        ),
        migrations.CreateModel(
            name="RecordRuleV4Spec",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creator", models.CharField(max_length=64, verbose_name="创建者")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updater", models.CharField(max_length=64, verbose_name="更新者")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "bk_tenant_id",
                    models.CharField(db_index=True, default="system", max_length=256, null=True, verbose_name="租户ID"),
                ),
                ("generation", models.IntegerField(verbose_name="用户声明版本")),
                ("raw_config", models.JSONField(default=dict, verbose_name="用户原始完整配置")),
                ("interval", models.CharField(default="1min", max_length=16, verbose_name="计算周期")),
                ("labels", models.JSONField(default=list, verbose_name="组级附加标签")),
                ("content_hash", models.CharField(max_length=64, verbose_name="配置内容指纹")),
                ("source", models.CharField(default="user", max_length=32, verbose_name="来源")),
                ("operator", models.CharField(blank=True, default="", max_length=128, verbose_name="操作人")),
                (
                    "rule",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="specs",
                        to="metadata.recordrulev4",
                        verbose_name="预计算规则组",
                    ),
                ),
            ],
            options={
                "verbose_name": "V4 预计算用户声明快照",
                "verbose_name_plural": "V4 预计算用户声明快照",
                "unique_together": {("rule", "generation")},
            },
        ),
        migrations.CreateModel(
            name="RecordRuleV4SpecRecord",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creator", models.CharField(max_length=64, verbose_name="创建者")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updater", models.CharField(max_length=64, verbose_name="更新者")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "bk_tenant_id",
                    models.CharField(db_index=True, default="system", max_length=256, null=True, verbose_name="租户ID"),
                ),
                ("record_key", models.CharField(max_length=64, verbose_name="内部稳定记录ID")),
                ("content_hash", models.CharField(max_length=64, verbose_name="记录内容指纹")),
                ("source_index", models.IntegerField(default=0, verbose_name="原始顺序")),
                ("input_type", models.CharField(max_length=32, verbose_name="输入类型")),
                ("input_config", models.JSONField(default=dict, verbose_name="用户原始输入")),
                ("metric_name", models.CharField(max_length=128, verbose_name="输出指标名")),
                ("labels", models.JSONField(default=list, verbose_name="附加标签")),
                (
                    "spec",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="records",
                        to="metadata.recordrulev4spec",
                        verbose_name="用户声明快照",
                    ),
                ),
            ],
            options={
                "verbose_name": "V4 预计算用户声明记录",
                "verbose_name_plural": "V4 预计算用户声明记录",
                "ordering": ("source_index", "id"),
                "unique_together": {("spec", "record_key")},
            },
        ),
        migrations.CreateModel(
            name="RecordRuleV4Resolved",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creator", models.CharField(max_length=64, verbose_name="创建者")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updater", models.CharField(max_length=64, verbose_name="更新者")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "bk_tenant_id",
                    models.CharField(db_index=True, default="system", max_length=256, null=True, verbose_name="租户ID"),
                ),
                ("generation", models.IntegerField(verbose_name="用户声明版本")),
                ("resolve_version", models.IntegerField(verbose_name="同声明下解析版本")),
                ("resolved_config", models.JSONField(default=dict, verbose_name="解析完整配置")),
                ("content_hash", models.CharField(max_length=64, verbose_name="解析内容指纹")),
                ("source", models.CharField(default="scheduler", max_length=32, verbose_name="来源")),
                (
                    "rule",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="resolved",
                        to="metadata.recordrulev4",
                        verbose_name="预计算规则组",
                    ),
                ),
                (
                    "spec",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="resolved",
                        to="metadata.recordrulev4spec",
                        verbose_name="用户声明快照",
                    ),
                ),
            ],
            options={
                "verbose_name": "V4 预计算解析快照",
                "verbose_name_plural": "V4 预计算解析快照",
                "unique_together": {("rule", "spec", "resolve_version")},
            },
        ),
        migrations.CreateModel(
            name="RecordRuleV4ResolvedRecord",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creator", models.CharField(max_length=64, verbose_name="创建者")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updater", models.CharField(max_length=64, verbose_name="更新者")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "bk_tenant_id",
                    models.CharField(db_index=True, default="system", max_length=256, null=True, verbose_name="租户ID"),
                ),
                ("record_key", models.CharField(max_length=64, verbose_name="内部稳定记录ID")),
                ("content_hash", models.CharField(max_length=64, verbose_name="解析记录内容指纹")),
                ("metricql", models.TextField(verbose_name="MetricQL")),
                ("labels", models.JSONField(default=list, verbose_name="合并附加标签")),
                (
                    "src_vm_table_ids",
                    models.JSONField(default=list, verbose_name="源 VM 结果表列表"),
                ),
                (
                    "src_result_table_configs",
                    models.JSONField(default=list, verbose_name="源结果表配置列表"),
                ),
                (
                    "resolved",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="records",
                        to="metadata.recordrulev4resolved",
                        verbose_name="解析快照",
                    ),
                ),
                (
                    "spec_record",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="resolved_records",
                        to="metadata.recordrulev4specrecord",
                        verbose_name="用户声明记录",
                    ),
                ),
            ],
            options={
                "verbose_name": "V4 预计算解析记录",
                "verbose_name_plural": "V4 预计算解析记录",
                "ordering": ("spec_record__source_index", "id"),
                "unique_together": {("resolved", "record_key")},
            },
        ),
        migrations.CreateModel(
            name="RecordRuleV4Flow",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creator", models.CharField(max_length=64, verbose_name="创建者")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updater", models.CharField(max_length=64, verbose_name="更新者")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "bk_tenant_id",
                    models.CharField(db_index=True, default="system", max_length=256, null=True, verbose_name="租户ID"),
                ),
                ("flow_name", models.CharField(max_length=128, verbose_name="V4 Flow 名称")),
                ("flow_config", models.JSONField(default=dict, verbose_name="V4 Flow 配置")),
                ("content_hash", models.CharField(max_length=64, verbose_name="Flow 内容指纹")),
                ("flow_status", models.CharField(blank=True, default="", max_length=32, verbose_name="Flow 实际状态")),
                ("last_observed_at", models.DateTimeField(blank=True, null=True, verbose_name="最近观测时间")),
                (
                    "resolved",
                    models.OneToOneField(
                        on_delete=models.deletion.CASCADE,
                        related_name="flow",
                        to="metadata.recordrulev4resolved",
                        verbose_name="解析快照",
                    ),
                ),
                (
                    "rule",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="flows",
                        to="metadata.recordrulev4",
                        verbose_name="预计算规则组",
                    ),
                ),
            ],
            options={
                "verbose_name": "V4 预计算 Flow",
                "verbose_name_plural": "V4 预计算 Flow",
                "ordering": ("id",),
            },
        ),
        migrations.CreateModel(
            name="RecordRuleV4Event",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creator", models.CharField(max_length=64, verbose_name="创建者")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updater", models.CharField(max_length=64, verbose_name="更新者")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "bk_tenant_id",
                    models.CharField(db_index=True, default="system", max_length=256, null=True, verbose_name="租户ID"),
                ),
                ("generation", models.IntegerField(default=0, verbose_name="用户声明版本")),
                ("event_type", models.CharField(max_length=64, verbose_name="事件类型")),
                ("status", models.CharField(max_length=32, verbose_name="事件状态")),
                ("source", models.CharField(default="system", max_length=32, verbose_name="来源")),
                ("operator", models.CharField(blank=True, default="", max_length=128, verbose_name="操作人")),
                ("reason", models.CharField(blank=True, default="", max_length=128, verbose_name="原因")),
                ("message", models.TextField(blank=True, default="", verbose_name="消息")),
                ("detail", models.JSONField(default=dict, verbose_name="详情")),
                (
                    "flow",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        to="metadata.recordrulev4flow",
                        verbose_name="Flow",
                    ),
                ),
                (
                    "resolved",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        to="metadata.recordrulev4resolved",
                        verbose_name="解析快照",
                    ),
                ),
                (
                    "rule",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="events",
                        to="metadata.recordrulev4",
                        verbose_name="预计算规则组",
                    ),
                ),
                (
                    "spec",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        to="metadata.recordrulev4spec",
                        verbose_name="用户声明快照",
                    ),
                ),
            ],
            options={
                "verbose_name": "V4 预计算事件",
                "verbose_name_plural": "V4 预计算事件",
                "index_together": {("rule", "generation"), ("rule", "event_type")},
            },
        ),
        migrations.AddField(
            model_name="recordrulev4",
            name="applied_resolved",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="+",
                to="metadata.recordrulev4resolved",
                verbose_name="最近成功生效的解析快照",
            ),
        ),
        migrations.AddField(
            model_name="recordrulev4",
            name="current_spec",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="+",
                to="metadata.recordrulev4spec",
                verbose_name="当前用户声明快照",
            ),
        ),
        migrations.AddField(
            model_name="recordrulev4spec",
            name="latest_resolved",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="+",
                to="metadata.recordrulev4resolved",
                verbose_name="最近解析快照",
            ),
        ),
    ]
