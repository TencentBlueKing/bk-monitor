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
import bisect
import copy
import json
import logging
import math
import re
import time
from abc import ABCMeta
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import chain
from typing import Dict, List, Tuple
from urllib.parse import parse_qs

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext as _
from elasticsearch_dsl import Q
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.cmdb.define import Host, ServiceInstance
from bkmonitor.aiops.alert.utils import parse_anomaly
from bkmonitor.aiops.utils import AiSetting
from bkmonitor.data_source import load_data_source
from bkmonitor.dataflow.constant import VisualType
from bkmonitor.documents import (
    ActionInstanceDocument,
    AlertDocument,
    AlertLog,
    EventDocument,
)
from bkmonitor.documents.base import BulkActionType
from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.models import (
    ActionInstance,
    AlertAssignGroup,
    AlgorithmModel,
    MetricListCache,
    StrategyModel,
)
from bkmonitor.share.api_auth_resource import ApiAuthResource
from bkmonitor.strategy.new_strategy import Strategy, parse_metric_id
from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.event_related_info import get_alert_relation_info
from bkmonitor.utils.range import load_agg_condition_instance
from bkmonitor.utils.request import get_request
from bkmonitor.utils.time_tools import (
    datetime2timestamp,
    now,
    utc2datetime,
    utc2localtime,
)
from bkmonitor.utils.user import get_global_user, get_request_username
from constants.action import (
    ACTION_DISPLAY_STATUS_DICT,
    ActionPluginType,
    ActionSignal,
    NoticeWay,
)
from constants.alert import (
    CLUSTER_PATTERN,
    AlertFieldDisplay,
    EventStatus,
    EventTargetType, EVENT_STATUS_DICT,
)
from constants.data_source import DataSourceLabel, DataTypeLabel, UnifyQueryDataSources
from constants.strategy import SPLIT_DIMENSIONS
from core.drf_resource import Resource, api, resource
from core.drf_resource.exceptions import CustomException
from core.errors.alert import (
    AIOpsFunctionAccessedError,
    AIOpsMultiAnomlayDetectError,
    AIOpsResultError,
    AlertNotFoundError,
)
from core.errors.api import BKAPIError
from core.unit import load_unit
from fta_web.alert.handlers.action import ActionQueryHandler
from fta_web.alert.handlers.alert import AlertQueryHandler
from fta_web.alert.handlers.alert_log import AlertLogHandler
from fta_web.alert.handlers.event import EventQueryHandler
from fta_web.alert.handlers.translator import PluginTranslator
from fta_web.alert.serializers import (
    ActionIDField,
    ActionSearchSerializer,
    AlertFeedbackSerializer,
    AlertIDField,
    AlertSearchSerializer,
    AlertSuggestionSerializer,
    EventSearchSerializer,
)
from fta_web.models.alert import (
    SEARCH_TYPE_CHOICES,
    AlertFeedback,
    AlertSuggestion,
    MetricRecommendationFeedback,
    SearchHistory,
    SearchType,
)
from monitor_web.aiops.metric_recommend.constant import (
    METRIC_RECOMMAND_SCENE_SERVICE_TEMPLATE,
)
from monitor_web.constants import AlgorithmType
from monitor_web.data_explorer.resources import GetGraphQueryConfig
from monitor_web.models import CustomEventGroup

logger = logging.getLogger("root")


class AlertPermissionResource(Resource):
    @classmethod
    def has_biz_permission(cls):
        """
        业务鉴权
        """
        client = Permission()
        request = get_request(peaceful=True)
        try:
            is_allowed = client.is_allowed_by_biz(request.biz_id, ActionEnum.VIEW_EVENT, raise_exception=False)
        except Exception:
            logger.warning(
                "user(%s) permission validate failed, request path(%s), request.user(%s),"
                " user.type(%s), current request meta %s",
                client.username,
                request.path_info,
                request.user.__dict__,
                type(request.user),
                request.META,
            )
            raise
        return is_allowed

    @classmethod
    def has_alert_permission(cls, alert_id: int):
        """
        事件鉴权
        """
        try:
            alert = AlertDocument.get(alert_id)
            username = get_request().user.username
            bk_biz_id = int(get_request().biz_id)
            if int(alert.event.bk_biz_id) == bk_biz_id and username in alert.assignee:
                # 业务ID能对上
                # 是当前告警的负责人
                return True
        except Exception:
            pass
        return False

    @classmethod
    def filter_alert_ids(cls, alert_ids: List[int]):
        """
        过滤出有权限的事件ID
        """

        search = (
            AlertDocument.search(all_indices=True)
            .filter("terms", id=alert_ids)
            .filter("term", assignee=get_request().user.username)
            .source(fields=["id"])
        )

        return [hit.id for hit in search.scan()]

    @classmethod
    def has_alert_collect_permission(cls, alert_collect_id: int):
        """
        通知汇总鉴权
        """
        try:
            action = ActionInstance.objects.get(id=str(alert_collect_id)[10:])
            for alert in action.alerts:
                if not cls.has_alert_permission(alert):
                    # 只要其中有告警没权限，返回没权限
                    return False
        except Exception:
            pass

        return False

    def request(self, request_data=None, **kwargs):
        """
        执行请求，并对请求数据和返回数据进行数据校验
        """
        request_data = request_data or kwargs
        validated_request_data = self.validate_request_data(request_data)

        if not self.has_biz_permission():
            if "id" in validated_request_data and not self.has_alert_permission(validated_request_data["id"]):
                raise ValidationError(_("无该告警查看权限"))
            if "event_id" in validated_request_data and not self.has_alert_permission(
                validated_request_data["event_id"]
            ):
                raise ValidationError(_("无该告警查看权限"))
            elif "ids" in validated_request_data:
                validated_request_data["ids"] = self.filter_alert_ids(validated_request_data["ids"])
            elif "alert_collect_id" in validated_request_data:
                if not self.has_alert_collect_permission(validated_request_data["alert_collect_id"]):
                    raise ValidationError(_("无该告警查看权限"))
            elif "action_id" in validated_request_data:
                if not self.has_alert_collect_permission(validated_request_data["action_id"]):
                    raise ValidationError(_("无该告警查看权限"))
            else:
                validated_request_data["receiver"] = get_request().user.username

        response_data = self.perform_request(validated_request_data)
        validated_response_data = self.validate_response_data(response_data)
        return validated_response_data


class QuickActionTokenResource(AlertPermissionResource):
    def validate_request_data(self, request_data):
        validated_data = super(QuickActionTokenResource, self).validate_request_data(request_data)
        validated_data["alert_ids"] = self.validate_token(str(validated_data["action_id"]), validated_data["token"])
        return validated_data

    def validate_token(self, action_id, token):
        try:
            action = ActionInstance.objects.get(id=action_id[10:])
            create_timestamp = int(action.create_time.timestamp())
            alert_ids = action.alerts
        except ActionInstance.DoesNotExist:
            action_doc = ActionInstanceDocument.get(action_id)
            if not action_doc:
                raise CustomException(_("Resource[{}] 请求参数格式错误, 请求的通知ID不存在").format(self.get_resource_name()))
            create_timestamp = action_doc.create_time
            alert_ids = action_doc.alert_id
        if count_md5([action_id, create_timestamp]) != token:
            raise CustomException(_("Resource[{}] 请求参数格式错误, 请求的token不正确").format(self.get_resource_name()))
        return alert_ids

    @staticmethod
    def redirect(bk_biz_id, action_id):
        request = get_request()
        mobile_url = f"/weixin/?bizId={bk_biz_id}&collectId={action_id}"
        pc_url = f"/?bizId={bk_biz_id}&routeHash=event-center/?collectId={action_id}#/"
        redirect_url = mobile_url if request.is_mobile() else pc_url
        return HttpResponseRedirect(redirect_url)


class ListAllowedBizResource(Resource):
    """
    获取用户有某个操作权限的业务
    """

    class RequestSerializer(serializers.Serializer):
        action_id = serializers.CharField(label="动作ID")

    def perform_request(self, validated_request_data):
        permission = Permission()
        biz_list = permission.filter_business_list_by_action(validated_request_data["action_id"])
        return [{"id": biz.bk_biz_id, "name": biz.bk_biz_name} for biz in biz_list]


class ListSearchHistoryResource(Resource):
    """
    获取检索历史
    """

    class RequestSerializer(serializers.Serializer):
        search_type = serializers.ChoiceField(label="检索类型", choices=SEARCH_TYPE_CHOICES, default=SearchType.ALERT)
        count = serializers.IntegerField(label="返回条数", default=10, min_value=1)

    def perform_request(self, validated_request_data):
        username = get_request_username()
        histories = SearchHistory.objects.filter(
            create_user=username, search_type=validated_request_data["search_type"]
        ).order_by("-create_time")

        result: List[SearchHistory] = []
        params_set = set()
        for history in histories.iterator():
            query_string = history.params.get("query_string")
            if not query_string or query_string in params_set:
                continue
            result.append(history)
            params_set.add(query_string)
            if len(result) >= validated_request_data["count"]:
                break

        return [
            {
                "create_user": history.create_user,
                "create_time": history.create_time,
                "params": history.params,
                "duration": history.duration,
                "search_type": history.search_type,
            }
            for history in result
        ]


class AlertDateHistogramResource(Resource):
    """
    查询告警分布直方图
    """

    class RequestSerializer(AlertSearchSerializer):
        interval = serializers.CharField(label="聚合周期", default="auto")

    def perform_request(self, validated_request_data):
        interval = validated_request_data.pop("interval")
        handler = AlertQueryHandler(**validated_request_data)
        data = list(handler.date_histogram(interval=interval).values())[0]
        return {
            "series": [
                {"data": list(series.items()), "name": status, "display_name": EVENT_STATUS_DICT[status]}
                for status, series in data.items()
            ],
            "unit": "",
        }


