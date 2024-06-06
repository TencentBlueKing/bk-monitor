# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import re
import time
from typing import Any, Dict, List

from django.db import models

from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.utils.cipher import transform_data_id_to_token
from bkmonitor.utils.db import JsonField
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api
from monitor_web.constants import EVENT_TYPE
from monitor_web.models import OperateRecordModelBase


class CustomEventGroup(OperateRecordModelBase):
    """
    自定义事件组
    """

    PLUGIN_TYPE_CHOICES = (
        (EVENT_TYPE.CUSTOM_EVENT, EVENT_TYPE.CUSTOM_EVENT),
        (EVENT_TYPE.KEYWORDS, EVENT_TYPE.KEYWORDS),
    )

    bk_event_group_id = models.IntegerField("事件分组ID", primary_key=True)
    bk_data_id = models.IntegerField("数据ID")
    bk_biz_id = models.IntegerField("业务ID", default=0, db_index=True)
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


class CustomTSTable(OperateRecordModelBase):
    """
    自定义时序
    """

    PROTOCOL_CHOICES = (
        ("json", "Json"),
        ("prometheus", "Prometheus"),
    )

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

    def metric_detail(self):
        custom_ts_items: List[Dict[str, Any]] = []
        params = {
            "time_series_group_id": self.time_series_group_id,
        }
        results = api.metadata.get_time_series_group(params)
        # 查询数据库记录以确定指标的分组标签
        old_metrics = CustomTSItem.objects.filter(table=self).only("metric_name", "label")
        metric_labels = {metric.metric_name: metric.label for metric in old_metrics}
        groups = CustomTSGroupingRule.objects.filter(**params)

        metric_names = []
        for result in results:
            for metric in result["metric_info_list"]:
                if not metric:
                    continue

                # 新增指标进行分组匹配
                if metric["field_name"] not in metric_labels:
                    metric_label = set()
                    for group in groups:
                        if metric["field_name"] in group.manual_list:
                            metric_label.add(group.name)
                        for rule in group.auto_rules:
                            if re.match(rule, metric["field_name"]):
                                metric_label.add(group.name)

                    CustomTSItem.objects.create(metric_name=metric["field_name"], table=self, label=list(metric_label))
                else:
                    metric_label = metric_labels[metric["field_name"]]

                metric_names.append(metric["field_name"])
                group_info = {
                    "table": self,
                    "metric_name": metric["field_name"],
                    "unit": metric["unit"],
                    "type": metric["type"],
                    "metric_display_name": metric["description"],
                    "dimension_list": metric["tag_list"],
                    "label": list(metric_label),
                }

                custom_ts_items.append(group_info)

        # 清理不存在的指标记录
        need_clean_metric_names = set(metric_labels.keys()) - set(metric_names)
        CustomTSItem.objects.filter(table=self, metric_name__in=need_clean_metric_names).delete()

        return custom_ts_items

    def get_metrics(self):
        field_map = {}
        for metric_info in self.metric_detail():
            if metric_info["metric_name"] not in field_map:
                field_map[metric_info["metric_name"]] = {
                    "name": metric_info["metric_name"],
                    "monitor_type": "metric",
                    "unit": metric_info["unit"],
                    "description": metric_info["metric_display_name"],
                    "type": metric_info["type"],
                    "dimension_list": [
                        {"id": dimension["field_name"], "name": dimension["description"]}
                        for dimension in metric_info["dimension_list"]
                    ],
                    "label": metric_info["label"],
                }
            for dimension in metric_info["dimension_list"]:
                if dimension["field_name"] not in field_map:
                    field_map[dimension["field_name"]] = {
                        "name": dimension["field_name"],
                        "monitor_type": "dimension",
                        "unit": "",
                        "description": dimension["description"],
                        "type": "string",
                    }
        return field_map

    def query_target(self, bk_biz_id: int):
        metric = CustomTSItem.objects.filter(table=self).first()
        if not metric:
            return []

        data_source_class = load_data_source(DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES)
        data_source = data_source_class(
            bk_biz_id=bk_biz_id,
            **{
                "table": self.table_id,
                "data_label": self.data_label,
                "group_by": ["target"],
                "metrics": [{"field": metric.metric_name}],
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

    def query_dimensions(self, metric):
        metric_info = self.metric_list.filter(metric_name=metric).first()
        if not metric_info:
            for field in self.metric_detail():
                if field["metric_name"] == metric:
                    dimension_list = field["dimension_list"]
                    break
            else:
                dimension_list = []
        else:
            dimension_list = metric_info.dimension_list
        dimensions = [dimension["field_name"] for dimension in dimension_list if dimension["field_name"] != "target"]
        return dimensions


class CustomTSItem(models.Model):
    """
    自定义时序指标
    """

    table = models.ForeignKey(
        CustomTSTable, verbose_name="自定义时序ID", related_name="metric_list", default=0, on_delete=models.CASCADE
    )
    metric_name = models.CharField("指标名称", max_length=128)
    type = models.CharField("类型", max_length=16, default="")
    unit = models.CharField("字段单位", max_length=16, default="")
    metric_display_name = models.CharField("指标别名", max_length=128, default="")
    dimension_list = JsonField("维度", default=[])
    label = JsonField("分组标签", default=[], blank=False)
    hidden = models.BooleanField("隐藏图表", default=False)


class CustomTSGroupingRule(models.Model):
    """
    自定义时序指标分组规则
    """

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
