"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db import models


class MediumBlobField(models.BinaryField):
    """取值 ID 列表使用 MEDIUMBLOB，最大容量为 16 MiB。"""

    def db_type(self, connection):
        if connection.vendor == "mysql":
            return "mediumblob"
        return super().db_type(connection)


class TimeSeriesReportValue(models.Model):
    """数据源内按内容去重的指标上报元信息。"""

    id = models.BigAutoField(primary_key=True)
    group_id = models.IntegerField(verbose_name="自定义时序数据源ID")
    field_name = models.CharField(verbose_name="实际指标名", max_length=255, db_collation="utf8_bin")
    fingerprint = models.CharField(verbose_name="元信息指纹", max_length=32, db_collation="ascii_bin")
    original_name = models.CharField(verbose_name="拆分前指标原名", max_length=255, db_collation="utf8_bin")
    original_type = models.CharField(verbose_name="原始指标类型", max_length=16)
    metric_type = models.CharField(verbose_name="实际序列类型", max_length=16)
    meta = models.JSONField(verbose_name="上报元信息", null=True)
    scope_count = models.IntegerField(verbose_name="引用的上报范围数", default=0)

    class Meta:
        verbose_name = "自定义时序指标上报取值"
        verbose_name_plural = "自定义时序指标上报取值表"
        constraints = [
            models.UniqueConstraint(fields=["group_id", "field_name", "fingerprint"], name="tsrv_group_field_fp_uniq")
        ]
        indexes = [
            models.Index(fields=["group_id", "original_name"], name="tsrv_group_original_idx"),
            models.Index(fields=["group_id", "scope_count"], name="tsrv_group_count_idx"),
        ]


class TimeSeriesReportScope(models.Model):
    """一个实际上报来源及其当前引用的取值 ID，与页面分组无关。"""

    id = models.BigAutoField(primary_key=True)
    group_id = models.IntegerField(verbose_name="自定义时序数据源ID")
    scope_hash = models.CharField(verbose_name="上报范围指纹", max_length=32, db_collation="ascii_bin")
    scope_type = models.CharField(verbose_name="上报范围类型", max_length=32)
    labels = models.JSONField(verbose_name="上报范围标签", null=True)
    raw_scope = models.CharField(verbose_name="采集器原始范围", max_length=512)
    # uint32 小端序、去重升序排列，每个 ID 占 4 字节，不含表头。
    report_value_ids = MediumBlobField(verbose_name="上报取值ID列表")
    value_count = models.IntegerField(verbose_name="上报取值数", default=0)
    last_seen = models.DateTimeField(verbose_name="最后上报时间")
    version = models.IntegerField(verbose_name="并发更新版本", default=0)

    class Meta:
        verbose_name = "自定义时序指标上报范围"
        verbose_name_plural = "自定义时序指标上报范围表"
        constraints = [models.UniqueConstraint(fields=["group_id", "scope_hash"], name="tsrs_group_hash_uniq")]
        indexes = [models.Index(fields=["group_id", "last_seen"], name="tsrs_group_seen_idx")]


class TimeSeriesMetricOverride(models.Model):
    """全局、服务或服务加 scope 范围内的用户配置，未设置的键继承上一级。"""

    id = models.BigAutoField(primary_key=True)
    group_id = models.IntegerField(verbose_name="自定义时序数据源ID")
    selector_hash = models.CharField(verbose_name="选择器指纹", max_length=32, db_collation="ascii_bin")
    selector = models.JSONField(verbose_name="配置选择器", null=True)
    field_name = models.CharField(verbose_name="实际指标名", max_length=255, db_collation="utf8_bin")
    field_config = models.JSONField(verbose_name="用户覆盖配置", null=True)
    # NULL 继承上一级，其他值关联 TimeSeriesScope.id；禁用标记保存在 field_config 中。
    scope_id = models.IntegerField(verbose_name="页面分组ID", null=True)

    class Meta:
        verbose_name = "自定义时序指标用户覆盖"
        verbose_name_plural = "自定义时序指标用户覆盖表"
        constraints = [
            models.UniqueConstraint(
                fields=["group_id", "selector_hash", "field_name"], name="tsmo_group_selector_field_uniq"
            )
        ]
