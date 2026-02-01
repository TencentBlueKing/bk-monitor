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
from collections import defaultdict
from typing import Optional

import six
from elasticsearch_dsl import Q
from rest_framework import serializers

from bkmonitor.documents import AlertDocument
from bkmonitor.models import QueryConfigModel, StrategyLabel, StrategyModel
from bkmonitor.views.serializers import BusinessOnlySerializer
from constants.aiops import SCENE_METRIC_MAP, SCENE_NAME_MAPPING
from constants.alert import EventStatus
from core.drf_resource import Resource, resource
from core.unit import UNITS, load_unit
from monitor_web.strategies.constant import ValueableList
from monitor_web.tasks import parse_scene_metrics

logger = logging.getLogger(__name__)


class NoticeVariableListResource(Resource):
    """
    获取告警模板变量列表
    """

    RequestSerializer = BusinessOnlySerializer

    def perform_request(self, validated_request_data):
        return ValueableList.VALUEABLELIST


class FetchItemStatus(Resource):
    """
    获取指定Item Metric_id的策略配置及告警情况
    return: {
        "{metric_id}": 0,1,2 # 0:未配置策略, 1:配置了策略, 2: 告警中
    }
    """

    BCS_TAG_NAMES = {
        "bcs_cluster_id",
        "namespace",
        "pod_name",
        "workload_kind",
        "workload_name",
        "container_name",
        "bk_monitor_name",
        "monitor_type",
    }

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        metric_ids = serializers.ListField(required=True, label="指标ID")
        target = serializers.DictField(required=False, default={}, label="当前目标")
        labels = serializers.ListField(
            required=False,
            default=[],
            label="标签过滤",
            child=serializers.CharField(allow_blank=False),
        )

    @classmethod
    def get_alarm_event_num(cls, validated_request_data: dict) -> dict:
        """获得告警事件数量 ."""
        bk_biz_id = validated_request_data["bk_biz_id"]
        target = validated_request_data["target"]
        labels = validated_request_data.get("labels", [])
        ip = target.get("bk_target_ip")
        bk_cloud_id = target.get("bk_target_cloud_id", 0)
        bk_service_instance_id = target.get("bk_service_instance_id")
        search_object = (
            AlertDocument.search(all_indices=True)
            .filter("term", status=EventStatus.ABNORMAL)
            .exclude("term", is_shielded=True)
            .filter("term", **{"event.bk_biz_id": bk_biz_id})
        )
        if ip:
            search_object = search_object.filter("term", **{"event.ip": ip}).filter(
                "term", **{"event.bk_cloud_id": bk_cloud_id}
            )
        elif bk_service_instance_id:
            search_object = search_object.filter("term", **{"event.bk_service_instance_id": bk_service_instance_id})
        # 添加event.tags查询
        search_object = cls.add_event_tags_query(search_object, target)
        # 添加策略标签过滤
        search_object = cls.add_labels_query(search_object, labels)
        # 获得告警策略关联的告警事件的数量
        search_object = search_object[:0]
        search_object.aggs.bucket("strategy_id", "terms", field="strategy_id", size=10000)
        search_result = search_object.execute()
        strategy_alert_num = {}
        if search_result.aggs:
            for bucket in search_result.aggs.strategy_id.buckets:
                strategy_id = int(bucket.key)
                strategy_alert_num[strategy_id] = bucket.doc_count
        return strategy_alert_num

    @classmethod
    def add_event_tags_query(cls, search_object, target):
        """添加event.tags查询 ."""
        bcs_cluster_id = target.get("bcs_cluster_id")
        if not bcs_cluster_id:
            return search_object
        query_dsl = cls.transform_target_to_dsl(target)
        if query_dsl:
            search_object = search_object.query(query_dsl)

        return search_object

    @classmethod
    def transform_target_to_dsl(cls, target: dict) -> Optional[Q]:  # noqa
        """将target转换为es dsl ."""
        if not target:
            return None
        # 构造query_string
        nested_list = []
        for key, value in target.items():
            if key not in cls.BCS_TAG_NAMES:
                continue
            if isinstance(value, list):
                continue
            nested_list.append(
                Q(
                    "nested",
                    path="event.tags",
                    query=Q(
                        "bool",
                        must=[
                            Q("term", **{"event.tags.key": {"value": key}}),
                            Q("match_phrase", **{"event.tags.value": {"query": value}}),
                        ],
                    ),
                )
            )
        if not nested_list:
            return None

        query = Q("bool", must=nested_list)

        return query

    @classmethod
    def add_labels_query(cls, search_object, labels: list[str]):
        """基于策略标签过滤告警"""
        if not labels:
            return search_object

        # 直接使用策略标签进行过滤，如 ["APM-APP(trpc_demo)", "APM-SERVICE(example.greeter)"]
        search_object = search_object.filter("terms", labels=labels)
        return search_object

    @staticmethod
    def get_strategy_numbers(bk_biz_id: int, metric_ids: list[str], labels: list[str]) -> dict[str, list[int]]:
        """获得指标关联的告警策略 ."""

        # 获得业务下的 Item
        all_strategy_ids: list[int] = list(
            StrategyModel.objects.filter(bk_biz_id=bk_biz_id).values_list("id", flat=True).distinct()
        )

        # 获得指标关联的告警策略
        strategy_ids: set[int] = set()
        strategy_numbers = defaultdict(list)
        for metric_id, strategy_id in QueryConfigModel.objects.filter(
            strategy_id__in=all_strategy_ids, metric_id__in=metric_ids
        ).values_list("metric_id", "strategy_id"):
            strategy_ids.add(strategy_id)
            strategy_numbers[metric_id].append(strategy_id)

        if not labels or not strategy_ids:
            # 如果没有标签过滤条件，或者没有找到任何策略，直接返回结果。
            return strategy_numbers

        # 找到配置所有 labels 的策略 ID
        labels = [resource.strategies.strategy_label.gen_label_name(label) for label in labels]

        # 必须给定初始值，避免仅存在部分的场景误判为存在全部标签的策略。
        strategy_ids_gby_label: dict[str, list[int]] = {label: [] for label in labels}
        for strategy_id, label in StrategyLabel.objects.filter(
            bk_biz_id=bk_biz_id, strategy_id__in=strategy_ids, label_name__in=labels
        ).values_list("strategy_id", "label_name"):
            strategy_ids_gby_label[label].append(strategy_id)

        for label, partial_strategy_ids in strategy_ids_gby_label.items():
            strategy_ids = strategy_ids & set(partial_strategy_ids)

        if not strategy_ids:
            # 没有任何策略包含这些标签，直接返回空结果。
            return {}

        # 基于标签过滤策略
        return {
            metric_id: list(set(partial_strategy_ids) & strategy_ids)
            for metric_id, partial_strategy_ids in strategy_numbers.items()
        }

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        metric_ids = validated_request_data["metric_ids"]
        # 获得当前目标下未恢复告警事件，若无当前目标则获取所有未恢复告警事件
        strategy_alert_num = self.get_alarm_event_num(validated_request_data)
        # 获得指标关联的告警策略
        strategy_numbers = self.get_strategy_numbers(bk_biz_id, metric_ids, validated_request_data.get("labels", []))
        # 返回结果
        # strategy_number：已设置的告警数
        # alarm_num：告警数
        # status: 1 配置了策略, 2 告警中
        alert_status = {}
        for metric_id, strategy_id_list in strategy_numbers.items():
            alert_status[metric_id] = {
                "status": 1,
                "alert_number": 0,
                "strategy_number": len(strategy_id_list),
            }
            for strategy_id in strategy_id_list:
                if strategy_id in strategy_alert_num:
                    alert_status[metric_id]["status"] = 2
                    alert_status[metric_id]["alert_number"] += strategy_alert_num[strategy_id]

        for metric_id in validated_request_data["metric_ids"]:
            if metric_id not in alert_status:
                alert_status[metric_id] = {"status": 0, "alert_number": 0, "strategy_number": 0}

        return alert_status


