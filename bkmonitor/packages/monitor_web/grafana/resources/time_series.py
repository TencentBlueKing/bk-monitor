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
import time
from functools import partial
from typing import Any, cast

from bk_monitor_base.uptime_check import list_nodes, list_tasks
from django.core.exceptions import EmptyResultSet
from django.db.models import Count, Q, QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkm_ipchooser.handlers import topo_handler
from bkmonitor.data_source import load_data_source
from bkmonitor.models import (
    BCSCluster,
    BCSContainer,
    BCSNode,
    BCSPod,
    BCSService,
    BCSWorkload,
    MetricListCache,
)
from bkmonitor.utils.range import load_agg_condition_instance
from bkmonitor.utils.request import get_request_tenant_id
from constants.data_source import (
    DATA_CATEGORY,
    GRAPH_MAX_SLIMIT,
    DataSourceLabel,
    DataTypeLabel,
)
from constants.strategy import EVENT_QUERY_CONFIG_MAP, SYSTEM_EVENT_RT_TABLE_ID
from core.drf_resource import Resource, api, resource
from core.errors.api import BKAPIError
from monitor_web.grafana.utils import get_cookies_filter, is_global_k8s_event
from monitor_web.models import CollectConfigMeta
from monitor_web.strategies.constant import CORE_FILE_SIGNAL_LIST
from monitor_web.strategies.default_settings.k8s_event import DEFAULT_K8S_EVENT_NAME

logger = logging.getLogger(__name__)

KUBERNETES_VARIABLE_FIELDS = {
    "cluster": [
        {"bk_property_id": "bcs_cluster_id", "bk_property_name": _("集群ID")},
        {"bk_property_id": "name", "bk_property_name": _("集群名称")},
    ],
    "namespace": [
        {"bk_property_id": "bcs_cluster_id", "bk_property_name": _("集群ID")},
        {"bk_property_id": "namespace", "bk_property_name": "NameSpace"},
    ],
    "pod": [
        {"bk_property_id": "bcs_cluster_id", "bk_property_name": _("集群ID")},
        {"bk_property_id": "namespace", "bk_property_name": "NameSpace"},
        {"bk_property_id": "name", "bk_property_name": _("Pod名称")},
    ],
    "container": [
        {"bk_property_id": "bcs_cluster_id", "bk_property_name": _("集群ID")},
        {"bk_property_id": "namespace", "bk_property_name": "NameSpace"},
        {"bk_property_id": "pod_name", "bk_property_name": _("Pod名称")},
        {"bk_property_id": "name", "bk_property_name": _("容器名称")},
    ],
    "node": [
        {"bk_property_id": "bcs_cluster_id", "bk_property_name": _("集群ID")},
        {"bk_property_id": "name", "bk_property_name": _("节点名称")},
        {"bk_property_id": "ip", "bk_property_name": _("节点IP")},
    ],
    "service": [
        {"bk_property_id": "bcs_cluster_id", "bk_property_name": _("集群ID")},
        {"bk_property_id": "namespace", "bk_property_name": "NameSpace"},
        {"bk_property_id": "name", "bk_property_name": _("服务名称")},
    ],
}


def query_data(params):
    """
    按查询条件查询时序数据
    :param params: 查询参数
    :return: 数据列表
    """

    if params["function"].get("empty"):
        return []

    data_source_class = load_data_source(params["data_source_label"], params["data_type_label"])

    if data_source_class.data_source_label == DataSourceLabel.BK_LOG_SEARCH:
        index_set_id = params["result_table_id"]
    else:
        index_set_id = None

    metrics = [{"field": params["metric_field"], "method": params["method"]}]
    for extend_metric in params["extend_metric_fields"]:
        metrics.append({"field": extend_metric, "method": params["method"]})

    data_source = data_source_class(
        bk_biz_id=params["bk_biz_id"],
        table=params["result_table_id"],
        data_label=params.get("data_label", ""),
        metrics=metrics,
        interval=params["interval"],
        where=params["agg_condition"],
        filter_dict=params["filter_dict"],
        group_by=params["group_by"],
        index_set_id=index_set_id,
        query_string=params["query_string"],
        time_field=params.get("time_field"),
    )

    slimit = None
    if params.get("slimit"):
        slimit = int(params["slimit"])

    records = data_source.query_data(start_time=params["start_time"], end_time=params["end_time"], slimit=slimit)
    return records