class AlertDetailResource(Resource):
    """
    根据ID获取告警
    """

    class RequestSerializer(serializers.Serializer):
        id = AlertIDField(required=True, label="告警ID")

    @classmethod
    def translate_bk_monitor_log_metric(cls, query_config, **kwargs):
        # 关键字的节点维度需要转换成实际的维度字段
        dimensions = kwargs.get("dimensions", {})
        if "bk_obj_id" in dimensions and "bk_inst_id" in dimensions:
            bk_obj_id = dimensions.pop("bk_obj_id")
            bk_inst_id = dimensions.pop("bk_inst_id")
            dimensions[f"bk_{bk_obj_id}_id"] = str(bk_inst_id)

        query_config["metric_field"] = "event.count"

    @classmethod
    def translate_custom_event_metric(cls, query_config, **kwargs):
        # 关键字的节点维度需要转换成实际的维度字段
        filter_dict = kwargs.get("filter_dict", {})
        filter_dict["event_name"] = query_config["custom_event_name"]
        query_config["metric_field"] = "_index"

    @classmethod
    def translate_bk_monitor_alert_metric(cls, query_config, **kwargs):
        query_config["metric_field"] = query_config["bkmonitor_strategy_id"]
        query_config["result_table_id"] = "alert"

    @classmethod
    def translate_bk_log_search_log_metric(cls, query_config, **kwargs):
        query_config["metric_field"] = "_index"

    @classmethod
    def get_graph_panel(cls, alert: AlertDocument, compare_function=None, use_raw_query_config: bool = False):
        """
        获取图表配置
        :param alert: 告警对象
        :param compare_function:
        :param use_raw_query_config: 是否使用原始查询配置（适用于AIOps接入后要获取原始数据源的场景）
        """
        if compare_function is None:
            compare_function = {"time_compare": ["1d", "1w"]}
        if not alert.strategy:
            # 策略为空，则显示告警数量统计
            return {
                "id": "event",
                "type": "bar",
                "title": _("异常事件统计"),
                "subTitle": alert.alert_name,
                "targets": [
                    {
                        "data": {
                            "expression": "",
                            "query_configs": [
                                {
                                    "data_source_label": DataSourceLabel.BK_FTA,
                                    "data_type_label": DataTypeLabel.ALERT,
                                    "group_by": [],
                                    "table": "alert",
                                    "metrics": [{"field": alert.alert_name, "method": "COUNT"}],
                                    "interval": 60,
                                    "where": [],
                                    "time_field": "time",
                                    "filter_dict": {"dedupe_md5": alert.dedupe_md5},
                                }
                            ],
                            "function": compare_function,
                        },
                        "datasourceId": "time_series",
                        "name": _("时序数据"),
                        "alias": "$time_offset",
                    }
                ],
            }

        item = alert.strategy["items"][0]
        query_config = item["query_configs"][0]

        if use_raw_query_config:
            raw_query_config = query_config.get("raw_query_config", {})
            query_config.update(raw_query_config)

        unify_query_params = {
            "expression": item.get("expression", ""),
            "functions": item.get("functions", []),
            "query_configs": [],
            "function": compare_function,
        }

        extra_unify_query_params = {
            "expression": item.get("expression", ""),
            "functions": item.get("functions", []),
            "query_configs": [],
            "function": compare_function,
        }

        if (
            query_config["data_source_label"],
            query_config["data_type_label"],
        ) in AlertGraphQueryResource.AVAILABLE_DATA_LABEL:
            for query_config in item["query_configs"]:
                if use_raw_query_config:
                    raw_query_config = query_config.get("raw_query_config", {})
                    query_config.update(raw_query_config)

                dimensions = {}
                dimension_fields = query_config.get("agg_dimension", [])
                try:
                    dimensions = alert.event.extra_info.origin_alarm.data.dimensions.to_dict()
                    dimension_fields = alert.event.extra_info.origin_alarm.data.dimension_fields
                    dimension_fields = [field for field in dimension_fields if not field.startswith("bk_task_index_")]
                except Exception:  # NOCC:broad-except(设计如此:)
                    pass

                dimensions = {
                    key: value
                    for key, value in dimensions.items()
                    if key in dimension_fields and not (key == "le" and value is None)
                }
                filter_dict = {}
                translate_method_name = 'translate_{}_{}_metric'.format(
                    query_config["data_source_label"].lower(), query_config["data_type_label"].lower()
                )

                if query_config["data_source_label"] == DataSourceLabel.BK_FTA:
                    query_config["metric_field"] = query_config["alert_name"]
                    query_config["result_table_id"] = "event"
                elif hasattr(cls, translate_method_name):
                    translate_method = getattr(cls, translate_method_name)
                    translate_method(query_config, dimensions=dimensions, filter_dict=filter_dict)

                # promql添加维度过滤特殊处理
                if query_config["data_source_label"] == DataSourceLabel.PROMETHEUS:
                    where = []
                    agg_dimension = []
                    metrics = []
                    filter_dict = dimensions
                else:
                    where = GetGraphQueryConfig.create_where_with_dimensions(query_config["agg_condition"], dimensions)
                    agg_dimension = list(set(query_config["agg_dimension"]) & set(dimensions.keys()))
                    if "le" in query_config["agg_dimension"]:
                        # 针对le做特殊处理
                        agg_dimension.append("le")

                    metrics = [
                        {
                            "field": query_config.get("metric_field", "_index"),
                            "method": query_config.get("agg_method", "COUNT"),
                            "alias": query_config.get("alias", "A"),
                        }
                    ]

                if query_config["data_type_label"] == DataTypeLabel.ALERT:
                    metrics[0]["display"] = True

                # 扩展指标（针对智能异常检测，需要根据敏感度来）
                algorithm_list = item.get("algorithms", [])
                intelligent_algorithm_list = [
                    algorithm
                    for algorithm in algorithm_list
                    if algorithm["level"] == alert.severity and algorithm["type"] in AlgorithmModel.AIOPS_ALGORITHMS
                ]

                intelligent_detect_accessed = bool(query_config.get("intelligent_detect", {}).get("result_table_id"))

                extra_metrics = []
                if not use_raw_query_config and intelligent_algorithm_list and intelligent_detect_accessed:
                    visual_type = intelligent_algorithm_list[0]["config"].get("visual_type")
                    if visual_type != VisualType.FORECASTING:
                        metrics.append(
                            {
                                "field": "is_anomaly",
                                "method": query_config.get("agg_method", "MAX"),
                                "display": True,
                            }
                        )

                    if visual_type == VisualType.BOUNDARY:
                        metrics.extend(
                            [
                                {
                                    "field": "lower_bound",
                                    "method": query_config.get("agg_method", "MIN"),
                                    "display": True,
                                },
                                {
                                    "field": "upper_bound",
                                    "method": query_config.get("agg_method", "MAX"),
                                    "display": True,
                                },
                            ]
                        )
                    elif visual_type == VisualType.SCORE:
                        extra_metrics.append(
                            {"field": "anomaly_score", "method": query_config.get("agg_method", "MAX")}
                        )
                    elif visual_type == VisualType.FORECASTING:
                        extra_metrics.extend(
                            [
                                metrics[0],
                                {"field": "predict", "method": "", "display": True},
                                {"field": "lower_bound", "method": "", "display": True},
                                {"field": "upper_bound", "method": "", "display": True},
                            ]
                        )

                    # 当算法是离群检测时需要做特别的处理
                    if intelligent_algorithm_list[0]["type"] == AlgorithmModel.AlgorithmChoices.AbnormalCluster:
                        metrics = [
                            {"field": "value", "method": "AVG"},
                            {"field": "bounds", "method": "", "display": True},
                        ]

                        extra_metrics = []

                        agg_dimension = ["cluster"]

                        clusters = alert.event.extra_info.origin_alarm.data["values"]["cluster"]
                        pattern = re.compile(CLUSTER_PATTERN)
                        cluster_str_list = pattern.findall(clusters)
                        where.append({"condition": "and", "key": "cluster", "method": "eq", "value": cluster_str_list})

                        for index, condition in enumerate(where.copy()):
                            if condition.get("key") == "is_anomaly":
                                where.pop(index)
                                break

                query_config = {
                    "custom_event_name": query_config.get("custom_event_name", ""),
                    "query_string": query_config.get("query_string", ""),
                    "index_set_id": query_config.get("index_set_id", 0),
                    "bk_biz_id": alert.event.bk_biz_id,
                    "data_source_label": query_config["data_source_label"],
                    "data_type_label": query_config["data_type_label"],
                    "group_by": agg_dimension,
                    "table": query_config.get("result_table_id", ""),
                    "data_label": query_config.get("data_label", ""),
                    "promql": query_config.get("promql", ""),
                    "metrics": metrics,
                    "interval": query_config.get("agg_interval", 60),
                    "where": where,
                    "time_field": query_config.get("time_field"),
                    "extend_fields": query_config.get("extend_fields", {}),
                    "filter_dict": filter_dict,
                    "functions": query_config.get("functions", []),
                }

                unify_query_params["query_configs"].append(query_config)

                if extra_metrics:
                    extra_query_config = copy.deepcopy(query_config)
                    extra_query_config["metrics"] = extra_metrics
                    extra_unify_query_params["query_configs"].append(extra_query_config)

        if not unify_query_params["query_configs"]:
            return

        data_source_label = unify_query_params["query_configs"][0]["data_source_label"]
        data_type_label = unify_query_params["query_configs"][0]["data_type_label"]
        is_bar = (data_source_label, data_type_label) in (
            (DataSourceLabel.BK_FTA, DataTypeLabel.ALERT),
            (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.ALERT),
            (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG),
            (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT),
            (DataSourceLabel.BK_FTA, DataTypeLabel.EVENT),
        )

        is_composite = data_type_label == DataTypeLabel.ALERT

        sub_titles = "\n".join([query_config["metric_id"] for query_config in item["query_configs"]])

        panel = {
            "id": "event",
            "type": "bar" if is_bar else "graph",
            "title": item.get("name") or item.get("expression", ""),
            "subTitle": sub_titles,
            "targets": [
                {
                    "data": unify_query_params,
                    "datasourceId": "time_series",
                    "name": _("时序数据"),
                    "alias": "$metric_field-$time_offset" if is_composite else "$time_offset",
                }
            ],
        }

        if extra_unify_query_params["query_configs"]:
            panel["targets"].append(
                {
                    "data": extra_unify_query_params,
                    "datasourceId": "time_series",
                    "name": _("时序数据"),
                    "alias": "$time_offset",
                }
            )

        return panel

    @classmethod
    def get_relation_info(cls, alert: AlertDocument):
        """
        获取告警最近的日志
        """
        return get_alert_relation_info(alert)

    def perform_request(self, validated_request_data):
        alert_id = validated_request_data["id"]

        alert = AlertDocument.get(alert_id)

        graph_panel = self.get_graph_panel(alert)
        relation_info = self.get_relation_info(alert)

        result = AlertQueryHandler.clean_document(alert)
        result["plugin_display_name"] = PluginTranslator().translate([result["plugin_id"]])[result["plugin_id"]]
        result["extend_info"] = resource.alert.alert_related_info(ids=[alert_id]).get(alert_id, {})
        result["graph_panel"] = graph_panel

        topo_info = result["extend_info"].get("topo_info", "")
        result["relation_info"] = f"{topo_info} {relation_info}"

        return result


class GetExperienceResource(ApiAuthResource):
    """
    获取告警处理经验
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        alert_id = AlertIDField(required=False, label="告警ID")
        metric_id = serializers.CharField(label="指标", required=False)

        def validate(self, attrs):
            if "alert_id" not in attrs and "metric_id" not in attrs:
                raise ValidationError("alert_id and metric_id cannot be empty at the same time")
            return attrs

    def perform_request(self, params):
        if "alert_id" in params:
            alert_id = params["alert_id"]
            alert = AlertDocument.get(alert_id)
            metric = list(alert.event_document.metric)
            bk_biz_id = alert.event_document.bk_biz_id or 0

            if not metric:
                alert_name = alert.alert_name
            else:
                alert_name = ""

            dimensions = {dimension.key: dimension.value for dimension in alert.dimensions}
            if alert.origin_alarm:
                dimensions.update(alert.origin_alarm.get("data", {}).get("dimensions", {}))
        else:
            bk_biz_id = params["bk_biz_id"]
            metric = params["metric_id"].split(",")
            dimensions = {}
            alert_name = ""

        suggestions = []

        for suggestion in AlertSuggestion.objects.filter(bk_biz_id=bk_biz_id).order_by("-update_time"):
            if suggestion.alert_name == alert_name and suggestion.metric == metric:
                data = AlertSuggestionSerializer(instance=suggestion).data
                if suggestion.type == AlertSuggestion.Type.METRIC:
                    data["is_match"] = True
                else:
                    condition_obj = load_agg_condition_instance(suggestion.conditions)
                    data["is_match"] = condition_obj.is_match(dimensions)
                suggestions.append(data)

        # 匹配的排在前头
        suggestions.sort(key=lambda x: x["is_match"], reverse=True)

        # metric 排在前头
        suggestions.sort(key=lambda x: x["type"] == AlertSuggestion.Type.METRIC, reverse=True)
        return suggestions


class SaveExperienceResource(Resource):
    """
    保存告警处理经验
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        alert_id = AlertIDField(required=False, label="告警ID")
        metric_id = serializers.CharField(required=False, label="指标ID")

        description = serializers.CharField(required=True, label="处理描述")
        type = serializers.ChoiceField(label="类型", choices=AlertSuggestion.TYPE_CHOICES)
        conditions = serializers.ListField(default=[], label="查询条件", allow_empty=True, child=serializers.DictField())

        def validate(self, attrs):
            if "alert_id" not in attrs and "metric_id" not in attrs:
                raise ValidationError("alert_id and metric_id cannot be empty at the same time")
            return attrs

    def perform_request(self, params):
        if "alert_id" in params:
            alert_id = params["alert_id"]

            alert = AlertDocument.get(alert_id)
            metric = list(alert.event_document.metric)
            bk_biz_id = alert.event_document.bk_biz_id or 0

            if not metric:
                alert_name = alert.alert_name
            else:
                alert_name = ""
        else:
            alert_name = ""
            bk_biz_id = params["bk_biz_id"]
            metric = params["metric_id"].split(",")
        if params["type"] == AlertSuggestion.Type.METRIC:
            params["conditions"] = []

        suggestion_id = AlertSuggestion.generate_id(
            bk_biz_id=bk_biz_id,
            type=params["type"],
            metric=metric,
            alert_name=alert_name,
            conditions=params["conditions"],
        )

        try:
            suggestion = AlertSuggestion.objects.get(id=suggestion_id)
        except AlertSuggestion.DoesNotExist:
            suggestion = AlertSuggestion(
                id=suggestion_id,
                create_user=get_global_user(),
                bk_biz_id=bk_biz_id,
                type=params["type"],
                metric=metric,
                alert_name=alert_name,
                conditions=params["conditions"],
            )

        suggestion.description = params["description"]
        suggestion.save()

        return AlertSuggestionSerializer(instance=suggestion).data


