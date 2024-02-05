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
import logging
from collections import defaultdict
from typing import Dict, List, Optional

import six
from django.utils.translation import ugettext as _
from elasticsearch_dsl import Q
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.aiops.utils import AiSetting
from bkmonitor.documents import AlertDocument
from bkmonitor.models import QueryConfigModel, StrategyLabel, StrategyModel
from bkmonitor.views.serializers import BusinessOnlySerializer
from constants.aiops import SceneSet
from constants.alert import EventStatus
from constants.data_source import DataSourceLabel, DataTypeLabel
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


class StrategyLabelResource(Resource):
    """
    创建/修改策略标签
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, default=0, label="业务ID")
        strategy_id = serializers.IntegerField(required=False, default=0, label="策略ID")
        id = serializers.CharField(required=False, label="标签ID", default=None)
        label_name = serializers.CharField(required=True, label="标签名")

        def validate_label_name(self, value):
            label_name = StrategyLabelResource.gen_label_name(value)
            return label_name

        def validate(self, attrs):
            label_name = attrs["label_name"]
            if StrategyLabel.objects.filter(
                label_name=label_name, strategy_id=attrs["strategy_id"], bk_biz_id=attrs["bk_biz_id"]
            ).exists():
                raise ValidationError(_("标签{}已存在").format(label_name))
            return attrs

    def edit_label(self, label_name, label_id=None, strategy_id=0, bk_biz_id=0):
        # create/update label
        # 将父节点全部删除，再新建当前全路径节点。
        # 输入：label_name-> /a/b/c/
        # 如果有 /a/b/c/.*/，则表示创建的是上层目录，啥都不做即可。
        # 删除/a/, /a/b/
        # 新增/a/b/c/
        parent_label = self.get_parent_labels(label_name)
        StrategyLabel.objects.filter(label_name__in=parent_label, bk_biz_id=bk_biz_id, strategy_id=strategy_id).delete()
        if StrategyLabel.objects.filter(
            label_name__startswith=label_name, bk_biz_id=bk_biz_id, strategy_id=strategy_id
        ).exists():
            # 如果有 /a/b/c/.*/，则表示创建的是上层目录，啥都不做即可。
            logger.info(f"label_name: {label_name} exists, nothing to do")
            if label_id:
                # 如果是编辑，那么原标签可以删掉了
                target_label = StrategyLabel.objects.get(
                    label_name=label_id, bk_biz_id=bk_biz_id, strategy_id=strategy_id
                )
                logger.info(f"{target_label.label_name} -> {label_name}, already exists another label, will delete ")
                target_label.delete()
            return None
        if label_id is None:
            label_obj = StrategyLabel.objects.create(
                label_name=label_name, bk_biz_id=bk_biz_id, strategy_id=strategy_id
            )
            label_id = label_obj.label_name
        else:
            StrategyLabel.objects.filter(label_name=label_id, bk_biz_id=bk_biz_id, strategy_id=strategy_id).update(
                label_name=label_name
            )
        return label_id

    @classmethod
    def get_global_label(cls, label_name):
        return StrategyLabel.objects.filter(label_name=label_name, bk_biz_id=0, strategy_id=0).first()

    def perform_request(self, validated_request_data):
        label_id = validated_request_data.get("id")
        if label_id:
            label_id = self.gen_label_name(label_id)
        label_name = validated_request_data["label_name"]
        strategy_id = validated_request_data["strategy_id"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        return self.edit_label(label_name, label_id, strategy_id=strategy_id, bk_biz_id=bk_biz_id)

    @classmethod
    def gen_label_name(cls, label):
        return f"/{label.strip('/')}/"

    def get_parent_labels(self, label_name):
        labels = []
        for label in filter(lambda x: x, label_name.split("/")):
            if labels:
                labels.append(self.gen_label_name("/".join([labels[-1].strip("/"), label])))
            else:
                labels.append(self.gen_label_name(label))
        if labels:
            if labels.pop(-1) != label_name:
                raise
        return labels


class DeleteStrategyLabelResource(Resource):
    """
    删除策略标签
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, default=0, label="业务ID")
        strategy_id = serializers.IntegerField(required=False, default=0, label="策略ID")
        label_name = serializers.CharField(required=False, label="标签名", default="")

        def validate_label_name(self, value):
            label_name = StrategyLabelResource.gen_label_name(value) if value else ""
            return label_name

        def validate(self, attrs):
            if attrs["bk_biz_id"] == attrs["strategy_id"] == 0:
                if not attrs["label_name"]:
                    raise ValidationError(_("参数缺少label_name"))
            return attrs

    def perform_request(self, validated_request_data):
        label_name = validated_request_data["label_name"]
        strategy_id = validated_request_data["strategy_id"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        if strategy_id == bk_biz_id == 0:
            StrategyLabel.objects.filter(label_name__startswith=label_name, bk_biz_id=0, strategy_id=0).delete()
            # 如果标签上级只剩下被删除标签，则创建上层级标签
            # a/b 删除后， 变成 a
            parents = resource.strategies.strategy_label.get_parent_labels(label_name)
            if parents:
                if not StrategyLabel.objects.filter(
                    label_name__startswith=parents[-1], bk_biz_id=0, strategy_id=0
                ).exists():
                    StrategyLabel.objects.create(label_name=parents[-1], bk_biz_id=0, strategy_id=0)
        elif strategy_id != 0:
            # 基于策略ID删除全部标签
            StrategyLabel.objects.filter(strategy_id=strategy_id).delete()


class StrategyLabelList(Resource):
    """
    获取策略标签列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, default=0, label="业务ID")
        strategy_id = serializers.IntegerField(required=False, default=0, label="策略ID")

    def perform_request(self, validated_request_data):
        strategy_id = validated_request_data["strategy_id"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        # strategy_id != 0 表示获取单策略的标签
        # strategy_id == 0 & bk_biz_id != 0 表示获取业务下策略标签+全局标签
        # bk_biz_id == 0 表示获取全局标签
        global_labels = StrategyLabel.objects.filter(bk_biz_id=0)
        if strategy_id != 0:
            labels = StrategyLabel.objects.filter(strategy_id=strategy_id)
        else:
            if bk_biz_id != 0:
                labels = StrategyLabel.objects.filter(bk_biz_id__in=[0, bk_biz_id])
            else:
                labels = global_labels
        return self.group_labels(labels, global_labels)

    def group_labels(self, labels, global_labels):
        labels_dict = {"global": {}, "custom": {}, "global_parent_nodes": [], "custom_parent_nodes": []}
        global_label_set = global_labels.values_list("label_name", flat=True)
        for label in labels.values("label_name", "id"):
            if label["label_name"] in global_label_set:
                labels_dict["global"][label["label_name"]] = label["label_name"].strip("/")
            else:
                labels_dict["custom"][label["label_name"]] = label["label_name"].strip("/")
        global_dict = labels_dict["global"]
        custom_dict = labels_dict["custom"]
        labels_dict["global"] = [{"label_name": v, "id": k} for k, v in global_dict.items()]
        global_parent_nodes = []
        custom_parent_nodes = []
        for label_id in global_dict.keys():
            global_parent_nodes.extend(resource.strategies.strategy_label.get_parent_labels(label_id))
        for label_id in custom_dict.keys():
            custom_parent_nodes.extend(resource.strategies.strategy_label.get_parent_labels(label_id))
        labels_dict["custom"] = [{"label_name": v, "id": k} for k, v in custom_dict.items()]
        for label_id in set(global_parent_nodes).difference(set(global_dict.keys())):
            labels_dict.setdefault("global_parent_nodes", []).append(
                {"label_name": label_id.strip("/"), "label_id": label_id}
            )
        for label_id in set(custom_parent_nodes).difference(set(custom_dict.keys())):
            labels_dict.setdefault("custom_parent_nodes", []).append(
                {"label_name": label_id.strip("/"), "label_id": label_id}
            )
        return labels_dict


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

    @classmethod
    def get_alarm_event_num(cls, validated_request_data: Dict) -> Dict:
        """获得告警事件数量 ."""
        bk_biz_id = validated_request_data["bk_biz_id"]
        target = validated_request_data["target"]
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
    def transform_target_to_dsl(cls, target: Dict) -> Optional[Q]:
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
                            Q("term", **{"event.tags.key": {'value': key}}),
                            Q("match_phrase", **{"event.tags.value": {'query': value}}),
                        ],
                    ),
                )
            )
        if not nested_list:
            return None

        query = Q("bool", must=nested_list)

        return query

    @staticmethod
    def get_strategy_numbers(bk_biz_id: int, metric_ids: List) -> Dict:
        """获得指标关联的告警策略 ."""
        # 获得业务下的Item
        strategy_ids = StrategyModel.objects.filter(bk_biz_id=bk_biz_id).values_list("id", flat=True).distinct()
        # 获得指标关联的告警策略
        query_configs = QueryConfigModel.objects.filter(strategy_id__in=strategy_ids, metric_id__in=metric_ids)
        strategy_numbers = defaultdict(list)
        for query_config in query_configs:
            strategy_numbers[query_config.metric_id].append(query_config.strategy_id)
        return strategy_numbers

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        metric_ids = validated_request_data["metric_ids"]
        # 获得当前目标下未恢复告警事件，若无当前目标则获取所有未恢复告警事件
        strategy_alert_num = self.get_alarm_event_num(validated_request_data)
        # 获得指标关联的告警策略
        strategy_numbers = self.get_strategy_numbers(bk_biz_id, metric_ids)
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
        bk_biz_id = serializers.IntegerField(required=False, default=0, label=_("业务ID"))

    @classmethod
    def parse_ai_setting(cls, bk_biz_id: int):
        # 获取业务的AI配置
        ai_setting = AiSetting(bk_biz_id=bk_biz_id).to_dict()
        if (
            "host" in ai_setting["multivariate_anomaly_detection"]
            and ai_setting["multivariate_anomaly_detection"]["host"]["is_enabled"]
        ):
            # AI配置有打开时，才返回配置
            intelligent_detect = ai_setting["multivariate_anomaly_detection"]["host"]["intelligent_detect"]
            metrics_config = parse_scene_metrics(ai_setting["multivariate_anomaly_detection"]["host"]["plan_args"])
            return True, intelligent_detect, metrics_config
        return False, {}, []

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        is_enabled, intelligent_detect, metrics_config = self.parse_ai_setting(bk_biz_id)
        if is_enabled:
            return [
                {
                    "scene_id": SceneSet.HOST,
                    "scene_name": _("主机场景"),
                    "query_config": {
                        "data_source_label": DataSourceLabel.BK_DATA,
                        "data_type_label": DataTypeLabel.TIME_SERIES,
                        "result_table_id": intelligent_detect["result_table_id"],
                        "metric_field": "is_anomaly",
                        # 添加anomaly_sort字段，用于算法检测输出报告
                        "extend_fields": {"values": ["anomaly_sort"]},
                        "agg_dimension": ["ip", "bk_cloud_id"],
                        "agg_method": "MAX",
                        "agg_interval": 60,
                        # 只查询出is_anomaly=1的数据
                        "agg_condition": [{"key": "is_anomaly", "value": [1], "method": "eq"}],
                        "alias": "a",
                    },
                    "metrics": metrics_config,
                }
            ]
        return []