class TimeSeriesMetric(Resource):
    """
    时序型指标
    """

    DisplayDataSource = (
        (DataSourceLabel.BK_DATA, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG),
        (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT),
    )

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        result_table_label = serializers.CharField(label="监控对象", default="", allow_blank=True)
        conditions = serializers.DictField(label="查询条件", default={})
        query_string = serializers.CharField(label="查询关键字", default="", allow_blank=True)
        flat_format = serializers.BooleanField(label="是否扁平展示", default=False)

    @staticmethod
    def handle_uptime_check_metric(metric):
        """
        处理拨测数据
        :param metric:
        :return:
        """
        if metric["result_table_id"].startswith("uptimecheck."):
            if metric["metric_field"] in ["response_code", "message"]:
                metric["method_list"] = ["COUNT"]
            else:
                metric["method_list"] = ["SUM", "AVG", "MAX", "MIN", "COUNT"]

    @staticmethod
    def get_metric_condition_methods(metric: MetricListCache):
        """
        根据指标获取可用的条件方法
        """
        return [
            {"label": "=", "value": "eq"},
            {"label": "!=", "value": "neq"},
            {"label": ">", "value": "gt"},
            {"label": ">=", "value": "gte"},
            {"label": "<", "value": "lt"},
            {"label": "<=", "value": "lte"},
            {"label": "include", "value": "include"},
            {"label": "exclude", "value": "exclude"},
            {"label": "regex", "value": "reg"},
            {"label": "nregex", "value": "nreg"},
        ]

    @staticmethod
    def filter_conditions(metrics: QuerySet, conditions: dict):
        """
        查询过滤
        """
        if "related_id" in conditions:
            metrics = metrics.filter(related_id=conditions["related_id"])

        if "data_label" in conditions:
            metrics = metrics.filter(data_label=conditions["data_label"])
        elif "result_table_id" in conditions:
            metrics = metrics.filter(result_table_id=conditions["result_table_id"])

        if "result_table_name" in conditions:
            metrics = metrics.filter(result_table_id="", result_table_name=conditions["result_table_name"])

        if "metric_field" in conditions and not (
            conditions["metric_field"] == "_index"
            and (conditions.get("data_source_label"), conditions.get("data_type_label"))
            == (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT)
        ):
            metrics = metrics.filter(metric_field=conditions["metric_field"])

        if "data_source_label" in conditions:
            metrics = metrics.filter(data_source_label=conditions["data_source_label"])

        if "data_type_label" in conditions:
            metrics = metrics.filter(data_type_label=conditions["data_type_label"])

        if "result_table_label" in conditions:
            metrics = metrics.filter(
                Q(result_table_label=conditions["result_table_label"]) | Q(data_source_label=DataSourceLabel.BK_DATA)
            )
        return metrics

    def query_metrics(self, params):
        """
        指标查询
        """
        metrics = MetricListCache.objects.filter(
            bk_biz_id__in=[params["bk_biz_id"], 0], bk_tenant_id=get_request_tenant_id()
        )

        # 过滤指标对象
        if params["result_table_label"]:
            metrics = metrics.filter(
                Q(result_table_label=params["result_table_label"]) | Q(data_source_label=DataSourceLabel.BK_DATA)
            )

        # 条件过滤
        if params.get("query_string"):
            metrics = metrics.filter(
                Q(related_id__contains=params["query_string"])
                | Q(related_name__contains=params["query_string"])
                | Q(result_table_id__contains=params["query_string"])
                | Q(data_label_contains=params["query_string"])
                | Q(result_table_name__contains=params["query_string"])
                | Q(metric_field__contains=params["query_string"])
                | Q(metric_field_name__contains=params["query_string"])
            )
        else:
            metrics = self.filter_conditions(metrics, params["conditions"])

        return metrics

    def perform_request(self, params):
        metrics = self.query_metrics(params)

        custom_event_data_ids = set()
        data_source_dict = {}
        metric_configs: list[dict] = []

        for metric in metrics:
            if (metric.data_source_label, metric.data_type_label) not in self.DisplayDataSource:
                continue
            if (
                params["result_table_label"]
                and metric.result_table_label != params["result_table_label"]
                and metric.data_source_label != DataSourceLabel.BK_DATA
            ):
                continue

            # 自定义事件指标需要修正
            if (metric.data_source_label, metric.data_type_label) == (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT):
                if metric.result_table_id in custom_event_data_ids:
                    continue

                custom_event_data_ids.add(metric.result_table_id)
                metric.metric_field = "_index"
                metric.metric_field_name = _("事件统计")
                metric.dimensions.append(
                    {"id": "event_name", "name": _("事件名称"), "is_dimension": True, "type": "string"}
                )

            metric_config = {
                "result_table_label": metric.result_table_label,
                "result_table_label_name": metric.result_table_label_name,
                "result_table_id": metric.result_table_id,
                "data_label": metric.data_label,
                "result_table_name": metric.result_table_name,
                "metric_field": metric.metric_field,
                "metric_field_name": metric.metric_field_name,
                "dimensions": metric.dimensions,
                "default_dimensions": metric.default_dimensions,
                "default_condition": metric.default_condition,
                "readable_name": metric.readable_name or metric.get_human_readable_name(),
                "collect_interval": metric.collect_interval,
                "data_source_label": metric.data_source_label,
                "data_source_label_name": metric.data_source_label,
                "data_type_label": metric.data_type_label,
                "unit": metric.unit,
                "description": metric.description,
                "extend_fields": metric.extend_fields,
                "id": metric.metric_field,
                "name": metric.metric_field_name,
                "related_id": metric.related_id or "default",
                "related_name": metric.related_name,
                "condition_methods": self.get_metric_condition_methods(metric),
            }
            self.handle_uptime_check_metric(metric_config)

            if params["flat_format"]:
                metric_configs.append(metric_config)
                if len(metric_configs) >= 100:
                    break

            else:
                # 获取数据源分类
                key = "other"
                name = _("其他")
                for category in DATA_CATEGORY:
                    if (
                        category["data_source_label"] == metric.data_source_label
                        and category["data_type_label"] == metric.data_type_label
                    ):
                        name = category["name"]
                        key = f"{metric.data_source_label}.{metric.data_type_label}"
                        continue

                if key not in data_source_dict:
                    data_source_dict[key] = {"id": key, "name": name, "children": {}}

                related_metrics: dict = data_source_dict[key]["children"]
                if metric.related_id not in related_metrics:
                    related_metrics[metric.related_id] = {
                        "id": metric.related_id or "default",
                        "name": metric.related_name or metric.related_id or _("默认"),
                        "children": {},
                    }

                result_table_metrics = related_metrics[metric.related_id]["children"]
                if metric.result_table_id not in result_table_metrics:
                    result_table_metrics[metric.result_table_id] = {
                        "id": metric.result_table_id,
                        "name": metric.result_table_name,
                        "children": [],
                    }
                result_table_metrics[metric.result_table_id]["children"].append(metric_config)

        if params["flat_format"]:
            return metric_configs
        else:
            result = []
            for data_source in data_source_dict.values():
                data_source["children"] = list(data_source["children"].values())
                for related in data_source["children"]:
                    related["children"] = list(related["children"].values())
                result.append(data_source)
            return result