class DeleteExperienceResource(Resource):
    """
    删除处理经验
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.CharField(label="处理建议ID")

    def perform_request(self, validated_request_data):
        try:
            suggestion = AlertSuggestion.objects.get(id=validated_request_data["id"])
        except AlertSuggestion.DoesNotExist:
            pass
        else:
            # 进行硬删除
            suggestion.delete(hard=True)


class AlertEventCountResource(Resource):
    """
    获取告警关联的事件数量
    """

    class RequestSerializer(serializers.Serializer):
        ids = serializers.ListField(label="告警ID", child=AlertIDField())

    @classmethod
    def cal_simple_event_count(cls, simple_alerts):
        # 计算简单告警的事件数量
        if not simple_alerts:
            return {}

        now_time = int(time.time())
        alert_mapping = {}
        for alert in simple_alerts:
            alert_mapping[alert.id] = {
                "dedupe_md5": alert.dedupe_md5,
                "query": (
                    Q("range", time={"gte": alert.begin_time, "lte": alert.latest_time or now_time})
                    & Q("term", dedupe_md5=alert.dedupe_md5)
                ),
            }

        event_count = {}
        # Step 2: 根据时间范围和MD5去查询告警信息
        search = EventDocument.search(all_indices=True)
        search = search.filter("terms", dedupe_md5=[alert["dedupe_md5"] for alert in alert_mapping.values()])

        for alert_id, alert in alert_mapping.items():
            # 为每个告警条件设置一个桶
            search.aggs.bucket(alert_id, "filter", alert["query"])

        search = search.extra(size=0)
        search_result = search.execute()

        for alert_id in alert_mapping:
            if not search_result.aggs:
                continue
            bucket = getattr(search_result.aggs, alert_id, None)
            if not bucket:
                continue
            event_count[alert_id] = bucket.doc_count
        return event_count

    @classmethod
    def cal_composite_event_count(cls, composite_alerts):
        """
        计算关联告警的事件数量
        """
        if not composite_alerts:
            return {}

        event_count = {}
        results = resource.alert.search_event.bulk_request(
            [{"alert_id": alert.id, "page_size": 1} for alert in composite_alerts], ignore_exceptions=True
        )
        for index, result in enumerate(results):
            if result:
                event_count[composite_alerts[index].id] = result["total"]
        return event_count

    def perform_request(self, validated_request_data):
        alert_ids = validated_request_data["ids"]

        # Step 1: 先根据告警ID，查询对应的告警，将开始结束时间和md5字段拿出来
        alerts = AlertDocument.mget(
            alert_ids, fields=["id", "begin_time", "end_time", "latest_time", "dedupe_md5", "extra_info"]
        )

        simple_alerts = []
        composite_alerts = []
        for alert in alerts:
            if alert.is_composite_strategy or alert.is_fta_event_strategy:
                composite_alerts.append(alert)
            else:
                simple_alerts.append(alert)

        event_count = {}
        for alert_id in alert_ids:
            event_count.setdefault(alert_id, 0)
        event_count.update(self.cal_simple_event_count(simple_alerts))
        event_count.update(self.cal_composite_event_count(composite_alerts))
        return event_count


class AlertRelatedInfoResource(Resource):
    """
    事件关联信息查询
    """

    class RequestSerializer(serializers.Serializer):
        ids = serializers.ListField(label="告警ID", child=AlertIDField())

    @staticmethod
    def get_cmdb_related_info(alerts: List[AlertDocument]) -> Dict[str, Dict]:
        """
        查询事件拓扑信息

        {
            "type": "host",
            "ip"： "",
            "bk_cloud_id": "",
            "hostname": "",
            "topo_info": ""
        }
        """
        related_infos = defaultdict(dict)

        # 提取事件的主机IP和服务实例ID，按业务分组
        instances_by_biz = defaultdict(lambda: {"ips": {}, "service_instance_ids": {}, "host_ids": {}})
        for alert in alerts:
            event = alert.event
            dimensions_dict = {d["key"]: d["value"] for d in alert.dimensions}
            if event.target_type == EventTargetType.HOST:
                if hasattr(event, "bk_host_id"):
                    instances_by_biz[event.bk_biz_id]["host_ids"][alert.id] = int(event.bk_host_id)
                else:
                    instances_by_biz[event.bk_biz_id]["ips"][alert.id] = {
                        "ip": event.ip,
                        "bk_cloud_id": int(event.bk_cloud_id),
                    }
                related_infos[alert.id]["ip"] = event.ip
                related_infos[alert.id]["bk_cloud_id"] = getattr(event, "bk_cloud_id", "")
                related_infos[alert.id]["type"] = "host"
            elif dimensions_dict.get("ip"):
                bk_cloud_id = dimensions_dict.get("bk_cloud_id", 0)
                if dimensions_dict.get("bk_host_id"):
                    instances_by_biz[event.bk_biz_id]["host_ids"][alert.id] = int(dimensions_dict["bk_host_id"])
                else:
                    instances_by_biz[event.bk_biz_id]["ips"][alert.id] = {
                        "ip": dimensions_dict["ip"],
                        "bk_cloud_id": bk_cloud_id,
                    }

                related_infos[alert.id]["ip"] = dimensions_dict["ip"]
                related_infos[alert.id]["bk_cloud_id"] = bk_cloud_id
                related_infos[alert.id]["type"] = dimensions_dict.get("target_type", "")
            elif event.target_type == EventTargetType.SERVICE:
                instances_by_biz[event.bk_biz_id]["service_instance_ids"][alert.id] = event.bk_service_instance_id

        for bk_biz_id, instances in instances_by_biz.items():
            ips = instances["ips"]
            service_instance_ids = instances["service_instance_ids"]
            host_ids = instances["host_ids"]
            # 查询主机和服务实例信息
            hosts: List[Host] = api.cmdb.get_host_by_ip(bk_biz_id=bk_biz_id, ips=list(ips.values()))
            hosts.extend(api.cmdb.get_host_by_id(bk_biz_id=bk_biz_id, bk_host_ids=list(host_ids.values())))
            service_instances: List[ServiceInstance] = api.cmdb.get_service_instance_by_id(
                bk_biz_id=bk_biz_id, service_instance_ids=list(service_instance_ids.values())
            )

            # 将主机和服务实例转为模块ID
            host_to_module_id = {(host.bk_host_innerip, host.bk_cloud_id): host.bk_module_ids for host in hosts}
            host_to_hostname = {(host.bk_host_innerip, host.bk_cloud_id): host.bk_host_name for host in hosts}
            host_id_to_module_id = {host.bk_host_id: host.bk_module_ids for host in hosts}
            host_id_to_hostname = {host.bk_host_id: host.bk_host_name for host in hosts}
            service_to_module_id = {service.service_instance_id: service.bk_module_id for service in service_instances}

            all_bk_module_ids = set()
            for host in hosts:
                all_bk_module_ids.update(host.bk_module_ids)
            for service_instance in service_instances:
                all_bk_module_ids.add(service_instance.bk_module_id)

            # 查询模块和集群信息
            modules = api.cmdb.get_module(bk_biz_id=bk_biz_id, bk_module_ids=all_bk_module_ids)
            module_to_set = {module.bk_module_id: module.bk_set_id for module in modules}
            sets = api.cmdb.get_set(bk_biz_id=bk_biz_id, bk_set_ids=list(module_to_set.values()))
            module_names = {module.bk_module_id: module.bk_module_name for module in modules}
            set_names = {s.bk_set_id: s.bk_set_name for s in sets}

            # 事件对应到模块ID
            alert_to_module_ids = {}
            for alert_id, ip in ips.items():
                alert_to_module_ids[alert_id] = host_to_module_id.get((ip["ip"], ip["bk_cloud_id"]), [])
                related_infos[alert_id]["hostname"] = host_to_hostname.get((ip["ip"], ip["bk_cloud_id"]), "")

            for alert_id, host_id in host_ids.items():
                alert_to_module_ids[alert_id] = host_id_to_module_id.get(host_id, [])
                related_infos[alert_id]["hostname"] = host_id_to_hostname.get(host_id, "")

            for alert_id, service_instance_id in service_instance_ids.items():
                if service_instance_id in service_to_module_id:
                    alert_to_module_ids[alert_id] = [service_to_module_id[service_instance_id]]

            # 记录事件集群模块描述信息
            for alert_id, bk_module_ids in alert_to_module_ids.items():
                topo_info = ""
                if not bk_module_ids:
                    related_infos[alert_id]["topo_info"] = topo_info
                    continue

                bk_set_ids = [
                    module_to_set[bk_module_id] for bk_module_id in bk_module_ids if bk_module_id in module_to_set
                ]

                if bk_set_ids:
                    topo_info += _("集群({}) ").format(
                        ",".join([set_names[bk_set_id] for bk_set_id in bk_set_ids if bk_set_id in set_names])
                    )

                topo_info += _("模块({})").format(
                    ",".join(
                        [module_names[bk_module_id] for bk_module_id in bk_module_ids if bk_module_id in module_names]
                    )
                )
                related_infos[alert_id]["topo_info"] = topo_info

        return related_infos

    @staticmethod
    def get_log_related_info(alerts: List[AlertDocument]) -> Dict[str, Dict]:
        """
        日志平台关联信息

        {
            "type": "log_search",
            "index_set_id": "",
            "query_string": "",
            "agg_condition": []
        }
        """

        related_infos = defaultdict(dict)

        for alert in alerts:
            if not alert.strategy:
                continue
            item = alert.strategy["items"][0]
            query_config = item["query_configs"][0]
            if query_config["data_source_label"] != DataSourceLabel.BK_LOG_SEARCH:
                continue

            if not query_config.get("index_set_id"):
                continue

            related_infos[alert.id] = {
                "type": "log_search",
                "index_set_id": query_config["index_set_id"],
                "query_string": query_config.get("query_string", "*"),
                "agg_condition": query_config["agg_condition"],
            }

        return related_infos

    @staticmethod
    def get_custom_event_related_info(alerts: List[AlertDocument]) -> Dict[str, Dict]:
        """
        自定义事件关联信息

        {
            "type": "custom_event",
            "bk_event_group_id": 1
        }
        """
        related_infos = defaultdict(dict)

        event_groups = CustomEventGroup.objects.filter(
            bk_biz_id__in=[alert.event.bk_biz_id for alert in alerts if alert.event.bk_biz_id]
        )
        table_id_to_group_ids = {event_group.table_id: event_group.bk_event_group_id for event_group in event_groups}

        for alert in alerts:
            if not alert.strategy:
                continue
            item = alert.strategy["items"][0]
            query_config = item["query_configs"][0]

            related_infos[alert.id]["result_table_id"] = query_config.get("result_table_id")
            related_infos[alert.id]["data_label"] = query_config.get("data_label", "")

            if (query_config["data_source_label"], query_config["data_type_label"]) != (
                DataSourceLabel.CUSTOM,
                DataTypeLabel.EVENT,
            ):
                continue

            if query_config["result_table_id"] in table_id_to_group_ids:
                related_infos[alert.id]["type"] = "custom_event"
                related_infos[alert.id]["bk_event_group_id"] = table_id_to_group_ids[query_config["result_table_id"]]

        return related_infos

    @staticmethod
    def get_bkdata_related_info(alerts: List[AlertDocument]) -> Dict[str, Dict]:
        """
        数据平台关联信息
        {
            "type": "bkdata",
            "metric_field": "",
            "group_by": "",
            "result_table_id": "",
            "method": "",
            "where": "",
            "interval": "",
        }
        """
        related_infos = defaultdict(dict)

        for alert in alerts:
            if not alert.strategy:
                continue
            strategy = alert.strategy

            if not strategy["items"]:
                continue

            item = strategy["items"][0]
            query_config = item["query_configs"][0]

            raw_query_config = query_config.get("raw_query_config", {})
            query_config.update(raw_query_config)

            if query_config["data_source_label"] != DataSourceLabel.BK_DATA:
                continue

            related_infos[alert.id] = {
                "type": "bkdata",
                "query_configs": [
                    {
                        "data_type_label": query_config["data_type_label"],
                        "data_source_label": query_config["data_source_label"],
                        "metric_field": query_config["metric_field"],
                        "group_by": query_config["agg_dimension"],
                        "result_table_id": query_config["result_table_id"],
                        "method": query_config["agg_method"],
                        "where": query_config["agg_condition"],
                        "interval": query_config["agg_interval"],
                    }
                ],
            }

        return related_infos

    def perform_request(self, validated_request_data):
        alerts = AlertDocument.mget(validated_request_data["ids"])
        related_infos = defaultdict(dict)

        for func in [
            self.get_cmdb_related_info,
            self.get_custom_event_related_info,
            self.get_bkdata_related_info,
            self.get_log_related_info,
        ]:
            infos = func(alerts)
            for alert_id, info in infos.items():
                related_infos[alert_id].update(info)

        return related_infos


class AckAlertResource(Resource):
    """
    告警确认
    """

    class RequestSerializer(serializers.Serializer):
        ids = serializers.ListField(label="告警ID", child=AlertIDField())
        message = serializers.CharField(required=True, allow_blank=True, label="确认信息")

    def perform_request(self, validated_request_data):
        alert_ids = validated_request_data["ids"]

        alerts_should_ack = set()
        alerts_already_ack = set()
        alerts_not_abnormal = set()

        alerts = AlertDocument.mget(alert_ids)

        for alert in alerts:
            if alert.status != EventStatus.ABNORMAL:
                alerts_not_abnormal.add(alert.id)
            elif alert.is_ack:
                alerts_already_ack.add(alert.id)
            else:
                alerts_should_ack.add(alert.id)

        alerts_not_exist = set(alert_ids) - alerts_should_ack - alerts_already_ack - alerts_not_abnormal

        now_time = int(time.time())
        # 保存流水日志
        AlertLog(
            alert_id=list(alerts_should_ack),
            op_type=AlertLog.OpType.ACK,
            create_time=now_time,
            description=validated_request_data["message"],
            operator=get_request_username(),
        ).save()

        # 更新告警确认状态
        alert_documents = [
            AlertDocument(
                id=alert_id,
                is_ack=True,
                is_ack_noticed=False,
                ack_operator=get_request_username(),
                update_time=now_time,
            )
            for alert_id in alerts_should_ack
        ]
        AlertDocument.bulk_create(alert_documents, action=BulkActionType.UPDATE)
        return {
            "alerts_ack_success": list(alerts_should_ack),
            "alerts_not_exist": list(alerts_not_exist),
            "alerts_already_ack": list(alerts_already_ack),
            "alerts_not_abnormal": list(alerts_not_abnormal),
        }


class AlertGraphQueryResource(ApiAuthResource):
    """
    告警图表接口
    """

    class RequestSerializer(serializers.Serializer):
        class QueryConfigSerializer(serializers.Serializer):
            class MetricSerializer(serializers.Serializer):
                field = serializers.CharField()
                method = serializers.CharField(allow_blank=True)
                alias = serializers.CharField(required=False)
                display = serializers.BooleanField(default=False)

            data_source_label = serializers.CharField(label="数据来源")
            data_type_label = serializers.CharField(
                label="数据类型", default="time_series", allow_null=True, allow_blank=True
            )
            metrics = serializers.ListField(label="查询指标", allow_empty=True, child=MetricSerializer(), default=[])
            table = serializers.CharField(label="结果表名", allow_blank=True, default="")
            data_label = serializers.CharField(label="db标识", allow_blank=True, default="")
            promql = serializers.CharField(label="PromQL", allow_blank=True, required=False)
            where = serializers.ListField(label="过滤条件", default=[])
            group_by = serializers.ListField(label="聚合字段", default=[])
            interval = serializers.IntegerField(default=60, label="时间间隔")
            filter_dict = serializers.DictField(default={}, label="过滤条件")
            time_field = serializers.CharField(label="时间字段", allow_blank=True, allow_null=True, required=False)

            # 日志平台配置
            query_string = serializers.CharField(default="", allow_blank=True, label="日志查询语句")
            index_set_id = serializers.IntegerField(required=False, label="索引集ID")
            functions = serializers.ListField(label="查询函数", default=[])

            def validate(self, attrs: Dict) -> Dict:
                if attrs["data_source_label"] == DataSourceLabel.BK_LOG_SEARCH and not attrs.get("index_set_id"):
                    raise ValidationError("index_set_id can not be empty.")
                return attrs

        id = serializers.IntegerField(label="事件ID")
        bk_biz_id = serializers.IntegerField(label="业务ID")
        query_configs = serializers.ListField(label="查询配置列表", default=[], child=QueryConfigSerializer())
        function = serializers.DictField(label="功能函数", default={})
        functions = serializers.ListField(label="计算函数", default=[])
        expression = serializers.CharField(label="查询表达式", allow_blank=True)
        start_time = serializers.IntegerField(required=False, label="开始时间")
        end_time = serializers.IntegerField(required=False, label="结束时间")

    AVAILABLE_DATA_LABEL = (
        (DataSourceLabel.BK_DATA, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG),
        (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT),
        (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG),
        (DataSourceLabel.BK_FTA, DataTypeLabel.EVENT),
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.ALERT),
        (DataSourceLabel.BK_FTA, DataTypeLabel.ALERT),
        (DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES),
    )

    def perform_request(self, params: Dict):
        alert = AlertDocument.get(params["id"])
        if not params.get("query_configs"):
            graph_query_config = AlertDetailResource.get_graph_panel(alert, compare_function={})
            params.update(graph_query_config["targets"][0]["data"])

        if alert.strategy:
            item = alert.strategy["items"][0]
            query_config = item["query_configs"][0]
            if (query_config["data_source_label"], query_config["data_type_label"]) not in self.AVAILABLE_DATA_LABEL:
                return []
        else:
            # 第三方告警的情况
            item = None
            query_config = {}

        threshold_band = {"from": alert.first_anomaly_time * 1000, "to": None}

        # 1. 时间的起始时间，当刚发生时是发生时间段往前60个周期的图。
        # 2. 当发生的时间一直往后延，起始时间变成 初次异常+5个周期前数据
        # 3. 结束时间一直到事件结束的后的5个周期 ，或者超过1440个周期 最多到1440个周期数据
        if not params.get("start_time") or not params.get("end_time"):
            start_time = alert.begin_time
            if alert.end_time:
                threshold_band["to"] = alert.end_time * 1000
                end_time = alert.end_time
            else:
                end_time = datetime2timestamp(now())
            interval = params["query_configs"][0]["interval"]
            end_time = min(end_time + interval * 5, start_time + 1440 * interval)
            diff = 1440 * interval - (end_time - start_time)
            if diff < interval * 5:
                diff = interval * 5
            elif diff > interval * 60:
                diff = interval * 60
            start_time -= diff
            params["start_time"] = int(start_time)
            params["end_time"] = int(end_time)
        else:
            start_time = params["start_time"]
            end_time = params["end_time"]
        for q_config in params["query_configs"]:
            q_config["bk_biz_id"] = params["bk_biz_id"]

        logger.info("alert graph query params %s", dict(params))
        result = resource.grafana.graph_unify_query(params)

        result["trace_series"] = []
        if (
            query_config
            and (query_config["data_source_label"], query_config["data_type_label"]) in UnifyQueryDataSources
        ):
            # 数据源是蓝鲸监控和自定义上报的时序数据才支持trace信息查找
            try:
                result["trace_series"] = resource.grafana.graph_trace_query(params).get("series", [])
            except BaseException as error:
                logger.warning("alert trace value query failed %s", str(error))
        data = result["series"]
        if not data or not item:
            return result

        unit = load_unit(data[0].get("unit", ""))
        # 暂时只支持静态阈值,以后显示同比环比
        # 用列表是因为同一level下,可以既有静态阈值,又有同比策略
        alert_algorithm_list = [algorithm for algorithm in item["algorithms"] if algorithm["level"] == alert.severity]
        threshold_line = []
        if len(alert_algorithm_list) == 1 and alert_algorithm_list[0]["type"] == AlgorithmType.Threshold:
            threshold_config = alert_algorithm_list[0]["config"]
            if len(threshold_config) == 1 and len(threshold_config[0]) == 1:
                # 算法的值转换为数值单位
                algorithm_unit = alert_algorithm_list[0].get("unit_prefix", "")
                threshold_value = float(threshold_config[0][0]["threshold"])
                threshold_value = unit.convert(threshold_value, unit.unit, algorithm_unit)

                threshold_line.append({"yAxis": threshold_value, "name": _("阈值算法")})

        # 取出首次异常点，保证首次异常点在图表中
        point = None
        try:
            # 针对时序预测进行特殊处理，将未来时间的点标记出来
            for series in data:
                if series["metric_field"] != "predict":
                    continue
                # 尝试取出预测点
                anomaly = alert.event.extra_info.origin_alarm.anomaly.to_dict()
                predict_point = list(anomaly.values())[0]["context"]["predict_point"]
                point = [predict_point[0], predict_point[1] * 1000]
                series["markPoints"] = [point]
                break
        except Exception:
            pass

        if point:
            return result

        point = [alert.origin_alarm["data"]["value"], threshold_band["from"]]
        point_time_list = [point[1] for point in data[0]["datapoints"]]
        first_anomaly_in_time_range = start_time <= threshold_band["from"] <= end_time
        if threshold_band["from"] not in point_time_list and first_anomaly_in_time_range:
            position = bisect.bisect(point_time_list, threshold_band["from"])
            data[0]["datapoints"].insert(position, point)

        mark_points = [point]

        # 离群检测算法特殊处理
        if (
            len(alert_algorithm_list) == 1
            and alert_algorithm_list[0]["type"] == AlgorithmModel.AlgorithmChoices.AbnormalCluster
        ):
            # 离群检测算法不需要异常点
            mark_points = []

            # 离群检测所有维度都需要区域
            for data_item in data:
                data_item["markTimeRange"] = [threshold_band]

        data[0]["markTimeRange"] = [threshold_band]
        data[0]["markPoints"] = mark_points
        data[0]["thresholds"] = threshold_line

        return result


class EventDateHistogramResource(Resource):
    class RequestSerializer(serializers.Serializer):
        alert_id = AlertIDField(required=True, label="告警ID")
        start_time = serializers.IntegerField(label="开始时间", required=False)
        end_time = serializers.IntegerField(label="结束时间", required=False)
        interval = serializers.CharField(label="聚合周期", default="auto")

    def perform_request(self, validated_request_data):
        alert_id = validated_request_data["alert_id"]
        alert = AlertDocument.get(alert_id)
        handler = EventQueryHandler(
            dedupe_md5=alert.dedupe_md5,
            start_time=validated_request_data.get("start_time") or alert.begin_time,
            end_time=validated_request_data.get("end_time") or alert.end_time or int(time.time()),
        )
        return handler.date_histogram(interval=validated_request_data["interval"])


class SearchAlertResource(Resource):
    """
    查询告警数据
    """

    class RequestSerializer(AlertSearchSerializer):
        ordering = serializers.ListField(label="排序", child=serializers.CharField(), default=[])
        page = serializers.IntegerField(label="页数", min_value=1, default=1)
        page_size = serializers.IntegerField(label="每页大小", min_value=0, max_value=5000, default=10)
        show_overview = serializers.BooleanField(label="展示总览统计信息", default=True)
        show_aggs = serializers.BooleanField(label="展示聚合统计信息", default=True)
        show_dsl = serializers.BooleanField(label="展示DSL", default=False)
        record_history = serializers.BooleanField(label="是否保存收藏历史", default=False)
        must_exists_fields = serializers.ListField(label="必要字段", child=serializers.CharField(), default=[])

    def perform_request(self, validated_request_data):
        show_overview = validated_request_data.pop("show_overview")
        show_aggs = validated_request_data.pop("show_aggs")
        show_dsl = validated_request_data.pop("show_dsl")
        record_history = validated_request_data.pop("record_history")

        handler = AlertQueryHandler(**validated_request_data)

        with SearchHistory.record(
            SearchType.ALERT,
            validated_request_data,
            enabled=record_history and validated_request_data.get("query_string"),
        ):
            result = handler.search(show_overview=show_overview, show_aggs=show_aggs, show_dsl=show_dsl)

        return result


class ExportAlertResource(Resource):
    """
    导出告警数据
    """

    class RequestSerializer(AlertSearchSerializer):
        ordering = serializers.ListField(label="排序", child=serializers.CharField(), default=[])

    def perform_request(self, validated_request_data):
        handler = AlertQueryHandler(**validated_request_data)
        alerts = handler.export()
        id_key = AlertFieldDisplay.ID
        ids = [item[id_key] for item in alerts]
        related_infos = AlertRelatedInfoResource().perform_request({"ids": ids})
        for alert_doc in alerts:
            # 更新关联信息
            alert_doc.update({AlertFieldDisplay.RELATED_INFO: related_infos.get(alert_doc[id_key], {})})
        return resource.export_import.export_package(list_data=alerts)


class SearchEventResource(ApiAuthResource):
    """
    搜索告警关联的事件数据
    """

    class RequestSerializer(EventSearchSerializer):
        page = serializers.IntegerField(label="页数", min_value=1, default=1)
        page_size = serializers.IntegerField(label="每页大小", min_value=0, max_value=1000, default=10)
        show_dsl = serializers.BooleanField(label="展示DSL", default=False)
        record_history = serializers.BooleanField(label="是否保存收藏历史", default=False)
        show_raw = serializers.BooleanField(label="是否展示原始事件", default=False)

    @staticmethod
    def get_dedupe_md5_set(alert, start_time, end_time, interval):
        dedupe_md5_set = set()
        for query_config in alert.strategy["items"][0]["query_configs"]:
            query_config["agg_dimension"] = ["dedupe_md5"]
            ds_cls = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
            ds = ds_cls.init_by_query_config(query_config)
            ds.interval = interval
            records = ds.query_data(start_time=start_time * 1000, end_time=end_time * 1000, limit=10000)
            for record in records:
                dedupe_md5_set.add(record["dedupe_md5"])
        return dedupe_md5_set

    @classmethod
    def search_composite_alerts(cls, alert, validated_request_data, show_dsl=False):
        # 如果是关联告警，需要找出其关联的告警内容，并将其适配为事件
        start_time = alert.begin_time
        end_time = alert.end_time if alert.end_time else int(time.time())
        interval = AlertQueryHandler.calculate_agg_interval(start_time, end_time)
        dedupe_md5_set = cls.get_dedupe_md5_set(alert, start_time, end_time, interval)
        conditions = [
            {
                "key": dim["key"],
                "value": [dim["value"]],
                "method": "eq",
                "condition": "and",
            }
            for dim in alert.dimensions or []
        ]

        handler = AlertQueryHandler(
            start_time=start_time,
            end_time=end_time,
            conditions=[
                {
                    "key": "dedupe_md5",
                    "value": list(dedupe_md5_set),
                    "method": "eq",
                }
            ]
            + conditions,
            **validated_request_data,
        )
        alert_result, _ = handler.search_raw()

        result = {
            "total": min(alert_result.hits.total.value, 10000),
            "events": EventQueryHandler.handle_hit_list(
                [AlertQueryHandler.adapt_to_event(alert.to_dict()) for alert in alert_result]
            ),
        }

        return result

    @classmethod
    def search_fta_alerts(cls, alert, validated_request_data, show_dsl=False):
        # 如果是关联告警，需要找出其关联的告警内容，并将其适配为事件
        start_time = alert.begin_time
        end_time = alert.end_time if alert.end_time else int(time.time())
        interval = EventQueryHandler.calculate_agg_interval(start_time, end_time)
        dedupe_md5_set = cls.get_dedupe_md5_set(alert, start_time, end_time, interval)
        conditions = [
            {
                "key": dim["key"],
                "value": [dim["value"]],
                "method": "eq",
                "condition": "and",
            }
            for dim in alert.dimensions or []
        ]

        handler = EventQueryHandler(
            start_time=start_time,
            end_time=end_time,
            conditions=[
                {
                    "key": "dedupe_md5",
                    "value": list(dedupe_md5_set),
                    "method": "eq",
                }
            ]
            + conditions,
            **validated_request_data,
        )
        result = handler.search(show_dsl=show_dsl)
        return result

    def perform_request(self, validated_request_data):
        alert_id = validated_request_data["alert_id"]
        record_history = validated_request_data.pop("record_history")
        show_dsl = validated_request_data.pop("show_dsl")

        alert = AlertDocument.get(alert_id)

        with SearchHistory.record(
            SearchType.EVENT,
            validated_request_data,
            enabled=record_history and validated_request_data.get("query_string"),
        ):
            if alert.is_composite_strategy and not validated_request_data["show_raw"]:
                result = self.search_composite_alerts(alert, validated_request_data, show_dsl)
            elif alert.is_fta_event_strategy and not validated_request_data["show_raw"]:
                result = self.search_fta_alerts(alert, validated_request_data, show_dsl)
            else:
                handler = EventQueryHandler(
                    dedupe_md5=alert.dedupe_md5,
                    start_time=alert.begin_time,
                    end_time=alert.latest_time or int(time.time()),
                    **validated_request_data,
                )
                result = handler.search(show_dsl=show_dsl)

        return result


class SearchActionResource(ApiAuthResource):
    """
    查询处理记录数据
    """

    class RequestSerializer(ActionSearchSerializer):
        ordering = serializers.ListField(label="排序", child=serializers.CharField(), default=[])
        page = serializers.IntegerField(label="页数", min_value=1, default=1)
        page_size = serializers.IntegerField(label="每页大小", min_value=0, max_value=1000, default=10)

        show_overview = serializers.BooleanField(label="展示总览统计信息", default=True)
        show_aggs = serializers.BooleanField(label="展示聚合统计信息", default=True)
        show_dsl = serializers.BooleanField(label="展示DSL", default=False)
        record_history = serializers.BooleanField(label="是否保存收藏历史", default=False)

    def perform_request(self, validated_request_data):
        show_overview = validated_request_data.pop("show_overview")
        show_aggs = validated_request_data.pop("show_aggs")
        show_dsl = validated_request_data.pop("show_dsl")
        record_history = validated_request_data.pop("record_history")

        handler = ActionQueryHandler(**validated_request_data)

        with SearchHistory.record(
            SearchType.ACTION,
            validated_request_data,
            enabled=record_history and validated_request_data.get("query_string"),
        ):
            result = handler.search(show_overview=show_overview, show_aggs=show_aggs, show_dsl=show_dsl)

        return result


class SubActionDetailResource(ApiAuthResource):
    """
    查询子任务执行详情
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
        parent_action_id = serializers.CharField(label="父任务ID", required=True)

    def perform_request(self, validated_request_data):
        validated_request_data["page_size"] = 500
        handler = ActionQueryHandler(**validated_request_data)
        resp_data = {}
        if handler.raw_id is None and handler.search_parent_action_id is None:
            # 如果当前告警处理ID记录不存在并且没有主任务直接返回空
            return resp_data
        actions = handler.search()["actions"]
        sub_actions = []
        action_relation = {}
        for action in actions:
            if action["signal"] != ActionSignal.COLLECT or action["id"] == validated_request_data["parent_action_id"]:
                sub_actions.append(action)
                continue
            for action_id in action["outputs"].get("related_actions", []):
                notice_way, notice_receiver = self.get_action_notice_info(action)
                action_relation["{}_{}_{}".format(str(action_id), notice_way, notice_receiver)] = action

        for action in sub_actions:
            notice_way, notice_receiver = self.get_action_notice_info(action)
            if not (notice_way and notice_receiver):
                continue

            real_action = (
                action_relation.get("{}_{}_{}".format(str(str(action["raw_id"])), notice_way, notice_receiver))
                or action
            )
            action_status = real_action["status"]
            status_display = ACTION_DISPLAY_STATUS_DICT.get(action_status, "--")
            try:
                # 解析notice_way, 保持前端只有一个notice_way的呈现，比如蓝鲸信息流，统一显示为蓝鲸信息流
                notice_way_display, _ = notice_way.split("|")
            except ValueError:
                # 如果解析不出来，表示是内置的通知方式
                notice_way_display = notice_way
            notice_result = {
                notice_way_display: {
                    "status": action_status,
                    "action_id": action["id"],
                    "status_display": status_display,
                    "status_tips": real_action["status_tips"] or status_display,
                }
            }
            if notice_receiver in resp_data:
                resp_data[notice_receiver].update(notice_result)
                continue
            resp_data[notice_receiver] = notice_result
        return resp_data

    @staticmethod
    def get_action_notice_info(action):
        """
        获取通知方式和通知人员
        """
        notice_way = action["inputs"].get("notice_way")
        notice_receiver = action["inputs"].get("notice_receiver")
        notice_way = notice_way[0] if isinstance(notice_way, list) else notice_way
        notice_receiver = ",".join(notice_receiver) if isinstance(notice_receiver, list) else notice_receiver
        return notice_way, notice_receiver


