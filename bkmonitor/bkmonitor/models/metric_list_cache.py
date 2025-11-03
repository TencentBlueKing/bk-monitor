"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from django.db import models
from django.utils.translation import gettext_lazy as _

from bkmonitor.utils.common_utils import safe_int
from bkmonitor.utils.db.fields import JsonField
from bkmonitor.utils.request import get_request
from constants.common import DEFAULT_TENANT_ID
from constants.data_source import DataSourceLabel, DataTypeLabel
from metadata.models import TimeSeriesGroup

logger = logging.getLogger(__name__)


class MetricListCacheManager(models.Manager):
    """指标选择器缓存管理器"""

    def get_queryset(self):
        queryset = super().get_queryset()
        # 过滤重名内置指标，目前仅针对容器指标处理
        # 从request中获取业务id，获取不到则返回原queryset
        request = get_request(peaceful=True)
        if not request:
            return queryset
        if request.biz_id:
            if not queryset.filter(bk_biz_id=0, result_table_id="").exists():
                return queryset
            # 过滤出该查询条件下该业务与0业务的重名指标
            duplicate_metrics = list(
                queryset.filter(is_duplicate=1, bk_biz_id=safe_int(request.biz_id), result_table_id="").values_list(
                    "metric_field", flat=1
                )
            )
            # 过滤出该查询条件下0业务的重名指标
            if not duplicate_metrics:
                return queryset
            # 原queryset排除0业务下的重名指标
            queryset = queryset.exclude(bk_biz_id=0, metric_field__in=duplicate_metrics, result_table_id="")
        return queryset