class TimeSeriesMetricLevel(TimeSeriesMetric):
    """
    指标分层信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        result_table_label = serializers.CharField(label="监控对象", default="", allow_blank=True)
        conditions = serializers.DictField(label="查询条件", default={})
        level = serializers.ChoiceField(
            choices=("result_table_label", "data_source", "related_id", "result_table_id", "metric")
        )

    def perform_request(self, params):
        # 过滤指标信息
        metrics = self.query_metrics(params)

        label_mapping = {}
        if params["level"] == "result_table_label":
            label_counts = {}
            for result_table_label in (
                metrics.values("result_table_label")
                .exclude(
                    Q(data_type_label=DataTypeLabel.EVENT)
                    | Q(data_source_label=DataSourceLabel.BK_LOG_SEARCH, data_type_label=DataTypeLabel.LOG)
                )
                .annotate(count=Count("*"), name_count=Count("result_table_label"))
            ):
                label_counts[result_table_label["result_table_label"]] = result_table_label["count"]

            labels = resource.commons.get_label()
            for first_label in labels:
                for second_label in first_label["children"]:
                    label_mapping[second_label["id"]] = (
                        f"{second_label['name']}({label_counts.get(second_label['id'], 0)})"
                    )
        if params["level"] == "data_source":
            source_counts = {}
            for source in metrics.values("data_source_label", "data_type_label").annotate(
                source_count=Count("data_source_label"), type_count=Count("data_type_label")
            ):
                source_counts[f"{source['data_source_label']}.{source['data_type_label']}"] = source["source_count"]
            for category in DATA_CATEGORY:
                if (category["data_source_label"], category["data_type_label"]) not in self.DisplayDataSource:
                    continue
                source_key = f"{category['data_source_label']}.{category['data_type_label']}"
                label_mapping[source_key] = f"{category['name']}({source_counts.get(source_key, 0)})"
        elif params["level"] == "related_id":
            for metric in metrics.values("related_id", "related_name").annotate(
                id_count=Count("related_id"), name_count=Count("related_name")
            ):
                label_mapping[metric["related_id"]] = f"{metric['related_name']}({metric['id_count']})"
        elif params["level"] == "result_table_id":
            for metric in metrics.values("result_table_id", "result_table_name").annotate(
                id_count=Count("result_table_id"), name_count=Count("result_table_name")
            ):
                if metric["result_table_id"]:
                    label_mapping[metric["result_table_id"]] = f"{metric['result_table_name']}({metric['id_count']})"
                else:
                    label_mapping[metric["result_table_name"]] = (
                        f"{metric['result_table_name']}({metric['name_count']})"
                    )
                    params["level"] = "result_table_name"

        result = [{"id": key, params["level"]: key, "name": name or _("默认")} for key, name in label_mapping.items()]
        return sorted(result, key=lambda i: i["id"])


class GetVariableField(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        type = serializers.CharField(label="查询类型")
        scenario = serializers.CharField(required=False, label="场景", default="os")

    extend_fields = {
        "host": [
            {"bk_property_id": "bk_host_id", "bk_property_name": _("主机ID")},
            {"bk_property_id": "bk_set_ids", "bk_property_name": _("集群ID")},
            {"bk_property_id": "bk_module_ids", "bk_property_name": _("模块ID")},
            {"bk_property_id": "display_name", "bk_property_name": _("展示名")},
            {"bk_property_id": "bk_host_name", "bk_property_name": _("主机名")},
            {"bk_property_id": "bk_host_innerip", "bk_property_name": _("内网IP")},
        ],
        "module": [
            {"bk_property_id": "bk_module_id", "bk_property_name": _("模块ID")},
            {"bk_property_id": "bk_module_name", "bk_property_name": _("模块名")},
            {"bk_property_id": "bk_set_id", "bk_property_name": _("集群ID")},
        ],
        "set": [
            {"bk_property_id": "bk_set_id", "bk_property_name": _("集群ID")},
            {"bk_property_id": "bk_set_name", "bk_property_name": _("集群名")},
        ],
        "service_instance": [
            {"bk_property_id": "service_instance_id", "bk_property_name": _("服务实例ID")},
            {"bk_property_id": "name", "bk_property_name": _("服务实例名")},
            {"bk_property_id": "service_category_id", "bk_property_name": _("服务分类ID")},
            {"bk_property_id": "bk_host_id", "bk_property_name": _("主机ID")},
            {"bk_property_id": "bk_module_id", "bk_property_name": _("集群ID")},
        ],
    }

    def perform_request(self, params):
        data = []
        scenario = params["scenario"]
        scope_type = params["type"]
        if scenario == "os":
            if scope_type not in ["host", "module", "service_instance", "set"]:
                raise ValidationError("type({}) not exists")

            properties = []
            if scope_type != "service_instance":
                try:
                    properties: list[dict] = api.cmdb.get_object_attribute(bk_obj_id=scope_type)
                except BKAPIError:
                    pass

            # 字段去重
            exists_fields = {p["bk_property_id"] for p in self.extend_fields.get(scope_type, [])}
            data = [
                {"bk_property_id": p["bk_property_id"], "bk_property_name": p["bk_property_name"]}
                for p in properties
                if p["bk_property_id"] not in exists_fields
            ]

            data.extend(self.extend_fields.get(scope_type, []))
        elif scenario == "kubernetes":
            data = KUBERNETES_VARIABLE_FIELDS.get(scope_type, [])
            return data
        return data


class GetVariableValue(Resource):
    """
    Grafana 变量值查询
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        type = serializers.CharField(label="查询类型")
        scenario = serializers.CharField(required=False, label="场景", default="os")
        params = serializers.DictField(label="查询参数")

        def validate_params(self, attrs):
            # 数据维度字段 去掉 告警落es时补充的  tags. 前缀
            attrs["field"] = attrs.get("field", "").replace("tags.", "")
            return attrs

    @staticmethod
    def format_label_and_value(labels, values):
        new_labels = []
        new_values = []
        for value in values:
            if value is None:
                value = ""
            elif isinstance(value, list):
                value = ",".join([str(x) for x in value])
            else:
                value = str(value)
            new_values.append(value)

        for label in labels:
            if label is None:
                label = ""
            elif isinstance(label, list):
                label = ",".join([str(x) for x in label])
            else:
                label = str(label)

            new_labels.append(label)

        if not new_labels:
            new_labels = new_values

        return new_labels, new_values

    @staticmethod
    def get_host_count(bk_biz_id: int, target_type: str) -> dict[int, int]:
        """
        获取主机数量，比如集群或者模块的主机数量
        """
        host_count = {}

        def collect(trees: list[dict[str, Any]]):
            for node in trees:
                if node["object_id"] == target_type:
                    host_count[node["instance_id"]] = node["count"]

                if "child" in node and node["child"]:
                    collect(node["child"])

        trees = topo_handler.TopoHandler.trees(
            scope_list=[{"bk_biz_id": bk_biz_id}],
            count_instance_type="host",
        )
        collect(trees)

        return host_count

    def query_cmdb(self, type, bk_biz_id, params):
        label_fields = [label_field for label_field in params["label_field"].split("|") if label_field]
        value_fields = [value_field for value_field in params["value_field"].split("|") if value_field]

        if type == "host":
            instances = api.cmdb.get_host_by_topo_node(bk_biz_id=bk_biz_id)
        elif type == "module":
            instances = api.cmdb.get_module(bk_biz_id=bk_biz_id)
            host_count = self.get_host_count(bk_biz_id, "module")
        elif type == "set":
            instances = api.cmdb.get_set(bk_biz_id=bk_biz_id)
            host_count = self.get_host_count(bk_biz_id, "set")
        elif type == "service_instance":
            instances = api.cmdb.get_service_instance_by_topo_node(bk_biz_id=bk_biz_id)
        else:
            raise ValidationError(f"type({type}) not exists")

        value_dict = {}

        condition = load_agg_condition_instance(params.get("where", []))
        for instance in instances:
            instance_dict = getattr(instance, "_extra_attr", {})
            instance_dict.update(instance.__dict__)
            if not condition.is_match(instance_dict):
                continue

            labels = [getattr(instance, label_field, "") for label_field in label_fields]
            values = [getattr(instance, value_field, "") for value_field in value_fields]

            if not values:
                continue

            new_labels, new_values = self.format_label_and_value(labels, values)
            if type in ["module", "set"]:
                # 模块和集群变量加上主机数量
                instance_id = instance.bk_module_id if type == "module" else instance.bk_set_id
                value_dict["|".join(new_values)] = "|".join(new_labels) + f"[{host_count.get(instance_id, 0)}]"
            else:
                value_dict["|".join(new_values)] = "|".join(new_labels)

        return [{"label": k, "value": v} for v, k in value_dict.items()]

    def query_kubernetes(self, type, bk_biz_id, params):
        field_set = {item["bk_property_id"] for item in KUBERNETES_VARIABLE_FIELDS[type]}
        label_fields = [
            label_field for label_field in params["label_field"].split("|") if label_field and label_field in field_set
        ]
        value_fields = [
            value_field for value_field in params["value_field"].split("|") if value_field and value_field in field_set
        ]

        instances = []

        cluster_resource_map = {
            "cluster": BCSCluster,
            "namespace": BCSWorkload,
            "pod": BCSPod,
            "container": BCSContainer,
            "service": BCSService,
            "node": BCSNode,
        }

        # 获得条件，支持共享集群
        resource_class = cluster_resource_map[type]
        try:
            query_set = resource_class.objects.filter_by_biz_id(bk_biz_id)
        except EmptyResultSet:
            return []

        if type == "cluster":
            # 获得业务下的所有集群
            instances = query_set.values("bcs_cluster_id", "name")
            instances = (
                {
                    "bcs_cluster_id": instance["bcs_cluster_id"],
                    "name": f"{instance['bcs_cluster_id']}({instance['name']})",
                }
                for instance in instances
            )
        elif type == "namespace":
            # 获得业务下的所有namespace
            instances = query_set.values("bcs_cluster_id", "namespace").distinct()
        elif type == "pod":
            instances = query_set.values("bcs_cluster_id", "namespace", "name")
        elif type == "container":
            instances = query_set.values("bcs_cluster_id", "namespace", "pod_name", "name")
        elif type == "service":
            instances = query_set.values("bcs_cluster_id", "namespace", "name")
        elif type == "node":
            instances = query_set.values("bcs_cluster_id", "name", "ip")

        value_dict = {}
        condition = load_agg_condition_instance(params.get("where", []))
        for instance in instances:
            if not condition.is_match(instance):
                continue

            labels = [instance[label_field] for label_field in label_fields]
            values = [instance[value_field] for value_field in value_fields]

            if not values:
                continue

            new_labels, new_values = self.format_label_and_value(labels, values)
            value_dict["|".join(new_values)] = "|".join(new_labels)

        return [{"label": k, "value": v} for v, k in value_dict.items()]

    def query_dimension(self, bk_biz_id, params):
        """
        查询维度
        """
        # 1、如果指标与待查询维度相同，则返回空
        if params["metric_field"] == params["field"]:
            return []

        # 2、支持多维度字段值的查询，如果没传维度则返回空
        fields = [field for field in params["field"].split("|") if field]
        if not fields:
            return []

        # 3、做以下兼容情况
        # 3.1 兼容grafana旧数据
        if not params["data_type_label"]:
            params["data_type_label"] = "time_series"
        if params["data_source_label"] == "log":
            params["data_source_label"] = "bk_log_search"

        # 3.2 兼容没有传入data_source_label及data_type_label的情况
        if "data_source_label" in params and "data_type_label" in params:
            data_source_label = params["data_source_label"]
            data_type_label = params["data_type_label"]
        else:
            metric = MetricListCache.objects.filter(
                result_table_id=params["result_table_id"],
                data_label=params.get("data_label", ""),
                metric_field=params["metric_field"],
                bk_biz_id__in=[0, bk_biz_id],
                bk_tenant_id=get_request_tenant_id(),
            ).first()
            if metric:
                data_source_label = metric.data_source_label
                data_type_label = metric.data_type_label
            else:
                data_source_label = DataSourceLabel.BK_MONITOR_COLLECTOR
                data_type_label = DataTypeLabel.TIME_SERIES

        # 3.3 兼容日志关键字查询
        if data_source_label == DataSourceLabel.BK_LOG_SEARCH and data_type_label == DataTypeLabel.LOG:
            params["metric_field"] = "_index"

        # 3.4 日志平台使用index_set_id查询
        index_set_id = None
        if data_source_label == DataSourceLabel.BK_LOG_SEARCH:
            if params.get("index_set_id"):
                index_set_id = params["index_set_id"]
            else:
                metric = MetricListCache.objects.filter(
                    data_source_label=DataSourceLabel.BK_LOG_SEARCH,
                    result_table_id=params["result_table_id"],
                    bk_biz_id=bk_biz_id,
                    bk_tenant_id=get_request_tenant_id(),
                ).first()
                if metric:
                    index_set_id = metric.extend_fields.get("index_set_id")

        # 3.5 http拨测，响应码和响应消息指标转换处理
        params = self.metric_filed_translate(params)

        # 3.6 事件型特殊处理
        if params["result_table_id"] == SYSTEM_EVENT_RT_TABLE_ID:
            # 特殊处理corefile signal的维度可选值
            if params["metric_field"] == "corefile-gse" and params["field"] == "signal":
                return [{"value": item, "label": item} for item in CORE_FILE_SIGNAL_LIST]
            elif params["metric_field"] in EVENT_QUERY_CONFIG_MAP:
                params.update(EVENT_QUERY_CONFIG_MAP[params["metric_field"]])
                data_type_label = DataTypeLabel.TIME_SERIES
            else:
                return []

        # 3.7 如果是要查询"拓扑节点名称(bk_inst_id)"，则需要把"拓扑节点类型(bk_obj_id)"一并带上
        if "bk_inst_id" in fields:
            # 确保bk_obj_id在bk_inst_id之前，为后面的dimensions翻译做准备
            fields = [f for f in fields if f != "bk_obj_id"]
            fields.insert(0, "bk_obj_id")

        # 4、获取查询起止时间和时间间隔，支持传入参数，也支持不传参数，没传参数时，基于当前时间作为结束时间来获取起止时间和时间间隔
        timestamp = int(time.time() // 60 * 60)
        start_time = params.get("start_time", timestamp - 30 * 60)
        end_time = params.get("end_time", timestamp)
        interval = params.get("interval")
        if not interval:
            time_range = end_time - start_time
            if time_range < 5 * 60:
                interval = 60
            elif time_range < 60 * 60:
                interval = 5 * 60
            elif time_range < 24 * 60 * 60:
                interval = 60 * 60
            else:
                interval = 24 * 60 * 60
        end_time += interval

        # 5、提取cookies中的符合规则的字段作为过滤条件
        cookies_filter = get_cookies_filter()
        if cookies_filter:
            if "filter_dict" not in params:
                params["filter_dict"] = {}
            params["filter_dict"]["cookies"] = cookies_filter

        # 6、查询维度的值，通过调用对应data_source的query_dimensions方法查询
        # 其中，CustomTimeSeriesDataSource和BkMonitorTimeSeriesDataSource是
        # 调用InfluxdbDimensionFetcher.query_dimensions查询维度的值
        data_source_class = load_data_source(data_source_label, data_type_label)
        data_source = data_source_class(
            bk_biz_id=bk_biz_id,
            table=params["result_table_id"],
            data_label=params.get("data_label", ""),
            metrics=[{"field": params["metric_field"], "method": "COUNT"}],
            where=params["where"],
            filter_dict=params.get("filter_dict", {}),
            group_by=fields,
            index_set_id=index_set_id,
            query_string=params.get("query_string", ""),
        )
        records = data_source.query_dimensions(
            dimension_field=fields,
            limit=GRAPH_MAX_SLIMIT,
            start_time=start_time * 1000,
            end_time=end_time * 1000,
            slimit=GRAPH_MAX_SLIMIT,
            interval=interval,
        )

        # 7、对维度的返回字段进行组装，使得其支持多字段查询
        dimensions = self.assemble_dimensions(fields, records)

        # 8、给全局k8s事件的 event_name 维度提供常用事件名的默认值
        if is_global_k8s_event(params, bk_biz_id):
            dimensions = set(dimensions) | set(DEFAULT_K8S_EVENT_NAME)

        # 9、对维度值进行翻译并返回
        return self.dimension_translate(bk_biz_id, params, list(dimensions))

    def query_promql(self, bk_biz_id, params):
        """
        查询promql label_values
        {
            "promql": "label_values(metric, label)",
            "start_time": 1111,
            "end_time": 111
        }
        """
        promql = params["promql"].strip()
        if not promql:
            return []
        promql = resource.grafana.graph_promql_query.remove_all_conditions(params["promql"])
        all_dimensions = set()
        for query in promql.split("\n"):
            if not query.strip():
                continue

            all_dimensions.update(
                resource.grafana.dimension_promql_query(
                    bk_biz_id=bk_biz_id,
                    promql=query,
                    start_time=params["start_time"],
                    end_time=params["end_time"],
                )
            )
        return [{"label": d, "value": d} for d in all_dimensions]

    @staticmethod
    def assemble_dimensions(fields, records):
        """
        对维度的返回字段进行组装，使得其支持多字段查询
        """
        dimensions: set[str] | None = set()

        def assemble_dimensions_by_drf(total, level, now):
            if len(fields) == level:
                total.add("|".join(now))
                return

            if records.get(fields[level], ""):
                for data in records.get(fields[level]):
                    now.append(data)
                    assemble_dimensions_by_drf(total, level + 1, now)
                    now.pop()
            else:
                # 如果数据不存在，则直接跳到下一层
                now.append("")
                assemble_dimensions_by_drf(total, level + 1, now)
                now.pop()

            return total

        if isinstance(records, list):
            return set(records)
        else:
            records = records.get("values", {})
            if len(fields) == 1:
                for data in records.get(fields[0], ""):
                    dimensions.add(str(data))
            else:
                dimensions = assemble_dimensions_by_drf(set(), 0, [])

        return dimensions

    @staticmethod
    def metric_filed_translate(query_params: dict):
        # http拨测，响应码和响应消息指标转换
        metric_field = query_params["metric_field"]
        result_table_id = query_params["result_table_id"]
        if str(result_table_id).startswith("uptimecheck."):
            query_params["where"] = []
            if metric_field in ["response_code", "message"]:
                query_params["metric_field"] = "available"

        return query_params

    @staticmethod
    def dimension_translate(bk_biz_id: int, params: dict[str, Any], dimensions: list):
        """
        维度翻译
        """
        bk_tenant_id = cast(str, get_request_tenant_id())
        result = None
        dimension_field = params["field"]
        if dimension_field == "bk_collect_config_id":
            configs = CollectConfigMeta.objects.filter(bk_biz_id=bk_biz_id, id__in=dimensions)
            id_to_names = {str(config.pk): config.name for config in configs}
            result = [{"label": id_to_names.get(str(v), v), "value": v} for v in dimensions]
        elif dimension_field == "bk_obj_id":
            topo_tree = api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id)
            obj_id_to_obj_name = {n.bk_obj_id: n.bk_obj_name for n in topo_tree.convert_to_flat_nodes()}
            result = [{"label": obj_id_to_obj_name.get(str(v), v), "value": v} for v in dimensions]
        elif dimension_field == "bk_target_service_instance_id":
            bk_target_service_instance_list = api.cmdb.get_service_instance_by_id(
                bk_biz_id=bk_biz_id, service_instance_ids=dimensions
            )
            result = [
                {"label": item.name, "value": item.service_instance_id} for item in bk_target_service_instance_list
            ]
        elif dimension_field == "bk_inst_id":
            topo_tree = api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id)
            id_to_names = {}
            for n in topo_tree.convert_to_flat_nodes():
                # 产品需求，不要前缀bk_obj_name，即 不要"模块-consul"，只需要 "consul"名称即可
                # id_to_names[f"{n.bk_obj_id}|{n.bk_inst_id}"] = f"{n.bk_obj_name}-{n.bk_inst_name}"
                id_to_names[f"{n.bk_obj_id}|{n.bk_inst_id}"] = f"{n.bk_inst_name}"

            result = []
            for v in dimensions:
                v_split = v.split("|")
                value = v_split[1] if len(v_split) == 2 else v
                result.append({"label": id_to_names.get(str(v), value), "value": value})
        elif dimension_field == "bcs_cluster_id":
            # 显示集群名称
            cluster_infos = api.kubernetes.fetch_k8s_cluster_list(bk_tenant_id=bk_tenant_id)
            cluster_id_to_name = {cluster["bcs_cluster_id"]: cluster["name"] for cluster in cluster_infos}
            result = []
            for v in sorted(dimensions):
                cluster_name = cluster_id_to_name.get(v)
                label = f"{v}({cluster_name})" if cluster_name else v
                result.append({"label": label, "value": v})
        elif dimension_field == "bk_biz_id":
            result = []
            bk_biz_ids = []
            for dimension in dimensions:
                try:
                    bk_biz_ids.append(int(dimension))
                except (TypeError, ValueError):
                    pass
            business = api.cmdb.get_business(bk_biz_ids=bk_biz_ids)
            biz_dict = {str(biz.bk_biz_id): biz.bk_biz_name for biz in business}
            for biz_id in dimensions:
                result.append({"label": biz_dict.get(biz_id, biz_id), "value": biz_id})
        # 拨测任务及节点翻译
        if str(params["result_table_id"]).startswith("uptimecheck.") or str(params["result_table_id"]).startswith(
            "uptimecheck_"
        ):
            if dimension_field == "task_id":
                uptime_check_tasks = list_tasks(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    query={"task_ids": dimensions},
                    fields=["id", "name"],
                )
                task_name_mapping = {str(task.id): task.name for task in uptime_check_tasks}
                result = [
                    {"label": task_name_mapping.get(v, _("任务({})已删除").format(v)), "value": v} for v in dimensions
                ]
            elif dimension_field == "node_id":
                nodes = list_nodes(bk_tenant_id=bk_tenant_id, query={"node_ids": dimensions})
                result = [{"label": node.name, "value": str(node.id)} for node in nodes]

        result = result or [{"label": v, "value": v} for v in dimensions]

        return result

    @staticmethod
    def query_collect(bk_biz_id: int, params):
        """
        查询采集配置
        """
        collects = CollectConfigMeta.objects.filter(bk_biz_id=bk_biz_id).only("id", "name")
        return [{"label": str(collect.pk), "value": collect.name} for collect in collects]

    def perform_request(self, validated_request_data: dict[str, Any]):
        scenario = validated_request_data["scenario"]
        scope_type = validated_request_data["type"]
        # 不支持promql的datasource,所以当"data_source_label": "prometheus" 直接返回空
        if scope_type == "dimension" and validated_request_data["params"].get("data_source_label") == "prometheus":
            return []

        query_processor = {}
        if scenario == "os":
            query_cmdb = partial(self.query_cmdb, type=scope_type)
            query_processor = {
                "host": query_cmdb,
                "module": query_cmdb,
                "set": query_cmdb,
                "service_instance": query_cmdb,
                "dimension": self.query_dimension,
                "collect": self.query_collect,
                "prometheus": self.query_promql,
            }
        elif scenario == "kubernetes":
            query_kubernetes = partial(self.query_kubernetes, type=scope_type)
            query_processor = {
                "cluster": query_kubernetes,
                "namespace": query_kubernetes,
                "pod": query_kubernetes,
                "container": query_kubernetes,
                "node": query_kubernetes,
                "service": query_kubernetes,
            }

        if scope_type not in query_processor:
            raise ValidationError(f"type({scope_type}) not exists")

        result = query_processor[scope_type](
            bk_biz_id=validated_request_data["bk_biz_id"], params=validated_request_data["params"]
        )
        return result


class Test(Resource):
    """
    Grafana数据源测试接口
    """

    def perform_request(self, validated_request_data: dict[str, Any]):
        return "OK"