class ExportActionResource(Resource):
    """
    导出处理记录数据
    """

    class RequestSerializer(ActionSearchSerializer):
        ordering = serializers.ListField(label="排序", child=serializers.CharField(), default=[])

    def perform_request(self, validated_request_data):
        handler = ActionQueryHandler(**validated_request_data)
        return resource.export_import.export_package(list_data=handler.export())


class AlertExtendFields(Resource):
    """
    获取告警列表所有的扩展字段
    """

    class RequestSerializer(serializers.Serializer):
        ids = serializers.ListField(label="告警ID", child=AlertIDField())

    def perform_request(self, validated_request_data):
        extend_info = resource.alert.alert_related_info(validated_request_data)
        event_count = resource.alert.alert_event_count(validated_request_data)

        result = defaultdict(lambda: {"extend_info": {}, "event_count": 0})

        for alert_id, item in extend_info.items():
            result[alert_id]["extend_info"] = item

        for alert_id, item in event_count.items():
            result[alert_id]["event_count"] = item

        return result


class ActionDetailResource(Resource):
    """
    根据ID获取处理记录详情
    """

    class RequestSerializer(serializers.Serializer):
        id = ActionIDField(required=True, label="处理记录ID")

    def perform_request(self, validated_request_data):
        action_id = validated_request_data["id"]
        action = ActionInstanceDocument.get(action_id)
        result = ActionQueryHandler.handle_hit_list([action])[0]
        return result


