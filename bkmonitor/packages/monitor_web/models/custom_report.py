"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import re
import time
from typing import Any

from django.db import models
from django.utils.functional import cached_property

from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.utils.cipher import transform_data_id_to_token
from bkmonitor.utils.db import JsonField
from bkmonitor.utils.request import get_request_username
from bkmonitor.utils.user import get_backend_username
from constants.common import DEFAULT_TENANT_ID
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api
from monitor_web.constants import EVENT_TYPE
from monitor_web.models import OperateRecordModelBase
from monitor_web.custom_report.constants import CustomTSMetricType, DEFAULT_FIELD_SCOPE


class CustomEventGroup(OperateRecordModelBase):
    """
    自定义事件组
    """

    PLUGIN_TYPE_CHOICES = (
        (EVENT_TYPE.CUSTOM_EVENT, EVENT_TYPE.CUSTOM_EVENT),
        (EVENT_TYPE.KEYWORDS, EVENT_TYPE.KEYWORDS),
    )

    bk_tenant_id = models.CharField("租户ID", default=DEFAULT_TENANT_ID, db_index=True, max_length=128)
    bk_biz_id = models.IntegerField("业务ID", default=0, db_index=True)
    bk_event_group_id = models.IntegerField("事件分组ID", primary_key=True)
    bk_data_id = models.IntegerField("数据ID")
    name = models.CharField("名称", max_length=128)
    scenario = models.CharField("监控场景", max_length=128, db_index=True)
    is_enable = models.BooleanField("是否启用", default=True)
    table_id = models.CharField("结果表ID", max_length=128, default="")
    type = models.CharField("事件组类型", max_length=128, choices=PLUGIN_TYPE_CHOICES, default="custom_event")
    is_platform = models.BooleanField("平台级", default=False)
    data_label = models.CharField("数据标签", max_length=128, default="")

    def __str__(self):
        return f"{self.name}"  # noqa

    def query_target(self):
        tag_values = api.metadata.query_tag_values(table_id=self.table_id, tag_name="target")
        return tag_values["tag_values"]

    def metric_detail(self):
        return []


class CustomEventItem(models.Model):
    """
    自定义事件定义
    """

    bk_event_group = models.ForeignKey(
        CustomEventGroup, verbose_name="事件分组ID", related_name="event_info_list", on_delete=models.CASCADE
    )
    custom_event_id = models.IntegerField("事件ID", primary_key=True)
    custom_event_name = models.CharField("名称", max_length=128)
    dimension_list = JsonField("维度", default=[])


class CustomTSField(models.Model):
    """
    [deprecated]自定义时序字段
    """

    METRIC_TYPE_CHOICES = (
        ("metric", "指标"),
        ("dimension", "维度"),
    )

    class MetricType:
        METRIC = "metric"
        DIMENSION = "dimension"

    MetricConfigFields = ["unit", "hidden", "aggregate_method", "function", "interval", "label", "dimensions"]
    DimensionConfigFields = ["common", "hidden"]

    time_series_group_id = models.IntegerField("时序分组ID")
    type = models.CharField("字段类型", max_length=16, choices=METRIC_TYPE_CHOICES, default=MetricType.METRIC)
    name = models.CharField("字段名称", max_length=128)
    description = models.CharField("字段描述", max_length=128, default="")
    disabled = models.BooleanField("禁用字段", default=False)
    config = models.JSONField("字段配置", default=dict)

    create_time = models.DateTimeField("创建时间", auto_now_add=True, null=True)
    update_time = models.DateTimeField("修改时间", auto_now=True, null=True)