class GetScenarioListResource(Resource):
    """
    获取平台全部的监控对象
    """

    def perform_request(self, validated_request_data):
        return resource.commons.get_label()


class GetUnitListResource(Resource):
    """
    获取指标单位列表
    """

    def perform_request(self, validated_request_data):
        unit_list = []
        for cat in UNITS:
            unit_list.append(
                {
                    "name": cat,
                    "formats": [
                        {"name": item.name, "id": item.gid, "suffix": item.suffix}
                        for item in six.itervalues(UNITS[cat])
                    ],
                }
            )
        return unit_list


class GetUnitInfoResource(Resource):
    """
    获取指标单位详细信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, default=0, label="业务ID")
        unit_id = serializers.CharField(required=False, label="二级标签", default="", allow_blank=True)

    def perform_request(self, validated_request_data):
        unit_instance = load_unit(validated_request_data["unit_id"])
        return {
            "name": unit_instance.name,
            "id": unit_instance.gid,
            "suffix": unit_instance.suffix,
            "unit_series": unit_instance.fn.unit_series(),
        }


class MultivariateAnomalyScenesResource(Resource):
    """
    获取智能AI观察场景列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, default=0, label="业务ID")

    def perform_request(self, validated_request_data):
        scenes = []

        for scene_id, scene_metric_list in SCENE_METRIC_MAP.items():
            metric_list = parse_scene_metrics(plan_args={"$metric_list": ",".join(scene_metric_list)})
            scenes.append(
                {
                    "scene_id": scene_id,
                    "scene_name": SCENE_NAME_MAPPING[scene_id],
                    "query_config": {
                        "data_source_label": metric_list[0]["metric"]["data_source_label"],
                        "data_type_label": metric_list[0]["metric"]["data_type_label"],
                        "result_table_id": metric_list[0]["metric"]["result_table_id"],
                        "metric_field": metric_list[0]["metric"]["metric_field"],
                        "extend_fields": {"values": []},
                        "agg_dimension": metric_list[0]["metric"]["default_dimensions"],
                        "agg_method": "AVG",
                        "agg_interval": 60,
                        "agg_condition": metric_list[0]["metric"]["default_condition"],
                        "alias": "a",
                    },
                    "metrics": metric_list,
                }
            )

        return scenes