class ActionDateHistogramResource(Resource):
    """
    查询告警分布直方图
    """

    class RequestSerializer(ActionSearchSerializer):
        interval = serializers.CharField(label="聚合周期", default="auto")

    def perform_request(self, validated_request_data):
        interval = validated_request_data.pop("interval")
        handler = ActionQueryHandler(**validated_request_data)
        return handler.date_histogram(interval=interval)


class ListAlertLogResource(ApiAuthResource):
    """
    获取告警流水记录
    """

    class RequestSerializer(serializers.Serializer):
        id = AlertIDField(required=True, label="告警ID")
        offset = serializers.IntegerField(required=False, label="偏移")
        limit = serializers.IntegerField(default=10, label="获取的条数")
        operate = serializers.ListField(default=[], label="记录类型")

    def perform_request(self, validated_request_data):
        alert_id = validated_request_data["id"]
        operate_list = validated_request_data["operate"]
        offset = validated_request_data.get("offset")
        limit = validated_request_data["limit"]

        handler = AlertLogHandler(alert_id)
        result_data = handler.search(operate_list=operate_list, offset=offset, limit=limit)
        return result_data


class ValidateQueryString(Resource):
    """
    校验 query_string 是否合法
    """

    class RequestSerializer(serializers.Serializer):
        search_type = serializers.ChoiceField(label="检索类型", choices=SEARCH_TYPE_CHOICES, default=SearchType.ALERT)
        query_string = serializers.CharField(label="查询字符串", allow_blank=True)

    def perform_request(self, validated_request_data):
        if not validated_request_data["query_string"]:
            return ""
        transformer_cls = {
            SearchType.ALERT: AlertQueryHandler.query_transformer,
            SearchType.ACTION: ActionQueryHandler.query_transformer,
            SearchType.EVENT: EventQueryHandler.query_transformer,
        }
        search_type = validated_request_data["search_type"]
        return transformer_cls[search_type].transform_query_string(query_string=validated_request_data["query_string"])


class BaseTopNResource(Resource):
    """
    统计告警TOP N
    """

    handler_cls = None

    class RequestSerializer(serializers.Serializer):
        fields = serializers.ListField(label="查询字段列表", child=serializers.CharField(), default=[])
        size = serializers.IntegerField(label="获取的桶数量", default=10)

    def perform_request(self, validated_request_data):
        handler = self.handler_cls(**validated_request_data)
        return handler.top_n(fields=validated_request_data["fields"], size=validated_request_data["size"])


class AlertTopNResource(BaseTopNResource):
    handler_cls = AlertQueryHandler

    class RequestSerializer(AlertSearchSerializer, BaseTopNResource.RequestSerializer):
        pass


class ActionTopNResource(BaseTopNResource):
    handler_cls = ActionQueryHandler

    class RequestSerializer(ActionSearchSerializer, BaseTopNResource.RequestSerializer):
        pass


class EventTopNResource(BaseTopNResource, ApiAuthResource):
    handler_cls = EventQueryHandler

    class RequestSerializer(EventSearchSerializer, BaseTopNResource.RequestSerializer):
        pass

    def perform_request(self, validated_request_data):
        alert = AlertDocument.get(validated_request_data["alert_id"])

        handler = EventQueryHandler(
            dedupe_md5=alert.dedupe_md5,
            start_time=alert.begin_time,
            end_time=alert.latest_time or int(time.time()),
            **validated_request_data,
        )
        return handler.top_n(fields=validated_request_data["fields"], size=validated_request_data["size"])


class ListAlertTagsResource(Resource):
    """
    获取告警标签
    """

    class RequestSerializer(AlertSearchSerializer):
        pass

    def perform_request(self, validated_request_data):
        handler = AlertQueryHandler(**validated_request_data)
        return handler.list_tags()


class StrategySnapshotResource(Resource):
    """
    获取策略快照
    """

    class ConfigChangedStatus(object):
        """
        策略配置变更状态
        """

        UNCHANGED = "UNCHANGED"
        UPDATED = "UPDATED"
        DELETED = "DELETED"

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="事件ID")

    def perform_request(self, validated_request_data):
        alert_id = validated_request_data["id"]
        is_enabled = False
        alert = AlertDocument.get(alert_id)
        strategy_config = alert.strategy
        if not strategy_config:
            return None

        # 策略更新状态
        changed_status = self.ConfigChangedStatus.UNCHANGED
        current_strategy = None
        try:
            strategy = StrategyModel.objects.get(id=strategy_config["id"])
            is_enabled = strategy.is_enabled
            current_strategy = Strategy.from_models([strategy])[0]
        except StrategyModel.DoesNotExist:
            changed_status = self.ConfigChangedStatus.DELETED
        else:
            if int(strategy.update_time.timestamp()) != strategy_config["update_time"]:
                changed_status = self.ConfigChangedStatus.UPDATED

        if current_strategy and "intelligent_detect" in strategy_config["items"][0]["query_configs"][0]:
            # AIOPS算法在告警检测时会对query_config本身进行修改导致查询配置无法还原，此时直接使用最新的query_config
            strategy_config["items"][0]["query_configs"][0] = current_strategy.items[0].query_configs[0].to_dict()

        strategy_config.update(strategy_status=changed_status)
        strategy_config["create_time"] = utc2datetime(strategy_config["create_time"])
        strategy_config["update_time"] = utc2datetime(strategy_config["update_time"])
        strategy_config["is_enabled"] = is_enabled
        Strategy.fill_user_groups([strategy_config])
        return strategy_config


class SearchAlertByEventResource(Resource):
    """
    TODO: 搜索告警关联的事件数据
    """

    class RequestSerializer(serializers.Serializer):
        """
        请求参数
        """

        event_id = serializers.CharField(label="事件ID", required=True)

    def perform_request(self, validated_request_data):
        # 对应的事件ID
        event_id = validated_request_data.get("event_id")

        # 根据event_id获取对应的event
        event = EventDocument.get_by_event_id(event_id)

        # 根据event 的去重md5获取到对应的告警
        try:
            alert = AlertDocument.get_by_dedupe_md5(event.dedupe_md5, event.time)
        except AlertNotFoundError:
            return {}
        if alert.strategy_id is None:
            # 如果策略ID不存在，通过target， create_time, 告警名称事件查询
            # 告警ID不存在的，都是通过fta接入
            metric_id = ["bk_fta.event.{}".format(alert.alert_name), "bk_fta.alert.{}".format(alert.alert_name)]
            new_event = None
            try:
                new_event = EventDocument.get_by_metric_id_and_target(metric_id, event.target, event.time)
            except BaseException as error:  # NOCC:broad-except(设计如此:)
                logger.info("get event failed %s, alert(%s)", str(error), alert.id)
            if new_event:
                try:
                    alert = AlertDocument.get_by_dedupe_md5(new_event.dedupe_md5, new_event.time)
                except AlertNotFoundError:
                    logger.info("no handle alert for event(%s)" % event.event_id)

        all_actions = ActionInstanceDocument.mget_by_alert(alert_ids=[alert.id])

        # 根据告警ID获取对应的处理信息
        handle_actions = [
            {
                "status": action.status,
                "action_plugin_type": action.action_plugin_type,
            }
            for action in all_actions
            if action.action_plugin_type != ActionPluginType.NOTICE
        ]
        notice_display_mapping = {msg["type"]: msg["label"] for msg in api.cmsi.get_msg_type()}
        voice_target_string = notice_display_mapping.get(NoticeWay.VOICE)

        voice_notice_actions = [
            {"status": action.status, "failure_type": action.failure_type}
            for action in all_actions
            if action.operate_target_string == voice_target_string
            and action.action_plugin_type == ActionPluginType.NOTICE
        ]

        event_info = {
            "id": event.id,
            "event_id": event.event_id,
            "create_time": utc2localtime(event.create_time),
            "ip": event.ip,
            "bk_biz_id": event.bk_biz_id,
            "bk_cloud_id": event.bk_cloud_id,
            "target_type": event.target_type,
            "target": event.target,
        }

        is_builtin_assign = AlertAssignGroup.objects.filter(
            id=alert.assign_group.get("group_id"), is_builtin=True
        ).exists()
        result = {
            "id": alert.id,
            "create_time": utc2localtime(alert.create_time),
            "begin_time": utc2localtime(alert.begin_time),
            "end_time": utc2localtime(alert.end_time) if alert.end_time else None,
            "bk_biz_id": event.bk_biz_id,
            "strategy_id": alert.strategy_id,
            "level": alert.severity,
            "status": alert.status,
            "plugin_id": getattr(alert.event, "plugin_id", None),
            "is_builtin_assign": is_builtin_assign,
            "target_key": "{}|{}".format(event.target_type.lower(), event.target),
            "assignee": [assignee for assignee in alert.assignee],
            "event": event_info,
            "is_shielded": alert.is_shielded is True,
            "is_handled": alert.is_handled is True,
            "is_ack": alert.is_ack is True,
            "handle_actions": handle_actions,
            "voice_notice_actions": voice_notice_actions,
        }
        return result


