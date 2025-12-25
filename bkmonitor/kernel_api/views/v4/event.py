"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db.models import Q
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.documents import AlertDocument
from bkmonitor.models import QueryConfigModel
from bkmonitor.strategy.new_strategy import Strategy
from bkmonitor.utils.event_related_info import get_alert_relation_info
from bkmonitor.utils.time_tools import (
    get_datetime_range,
    parse_time_range,
    utc2localtime,
)
from kernel_api.resource.event import ListEventsResource, GetEventViewConfigResource, SearchEventLogResource
from core.drf_resource import Resource, resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class SearchEvent(Resource):
    """
    查询事件
    """

    def get_strategies_by_data_source(self, data_source):
        """
        通过datasource获取对应的策略ID
        """

        if not isinstance(data_source, list):
            return []
        data_source_where = None
        for data in data_source:
            data_split_list = data.split("|")
            if len(data_split_list) == 2:
                data_source_label, data_type_label = data_split_list
            else:
                data_source_label, data_type_label = None, None
            if data_source_where is None:
                data_source_where = Q(data_type_label=data_type_label, data_source_label=data_source_label)
            else:
                data_source_where = data_source_where | Q(
                    data_type_label=data_type_label, data_source_label=data_source_label
                )

        return QueryConfigModel.objects.filter(data_source_where).values_list("strategy_id", flat=True).distinct()

    def perform_request(self, params):
        params["ordering"] = ["-status", "-end_time", "-id"]

        # 搜索事件范围转换
        time_range = params.pop("time_range", "")
        days = params.pop("days", 0)
        if params.get("page") is None:
            # 不带page参数
            params["page"] = 1
            params["page_size"] = 5000
        if time_range:
            start_time, end_time = parse_time_range(time_range)
        elif days:
            begin_time, end_time = get_datetime_range("day", days, rounding=False)
            start_time = int(begin_time.timestamp())
            end_time = int(end_time.timestamp())
        else:
            begin_time, end_time = get_datetime_range("day", 1, rounding=False)
            start_time = int(begin_time.timestamp())
            end_time = int(end_time.timestamp())
        if start_time and end_time:
            params["start_time"] = start_time
            params["end_time"] = end_time

        params["conditions"] = params.get("conditions", [])
        for condition in params["conditions"]:
            condition_mapping = {
                "event_status": "status",
                "level": "severity",
            }
            condition["key"] = condition_mapping.get(condition["key"], condition["key"])
            if condition["key"] == "data_source":
                strategies = self.get_strategies_by_data_source(condition["value"])
                condition["key"] = "strategy_id"
                condition["value"] = strategies
                continue

        params["conditions"].append({"key": "strategy_id", "value": [0, ""], "method": "neq"})
        params["must_exists_fields"] = ["strategy_id"]
        alerts = resource.alert.search_alert(**params)["alerts"]

        fields = params.get("fields")
        if not isinstance(fields, list):
            fields = []

        result = [
            {
                "id": alert["id"],
                "create_time": utc2localtime(alert["create_time"]),
                "begin_time": utc2localtime(alert["begin_time"]),
                "end_time": utc2localtime(alert["end_time"]) if alert.get("end_time") else None,
                "event_id": alert["id"],
                "bk_biz_id": alert["bk_biz_id"],
                "strategy_id": alert["strategy_id"],
                "level": alert["severity"],
                "status": alert["status"],
                "is_ack": alert["is_ack"],
                "p_event_id": alert.get("p_event_id", ""),
                "is_shielded": alert["is_shielded"],
                "target_key": "{}|{}".format(alert["target_type"].lower(), alert["target"]),
            }
            for alert in alerts
        ]

        alert_docs = {doc.id: doc for doc in AlertDocument.mget(ids=[alert["id"] for alert in alerts])}
        for record in result:
            alert_doc = alert_docs.get(record["id"])
            if not alert_doc:
                continue
            try:
                record["origin_alarm"] = alert_doc.origin_alarm
            except Exception:
                record["origin_alarm"] = {}
            try:
                record["origin_config"] = Strategy.convert_v2_to_v1(alert_doc.strategy)
                if fields and "related_info" in fields:
                    record["related_info"] = get_alert_relation_info(alert_doc)
            except Exception:
                continue

        # 字段过滤
        if fields:
            for index, alert in enumerate(result):
                result[index] = {key: value for key, value in list(alert.items()) if key in fields}

        return result


class SearchEventLog(Resource):
    """
    查询事件流水
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField()

    def perform_request(self, params):
        event_log_list = resource.alert.list_alert_log({"id": params["id"], "limit": 0})

        return [
            {
                "operate": event_action["operate"],
                "message": ",".join(event_action["contents"]),
                "extend_info": {},
                "status": "SUCCESS",
                "event_id": params["id"],
                "create_time": event_action["time"],
            }
            for event_action in event_log_list
        ]


class AckEvent(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=False, label="事件ID")
        message = serializers.CharField(required=True, allow_blank=True, label="确认信息")
        ids = serializers.ListField(child=serializers.IntegerField(), required=False)

    def perform_request(self, validated_request_data):
        if "ids" in validated_request_data:
            event_ids = validated_request_data["ids"]
        elif "id" in validated_request_data:
            event_ids = [validated_request_data["id"]]
        else:
            raise ValidationError(_("id不能为空"))

        resource.alert.ack_alert({"ids": event_ids, "message": validated_request_data["message"]})


class EventViewSet(ResourceViewSet):
    """
    告警事件API
    """

    resource_routes = [
        ResourceRoute("POST", SearchEvent, endpoint="search"),
        ResourceRoute("GET", SearchEventLog, endpoint="event_log"),
        # 告警确认
        ResourceRoute("POST", AckEvent, endpoint="ack_event"),
        # 事件列表
        ResourceRoute("POST", ListEventsResource, endpoint="list_events"),
        # 事件视图配置
        ResourceRoute("POST", GetEventViewConfigResource, endpoint="get_event_view_config"),
        # 事件日志
        ResourceRoute("POST", SearchEventLogResource, endpoint="search_event_log"),
    ]