class CustomTSTable(OperateRecordModelBase):
    """
    自定义时序
    """

    PROTOCOL_CHOICES = (
        ("json", "Json"),
        ("prometheus", "Prometheus"),
    )

    bk_tenant_id = models.CharField("租户ID", max_length=128, default=DEFAULT_TENANT_ID)
    time_series_group_id = models.IntegerField("时序分组ID", primary_key=True)
    bk_data_id = models.IntegerField("数据ID")
    bk_biz_id = models.IntegerField("业务ID", default=0, db_index=True)
    name = models.CharField("名称", max_length=128)
    scenario = models.CharField("监控场景", max_length=128, db_index=True)
    table_id = models.CharField("结果表ID", max_length=128, default="")
    is_platform = models.BooleanField("平台级", default=False)
    data_label = models.CharField("数据标签", max_length=128, default="")
    protocol = models.CharField("上报协议", max_length=128, default="json", choices=PROTOCOL_CHOICES)
    desc = models.CharField("说明", max_length=1024, default="", blank=True)
    auto_discover = models.BooleanField("自动发现", default=True)

    def __str__(self):
        return f"[{self.bk_biz_id}]{self.table_id}-{self.bk_data_id}"

    @property
    def token(self):
        if self.protocol == "prometheus":
            params = {
                "metric_data_id": self.bk_data_id,
                "bk_biz_id": self.bk_biz_id,
                "app_name": self.name,
            }
            return transform_data_id_to_token(**params)
        else:
            data_id_info = api.metadata.get_data_id({"bk_data_id": self.bk_data_id, "with_rt_info": False})
            return data_id_info["token"]

    # 计划移除，应该不存在这个问题了
    def save_to_metadata(self):
        """
        保存 metadata 信息
        """
        request_params = {
            "operator": get_request_username() or get_backend_username(),
            "time_series_group_id": self.time_series_group_id,
            "time_series_group_name": self.name,
            "label": self.scenario,
            "data_label": self.data_label,
            "enable_field_black_list": self.auto_discover,
        }

        api.metadata.modify_time_series_group(request_params)

    def get_metrics(self) -> dict[tuple[str, str, str], dict]:
        """获取指标/维度信息

        Returns:
        字典，键为 (scope_name, 字段类型，字段名称) 元组，值为指标详细信息字典
        """

        dimension_alias_map: dict[tuple[str, str], str] = {}
        field_map: dict[tuple[str, str, str], dict[str, Any]] = {}
        for scope_dict in self.query_time_series_scope:
            scope_name: str = scope_dict["scope_name"]
            for dimension_name, dimension_config in scope_dict.get("dimension_config", {}).items():
                dimension_alias: str = dimension_config.get("alias", "")
                dimension_alias_map[(scope_name, dimension_name)] = dimension_alias
                field_map[(scope_name, CustomTSMetricType.DIMENSION, dimension_name)] = {
                    "scope_name": scope_name,
                    "name": dimension_name,
                    "monitor_type": CustomTSMetricType.DIMENSION,
                    "unit": "",
                    "description": dimension_alias,
                    "type": CustomTSMetricType.DIMENSION,
                    "aggregate_method": "",
                }
            for metric_dict in scope_dict["metric_list"]:
                metric_name: str = metric_dict["metric_name"]
                metric_config: dict[str, Any] = metric_dict.get("field_config", {})
                if metric_config.get("disabled"):
                    continue
                field_map[(scope_name, CustomTSMetricType.METRIC, metric_name)] = {
                    "scope_name": scope_name,
                    "name": metric_name,
                    "monitor_type": CustomTSMetricType.METRIC,
                    "unit": metric_config.get("unit", ""),
                    "description": metric_config.get("alias", ""),
                    "type": CustomTSMetricType.METRIC,
                    "aggregate_method": metric_config.get("aggregate_method", ""),
                    "dimension_list": [
                        {"id": dimension_name, "name": dimension_alias_map.get((scope_name, dimension_name), "")}
                        for dimension_name in metric_dict.get("tag_list", [])
                    ],
                    "label": [scope_name],
                    "field_scope": metric_dict.get("field_scope", DEFAULT_FIELD_SCOPE),
                }
        return field_map

    def query_target(self, bk_biz_id: int) -> list:
        """
        查询 target 维度字段
        """
        metric_name: str = ""
        for scope_dict in self.query_time_series_scope:
            metric_list: list[dict[str, Any]] = scope_dict.get("metric_list", [])
            if metric_list:
                metric_name = metric_list[0]["metric_name"]
                break
        if not metric_name:
            return []

        data_source_class = load_data_source(DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES)
        data_source = data_source_class(
            bk_biz_id=bk_biz_id,
            **{
                "table": self.table_id,
                "data_label": self.data_label,
                "group_by": ["target"],
                "metrics": [{"field": metric_name}],
            },
        )
        query = UnifyQuery(bk_biz_id=bk_biz_id, data_sources=[data_source], expression="")

        # todo: 后续改完指定时间段查询后，需要修改此处
        now = int(time.time())

        values = query.query_dimensions(
            dimension_field="target",
            limit=5000,
            start_time=(now - 60 * 60 * 24) * 1000,
            end_time=now * 1000,
        )
        if not values or "values" not in values:
            return []
        return values["values"]["target"]

    @cached_property
    def query_time_series_scope(self) -> list[dict[str, Any]]:
        return api.metadata.query_time_series_scope(group_id=self.time_series_group_id, include_metrics=True)


class CustomTSItem(models.Model):
    """
    自定义时序指标(legacy)
    """

    table = models.ForeignKey(
        CustomTSTable, verbose_name="自定义时序ID", related_name="metric_list", default=0, on_delete=models.CASCADE
    )
    metric_name = models.CharField("指标名称", max_length=128)
    type = models.CharField("类型", max_length=16, default="")
    label = JsonField("分组标签", default=list, blank=False)

    unit = models.CharField("字段单位", max_length=16, default="")
    metric_display_name = models.CharField("指标别名", max_length=128, default="")
    dimension_list = JsonField("维度", default=list)
    hidden = models.BooleanField("隐藏指标", default=False)
    disabled = models.BooleanField("禁用指标", default=False)
    interval = models.IntegerField("指标周期", default=0)
    aggregate_method = models.CharField("默认聚合方法", max_length=128, default="")
    # {"function": "top", "params": {}}
    function = models.JSONField("指标函数", default=dict)


class CustomTSGroupingRule(models.Model):
    """
    [deprecated]自定义时序指标分组规则
    """

    index = models.IntegerField("排序", default=0)
    name = models.CharField("分组名称", max_length=128)
    time_series_group_id = models.IntegerField("时序分组ID")
    manual_list = JsonField("手动分组的指标列表", default=[])
    auto_rules = JsonField("自动分组的匹配规则列表", default=[])

    def to_json(self):
        return {
            "name": self.name,
            "time_series_group_id": self.time_series_group_id,
            "manual_list": self.manual_list,
            "auto_rules": self.auto_rules,
        }

    def match_metric(self, metric_name: str):
        """
        匹配指标
        """
        # 手动分组
        if metric_name in self.manual_list:
            return True

        # 自动分组
        for rule in self.auto_rules:
            if re.match(rule, metric_name):
                return True
        return False