class ListIndexByHost(Resource):
    class RequestSerializer(serializers.Serializer):
        ip = serializers.CharField(required=True, label="主机IP")
        bk_cloud_id = serializers.IntegerField(required=False, label="云区域ID", default=0, allow_null=True)
        bk_biz_id = serializers.IntegerField(required=True, help_text="业务ID")

    def perform_request(self, validated_request_data):
        params = {}
        params.update(validated_request_data)
        params["bk_host_innerip"] = params.pop("ip")
        try:
            result = api.log_search.list_collectors_by_host(params)
        except Exception:
            result = []
        return result


class FeedbackAlertResource(Resource):
    """
    告警反馈
    """

    class RequestSerializer(serializers.Serializer):
        alert_id = AlertIDField(required=True, label="告警ID")
        is_anomaly = serializers.BooleanField(label="是否为异常")
        description = serializers.CharField(label="反馈说明", allow_blank=True, default="")

    def feedback_to_bkdata(self, alert: AlertDocument, is_anomaly: bool, description: str):
        if not settings.IS_ACCESS_BK_DATA:
            # 没接入计算平台的，忽略
            return

        if not alert.strategy:
            # 没有策略的，忽略
            return

        query_config = None
        for item in alert.strategy["items"]:
            for qc in item["query_configs"]:
                if qc.get("intelligent_detect", {}).get("result_table_id"):
                    query_config = qc

        if not query_config:
            # 没有智能异常检测的，忽略
            return

        origin_data = alert.origin_alarm.get("data") if alert.origin_alarm else None
        if not origin_data:
            # 拿不到异常数据，忽略
            return

        dimensions = {
            key: value
            for key, value in origin_data["dimensions"].items()
            if key in query_config.get("agg_dimension", [])
        }

        feedback_data = {
            "dtEventTimeStamp": origin_data["time"] * 1000,
            "is_anomaly": origin_data["values"].get("is_anomaly"),
            "label": 1 if is_anomaly else 0,
            "label_description": description,
            "value": origin_data["value"],
            "extra_info": origin_data["values"].get("extra_info"),
        }

        feedback_data.update(dimensions)

        api.bkdata.sample_set_feedback(
            rt_id=query_config["intelligent_detect"]["result_table_id"],
            feedback_data=[feedback_data],
        )

    def perform_request(self, params):
        alert = AlertDocument.get(params["alert_id"])
        AlertFeedback.objects.create(
            alert_id=params["alert_id"],
            is_anomaly=params["is_anomaly"],
            description=params["description"],
        )

        self.feedback_to_bkdata(alert=alert, is_anomaly=params["is_anomaly"], description=params["description"])


class ListAlertFeedbackResource(ApiAuthResource):
    """
    获取告警反馈
    """

    class RequestSerializer(serializers.Serializer):
        alert_id = AlertIDField(required=True, label="告警ID")

    def perform_request(self, validated_request_data):
        feedback = AlertFeedback.objects.filter(alert_id=validated_request_data["alert_id"])
        return AlertFeedbackSerializer(feedback, many=True).data


class AIOpsBaseResource(Resource, metaclass=ABCMeta):
    """
    AIOps基础资源配置
    """

    AIOPS_FUNCTION_NOT_ACCESSED_CODE = 1513810

    CACHE_SCOPE = None

    class RequestSerializer(serializers.Serializer):
        alert_id = AlertIDField(required=True, label="告警ID")

    def get_cache_results(self, alert_id: str) -> Dict:
        """获取缓存的AIOps类数据的缓存.

        :param alert_id: 告警ID
        """
        cache_key = f"{alert_id}_{self.CACHE_SCOPE}_cache"
        return cache.get(cache_key)

    def set_cache_results(self, alert_id: str, cache_result: Dict, timeout: int = 86400) -> Dict:
        """把AIOps类数据缓存到cache中.

        :param alert_id: 告警ID
        """
        cache_key = f"{alert_id}_{self.CACHE_SCOPE}_cache"
        return cache.set(cache_key, cache_result, timeout=timeout)

    def cache_valid(self, alert: AlertDocument, cache_result: Dict) -> bool:
        """判断当前cache是否还在有效期内.

        :param alert: 告警详情
        :param cache_result: 缓存的内容
        """
        return True

    def perform_request(self, validated_request_data):
        alert = AlertDocument.get(validated_request_data["alert_id"])
        cache_result = self.get_cache_results(alert.id)

        if not cache_result or not self.cache_valid(alert, cache_result):
            request_result = self.fetch_aiops_result(alert)
            self.set_cache_results(alert.id, request_result)
            cache_result = request_result

        return cache_result

    def fetch_aiops_result(self, alert):
        """各种场景下获取AIOps算法结果.

        :param alert: 告警详情
        """
        pass