class MetricListCache(models.Model):
    """
    指标选择器缓存表
    """

    BUILTIN_TERMS = [
        "apache",
        "beat_monitor",
        "gse_event_report_base",
        "mysql",
        "nginx",
        "pingserver",
        "redis",
        "system",
        "tomcat",
        "uptimecheck",
        "process",
        "agentmetric",
    ]

    bk_tenant_id = models.CharField(max_length=128, default=DEFAULT_TENANT_ID, verbose_name="租户ID")
    bk_biz_id = models.IntegerField(verbose_name="业务ID", db_index=True)
    result_table_id = models.CharField(max_length=256, default="", verbose_name="sql查询表")
    result_table_name = models.CharField(max_length=256, default="", verbose_name="表别名")
    metric_field = models.CharField(max_length=256, default="", verbose_name="指标名")
    metric_field_name = models.CharField(max_length=256, default="", verbose_name="指标别名")
    unit = models.CharField(max_length=256, default="", verbose_name="单位")
    unit_conversion = models.FloatField(default=1.0, verbose_name="单位换算")
    dimensions = JsonField(default=[], verbose_name="维度名")
    plugin_type = models.CharField(max_length=256, default="", verbose_name="插件类型")
    related_name = models.CharField(max_length=256, default="", verbose_name="插件名、拨测任务名")
    related_id = models.CharField(max_length=256, default="", verbose_name="插件id、拨测任务id")
    collect_config = models.TextField(default="", verbose_name="插件采集关联采集配置")
    collect_config_ids = JsonField(verbose_name="插件采集关联采集配置id")
    result_table_label = models.CharField(max_length=128, verbose_name="表标签")
    data_source_label = models.CharField(max_length=128, verbose_name="数据源标签")
    data_type_label = models.CharField(max_length=128, verbose_name="数据类型标签")
    data_target = models.CharField(max_length=128, verbose_name="数据目标标签")
    default_dimensions = JsonField(verbose_name="默认维度列表")
    default_condition = JsonField(verbose_name="默认监控条件")
    description = models.TextField(default="", verbose_name="指标含义")
    collect_interval = models.IntegerField(default=1, verbose_name="指标采集周期")
    category_display = models.CharField(max_length=128, default="", verbose_name="分类显示名")
    result_table_label_name = models.CharField(max_length=255, default="", verbose_name="表标签别名")
    extend_fields = JsonField(default={}, verbose_name="额外字段")
    use_frequency = models.IntegerField(default=0, verbose_name="使用频率")
    last_update = models.DateTimeField(auto_now=True, verbose_name="最近更新时间", db_index=True)
    is_duplicate = models.IntegerField(default=0, verbose_name="是否重名")
    readable_name = models.CharField(verbose_name="指标可读名", max_length=255, null=True, blank=True, db_index=True)
    metric_md5 = models.CharField(verbose_name="指标MD5", max_length=255, null=True, blank=True)
    data_label = models.CharField(max_length=256, default="", verbose_name="db标识")

    objects = MetricListCacheManager()

    class Meta:
        index_together = (
            ("bk_tenant_id", "bk_biz_id"),
            ("result_table_id", "metric_field", "bk_biz_id"),
            ("data_type_label", "data_source_label", "bk_biz_id"),
            ("data_label", "metric_field", "bk_biz_id"),
        )

    @classmethod
    def item_description(cls, item):
        """
        策略监控项说明
        """
        templates = {
            DataSourceLabel.BK_MONITOR_COLLECTOR: {
                DataTypeLabel.TIME_SERIES: "{item_name}({result_table_id}.{metric_field})",
                DataTypeLabel.EVENT: "{item_name}",
                DataTypeLabel.LOG: "{item_name}",
            },
            DataSourceLabel.BK_DATA: {
                DataTypeLabel.TIME_SERIES: "{metric_field_name}({result_table_id}.{metric_field})",
            },
            DataSourceLabel.BK_LOG_SEARCH: {
                DataTypeLabel.TIME_SERIES: _("{metric_field}(索引集:{item_name})"),
                DataTypeLabel.LOG: _("{keywords_query_string}(索引集:{item_name})"),
            },
            DataSourceLabel.CUSTOM: {
                DataTypeLabel.EVENT: _("{item_name}(数据ID:{result_table_id})"),
                DataTypeLabel.TIME_SERIES: "{item_name}({result_table_id}.{metric_field})",
            },
        }

        params = {
            "metric_field": item.get("metric_field", ""),
            "metric_field_name": item.get("metric_field_name", ""),
            "result_table_id": item.get("data_label", "") or item.get("result_table_id", ""),
            "item_name": item.get("item_name", ""),
            "keywords_query_string": item.get("keywords_query_string", ""),
        }

        return templates[item["data_source_label"]][item["data_type_label"]].format(**params)

    @classmethod
    def metric_description(cls, item=None, metric=None):
        """
        指标说明
        :param item: 监控指标配置
        :type item: dict
        :return: 指标说明
        :type: str
        """
        templates = {
            DataSourceLabel.BK_MONITOR_COLLECTOR: {
                DataTypeLabel.TIME_SERIES: _(
                    "指标：{metric_field}；指标分类：{result_table_name}；插件名：{related_name}；数据来源：监控采集"
                ),
                DataTypeLabel.EVENT: _("数据来源：系统事件"),
                DataTypeLabel.LOG: _("数据来源：采集配置"),
                DataTypeLabel.ALERT: _("数据来源：监控策略"),
            },
            DataSourceLabel.BK_DATA: {
                DataTypeLabel.TIME_SERIES: _("指标：{metric_field}；结果表：{result_table_name}；数据来源：计算平台"),
            },
            DataSourceLabel.BK_LOG_SEARCH: {
                DataTypeLabel.TIME_SERIES: _("索引：{result_table_name}；索引集：{related_name}；数据来源：日志平台"),
                DataTypeLabel.LOG: _("数据来源：日志平台"),
            },
            DataSourceLabel.CUSTOM: {
                DataTypeLabel.EVENT: _(
                    "数据ID：{result_table_id}；数据名称：{result_table_name}；数据来源：自定义事件"
                ),
                DataTypeLabel.TIME_SERIES: _(
                    "指标：{metric_field_name}；数据名称：{related_name}；数据来源：自定义时序"
                ),
            },
            DataSourceLabel.BK_FTA: {
                DataTypeLabel.EVENT: _("数据来源：故障自愈第三方告警"),
                DataTypeLabel.ALERT: _("数据来源：故障自愈第三方告警"),
            },
        }

        if item:
            template = templates.get(item["data_source_label"], {}).get(item["data_type_label"], "")

            if (item["data_source_label"], item["data_type_label"]) in [
                (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG),
                (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG),
                (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.EVENT),
            ]:
                return template
            if not item.get("result_table_id"):
                rt_id = ".".join(item["metric_id"].split(".")[-2:])
            else:
                rt_id = item.get("result_table_id", "")
            metric = cls.objects.filter(
                data_source_label=item["data_source_label"],
                data_type_label=item["data_type_label"],
                result_table_id=rt_id,
                metric_field=item["metric_id"].split(".")[-1],
            )

            if not metric:
                return ""
            metric = metric[0]
        elif metric:
            template = templates.get(metric.data_source_label, {}).get(metric.data_type_label, "")
        else:
            return ""

        if (
            metric.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
            and metric.data_type_label == DataTypeLabel.TIME_SERIES
            and metric.result_table_label == "uptimecheck"
        ):
            template = _("指标：{metric_field}；指标分类：{result_table_name}；数据来源：监控采集")

        return template.format(**metric.__dict__)

    def save(self, *args, **kwargs):
        """当可读名不存在时添加"""
        if not self.readable_name:
            self.readable_name = self.get_human_readable_name()

        super().save(*args, **kwargs)

    @property
    def is_already_readable(self) -> bool:
        """判断当前指标名是否已经可读"""
        parts = self.result_table_readable_name.split(".")

        # 容器指标通常是没有 result_table_id，不需要二段式改造
        if len(parts) <= 2:
            return True

        # 系统内置指标也不做二段式处理
        if parts[0] in self.BUILTIN_TERMS:
            return True

        return False

    @property
    def result_table_readable_name(self):
        """使用 result_table 拼接的可读名"""
        return ".".join(x for x in [self.result_table_id, self.metric_field] if x)

    def get_human_readable_name(self) -> str:
        """获取可读的指标名"""

        # 系统内置指标 & 容器指标
        if self.is_already_readable:
            # 保持和原来前端拼接的方式一致
            return self.result_table_readable_name

        # 支持指标二段式的指标：插件采集 & 自定义上报
        if self.data_label:
            return f"{self.data_label}.{self.metric_field}"

        # 插件采集指标
        if self.plugin_type:
            return f"{self.related_id}.{self.metric_field}"

        # table_id 基于物理存储的 {db}.{measurement} 定义
        # 自定义指标上报的内置指标都是同一个dataID上报的数据，因此不会出现重名的指标
        # 所以 measurement 可以被删减掉
        db = self.result_table_id.split(".")[0]
        if TimeSeriesGroup.objects.filter(table_id__startswith=db).exists():
            return f"{db}.{self.metric_field}"

        return self.result_table_readable_name
