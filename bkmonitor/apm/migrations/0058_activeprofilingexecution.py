"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("apm", "0057_toponode_heartbeat")]

    operations = [
        migrations.CreateModel(
            name="ActiveProfilingTask",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(default=True, verbose_name="是否启用")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("create_user", models.CharField(blank=True, default="", max_length=32, verbose_name="创建人")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("update_user", models.CharField(blank=True, default="", max_length=32, verbose_name="最后修改人")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="最后修改时间")),
                ("bk_biz_id", models.IntegerField(db_index=True, verbose_name="业务 ID")),
                ("name", models.CharField(max_length=128, verbose_name="任务名称")),
                ("collection_method", models.CharField(max_length=32, verbose_name="采集方式")),
                ("collection_type", models.CharField(max_length=32, verbose_name="采集类型")),
                ("deployment_status", models.CharField(default="deploying", max_length=32, verbose_name="部署状态")),
                ("subscription_id", models.IntegerField(default=0, verbose_name="节点管理订阅 ID")),
                ("target_config", models.JSONField(default=dict, verbose_name="目标主机配置")),
                ("process_selector", models.JSONField(default=dict, verbose_name="进程选择器")),
                ("schedule", models.JSONField(default=dict, verbose_name="调度配置")),
                ("collector_config", models.JSONField(default=dict, verbose_name="采集参数")),
                ("resource_guard_config", models.JSONField(default=dict, verbose_name="资源保护参数")),
            ],
            options={
                "verbose_name": "主动 Profiling 计划",
                "index_together": {("bk_biz_id", "is_deleted")},
            },
        ),
        migrations.CreateModel(
            name="ActiveProfilingHostExecution",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("execution_id", models.IntegerField(verbose_name="执行 ID")),
                ("bk_biz_id", models.IntegerField(verbose_name="业务 ID")),
                ("scheduled_at", models.BigIntegerField(verbose_name="执行计划时间")),
                ("bk_host_id", models.IntegerField(verbose_name="主机 ID")),
                ("ip", models.CharField(default="", max_length=64, verbose_name="执行时 IP")),
                ("status", models.CharField(max_length=32, verbose_name="主机执行状态")),
                ("started_at", models.BigIntegerField(null=True, verbose_name="开始时间")),
                ("finished_at", models.BigIntegerField(null=True, verbose_name="结束时间")),
                ("error_type", models.CharField(default="", max_length=32, verbose_name="失败类型")),
                ("message", models.TextField(default="", verbose_name="执行信息")),
                ("process_names", models.TextField(default="", verbose_name="进程名")),
                ("process_pids", models.TextField(default="", verbose_name="进程 PID")),
                ("processes", models.JSONField(default=list, verbose_name="采集进程")),
                ("event_time", models.BigIntegerField(verbose_name="生效 Event 时间")),
                ("unknown_at", models.BigIntegerField(null=True, verbose_name="转为 unknown 的时间")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "verbose_name": "主动 Profiling 主机执行",
                "unique_together": {("execution_id", "bk_host_id")},
                "index_together": {("bk_biz_id", "scheduled_at", "execution_id", "bk_host_id")},
            },
        ),
        migrations.CreateModel(
            name="ActiveProfilingExecution",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_tenant_id", models.CharField(default="system", max_length=64, verbose_name="租户 ID")),
                ("bk_biz_id", models.IntegerField(verbose_name="业务 ID")),
                ("schedule_type", models.CharField(max_length=16, verbose_name="执行方式")),
                ("task_id", models.IntegerField(default=0, verbose_name="任务 ID")),
                ("scheduled_at", models.BigIntegerField(verbose_name="执行计划时间")),
                ("task_name", models.CharField(max_length=128, verbose_name="任务名称")),
                ("creator", models.CharField(max_length=128, verbose_name="创建人")),
                ("collection_method", models.CharField(max_length=32, verbose_name="采集方式")),
                ("collection_type", models.CharField(max_length=32, verbose_name="采集类型")),
                ("execution_status", models.CharField(max_length=32, verbose_name="执行状态")),
                ("status_summary", models.JSONField(default=dict, verbose_name="主机状态计数")),
                ("target_count", models.IntegerField(default=0, verbose_name="主机数")),
                ("started_at", models.BigIntegerField(null=True, verbose_name="开始时间")),
                ("finished_at", models.BigIntegerField(null=True, verbose_name="结束时间")),
                ("config", models.JSONField(default=dict, verbose_name="执行配置")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "verbose_name": "主动 Profiling 执行",
                "unique_together": {("bk_tenant_id", "bk_biz_id", "task_id", "scheduled_at")},
                "index_together": {
                    ("bk_tenant_id", "bk_biz_id", "scheduled_at", "task_id"),
                    ("bk_tenant_id", "bk_biz_id", "execution_status", "scheduled_at", "task_id"),
                },
            },
        ),
    ]