class DimensionDrillDownResource(AIOpsBaseResource):
    """
    维度下钻详情
    """

    CACHE_SCOPE = 'drill_down'

    def cache_valid(self, alert: AlertDocument, cache_result: Dict) -> bool:
        """判断当前cache是否还在有效期内.

        :param cache_result: 缓存的内容
        """
        return cache_result["alert_latest_time"] == alert.latest_time

    def fetch_aiops_result(self, alert):
        """获取维度下钻的详情.

        :param alert: 告警详情
        """
        graph_panel = AlertDetailResource.get_graph_panel(alert, use_raw_query_config=True)
        query_configs = copy.deepcopy(graph_panel["targets"][0]["data"]["query_configs"])

        # 获取当前告警的指标详情
        metric_info = parse_metric_id(alert.event["metric"][0])
        metric = MetricListCache.objects.filter(**metric_info).first()

        processing_id = settings.BK_DATA_DIMENSION_DRILL_PROCESSING_ID
        try:
            response = api.bkdata.api_serving_execute(
                processing_id=processing_id,
                data={
                    "inputs": [
                        {
                            "timestamp": alert.latest_time * 1000,
                        }
                    ]
                },
                config={"predict_args": self.generate_predict_args(alert, metric, query_configs)},
            )
            if not response["result"]:
                logger.exception(f"aiops api serving return error: ({processing_id}): {response['message']}")
                raise AIOpsResultError({"err": response['message']})

            if len(response["data"]["data"][0]["output"]) == 0:
                raise AIOpsResultError({"err": _("算法无输出")})
        except BKAPIError as e:
            logger.exception(f"failed to call aiops api serving({processing_id}): {e}")

            if e.data.get("code") == self.AIOPS_FUNCTION_NOT_ACCESSED_CODE:
                raise AIOpsFunctionAccessedError({"func": _("维度下钻")})
            else:
                raise AIOpsResultError({"err": str(e)})

        info, anomaly_dimensions, graph_dimensions = self.parse_serving_result(
            metric, response["data"]["data"][0]["output"][0]
        )
        graph_panels = self.generate_anomaly_graph_panels(alert, metric, graph_panel, graph_dimensions)

        return {
            "info": info,
            "anomaly_dimensions": anomaly_dimensions,
            "graph_panels": graph_panels,
            "alert_latest_time": alert.latest_time,
        }

    def generate_predict_args(self, alert: AlertDocument, metric: MetricListCache, query_configs: List[dict]) -> Dict:
        """基于告警信息构建维度下钻API Serving的预测参数.

        :param alert: 告警信息
        :parma metric: 告警指标详情
        :param query_configs: 告警指标默认查询参数
        """
        for query_config in query_configs:
            group_bys = []
            src_group_bys = query_config["group_by"]

            for dimension in metric.dimensions:
                # 如果某个维度在过滤条件里，则不对该维度进行下钻
                if dimension.get("is_dimension", True) and dimension["id"] not in chain(
                    src_group_bys, SPLIT_DIMENSIONS
                ):
                    group_bys.append(dimension["id"])

            query_config["group_by"] = group_bys

        return {
            "json_args": json.dumps(
                {
                    "expression": "a",
                    "query_configs": query_configs,
                    "target_time": alert.latest_time * 1000,
                    "bk_biz_id": alert.event["bk_biz_id"],
                    "alert_id": alert.id,
                }
            ),
        }

    def parse_serving_result(
        self, metric: MetricListCache, serving_output: Dict
    ) -> Tuple[Dict, List[Dict], List[Dict]]:
        """解析维度下钻算法的预测结果.

        :param metric: 告警指标详情
        :param serving_output: 预测输出
        """
        graph_dimensions = json.loads(serving_output["root_leaves"])

        root_dimensions = json.loads(serving_output["root_dims"])
        info = {
            "anomaly_dimension_count": len(root_dimensions),
            "anomaly_dimension_value_count": sum(map(lambda x: x["root_cnt"], root_dimensions)),
        }

        # 维度中文名映射
        dim_mappings = {item["id"]: item["name"] for item in metric.dimensions if item.get("is_dimension", True)}

        anomaly_dimensions = []
        for root_dimension in root_dimensions:
            sorted_dimension = sorted(root_dimension["dim_combine"])
            anomaly_dimensions.append(
                {
                    "anomaly_dimension": sorted_dimension,
                    "anomaly_dimension_alias": "|".join(map(lambda x: dim_mappings[x], sorted_dimension)),
                    "anomaly_dimension_class": "&".join(sorted_dimension),
                    "dimension_anomaly_value_count": root_dimension["root_cnt"],
                    "dimension_value_total_count": root_dimension["total_cnt"],
                    "dimension_value_percent": (
                        round(root_dimension["root_cnt"] * 100 / root_dimension["total_cnt"], 2)
                        if root_dimension["total_cnt"]
                        else 0
                    ),
                    "anomaly_score_top10": self.generate_anomaly_score_top10(root_dimension),
                    "anomaly_score_distribution": self.generate_anomaly_score_distribution(metric, root_dimension),
                    "dim_surprise": root_dimension["dim_surprise"],
                }
            )

        return info, anomaly_dimensions, graph_dimensions

    def generate_anomaly_graph_panels(
        self, alert: AlertDocument, metric: MetricListCache, graph_panel: Dict, graph_dimensions: List[Dict]
    ) -> List[Dict]:
        """生成异常分值较高的维度图表参数.

        :param alert: 告警信息
        :param metric: 指标详情，用来补充中文维度信息
        :param graph_panel: 原始告警图表参数
        :param graph_dimensions: 异常分值较高的维度组合
            [
                {
                    "root": {
                        "bk_target_ip": "127.0.0.1",
                    },
                    "surprise": 0.013142875563731185,
                    "score": 0.07142857142857142,
                    "dim_surprise": 15.814226534141184
                },
                {
                    "root": {
                        "bk_target_ip": "127.0.0.1",
                    },
                    "surprise": 0.0016981856483826371,
                    "score": 0.07142857142857142,
                    "dim_surprise": 15.814226534141184
                }
            ]
        :return: 以graph_panel作为模板，基于维度下钻结果构建的panels配置列表
        """
        graph_panels = []

        # 维度中文名映射
        dim_mappings = {item["id"]: item["name"] for item in metric.dimensions if item.get("is_dimension", True)}

        for dimension in graph_dimensions:
            base_graph_panel = copy.deepcopy(graph_panel)
            base_graph_panel["id"] = self.generate_id_by_dimension_dict(dimension["root"])
            base_graph_panel["type"] = "aiops-dimension-lint"
            base_graph_panel["subTitle"] = " "
            base_graph_panel["anomaly_score"] = round(float(dimension["score"]), 2)
            base_graph_panel["targets"][0]["api"] = "alert.alertGraphQuery"
            base_graph_panel["targets"][0]["alias"] = ""
            base_graph_panel["targets"][0]["data"]["id"] = alert.id
            base_graph_panel["targets"][0]["data"]["function"] = {}

            # 因为告警维度已经确认，所以这里查询需要清空原始维度聚合配置
            query_configs = base_graph_panel["targets"][0]["data"]["query_configs"]
            for query_config in query_configs:
                query_config["group_by"] = []
                query_config["functions"] = [{"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}]

            # 补充维度下钻的维度过滤条件
            dimension_keys = sorted(dimension["root"].keys())
            base_graph_panel["title"] = "_".join(
                map(lambda x: f"{dim_mappings.get(x, x)}: {dimension['root'][x]}", dimension_keys)
            )
            base_graph_panel["anomaly_dimension_class"] = "&".join(dimension_keys)
            for condition_key in dimension_keys:
                condition_value = dimension["root"][condition_key]
                condition = {"key": condition_key, "value": [condition_value], "method": "eq", "condition": "and"}
                for query_config in query_configs:
                    query_config["group_by"].append(condition_key)
                    query_config["where"].append(condition)

            graph_panels.append(base_graph_panel)

        return sorted(graph_panels, key=lambda x: -x["anomaly_score"])

    def generate_anomaly_score_top10(self, root_dimension: Dict) -> List[Dict]:
        """根据API Serving的异常维度信息构建异常分值Top10的维度组合列表.

        :param root_dimension: 异常维度信息
            {
                "dim_combine": ["bk_target_ip"],     # 异常维度列表
                "total_cnt": 2476,                   # 维度组合总数
                "root_cnt": 10,                      # 异常维度组合总数
                "dim_surprise": 15.814226534141184,  # JS散度
                "anomaly_data": [                    # 异常分值超过阈值的维度组合
                    [
                        ("127.0.0.1"),               # 跟dim_combine一一对应的维度值
                        "0.0",                       # 指标值
                        "0.07"                       # 异常分值
                    ]
                ],
                "normal_data": [                     # 异常分值不超过阈值的维度组合
                    [
                        ("127.0.0.2"),
                        "0.0",
                        "0.06"
                    ]
                ]
            }
        :return: 异常分值前10的维度组合列表，如果存在并列的异常分值且全取会超过10，则随机选择补充列表至10即可
            [
                {
                    "id": "bk_target_ip=127.0.0.1",
                    "dimension_value": "127.0.0.1",
                    "anomaly_score": 0.07,
                    "is_anomaly": true
                },
                {
                    "id": "bk_target_ip=127.0.0.2",
                    "dimension_value": "127.0.0.2",
                    "anomaly_score": 0.06,
                    "is_anomaly": false
                }
            ]
        """
        # 基于异常分值倒序排序
        anomaly_data = sorted(root_dimension["anomaly_data"], key=lambda x: -float(x[2]))
        top10_data = anomaly_data[:10]

        return [
            {
                **self.generate_anomaly_dimension_detail(root_dimension["dim_combine"], item),
                "is_anomaly": True,
            }
            for item in top10_data
        ]

    def generate_anomaly_score_distribution(self, metric: MetricListCache, root_dimension: Dict) -> Dict:
        """根据API Serving的异常维度信息构建异常维度分布.

        :param alert: 告警详情
        :param root_dimension: 异常维度信息
            {
                "dim_combine": ["bk_target_ip"],     # 异常维度列表
                "total_cnt": 2476,                   # 维度组合总数
                "root_cnt": 10,                      # 异常维度组合总数
                "dim_surprise": 15.814226534141184,  # JS散度
                "anomaly_data": [                    # 异常分值超过阈值的维度组合
                    [
                        ("127.0.0.1"),               # 跟dim_combine一一对应的维度值
                        "0.0",                       # 指标值
                        "0.07"                       # 异常分值
                    ]
                ],
                "normal_data": [                     # 异常分值不超过阈值的维度组合
                    [
                        ["127.0.0.2"],
                        "0.0",
                        "0.06"
                    ]
                ]
            }
        :return: 异常维度分布，异常分值按照四舍五入的方式放入以0.1为间隔的0-1的箱子中
            {
                "metric_alias": "CPU使用率",
                "unit": "%",
                "median": 0.5,
                "data": [
                    {
                        "anomaly_score": 1.0,
                        "dimension_details": [
                            {
                                "id": "bk_target_cluster=集群4",
                                "dimension_value": "集群4",
                                "metric_value": 80,
                                "anomaly_score": 1.0
                            }
                        ]
                    },
                    {
                        "anomaly_score": 0.9,
                        "dimension_details": [
                            {
                                "id": "bk_target_cluster=集群5",
                                "dimension_value": "集群5",
                                "metric_value": 80,
                                "anomaly_score": 0.88
                            },
                            {
                                "id": "bk_target_cluster=集群6",
                                "dimension_value": "集群6",
                                "metric_value": 80,
                                "anomaly_score": 0.91
                            }
                        ]
                    }
                ]
            }
        """

        distribution_data = defaultdict(lambda: {"is_anomaly": False, "details": []})
        score_data = []
        # 处理异常数据
        for item in root_dimension["anomaly_data"]:
            anomaly_score = round(float(item[2]), 1)
            score_data.append(float(item[2]))
            distribution_data[anomaly_score]["is_anomaly"] = True
            distribution_data[anomaly_score]["details"].append(
                {**self.generate_anomaly_dimension_detail(root_dimension["dim_combine"], item), "is_anomaly": True}
            )

        # 处理正常数据
        for item in root_dimension["normal_data"]:
            dimension_score = max(float(item[2]), 0)  # 如果异常分值小于0，说明维度是正常的，则取0来作展示
            anomaly_score = round(dimension_score, 1)
            score_data.append(dimension_score)
            distribution_data[anomaly_score]["details"].append(
                {**self.generate_anomaly_dimension_detail(root_dimension["dim_combine"], item), "is_anomaly": False}
            )

        for anomaly_data in distribution_data.values():
            anomaly_data["details"] = sorted(anomaly_data["details"], key=lambda x: -x["anomaly_score"])

        # 获取score_data的中位数
        if not score_data:
            score_data_median = 0
        elif len(score_data) % 2 == 0:
            score_data_median = (
                sorted(score_data)[len(score_data) // 2] + sorted(score_data)[len(score_data) // 2 - 1]
            ) / 2
        else:
            score_data_median = sorted(score_data)[len(score_data) // 2]

        return {
            "metric_alias": metric.metric_field_name,
            "unit": metric.unit,
            "median": round(score_data_median, 2),
            "data": sorted(
                [
                    {
                        "anomaly_score": round(anomaly_score, 2),
                        "is_anomaly": distribution_item["is_anomaly"],
                        "dimension_details": distribution_item["details"],
                    }
                    for anomaly_score, distribution_item in distribution_data.items()
                ],
                key=lambda item: -item["anomaly_score"],
            ),
        }

    def generate_id_by_dimension_dict(self, dimensions: Dict) -> str:
        """根据维度字典生成某个维度组合的唯一ID.

        :param dimensions: 维度字典
        :return: 类似querystring的结构, 如: dim_key1-dim_value1&dim_key2-dim_value2
        """
        keys = sorted(list(dimensions.keys()))
        return "&".join(f"{key}-{dimensions[key]}" for key in keys)

    def generate_anomaly_dimension_detail(self, dimension_keys: List, dimension_data: List) -> Dict:
        """根据异常维度数据生成维度详情.

        :param dimension_keys: 维度列表
        :param dimension_data: 异常维度数据
        """
        return {
            "id": self.generate_id_by_dimension_dict(dict(zip(dimension_keys, dimension_data[0]))),
            "dimension_value": "|".join(dimension_data[0]),
            "metric_value": float(dimension_data[1]) if not math.isnan(float(dimension_data[1])) else "NaN",
            "anomaly_score": max(round(float(dimension_data[2]), 2), 0),  # 如果异常分值小于0，说明维度是正常的，则取0来作展示
        }


class MetricRecommendationResource(AIOpsBaseResource):
    """
    指标推荐详情
    """

    CACHE_SCOPE = 'metric_recommend'

    def fetch_aiops_result(self, alert: AlertDocument) -> Dict:
        """获取指标推荐的详情.

        :param alert: 告警详情
        """
        graph_panel = AlertDetailResource.get_graph_panel(alert, use_raw_query_config=True)

        # 告警指标大于1、没有告警指标或为多指标异常检测时，则不进行推荐
        if len(alert.event["metric"]) != 1:
            return {}
        try:
            algoritm = alert.strategy["items"][0]["algorithms"][0]
            if algoritm["type"] == AlgorithmModel.AlgorithmChoices.MultivariateAnomalyDetection:
                return {}
        except (KeyError, IndexError):
            # 如果配置中没有找到算法类型，则跳过当前检测
            pass

        processing_id = f'{settings.BK_DATA_METRIC_RECOMMEND_PROCESSING_ID_PREFIX}'
        try:
            response = api.bkdata.api_serving_execute(
                processing_id=processing_id,
                data={
                    "inputs": [
                        {
                            "timestamp": alert.first_anomaly_time * 1000,
                        }
                    ]
                },
                config={
                    "predict_args": self.generate_predict_args(alert, copy.deepcopy(graph_panel['targets'][0]['data']))
                },
            )
            if not response["result"]:
                logger.exception(f"aiops api serving return error: ({processing_id}): {response['message']}")
                raise AIOpsResultError({"err": response['message']})

            if len(response["data"]["data"][0]["output"]) == 0:
                raise AIOpsResultError({"err": _("算法无输出")})
        except BKAPIError as e:
            logger.exception(f'failed to call aiops api serving({processing_id}): {e}')

            if e.data.get("code") == self.AIOPS_FUNCTION_NOT_ACCESSED_CODE:
                raise AIOpsFunctionAccessedError({"func": _("指标推荐")})
            else:
                raise AIOpsResultError({"err": str(e)})

        recommended_results = response["data"]["data"][0]["output"][0]
        recommended_metric_panels = self.generate_recommended_metric_panels(alert, graph_panel, recommended_results)
        recommended_metrics = self.classify_recommended_metrics(recommended_metric_panels)

        return {
            "info": {
                # 每个panel对应单推荐指标的某个单维度值，因此推荐指标维度数可基于panel来计算，其中主机类指标只有ip单维度。
                "recommended_metric_count": len(recommended_metric_panels),
            },
            "recommended_metrics": recommended_metrics,
        }

    def generate_predict_args(self, alert: AlertDocument, exp_config: Dict) -> Dict:
        """基于告警信息构建指标推荐PI Serving的预测参数.

        :param alert: 告警信息
        :param exp_config: 查询表达式配置
        """
        # 查询该业务是否配置有ai设置
        ai_setting = AiSetting(bk_biz_id=alert.event["bk_biz_id"])
        metric_recommend = ai_setting.metric_recommend

        return {
            "json_args": json.dumps(
                {
                    "expression": exp_config["expression"],
                    "query_configs": exp_config["query_configs"],
                    "start_time": alert.begin_time,
                    "end_time": alert.latest_time,
                    "bk_biz_id": alert.event["bk_biz_id"],
                    "alert_id": alert.id,
                }
            ),
            "reference_table": metric_recommend.result_table_id
            or (
                f"{settings.DEFAULT_BKDATA_BIZ_ID}_"
                f"{settings.BK_DATA_METRIC_RECOMMEND_PROCESSING_ID_PREFIX}_"
                f"{alert.event['bk_biz_id']}"
            ),
        }

    def generate_recommended_metric_panels(
        self, alert: AlertDocument, graph_panel: Dict, recommended_results: Dict
    ) -> List[Dict]:
        """生成推荐指标的图表配置.

        :param alert: 告警信息
        :param graph_panel: 原始告警图表参数
        :param recommended_results: 推荐结果
            {
                "timestamp": 1669003786760,
                "__index__": "",
                "__group_id__": "",
                "__id__": "",
                "target_metric": "bcs_eternal_metrics.mean_rate",
                "recommend_metrics": "[[\"bcs_eternal_metrics.count\", 0.342319397206, \"None\", [\"\\形\\状\\相\\似\"]]]",
                "metric_exist": 1,
                "extra_info":"{\"detail\": \"\\目\\标\\指\\标\\找\\到1\\相\\似\\指\\标\", \"reason\": [\"\\形\\状\\相\\似\"]}"
            }
        :return: 以graph_panel作为模板，基于指标推荐结果构建的panels配置列表
        """
        graph_panels = []

        recommend_metrics = json.loads(recommended_results["recommend_metrics"])

        for recommend_metric in recommend_metrics:
            base_graph_panel = copy.deepcopy(graph_panel)

            # 获取当前推荐指标的详情
            metric_name, dimensions = self.parse_recommend_metric(recommend_metric[0])
            metric_info = parse_metric_id(metric_name)
            if not metric_info:
                continue
            metric = MetricListCache.objects.filter(**metric_info).first()
            if not metric:
                continue

            recommend_info = {
                "reasons": recommend_metric[3],
                "class": recommend_metric[2],
                "src_metric_id": alert.event["metric"][0],
                "anomaly_points": recommend_metric[4] if isinstance(recommend_metric[4], list) else [],
            }

            # 维度中文名映射
            dim_mappings = {item["id"]: item["name"] for item in metric.dimensions if item.get("is_dimension", True)}
            dimension_keys = sorted(dimensions.keys())

            base_graph_panel["id"] = recommend_metric[0]
            base_graph_panel["type"] = "aiops-dimension-lint"
            base_graph_panel["enable_threshold"] = False
            base_graph_panel["title"] = "_".join(
                map(lambda x: f"{dim_mappings.get(x, x)}: {dimensions[x]}", dimension_keys)
            )
            base_graph_panel["subTitle"] = metric_name
            base_graph_panel["bk_biz_id"] = alert.event.bk_biz_id
            base_graph_panel["recommend_info"] = recommend_info
            base_graph_panel["result_table_label"] = metric.result_table_label
            base_graph_panel["result_table_label_name"] = metric.result_table_label_name
            base_graph_panel["metric_name_alias"] = metric.metric_field_name

            base_graph_panel["targets"][0]["data"]["function"] = {}
            base_graph_panel["targets"][0]["api"] = "alert.alertGraphQuery"
            base_graph_panel["targets"][0]["alias"] = ""
            base_graph_panel["targets"][0]["data"]["id"] = alert.id

            # 补充维度过滤条件
            where = []
            dimension_keys = sorted(dimensions.keys())
            for condition_key in dimension_keys:
                condition_value = dimensions[condition_key]
                condition = {
                    "key": condition_key,
                    "value": [condition_value] if not isinstance(condition_value, list) else condition_value,
                    "method": "eq",
                }
                if len(where) > 0:
                    condition["condition"] = "and"
                where.append(condition)

            # 因为推荐指标不一定具有告警相同的维度，因此这里不对维度进行任何聚合，只做指标的推荐
            query_configs = base_graph_panel["targets"][0]["data"]["query_configs"]
            for query_config in query_configs:
                query_config["group_by"] = []
                query_config["where"] = where
                query_config["data_source_label"] = metric.data_source_label
                query_config["data_type_label"] = metric.data_type_label
                query_config["table"] = metric.result_table_id
                query_config["functions"] = [{"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}]
                for query_metric in query_config["metrics"]:
                    query_metric["field"] = metric.metric_field

            graph_panels.append(base_graph_panel)

        return graph_panels

    def parse_recommend_metric(self, recommend_metric: str) -> Tuple[str, Dict]:
        """解析推荐的指标及其维度信息.

        :param recommend_metric: 推荐的指标
        """
        metric_tokens = recommend_metric.split('|')
        if len(metric_tokens) <= 1:
            return metric_tokens[0], {}

        dimensions = {key: value[0] for key, value in parse_qs(metric_tokens[1]).items()}

        return metric_tokens[0], dimensions

    def classify_recommended_metrics(self, recommended_metric_panels: List[Dict]) -> List[Dict]:
        """把推荐指标进行分类.

        :param recommended_metric_panels: 未分类的推荐指标列表，包含画图的panels信息
        """
        recommended_metrics = {}

        for metric_panel in recommended_metric_panels:
            if metric_panel["result_table_label"] not in recommended_metrics:
                recommended_metrics[metric_panel["result_table_label"]] = {
                    "result_table_label": metric_panel["result_table_label"],
                    "result_table_label_name": metric_panel["result_table_label_name"],
                    "metrics": {},
                }

            if metric_panel["subTitle"] not in recommended_metrics[metric_panel["result_table_label"]]["metrics"]:
                recommended_metrics[metric_panel["result_table_label"]]["metrics"][metric_panel["subTitle"]] = {
                    "metric_name": metric_panel["subTitle"],
                    "metric_name_alias": metric_panel["metric_name_alias"],
                    "panels": [],
                }

            recommended_metrics[metric_panel["result_table_label"]]["metrics"][metric_panel["subTitle"]][
                "panels"
            ].append(metric_panel)

        for label_metrics in recommended_metrics.values():
            label_metrics["metrics"] = list(label_metrics["metrics"].values())
        recommended_metrics = list(recommended_metrics.values())

        return recommended_metrics

    def perform_request(self, validated_request_data):
        result = super(MetricRecommendationResource, self).perform_request(validated_request_data)

        for label_info in result.get("recommended_metrics", []):
            for metric_info in label_info["metrics"]:
                for recommend_panel in metric_info["panels"]:
                    recommend_info = recommend_panel["recommend_info"]
                    alert_metric_id = recommend_info["src_metric_id"]
                    recommendation_metric = recommend_panel["id"]
                    bk_biz_id = recommend_panel["bk_biz_id"]

                    feedback = MetricRecommendationFeedbackResource.get_feedback(
                        alert_metric_id=alert_metric_id,
                        recommendation_metric=recommendation_metric,
                        bk_biz_id=bk_biz_id,
                        username=get_request_username(),
                    )

                    recommend_panel["feedback"] = feedback

        return result


class MetricRecommendationFeedbackResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        alert_metric_id = serializers.CharField(required=True, label="告警指标ID")
        recommendation_metric_id = serializers.CharField(required=True, label="推荐指标")
        recommendation_metric_class = serializers.CharField(required=True, label="指标分类标签")
        feedback = serializers.ChoiceField(required=True, label="指标推荐反馈", choices=["good", "bad"])

    @staticmethod
    def get_feedback_count(alert_metric_id, recommendation_metric, bk_biz_id):
        """获取业务下，告警指标,被推荐指标关系下的点赞和点踩数

        :param alert_metric_id: 告警指标名
        :param recommendation_metric: 被推荐指标
        :param bk_biz_id: 业务id
        :return: (点赞数,点踩数)
        """
        feedback_annotate = (
            MetricRecommendationFeedback.objects.filter(
                alert_metric_id=alert_metric_id,
                recommendation_metric_hash=MetricRecommendationFeedback.generate_recommendation_metric_hash(
                    recommendation_metric
                ),
                bk_biz_id=bk_biz_id,
            )
            .values("feedback")
            .annotate(Count("feedback"))
        )

        good_count = 0
        bad_count = 0
        for feedback_annotate_item in feedback_annotate:
            if feedback_annotate_item["feedback"] == MetricRecommendationFeedback.FeedBackChoices.GOOD:
                good_count = feedback_annotate_item["feedback__count"]
            elif feedback_annotate_item["feedback"] == MetricRecommendationFeedback.FeedBackChoices.BAD:
                bad_count = feedback_annotate_item["feedback__count"]
        return good_count, bad_count

    @classmethod
    def get_feedback(cls, alert_metric_id, recommendation_metric, bk_biz_id, username):
        """获取用户的反馈

        :param alert_metric_id: 告警指标名
        :param recommendation_metric: 被推荐指标
        :param bk_biz_id: 业务id
        :param username: 用户名
        :return: 业务下对应告警指标和被推荐指标的点赞数和点踩数，以及用户的反馈
        """
        good_count, bad_count = cls.get_feedback_count(alert_metric_id, recommendation_metric, bk_biz_id)

        username_feedback = MetricRecommendationFeedback.objects.filter(
            alert_metric_id=alert_metric_id,
            recommendation_metric_hash=MetricRecommendationFeedback.generate_recommendation_metric_hash(
                recommendation_metric
            ),
            bk_biz_id=bk_biz_id,
            create_user=username,
        ).first()

        return {
            "good": good_count,
            "bad": bad_count,
            "self": username_feedback.feedback if username_feedback else None,
        }

    @classmethod
    def get_recommend_metric_bkdata_rt_id(bk_biz_id):
        """获取被推荐指标的计算平台结果表id

        :param recommend_metric: 被推荐的指标(附带维度,并且使用|(竖线)分割)
        :return: 被推荐指标所在的计算平台结果表
        """
        # 从接入表中找到对应对象，使用统一的属性获取该结果表在计算平台的out_table_name
        return METRIC_RECOMMAND_SCENE_SERVICE_TEMPLATE(bk_biz_id=bk_biz_id)

    @classmethod
    def feedback_to_bkdata(cls, request_user, feedback_obj, good_count, bad_count, recommendation_metric_class):
        """反馈到计算平台

        :param request_user: 反馈用户
        :param feedback_obj: 反馈orm对象()
        :param good_count: 点赞数
        :param bad_count: 点踩数
        :param recommendation_metric_class: 被推荐指标标签
        """
        feedback_info = {
            "user": request_user,
            "good_num": good_count,
            "bad_num": bad_count,
            "class": recommendation_metric_class,
            "target_metric_name": feedback_obj.alert_metric_id,
            "target_series_json": [],
        }

        feedback_data = {
            "series_json": json.dumps([]),
            "metric_name": feedback_obj.recommendation_metric,
            "feedback_info": feedback_info,
        }

        try:
            rt_id = cls.get_recommend_metric_bkdata_rt_id(feedback_obj.bk_biz_id)

            api.bkdata.sample_set_feedback(
                rt_id=rt_id,
                feedback_data=[feedback_data],
            )
        except Exception as e:
            logger.exception(f"metric: [{feedback_obj.recommendation_metric}] feedback failed. exception: {e}")

    def perform_request(self, validated_request_data):
        alert_metric_id = validated_request_data["alert_metric_id"]
        recommendation_metric = validated_request_data["recommendation_metric_id"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        feedback = validated_request_data["feedback"]
        recommendation_metric_class = validated_request_data["recommendation_metric_class"]

        request_user = get_request_username()

        feedback_obj, _ = MetricRecommendationFeedback.objects.update_or_create(
            alert_metric_id=alert_metric_id,
            recommendation_metric_hash=MetricRecommendationFeedback.generate_recommendation_metric_hash(
                recommendation_metric
            ),
            bk_biz_id=bk_biz_id,
            create_user=request_user,
            defaults={"feedback": feedback, "recommendation_metric": recommendation_metric},
        )

        good_count, bad_count = self.get_feedback_count(alert_metric_id, recommendation_metric, bk_biz_id)

        self.feedback_to_bkdata(
            request_user=request_user,
            feedback_obj=feedback_obj,
            good_count=good_count,
            bad_count=bad_count,
            recommendation_metric_class=recommendation_metric_class,
        )

        result = {"feedback": {"good": good_count, "bad": bad_count, "self": feedback}}

        return result


class MultiAnomalyDetectGraphResource(AIOpsBaseResource):
    """提供主机智能异常检测告警详情的图表配置."""

    def perform_request(self, validated_request_data):
        alert = AlertDocument.get(validated_request_data["alert_id"])

        graph_panels = []
        try:
            strategy_algorithm = alert.strategy["items"][0]["algorithms"][0]
            if strategy_algorithm["type"] == AlgorithmModel.AlgorithmChoices.MultivariateAnomalyDetection:
                anomaly_sort = alert.event.extra_info["origin_alarm"]["data"]["values"]["anomaly_sort"]
                anomaly_metrics = parse_anomaly(anomaly_sort, strategy_algorithm["config"])

                base_graph_panel = AlertDetailResource.get_graph_panel(alert, use_raw_query_config=True)
                for anomaly_metric in anomaly_metrics:
                    graph_panel = self.generate_metric_graph_panel(
                        copy.deepcopy(base_graph_panel),
                        anomaly_metric,
                    )
                    if graph_panel:
                        graph_panels.append(graph_panel)
        except (KeyError, IndexError):
            raise AIOpsMultiAnomlayDetectError()

        return graph_panels

    def generate_metric_graph_panel(self, base_graph_panel: Dict, anomaly_metric: List) -> Dict:
        """根据图表基础配置和指标ID生成指标图表配置

        :param base_graph_panel: 基础图表配置
        :param anomaly_metric: 异常指标
            格式: [指标名, 数值, 异常得分, 带单位的数值, 指标中文名]
            参考: ["bk_monitor.system.net.speed_recv", 2812154.0, 0.9799, "2812154.0Kbs", "网卡入流量"]
        :return: 指标图表配置
        """
        graph_panel = copy.deepcopy(base_graph_panel)

        # 获取当前异常指标的详情
        metric_info = parse_metric_id(anomaly_metric[0])
        if not metric_info:
            return {}

        metric = MetricListCache.objects.filter(**metric_info).first()
        if not metric:
            return {}

        anomaly_info = {
            "metric_id": anomaly_metric[0],
            "anomaly_point": anomaly_metric[1],
            "anomaly_score": anomaly_metric[2],
            "anomaly_point_with_unit": anomaly_metric[3],
            "metric_name": anomaly_metric[4],
        }

        graph_panel["id"] = anomaly_metric[0]
        graph_panel["title"] = anomaly_metric[4]
        graph_panel["subTitle"] = anomaly_metric[0]
        graph_panel["anomaly_info"] = anomaly_info
        graph_panel["result_table_label"] = metric.result_table_label
        graph_panel["result_table_label_name"] = metric.result_table_label_name
        graph_panel["metric_name_alias"] = metric.metric_field_name
        graph_panel["targets"][0]["api"] = "alert.alertGraphQuery"
        graph_panel["targets"][0]["alias"] = ""

        # 因为推荐指标不一定具有告警相同的维度，因此这里不对维度进行任何聚合，只做指标的推荐
        query_configs = graph_panel["targets"][0]["data"]["query_configs"]
        for query_config in query_configs:
            query_config["where"] = [item for item in query_config["where"] if item["key"] != "is_anomaly"]
            query_config["data_source_label"] = metric.data_source_label
            query_config["data_type_label"] = metric.data_type_label
            query_config["table"] = metric.result_table_id
            query_config["metrics"] = [{"field": metric.metric_field, "method": "AVG", "alias": "a"}]

        return graph_panel


class QuickAlertShield(QuickActionTokenResource):
    class RequestSerializer(serializers.Serializer):
        action_id = serializers.IntegerField(label="告警ID")
        token = serializers.CharField(label="通知token")
        bk_biz_id = serializers.IntegerField(label="业务ID")
        shield_hours = serializers.IntegerField(label="屏蔽时间", default=3)

    def handle(self, params, alert_id):
        shield_params = {
            "end_time": params["end_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "begin_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "description": params["description"],
            "bk_biz_id": params["bk_biz_id"],
            "shield_notice": False,
            "cycle_config": {"begin_time": "", "type": 1, "end_time": ""},
            "is_quick": True,
        }

        shield_params.update({"category": "event", "dimension_config": {"id": alert_id}})
        return shield_params

    def perform_request(self, validated_data):
        alert_ids = validated_data.pop("alert_ids", [])
        bk_biz_id = validated_data["bk_biz_id"]
        shield_hours = validated_data.get("shield_hours", 3)
        shield_end_time = datetime.now() + timedelta(hours=shield_hours)
        success_alerts = []
        failed_alerts = []
        for alert_id in alert_ids:
            params = {
                "type": "event",
                "event_id": alert_id,
                "end_time": shield_end_time,
                "bk_biz_id": bk_biz_id,
                "description": _("快捷屏蔽3小时"),
            }
            try:
                resource.shield.add_shield(self.handle(params, alert_id))
                success_alerts.append(alert_id)
            except BaseException:
                failed_alerts.append(alert_id)
                logger.exception("quick shield alert(%s) error %s", alert_id)
        if not failed_alerts:
            return self.redirect(bk_biz_id, validated_data["action_id"])

        return _("完成快捷屏蔽{shield_hours}小时, 成功({success_alerts})， 失败({failed_alerts})").format(
            shield_hours=shield_hours, success_alerts=len(success_alerts), failed_alerts=len(failed_alerts)
        )


class QuickAlertAck(QuickActionTokenResource):
    """
    基于告警汇总对事件进行批量确认
    """

    class RequestSerializer(serializers.Serializer):
        action_id = serializers.IntegerField(label="处理记录ID")
        token = serializers.CharField(label="通知token")
        bk_biz_id = serializers.IntegerField(label="业务ID")

    def perform_request(self, validated_data):
        result = resource.alert.ack_alert(ids=validated_data["alert_ids"], message=_("移动端通知快捷确认"))

        if not (result["alerts_not_exist"]):
            return self.redirect(validated_data["bk_biz_id"], validated_data["action_id"])

        return _(
            "完成快捷确认, 成功({success_alerts})，失败({failed_alerts})，" "已确认({alerts_already_ack})，已结束({alerts_not_abnormal})"
        ).format(
            success_alerts=len(result["alerts_ack_success"]),
            failed_alerts=len(result["alerts_not_exist"]),
            alerts_already_ack=len(result["alerts_already_ack"]),
            alerts_not_abnormal=len(result["alerts_not_abnormal"]),
        )
