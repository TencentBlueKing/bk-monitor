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
import re
import time
from typing import Any

from django.db.models import Max, Q, QuerySet
from django.utils.translation import gettext as _
from rest_framework import serializers

from bkm_space.api import SpaceApi
from bkm_space.define import Space, SpaceTypeEnum
from bkm_space.utils import bk_biz_id_to_space_uid
from bkmonitor.models import BCSCluster, MetricListCache
from bkmonitor.utils.request import get_request_tenant_id
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import Resource
from fta_web.alert.handlers.alert import AlertQueryHandler

logger = logging.getLogger(__name__)


class GetDataSourceConfigResource(Resource):
    """
    获取数据源配置信息
    """

    _TABLE_ALIAS_MAP: dict[str, str] = {"gse_system_event": _("主机事件")}

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        data_source_label = serializers.CharField(label="数据来源")
        data_type_label = serializers.CharField(label="数据类型")
        # 对于不需要返回维度数据的场景，设置 return_dimensions=false，减少接口返回
        return_dimensions = serializers.BooleanField(label="是否返回维度", default=True)

    @classmethod
    def _fetch_metrics(cls, qs: QuerySet[MetricListCache]) -> list[dict[str, Any]]:
        return list(
            qs.values(
                "bk_biz_id",
                "result_table_id",
                "result_table_name",
                "related_name",
                "extend_fields",
                "dimensions",
                "metric_field",
                "metric_field_name",
            )
        )

    @classmethod
    def _fetch_metrics_without_dimensions(cls, qs: QuerySet[MetricListCache]) -> list[dict[str, Any]]:
        metric_row_ids = list(
            metric_info["max_id"] for metric_info in qs.values("result_table_id").annotate(max_id=Max("id")).order_by()
        )
        return cls._fetch_metrics(qs.filter(id__in=metric_row_ids))

    def perform_request(self, validated_request_data: dict[str, Any]):
        bcs_cluster_id_match_regex = r"\((?P<bcs_cluster_id>BCS-K8S-\d{5})\)$"
        data_source_label = validated_request_data["data_source_label"]
        data_type_label = validated_request_data["data_type_label"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        target_cluster_ids: list[str] = []

        # 当且仅当空间为非业务空间，且查询事件数据源时，需要查询关联的bkcc业务下的指标，并按项目集群过滤
        related_bk_biz_id = None
        if bk_biz_id < 0 and (data_source_label, data_type_label) == (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT):
            space_uid = bk_biz_id_to_space_uid(bk_biz_id)
            # 获取项目空间下的集群
            target_cluster_ids = list(
                BCSCluster.objects.filter(space_uid=space_uid).values_list("bcs_cluster_id", flat=True)
            )
            space: Space = SpaceApi.get_related_space(space_uid, SpaceTypeEnum.BKCC.value)
            if space:
                related_bk_biz_id = space.bk_biz_id

        qs = MetricListCache.objects.filter(
            data_type_label=data_type_label,
            data_source_label=data_source_label,
            bk_tenant_id=get_request_tenant_id(),
        )

        # 过滤关联业务
        if related_bk_biz_id:
            qs = qs.filter(
                Q(bk_biz_id__in=[0, bk_biz_id]) | Q(bk_biz_id=related_bk_biz_id, result_table_name__contains="BCS-K8S-")
            )
        else:
            qs = qs.filter(bk_biz_id__in=[0, bk_biz_id])

        if validated_request_data.get("return_dimensions"):
            metrics = self._fetch_metrics(qs)
        else:
            metrics = self._fetch_metrics_without_dimensions(qs)

        metric_dict = {}
        table_dimension_mapping = {}
        ignore_name_list = []
        for metric in metrics:
            table_id = metric["result_table_id"]
            if table_id not in metric_dict:
                name = bk_data_id = ""
                if (data_source_label, data_type_label) == (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG):
                    name = metric["related_name"]
                    bk_data_id = table_id.split("_", -1)[-1]
                elif (data_source_label, data_type_label) == (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT):
                    name = metric["result_table_name"]
                    bk_data_id = metric["extend_fields"].get("bk_data_id", "")

                    # 过滤掉已经处理过的需要过滤的指标
                    if name in ignore_name_list:
                        continue

                    # 如果是关联业务的指标，需要过滤掉非项目集群
                    if metric["bk_biz_id"] == related_bk_biz_id:
                        # 项目空间， 仅列出项目集群， metrics包含关联业务的全部集群
                        if not target_cluster_ids:
                            ignore_name_list.append(name)
                            continue
                        matched = re.search(bcs_cluster_id_match_regex, name, re.I | re.M)
                        if matched:
                            bcs_cluster_id = matched.groupdict()["bcs_cluster_id"]
                            if bcs_cluster_id not in target_cluster_ids:
                                ignore_name_list.append(name)
                                continue

                if table_id in self._TABLE_ALIAS_MAP:
                    name = _("{alias}（{name}）").format(alias=self._TABLE_ALIAS_MAP[table_id], name=name)

                metric_dict[table_id] = {
                    "id": table_id,
                    "bk_data_id": bk_data_id,
                    "name": name,
                    "metrics": [],
                    "time_field": "time",
                    "is_platform": metric["bk_biz_id"] == 0,
                }
            else:
                for dimension in metric["dimensions"]:
                    table_dimension_mapping.setdefault(table_id, {})[dimension["id"]] = dimension

            metric_dict[table_id]["metrics"].append({"id": metric["metric_field"], "name": metric["metric_field_name"]})

        for table_id, data_source_config in metric_dict.items():
            data_source_config["dimensions"] = list(table_dimension_mapping.get(table_id, {}).values())
        return list(metric_dict.values())


class GetAlarmEventField(Resource):
    """
    获取告警事件字段
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        start_time = serializers.IntegerField(label="开始时间", required=False)
        end_time = serializers.IntegerField(label="结束时间", required=False)

    def perform_request(self, validated_request_data: dict[str, Any]):
        now = int(time.time())
        handler = AlertQueryHandler(
            bk_biz_ids=[validated_request_data["bk_biz_id"]],
            start_time=validated_request_data.get("start_time", now - 3600 * 24 * 7),
            end_time=validated_request_data.get("end_time", now),
        )
        tags = handler.list_tags()
        for tag in tags:
            tag["is_dimension"] = True

        return [
            {"id": "severity", "name": _("告警级别"), "is_dimension": True},
            {"id": "status", "name": _("告警状态"), "is_dimension": True},
            {"id": "alert_name", "name": _("告警名称"), "is_dimension": True},
            {"id": "strategy_id", "name": _("策略ID"), "is_dimension": True},
            {"id": "event.ip", "name": "IP", "is_dimension": True},
            {"id": "event.bk_cloud_id", "name": _("云区域ID"), "is_dimension": True},
            *tags,
        ]


class GetAlarmEventDimensionValue(Resource):
    """
    获取告警事件维度值
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        field = serializers.CharField(label="维度字段")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")

    def perform_request(self, validated_request_data: dict[str, Any]):
        now = int(time.time())
        handler = AlertQueryHandler(
            bk_biz_ids=[validated_request_data["bk_biz_id"]],
            start_time=validated_request_data.get("start_time", now - 3600 * 24 * 7),
            end_time=validated_request_data.get("end_time", now),
        )
        fields = handler.top_n(fields=[validated_request_data["field"]], size=100, char_add_quotes=False)["fields"]
        if not fields:
            return []

        data = fields[0]
        return data["buckets"]


class QueryAlarmEventGraph(Resource):
    """
    查询告警事件图表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        where = serializers.ListField(label="查询条件", default=[])
        group_by = serializers.ListField(label="维度", default=[])
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        interval = serializers.CharField(label="时间间隔", default="auto")
        interval_unit = serializers.ChoiceField(label="时间间隔单位", default="s", choices=["h", "m", "d", "s"])

        def validate(self, attrs):
            if attrs["interval"] == "auto":
                return attrs

            try:
                attrs["interval"] = int(attrs["interval"])
            except (ValueError, TypeError):
                raise serializers.ValidationError(_("时间间隔必须为整数或auto"))

            # 时间单位转换
            if attrs["interval_unit"] == "h":
                attrs["interval"] = attrs["interval"] * 3600
            elif attrs["interval_unit"] == "m":
                attrs["interval"] = attrs["interval"] * 60
            elif attrs["interval_unit"] == "d":
                attrs["interval"] = attrs["interval"] * 3600 * 24
            return attrs

    def perform_request(self, validated_request_data: dict[str, Any]):
        handler = AlertQueryHandler(
            bk_biz_ids=[validated_request_data["bk_biz_id"]],
            conditions=validated_request_data["where"],
            start_time=validated_request_data["start_time"],
            end_time=validated_request_data["end_time"],
        )

        data = handler.date_histogram(validated_request_data["interval"], validated_request_data["group_by"])

        series = []
        for dimension_tuple, status_mapping in data.items():
            dimensions = dict(dimension_tuple)
            for status, value in status_mapping.items():
                datapoints = [[count, timestamp] for timestamp, count in value.items()]
                dimensions = {k.replace(".", "__"): v for k, v in dimensions.items()}

                if "status" in validated_request_data["group_by"]:
                    new_dimensions = {"status": status, **dimensions}
                else:
                    new_dimensions = dimensions
                series.append(
                    {
                        "datapoints": datapoints,
                        "dimensions": new_dimensions,
                        "target": "|".join([f"{k}:{v}" for k, v in new_dimensions.items()]),
                    }
                )
        return {"series": series}
