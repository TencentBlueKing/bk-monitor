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

from django.db import models

from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.utils.cipher import transform_data_id_to_token
from bkmonitor.utils.db import JsonField
from bkmonitor.utils.request import get_request_username
from bkmonitor.utils.user import get_backend_username
from constants.common import DEFAULT_TENANT_ID
from constants.data_source import DataSourceLabel, DataTypeLabel, METRIC_TYPE_CHOICES, MetricType
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
    自定义时序字段
    """

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

    def save_to_metadata(self, with_fields=False):
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

        # 如果没有开启自动发现，才需要设置指标维度
        if with_fields:
            fields = CustomTSField.objects.filter(time_series_group_id=self.time_series_group_id)
            request_params["field_list"] = [
                {
                    "field_name": field.name,
                    "tag": field.type,
                    "field_type": "string" if field.type == "dimension" else "float",
                    "description": field.description,
                    "unit": field.config.get("unit", ""),
                    "is_disabled": field.disabled,
                }
                for field in fields
            ]

        api.metadata.modify_time_series_group(request_params)

    def get_and_sync_fields(self) -> list[CustomTSField]:
        """
        获取并同步指标信息
        1. 在查询自定义指标的指标/维度列表时，尝试从 metadata 中获取指标/维度列表，并写入到 CustomTSField中
        2. 同步时只增不删，除非用户手动删除
        3. 同步需要设置时间间隔，避免过于频繁请求
        4. 当开启自动发现时，修改指标信息不需要向 metadata 同步，反之则需要同步
        """
        # 获取当前指标/维度集合
        fields: dict[tuple[str, str], CustomTSField] = {
            (item.name, item.type): item
            for item in CustomTSField.objects.filter(time_series_group_id=self.time_series_group_id)
        }

        # 获取 metadata
        results = api.metadata.get_time_series_group(time_series_group_id=self.time_series_group_id)

        # 计算需要补充指标/维度
        need_create_fields: list[CustomTSField] = []
        need_update_fields: list[CustomTSField] = []
        for result in results:
            for metric_info in result["metric_info_list"]:
                # 指标信息同步，为了向前兼容
                dimensions = sorted([tag["field_name"] for tag in metric_info["tag_list"]])
                metric = fields.get((metric_info["field_name"], "")) or fields.get(
                    (metric_info["field_name"], MetricType.METRIC)
                )
                if not metric:
                    # 新建指标
                    metric = CustomTSField(
                        time_series_group_id=self.time_series_group_id,
                        name=metric_info["field_name"],
                        type=MetricType.METRIC,
                        config={
                            "dimensions": dimensions,
                            "unit": metric_info["unit"],
                            "label": [],
                        },
                        description=metric_info["description"],
                        disabled=metric_info["is_disabled"],
                    )
                    need_create_fields.append(metric)
                else:
                    changed = False

                    # 指标信息同步
                    if not metric.type:
                        metric.type = MetricType.METRIC
                        changed = True

                    if not metric.config.get("unit") and metric_info.get("unit"):
                        metric.config["unit"] = metric_info["unit"]
                        changed = True

                    if not metric.description and metric_info.get("description"):
                        metric.description = metric_info["description"]
                        changed = True

                    # 维度变化
                    if dimensions != metric.config.get("dimensions", []):
                        metric.config["dimensions"] = dimensions
                        changed = True

                    # 需要更新
                    if changed:
                        need_update_fields.append(metric)

                # 兼容旧的字段
                if (metric.name, "") in fields:
                    fields.pop((metric.name, ""))
                fields[(metric.name, metric.type)] = metric

                # 遍历维度
                for tag in metric_info["tag_list"]:
                    # 需要补充的维度
                    if (tag["field_name"], MetricType.DIMENSION) not in fields:
                        item = CustomTSField(
                            time_series_group_id=self.time_series_group_id,
                            name=tag["field_name"],
                            type=MetricType.DIMENSION,
                            description=tag["description"],
                        )
                        # 添加维度字段
                        need_create_fields.append(item)
                        fields[(tag["field_name"], MetricType.DIMENSION)] = item
                    else:
                        # 如果存在维度别名不为空，则更新
                        item = fields[(tag["field_name"], MetricType.DIMENSION)]
                        if item.description == "" and tag["description"]:
                            item.description = tag["description"]
                            need_update_fields.append(item)

        if need_create_fields:
            # 获取分组规则
            group_rules = CustomTSGroupingRule.objects.filter(time_series_group_id=self.time_series_group_id)

            # 对新增指标进行分组匹配
            for field in need_create_fields:
                # 跳过维度
                if field.type == MetricType.DIMENSION:
                    continue

                labels = []
                for group in group_rules:
                    if group.match_metric(field.name):
                        labels.append(group.name)
                field.config["label"] = sorted(labels)

            # 批量创建
            CustomTSField.objects.bulk_create(need_create_fields, batch_size=500)

        # 批量更新
        if need_update_fields:
            CustomTSField.objects.bulk_update(
                need_update_fields,
                ["config", "description", "disabled", "type"],
                batch_size=500,
            )

        return list(fields.values())

    def renew_metric_labels(self, group_rules: list["CustomTSGroupingRule"], delete=False, clean=False):
        """
        更新指标标签
        """
        # 获取当前指标标签
        fields = CustomTSField.objects.filter(time_series_group_id=self.time_series_group_id, type=MetricType.METRIC)
        updated_fields = []
        for field in fields:
            # 清空标签
            if clean:
                labels = []
            else:
                labels = field.config.get("label", []).copy()

            for group_rule in group_rules:
                if not delete and group_rule.match_metric(field.name):
                    if group_rule.name not in labels:
                        labels.append(group_rule.name)
                else:
                    if group_rule.name in labels:
                        labels.remove(group_rule.name)

            # 排序
            labels = sorted(labels)

            # 如果分组名称变更，则需要更新
            if labels != field.config.get("label"):
                field.config["label"] = labels
                updated_fields.append(field)

        # 批量更新
        if updated_fields:
            CustomTSField.objects.bulk_update(updated_fields, ["config"], batch_size=500)

    def get_metrics(self) -> dict[str, dict]:
        """
        获取指标/维度信息
        """
        fields = self.get_and_sync_fields()
        dimension_names: dict[str, str] = {
            dimension.name: dimension.description
            for dimension in CustomTSField.objects.filter(
                time_series_group_id=self.time_series_group_id, type=MetricType.DIMENSION
            )
        }

        field_map = {}
        for field in fields:
            field_map[field.name] = {
                "name": field.name,
                "monitor_type": field.type,
                "unit": field.config.get("unit", ""),
                "description": field.description,
                "type": field.type,
                "aggregate_method": field.config.get("aggregate_method", ""),
            }

            if field.type == MetricType.METRIC:
                field_map[field.name].update(
                    {
                        "dimension_list": [
                            {"id": dimension, "name": dimension_names[dimension]}
                            for dimension in field.config.get("dimensions", [])
                        ],
                        "label": field.config.get("label", []),
                    }
                )
        return field_map

    def query_target(self, bk_biz_id: int) -> list:
        """
        查询 target 维度字段
        """
        metric = CustomTSField.objects.filter(
            time_series_group_id=self.time_series_group_id, type=MetricType.METRIC
        ).first()
        if not metric:
            return []

        data_source_class = load_data_source(DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES)
        data_source = data_source_class(
            bk_biz_id=bk_biz_id,
            **{
                "table": self.table_id,
                "data_label": self.data_label,
                "group_by": ["target"],
                "metrics": [{"field": metric.name}],
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
    自定义时序指标分组规则
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
