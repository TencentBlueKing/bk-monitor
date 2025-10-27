"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import bisect
import datetime
import time
from collections import defaultdict

import pytz
from django.conf import settings
from django.core.exceptions import EmptyResultSet
from django.core.paginator import Paginator
from django.db.models import Max, Q, Sum
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from pytz import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.cmdb.define import Host, ServiceInstance
from bkmonitor.documents import AlertDocument
from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.models import (
    Alert,
    AlgorithmModel,
    AnomalyRecord,
    Event,
    EventAction,
    MetricListCache,
    Shield,
    StrategyModel,
)
from bkmonitor.utils import extended_json
from bkmonitor.utils.common_utils import logger
from bkmonitor.utils.event_related_info import get_event_relation_info
from bkmonitor.utils.request import get_request
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from bkmonitor.utils.thread_backend import InheritParentThread
from bkmonitor.utils.time_tools import (
    datetime2timestamp,
    gen_default_time_range,
    get_datetime_range,
    hms_string,
    now,
    parse_time_range,
    strftime_local,
    utc2biz_str,
    utc2datetime,
)
from bkmonitor.utils.user import get_backend_username, set_local_username
from constants.data_source import DataSourceLabel, DataTypeLabel, LabelType
from constants.shield import ShieldType
from constants.strategy import (
    AGG_METHOD_REAL_TIME,
    AdvanceConditionMethod,
    DataTarget,
    SourceType,
)
from core.drf_resource import Resource, api, resource
from core.errors.event import (
    AggmethodIsRealtimeError,
    EventNotExist,
    NotTimeSeriesError,
)
from core.errors.strategy import StrategyNotExist
from core.unit import load_unit
from monitor_web.alert_events.constant import (
    AlertStatus,
    ConfigChangedStatus,
    EventActionStatus,
    EventOperate,
    EventStatus,
)
from monitor_web.alert_events.event_filters import EventFilterManager
from monitor_web.constants import EVENT_FIELD_CHINESE, AlgorithmType, EventLevel
from monitor_web.data_explorer.resources import GetGraphQueryConfig
from monitor_web.models import CustomEventGroup
from monitor_web.models.alert_events import AlertSolution
from monitor_web.scene_view.resources import HostIndexQueryMixin


class EventDimensionMixin:
    @staticmethod
    def get_dimension_display_value(value):
        if isinstance(value, list):
            display_value = ",".join(value)
        else:
            display_value = value

        return display_value

    @classmethod
    def get_dimensions_str(cls, event, related=True):
        dimension_list = cls.get_dimensions(event, related)

        dimension_str_list = []
        for dimension in dimension_list:
            if dimension["name"] in ["bk_target_cloud_id", "bk_cloud_id"] and dimension["value"] == "0":
                continue
            dimension_str_list.append("{display_name}({display_value})".format(**dimension))

        # 隐藏默认云区域
        return " - ".join(dimension_str_list)

    @classmethod
    def get_dimensions(cls, event, related=True):
        """
        获取维度展示字段
        :param event: 事件
        :param related:
        :rtype: list(dict)
        """
        dimensions = event.origin_alarm.get("dimension_translation", None)
        if not dimensions:
            return []

        dimension_list = []
        # 拓扑维度特殊处理
        ignore_topo_dimension = False
        if "bk_obj_id" in dimensions and "bk_inst_id" in dimensions:
            ignore_topo_dimension = True
            dimension_list.append(
                {
                    "name": dimensions["bk_obj_id"]["display_value"],
                    "value": dimensions["bk_inst_id"]["display_value"],
                    "display_name": cls.get_dimension_display_value(dimensions["bk_obj_id"]["display_value"]),
                    "display_value": cls.get_dimension_display_value(dimensions["bk_inst_id"]["display_value"]),
                }
            )

        for key, value in list(dimensions.items()):
            if key in ["bk_obj_id", "bk_inst_id"] and ignore_topo_dimension:
                continue

            if key == "bk_topo_node":
                if not related:
                    continue

                node_dict = {}
                for node, display_node in zip(value["value"], value["display_value"]):
                    node_name, node_value = node.split("|")

                    # 兼容节点维度翻译失败的情况
                    if isinstance(display_node, dict) and "bk_obj_name" in display_node:
                        display_name = display_node["bk_obj_name"]
                        display_value = display_node["bk_inst_name"]
                    else:
                        display_name = node_name
                        display_value = node_value

                    node_dict.setdefault(
                        node_name,
                        {
                            "name": node_name,
                            "display_name": display_name,
                            "value": [],
                            "display_value": [],
                        },
                    )

                    node_dict[node_name]["value"].append(node_value)
                    node_dict[node_name]["display_value"].append(display_value)

                for node in node_dict.values():
                    dimension_list.append(
                        {
                            "name": node["name"],
                            "display_name": node["display_name"],
                            "value": cls.get_dimension_display_value(node["value"]),
                            "display_value": cls.get_dimension_display_value(node["display_value"]),
                        }
                    )
            else:
                dimension_list.append(
                    {
                        "name": key,
                        "value": value["value"],
                        "display_name": value["display_name"],
                        "display_value": cls.get_dimension_display_value(value["display_value"]),
                    }
                )

        return dimension_list


class EventPermissionResource(Resource):
    """
    事件接口权限校验处理
    """

    iam_actions = [ActionEnum.VIEW_EVENT]

    @classmethod
    def has_biz_permission(cls):
        """
        业务鉴权
        """
        client = Permission()
        for action_id in cls.iam_actions:
            is_allowed = client.is_allowed_by_biz(get_request().biz_id, action_id, raise_exception=False)
            if is_allowed:
                return True
        return False

    @classmethod
    def has_event_permission(cls, event_id: int):
        """
        事件鉴权
        """
        try:
            event = Event.objects.only("event_id").get(id=event_id, bk_biz_id=get_request().biz_id)
        except Event.DoesNotExist:
            return False

        return Alert.objects.filter(event_id=event.event_id, username=get_request().user.username).exists()

    @classmethod
    def filter_event_ids(cls, event_ids: list[int]):
        """
        过滤出有权限的事件ID
        """
        events = Event.objects.filter(id__in=event_ids, bk_biz_id=get_request().biz_id).values("event_id", "id")
        event_id_mapping = {event["event_id"]: event["id"] for event in events}

        allow_event_ids = (
            Alert.objects.filter(event_id__in=list(event_id_mapping.keys()), username=get_request().user.username)
            .values_list("event_id", flat=True)
            .distinct()
        )

        return [event_id_mapping[event_id] for event_id in allow_event_ids]

    def request(self, request_data=None, **kwargs):
        """
        执行请求，并对请求数据和返回数据进行数据校验
        """
        request_data = request_data or kwargs
        validated_request_data = self.validate_request_data(request_data)

        if not self.has_biz_permission():
            if "id" in validated_request_data and not self.has_event_permission(validated_request_data["id"]):
                raise ValidationError(_("无该事件权限"))
            elif "ids" in validated_request_data:
                validated_request_data["ids"] = self.filter_event_ids(validated_request_data["ids"])
            else:
                validated_request_data["receiver"] = get_request().user.username

        response_data = self.perform_request(validated_request_data)
        validated_response_data = self.validate_response_data(response_data)
        return validated_response_data


class QueryEventsResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_ids = serializers.ListField(required=True, label="业务id列表")
        time_range = serializers.CharField(required=False, allow_blank=True, label="时间范围")
        receiver = serializers.CharField(required=False, allow_blank=True, label="通知接受人")
        conditions = serializers.ListField(default=[], label="搜索条件")
        days = serializers.IntegerField(required=False, label="天数时间范围")

    def perform_request(self, validated_request_data):
        bk_biz_ids = validated_request_data["bk_biz_ids"]
        receiver = validated_request_data.get("receiver")
        time_range = validated_request_data.get("time_range")
        conditions = validated_request_data["conditions"]
        days = validated_request_data.get("days")

        if time_range:
            start, end = parse_time_range(time_range)
            begin_time = datetime.datetime.fromtimestamp(start)
            end_time = datetime.datetime.fromtimestamp(end)
        elif days:
            begin_time, end_time = get_datetime_range("day", days, rounding=False)
        else:
            begin_time, end_time = gen_default_time_range()

        # 过滤业务id和事件范围
        event_queryset = Event.objects.filter(
            Q(bk_biz_id__in=bk_biz_ids)
            & (
                Q(end_time__range=(begin_time, end_time))
                | Q(end_time=datetime.datetime(1980, 1, 1, 8, tzinfo=pytz.UTC))
            )
        )

        if receiver:
            conditions.append({"key": "receiver", "value": receiver})

        for condition in conditions:
            condition.update(bk_biz_ids=bk_biz_ids)

        # 过滤搜索条件
        event_filter = EventFilterManager((begin_time, end_time), event_queryset)
        event_filter.filter(conditions)

        return event_filter.queryset


class ListEventResource(EventPermissionResource, EventDimensionMixin):
    """
    事件列表
    """

    iam_actions = [ActionEnum.VIEW_EVENT, ActionEnum.VIEW_EVENT]

    class RequestSerializer(serializers.Serializer):
        bk_biz_ids = serializers.ListField(required=True, label="业务id列表")
        time_range = serializers.CharField(required=False, allow_blank=True, label="时间范围")
        receiver = serializers.CharField(required=False, allow_blank=True, label="通知接受人")
        status = serializers.ChoiceField(
            required=False, allow_blank=True, choices=["ABNORMAL", "SHIELD_ABNORMAL"], label="事件状态"
        )
        conditions = serializers.ListField(default=[], label="搜索条件")
        page_size = serializers.IntegerField(default=10, label="获取的条数")
        page = serializers.IntegerField(default=1, label="页数")
        order = serializers.CharField(required=False, label="排序", default=None)
        export = serializers.BooleanField(required=False, label="导出事件", default=None)

    def __init__(self):
        super().__init__()
        self.event_queryset = Event.objects.filter()
        self.event_paginator = None
        self.related_data = {}
        self.event_page = []

    def unshielded_abnormal_count(self, count):
        """未屏蔽的异常事件数量"""
        count.append(self.event_queryset.filter(status=EventStatus.ABNORMAL, is_shielded=False).count())

    def shielded_abnormal_count(self, count):
        """已屏蔽的异常事件数量"""
        count.append(
            self.event_queryset.filter(
                status=EventStatus.ABNORMAL, is_shielded=True, shield_type=ShieldType.SAAS_CONFIG
            ).count()
        )

    def all_event_count(self, count):
        """当前查询所有状态事件数量"""
        count.append(self.event_queryset.count())

    def get_related_data(self, page_data):
        events = {event.event_id: event for event in page_data}
        event_ids = events.keys()
        # 获取事件关联的异常点数量
        count_list = (
            AnomalyRecord.objects.filter(event_id__in=event_ids)
            .values("event_id")
            .annotate(total=Sum("count"))
            .order_by()
        )
        for data in count_list:
            event_related_data = self.related_data.setdefault(data["event_id"], {})
            event_related_data["anomaly_count"] = data["total"]

        # 最近一次次通知状态
        action_id_list = tuple(
            EventAction.objects.filter(event_id__in=event_ids, operate=EventOperate.ANOMALY_NOTICE)
            .values("event_id")
            .annotate(Max("id"))
            .values_list("id__max", flat=True)
        )
        last_notice_list = EventAction.objects.filter(id__in=action_id_list)
        for notice in last_notice_list:
            event_related_data = self.related_data.setdefault(notice.event_id, {})
            if notice.status == EventActionStatus.FAILED and notice.extend_info.get("empty_receiver", False):
                event_related_data["last_notice_status"] = "EMPTY_RECEIVER"
            else:
                event_related_data["last_notice_status"] = notice.status

        # 事件确认信息
        ack_action_list = EventAction.objects.filter(event_id__in=event_ids, operate=EventOperate.ACK)
        for ack_action in ack_action_list:
            event_related_data = self.related_data.setdefault(ack_action.event_id, {})
            event_related_data.update(
                ack_user=ack_action.username, ack_message=ack_action.extend_info.get("message", "")
            )

        # 获取最新的异常描述
        last_anomaly_ids = tuple(
            AnomalyRecord.objects.filter(event_id__in=event_ids)
            .values("event_id")
            .annotate(Max("id"))
            .values_list("id__max", flat=True)
        )
        last_anomaly_list = AnomalyRecord.objects.filter(id__in=last_anomaly_ids)
        for anomaly in last_anomaly_list:
            event_related_data = self.related_data.setdefault(anomaly.event_id, {})
            anomaly_event = events[anomaly.event_id]
            anomaly_info = anomaly.origin_alarm.get("anomaly", {})
            if str(anomaly_event.level) not in anomaly_info:
                anomaly_message = anomaly_event.anomaly_message
            else:
                anomaly_message = anomaly_info[(str(anomaly_event.level))]["anomaly_message"]
            event_related_data["latest_anomaly"] = anomaly_message

    def get_page(self, page, page_size, status=None, order=None, export=False):
        # 按事件状态和事件开始时间进行排序
        if not order:
            event_queryset = self.event_queryset.extra(order_by=["-status", "-end_time", "-id"])
        else:
            event_queryset = self.event_queryset.order_by(order)
        if status == "SHIELD_ABNORMAL":
            event_queryset = event_queryset.filter(
                status=EventStatus.ABNORMAL, is_shielded=True, shield_type=ShieldType.SAAS_CONFIG
            )
        elif status == "ABNORMAL":
            event_queryset = event_queryset.filter(status=EventStatus.ABNORMAL, is_shielded=False)

        if export:
            # 如果是导出事件，则不需要分页
            self.get_related_data(event_queryset)
            return event_queryset

        # 分页(展示数据)
        self.event_paginator = Paginator(event_queryset, page_size)
        event_page = self.event_paginator.page(number=page)
        # 获取关联数据
        self.get_related_data(event_page)

        return event_page

    def get_event_message(self, event, event_related_data):
        # 如果维度解析失败直接原样输出dimension_translation
        try:
            dimensions_str = self.get_dimensions_str(event, False)
        except Exception as e:
            logger.error(str(e))
            dimensions_str = str(event.origin_alarm.get("dimension_translation", ""))

        anomaly_message = event_related_data.get("latest_anomaly", {})
        return [_("维度信息：{}").format(dimensions_str), _("告警内容：{}").format(anomaly_message)]

    def perform_request(self, validated_request_data):
        """
        :param validated_request_data:
        :return:
        """
        status = validated_request_data.pop("status", None)
        page = validated_request_data.pop("page")
        page_size = validated_request_data.pop("page_size")
        order = validated_request_data.pop("order")
        # 根据各种条件进行事件列表查询
        self.event_queryset = resource.alert_events.query_events(validated_request_data)

        try:
            logger.info(f"event query: {self.event_queryset.query}")
        except EmptyResultSet:
            logger.info("EmptyResultSet: query won’t return any results")

        # 分页
        event_page = self.get_page(page, page_size, status, order, validated_request_data["export"])

        unshielded_abnormal_count = []
        shielded_abnormal_count = []
        all_event_count = []

        th_list = [
            InheritParentThread(target=self.unshielded_abnormal_count, args=(unshielded_abnormal_count,)),
            InheritParentThread(target=self.shielded_abnormal_count, args=(shielded_abnormal_count,)),
            InheritParentThread(target=self.all_event_count, args=(all_event_count,)),
        ]
        list([t.start() for t in th_list])

        # 获取当前时间
        now_time = now()
        event_list = []

        # 查询最新的时间关联策略名称
        strategies = StrategyModel.objects.filter(id__in=[event.strategy_id for event in event_page]).values(
            "id", "name"
        )
        strategies = {strategy["id"]: strategy["name"] for strategy in strategies}

        for event in event_page:
            # 计算频率
            event_related_data = self.related_data.get(event.event_id, {})
            target_key = str(event.target_key).split("|", 1)
            if target_key[0] == "host":
                target_key = "{} {}".format(_("主机"), target_key[1].split("|", 1)[0])
            else:
                dimension_translation = event.origin_alarm["dimension_translation"]
                if target_key[0] == "service":
                    # 服务实例ID 13
                    service_instance_id = dimension_translation["bk_target_service_instance_id"]
                    target_key = "{} {}".format(
                        service_instance_id["display_name"], service_instance_id["display_value"]
                    )
                elif target_key[0] == "topo":
                    # 节点
                    target_key = "{} {}".format(
                        dimension_translation["bk_obj_id"]["display_name"],
                        dimension_translation["bk_inst_id"]["display_name"],
                    )
                else:
                    target_key = ""

            # 尝试取最新策略名
            strategy_name = strategies.get(event.strategy_id, event.origin_config.get("name", ""))

            event_list.append(
                {
                    "id": event.id,
                    "bk_biz_id": event.bk_biz_id,
                    "anomaly_count": event_related_data.get("anomaly_count", 0),
                    "duration": hms_string(event.duration.total_seconds()),
                    "begin_time": event.begin_time,
                    "strategy_name": strategy_name,
                    "event_message": self.get_event_message(event, event_related_data),
                    "alert_status": event_related_data.get("last_notice_status", ""),
                    "event_status": event.status,
                    "level": event.level,
                    "is_ack": event.is_ack,
                    "ack_user": event_related_data.get("ack_user", ""),
                    "ack_message": event_related_data.get("ack_message", ""),
                    "children": [],
                    "target_key": target_key,
                    "display_begin_time": _("{}前").format(
                        hms_string(
                            (now_time - event.begin_time).total_seconds(),
                            display_num=1,
                            day_unit=_("天"),
                            hour_unit=_("小时"),
                            minute_unit=_("分钟"),
                            second_unit=_("秒"),
                        )
                    ),
                    "is_shielded": event.is_shielded,
                    "shield_type": event.shield_type,
                }
            )

        list([t.join() for t in th_list])
        # 获取统计信息
        if validated_request_data["export"]:
            if not event_list:
                return {}

            # 替换字段为中文（表头）
            for event in event_list:
                for field in list(event.keys()):
                    if field in EVENT_FIELD_CHINESE:
                        # 补全告警等级
                        if field == "level":
                            event[field] = EventLevel.EVENT_LEVEL_MAP[event[field]]
                        event[EVENT_FIELD_CHINESE[field]] = event.pop(field)
                    else:
                        event.pop(field)

            return resource.export_import.export_package(list_data=event_list)

        return {
            "statistics_data": {
                "abnormal_count": unshielded_abnormal_count[0],
                "shield_abnormal_count": shielded_abnormal_count[0],
                "all_count": all_event_count[0],
            },
            "event_list": event_list,
        }


class StackedChartResource(EventPermissionResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_ids = serializers.ListField(required=True, label="业务id列表")
        time_range = serializers.CharField(required=True, allow_blank=True, label="时间范围")
        receiver = serializers.CharField(required=False, allow_blank=True, label="通知接受人")
        conditions = serializers.ListField(default=[], label="搜索条件")

    def split_time_range(self, time_range, series_length=45):
        """
        划分时间范围成series_length长度的时间序列
        :param time_range: 时间范围
        :param series_length: 时间序列长度
        :return: [[时间,异常数(0),恢复数(0)]]
        """
        start, end = parse_time_range(time_range)
        now_timestamp = datetime2timestamp(now())
        if end > now_timestamp:
            end = now_timestamp

        total_seconds = end - start
        time_list = [[start, 0, 0]]

        if total_seconds < series_length * 60:
            if total_seconds < 60:
                time_list.append([end, 0, 0])
                return time_list
            time_interval = 60
            for i in range((total_seconds - 1) // 60):
                key = time_list[-1][0] + time_interval
                time_list.append([key, 0, 0])
        else:
            time_interval = total_seconds // series_length
            for i in range(series_length - 1):
                key = time_list[-1][0] + time_interval
                time_list.append([key, 0, 0])
        # 补上最后一个点
        # 时间的列表---[[时间,异常数,恢复数]]
        time_list.append([end, 0, 0])
        time_list.pop(0)

        return time_list

    def perform_request(self, validated_request_data):
        # 针对前端传递的时间范围进行分割，并拿到时间序列
        # 前端需要45个长度的时间序列的异常数和恢复数进行展示，为避免第一列数据不准确，取46个长度的时间序列并过滤第一列
        time_list = self.split_time_range(validated_request_data["time_range"], series_length=46)
        event_queryset = (
            resource.alert_events.query_events(validated_request_data)
            .values("status", "begin_time", "end_time")
            .order_by("begin_time")
        )
        event_set = list(event_queryset)
        data_recover = []
        data_abnormal = []

        index = 1
        for i in event_set:
            # 减少查询time范围
            if index < len(time_list):
                # 事件的起始时间大于查询开始时间
                if i["begin_time"] > datetime.datetime.fromtimestamp(time_list[index][0]).replace(
                    tzinfo=timezone(settings.TIME_ZONE)
                ):
                    index += 1

            # 事件起始时间至查询时间结束
            for time_info in time_list[index:]:
                # 转时区
                datetime_time = datetime.datetime.fromtimestamp(time_info[0]).replace(
                    tzinfo=timezone(settings.TIME_ZONE)
                )
                previous_datetime_time = datetime.datetime.fromtimestamp(time_list[index - 1][0]).replace(
                    tzinfo=timezone(settings.TIME_ZONE)
                )
                # 重置未恢复事件的end_time
                if i["end_time"] == Event.DEFAULT_END_TIME:
                    i["end_time"] = ""

                # 判断事件在时间的范围
                # 异常
                if i["begin_time"] <= datetime_time and (not i["end_time"] or i["end_time"] > datetime_time):
                    time_info[1] += 1
                # 恢复
                elif i["end_time"]:
                    if (previous_datetime_time < i["end_time"] <= datetime_time) and i[
                        "status"
                    ] == EventStatus.RECOVERED:
                        time_info[2] += 1
                        # 找到事件的结束点后跳出一层
                        break

        # 修改成前端需要的数据结构
        for time_info in time_list[1:]:
            # 去除第一个值，以免对前端展示的第一列造成影响
            data_abnormal.append([time_info[0] * 1000, time_info[1]])
            data_recover.append([time_info[0] * 1000, time_info[2]])

        result_data = {
            "series": [{"data": data_abnormal, "name": _("未恢复")}, {"data": data_recover, "name": _("已恢复")}],
            "unit": "",
        }
        return result_data


class EventGraphQueryResource(EventPermissionResource):
    """
    事件图表接口
    """

    class RequestSerializer(serializers.Serializer):
        class QueryConfigSerializer(serializers.Serializer):
            class MetricSerializer(serializers.Serializer):
                field = serializers.CharField()
                method = serializers.CharField()
                alias = serializers.CharField(required=False)
                display = serializers.BooleanField(default=False)

            data_source_label = serializers.CharField(label="数据来源")
            data_type_label = serializers.CharField(
                label="数据类型", default="time_series", allow_null=True, allow_blank=True
            )
            metrics = serializers.ListField(label="查询指标", allow_empty=False, child=MetricSerializer())
            table = serializers.CharField(label="结果表名", required=False, allow_blank=True)
            where = serializers.ListField(label="过滤条件")
            group_by = serializers.ListField(label="聚合字段")
            interval = serializers.IntegerField(default=60, label="时间间隔")
            filter_dict = serializers.DictField(default={}, label="过滤条件")
            time_field = serializers.CharField(label="时间字段", allow_blank=True, allow_null=True, required=False)

            # 日志平台配置
            query_string = serializers.CharField(default="", allow_blank=True, label="日志查询语句")
            index_set_id = serializers.IntegerField(required=False, label="索引集ID")
            functions = serializers.ListField(label="查询函数", default=[])

            def validate(self, attrs: dict) -> dict:
                if attrs["data_source_label"] == DataSourceLabel.BK_LOG_SEARCH and not attrs.get("index_set_id"):
                    raise ValidationError("index_set_id can not be empty.")
                return attrs

        id = serializers.IntegerField(label="事件ID")
        bk_biz_id = serializers.IntegerField(label="业务ID")
        query_configs = serializers.ListField(label="查询配置列表", allow_empty=False, child=QueryConfigSerializer())
        function = serializers.DictField(label="功能函数", default={})
        functions = serializers.ListField(label="计算函数", default=[])
        expression = serializers.CharField(label="查询表达式", allow_blank=True)
        start_time = serializers.IntegerField(label="开始时间", required=False)
        end_time = serializers.IntegerField(label="结束时间", required=False)

    AvailableDataLabel = (
        (DataSourceLabel.BK_DATA, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG),
        (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT),
        (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG),
    )

    def perform_request(self, params: dict):
        try:
            event = Event.objects.get(id=params["id"])
        except Event.DoesNotExist:
            raise EventNotExist(event_id=params["id"])

        strategy = event.origin_strategy
        item = strategy["items"][0]
        query_config = item["query_configs"][0]

        if (query_config["data_source_label"], query_config["data_type_label"]) not in self.AvailableDataLabel:
            return []

        threshold_band = {"from": event.origin_alarm["data"]["time"] * 1000, "to": None}

        # 1. 时间的起始时间，当刚发生时是发生时间段往前60个周期的图。
        # 2. 当发生的时间一直往后延，起始时间变成 初次异常+5个周期前数据
        # 3. 结束时间一直到事件结束的后的5个周期 ，或者超过1440个周期 最多到1440个周期数据
        if not params.get("start_time") or not params.get("end_time"):
            start_time = int(datetime2timestamp(event.begin_time))
            if event.status == EventStatus.RECOVERED:
                threshold_band["to"] = int(datetime2timestamp(event.end_time)) * 1000
                end_time = int(datetime2timestamp(event.end_time))
            else:
                end_time = datetime2timestamp(now())
            interval = params["query_configs"][0]["interval"]
            end_time = min(end_time + interval * 5, start_time + 1440 * interval, datetime2timestamp(now()))
            diff = 1440 * interval - (end_time - start_time)
            if diff < interval * 5:
                diff = interval * 5
            elif diff > interval * 60:
                diff = interval * 60
            start_time -= diff
            params["start_time"] = start_time
            params["end_time"] = end_time
        else:
            start_time = params["start_time"]
            end_time = params["end_time"]

        result = resource.grafana.graph_unify_query(params)

        data = result["series"]
        if not data:
            return []

        unit = load_unit(data[0].get("unit", ""))

        # 暂时只支持静态阈值,以后显示同比环比
        # 用列表是因为同一level下,可以既有静态阈值,又有同比策略
        alert_algorithm_list = [algorithm for algorithm in item["algorithms"] if algorithm["level"] == event.level]
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
        point = [event.origin_alarm["data"]["value"], threshold_band["from"]]
        point_time_list = [point[1] for point in data[0]["datapoints"]]
        first_anomaly_in_time_range = start_time <= threshold_band["from"] <= end_time
        if threshold_band["from"] not in point_time_list and first_anomaly_in_time_range:
            position = bisect.bisect(point_time_list, threshold_band["from"])
            data[0]["datapoints"].insert(position, point)

        data[0]["markTimeRange"] = [threshold_band]
        data[0]["markPoints"] = [point]
        data[0]["thresholds"] = threshold_line

        return data


class DetailEventResource(EventPermissionResource, EventDimensionMixin):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="事件ID")

    @staticmethod
    def get_target_relation_info(bk_biz_id, target_key):
        """
        解析事件目标并获取关联信息
        :param bk_biz_id: 业务ID
        :param target_key: 事件目标
        :return: 结构化的目标信息，关联信息
        """
        relation_info = ""
        if not target_key:
            return relation_info

        if not target_key.startswith("host|") and not target_key.startswith("service|"):
            return relation_info

        bk_module_ids = []
        if target_key.startswith("host|"):
            no_use, ip, bk_cloud_id = target_key.split("|")
            hosts = api.cmdb.get_host_by_ip(
                bk_biz_id=bk_biz_id,
                ips=[{"ip": ip, "bk_cloud_id": bk_cloud_id}],
            )
            if hosts:
                bk_module_ids.extend(hosts[0].bk_module_ids)
        else:
            no_use, service_instance_id = target_key.split("|")
            instances = api.cmdb.get_service_instance_by_id(
                bk_biz_id=bk_biz_id, service_instance_ids=[service_instance_id]
            )
            if instances:
                bk_module_ids.append(instances[0].bk_module_id)

        modules = api.cmdb.get_module(bk_biz_id=bk_biz_id, bk_module_ids=bk_module_ids)
        sets = api.cmdb.get_set(bk_biz_id=bk_biz_id, bk_set_ids=[module.bk_set_id for module in modules])

        if sets:
            relation_info += _("集群({}) ").format(",".join([s.bk_set_name for s in sets]))

        if modules:
            relation_info += _("模块({}) ").format(",".join([m.bk_module_name for m in modules]))

        return relation_info

    @staticmethod
    def stat_alert_info(notice_list):
        alert_info = {
            "count": 0,
            "success_count": 0,
            "partial_count": 0,
            "shielded_count": 0,
            "empty_receiver_count": 0,
            "failed_count": 0,
        }
        for notice in notice_list:
            if notice.status == EventActionStatus.SUCCESS:
                alert_info["success_count"] += 1
            elif notice.status == EventActionStatus.SHIELDED:
                alert_info["shielded_count"] += 1
            elif notice.status == EventActionStatus.FAILED:
                if notice.extend_info.get("empty_receiver", False):
                    alert_info["empty_receiver_count"] += 1
                else:
                    alert_info["failed_count"] += 1
            elif notice.status == EventActionStatus.PARTIAL_SUCCESS:
                alert_info["partial_count"] += 1
            else:
                continue

            alert_info["count"] += 1
        return alert_info

    def perform_request(self, validated_request_data):
        set_local_username(get_backend_username() or "admin")
        event = resource.alert_events.get_event(validated_request_data)
        notice_list = EventAction.objects.filter(event_id=event.event_id, operate=EventOperate.ANOMALY_NOTICE)
        # 统计每次通知的状态
        alert_info = self.stat_alert_info(notice_list)

        # 获取最新策略名
        strategy = StrategyModel.objects.filter(id=event.strategy_id).values("name")
        strategy_name = strategy[0]["name"] if strategy else event.origin_config.get("name", "")

        try:
            relation_info = self.get_target_relation_info(validated_request_data["bk_biz_id"], event.target_key)
            relation_info += get_event_relation_info(event)
        except Exception as err:
            logger.exception(f"Get anomaly content err, msg is {err}")
            relation_info = ""

        item = event.origin_strategy["items"][0]
        query_config = item["query_configs"][0]

        unify_query_params = {
            "expression": item.get("expression", ""),
            "query_configs": [],
            "function": {"time_compare": ["1d", "1w"]},
        }

        index_set_id = None
        if (
            query_config["data_source_label"],
            query_config["data_type_label"],
        ) in EventGraphQueryResource.AvailableDataLabel:
            for query_config in item["query_configs"]:
                dimensions = event.origin_alarm.get("data", {}).get("dimensions", {})
                dimensions = {key: value for key, value in dimensions.items() if key in query_config["agg_dimension"]}
                filter_dict = {}

                if (query_config["data_source_label"], query_config["data_type_label"]) == (
                    DataSourceLabel.BK_MONITOR_COLLECTOR,
                    DataTypeLabel.LOG,
                ):
                    # 关键字的节点维度需要转换成实际的维度字段
                    if "bk_obj_id" in dimensions and "bk_inst_id" in dimensions:
                        bk_obj_id = dimensions.pop("bk_obj_id")
                        bk_inst_id = dimensions.pop("bk_inst_id")
                        dimensions[f"bk_{bk_obj_id}_id"] = str(bk_inst_id)

                    query_config["metric_field"] = "event.count"
                elif (query_config["data_source_label"], query_config["data_type_label"]) == (
                    DataSourceLabel.CUSTOM,
                    DataTypeLabel.EVENT,
                ):
                    # 自定义事件需要添加额外的过滤条件
                    if query_config["custom_event_name"]:
                        filter_dict["event_name"] = query_config["custom_event_name"]
                    query_config["metric_field"] = "_index"
                elif (query_config["data_source_label"], query_config["data_type_label"]) == (
                    DataSourceLabel.BK_LOG_SEARCH,
                    DataTypeLabel.LOG,
                ):
                    query_config["metric_field"] = "_index"

                where = GetGraphQueryConfig.create_where_with_dimensions(query_config["agg_condition"], dimensions)
                agg_dimension = list(set(query_config["agg_dimension"]) & set(dimensions.keys()))

                metrics = [
                    {
                        "field": query_config.get("metric_field", "_index"),
                        "method": query_config.get("agg_method", "COUNT"),
                        "alias": query_config.get("alias", "A"),
                    }
                ]

                # 扩展指标（针对智能异常检测，需要根据敏感度来）
                extend_metric_fields = query_config.get("values", [])
                algorithm_list = item.get("algorithms", [])
                intelligent_algorithm_list = [
                    algorithm
                    for algorithm in algorithm_list
                    if algorithm["level"] == event.level
                    and algorithm["type"] == AlgorithmModel.AlgorithmChoices.IntelligentDetect
                ]
                if intelligent_algorithm_list:
                    extend_metric_fields = ["is_anomaly", "lower_bound", "upper_bound"]
                for extend_metric in extend_metric_fields:
                    metrics.append({"field": extend_metric, "method": query_config.get("agg_method", "COUNT")})

                unify_query_params["query_configs"].append(
                    {
                        "custom_event_name": query_config.get("custom_event_name", ""),
                        "query_string": query_config.get("query_string", ""),
                        "index_set_id": query_config.get("index_set_id", 0),
                        "bk_biz_id": validated_request_data["bk_biz_id"],
                        "data_source_label": query_config["data_source_label"],
                        "data_type_label": query_config["data_type_label"],
                        "group_by": agg_dimension,
                        "table": query_config["result_table_id"],
                        "metrics": metrics,
                        "interval": query_config["agg_interval"],
                        "where": where,
                        "time_field": query_config.get("time_field"),
                        "extend_fields": query_config.get("extend_fields", {}),
                        "filter_dict": filter_dict,
                        "functions": query_config.get("functions", []),
                    }
                )

                index_set_id = query_config.get("index_set_id", 0)

        result_data = {
            "id": event.id,
            "bk_biz_id": event.bk_biz_id,
            "hold_time": hms_string(event.duration.total_seconds()),
            "first_anomaly_time": event.begin_time,
            "event_begin_time": event.create_time,
            "strategy_id": event.strategy_id,
            "strategy_name": strategy_name,
            "dimensions": self.get_dimensions(event, False),
            "dimension_message": self.get_dimensions_str(event, False),
            "level": event.level,
            "event_status": event.status,
            "is_shielded": event.is_shielded,
            "is_ack": event.is_ack,
            "alert_info": alert_info,
            "algorithm_list": item.get("algorithms", []),
            "event_message": event.anomaly_message,
            "relation_info": relation_info,
            "log_index_id": index_set_id,
        }

        if unify_query_params["query_configs"]:
            data_source_label = unify_query_params["query_configs"][0]["data_source_label"]
            data_type_label = unify_query_params["query_configs"][0]["data_type_label"]
            is_bar = (data_source_label, data_type_label) in (
                (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG),
                (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT),
            )

            sub_titles = "\n".join([query_config["metric_id"] for query_config in item["query_configs"]])

            result_data["graph_panel"] = {
                "id": "event",
                "type": "bar" if is_bar else "graph",
                "title": item.get("name") or item.get("expression", ""),
                "subTitle": sub_titles,
                "targets": [
                    {
                        "data": unify_query_params,
                        "datasourceId": "time_series",
                        "name": _("时序数据"),
                        "alias": "$time_offset",
                    }
                ],
            }

        return result_data


class StrategySnapshotResource(EventPermissionResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="事件ID")

    def perform_request(self, validated_request_data):
        event_id = validated_request_data["id"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        is_enabled = False
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            raise EventNotExist({"event_id": event_id})

        strategy_config = event.origin_strategy

        # 策略更新状态
        changed_status = ConfigChangedStatus.UNCHANGED
        try:
            strategy = StrategyModel.objects.get(bk_biz_id=bk_biz_id, id=event.strategy_id)
            is_enabled = strategy.is_enabled
        except StrategyNotExist:
            changed_status = ConfigChangedStatus.DELETED
        else:
            if int(strategy.update_time.timestamp()) != strategy_config["update_time"]:
                changed_status = ConfigChangedStatus.UPDATED

        strategy_config.update(strategy_status=changed_status)
        try:
            strategy_config["create_time"] = utc2datetime(strategy_config["create_time"])
            strategy_config["update_time"] = utc2datetime(strategy_config["update_time"])
        except Exception:
            pass
        strategy_config["is_enabled"] = is_enabled
        return strategy_config


class ListAlertNoticeResource(EventPermissionResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="事件ID")

    def perform_request(self, validated_request_data):
        event_unique_id = validated_request_data["id"]
        try:
            event_instance = Event.objects.get(id=event_unique_id)
        except Event.DoesNotExist:
            raise EventNotExist({"event_id": event_unique_id})

        event_action_instances = EventAction.objects.filter(
            event_id=event_instance.event_id,
            operate=EventOperate.ANOMALY_NOTICE,
            status__in=[
                EventActionStatus.SUCCESS,
                EventActionStatus.PARTIAL_SUCCESS,
                EventActionStatus.FAILED,
                EventActionStatus.SHIELDED,
            ],
        )
        result_list = []
        index = 0
        for event_action in event_action_instances:
            index += 1
            if event_action.status == EventActionStatus.FAILED and event_action.extend_info.get(
                "empty_receiver", False
            ):
                status = "EMPTY_RECEIVER"
            else:
                status = event_action.status

            result_list.append(
                {
                    "index": index,
                    "action_time": strftime_local(event_action.create_time, "%Y-%m-%d %H:%M:%S"),
                    "action_id": event_action.id,
                    "status": status,
                }
            )

        return result_list


class DetailAlertNoticeResource(Resource):
    class RequestSerializer(serializers.Serializer):
        action_id = serializers.CharField(required=True, label="通知时间")

    @staticmethod
    def status_convert(status):
        status_mapping = {AlertStatus.FAILED: 0, AlertStatus.SUCCESS: 1, AlertStatus.SHIELDED: 2}
        return status_mapping.get(status, 3)

    def perform_request(self, validated_request_data):
        action_id = validated_request_data["action_id"]
        alert_list = Alert.objects.filter(action_id=action_id)
        alert_way = []
        alert_data = {}
        notify_roles = resource.cc.get_notify_roles()
        for alert in alert_list:
            user_alert_info = alert_data.setdefault(
                alert.username,
                {"receiver": alert.username, "notice_group": notify_roles.get(alert.role, "")},
            )
            user_alert_info.update(
                {alert.method: {"status": self.status_convert(alert.status), "message": alert.message}}
            )
            # 记录通知方式
            if alert.method not in alert_way:
                alert_way.append(alert.method)

        # 获取通知方式名称
        origin_notice_way = resource.notice_group.get_notice_way()
        # 建立通知方式type和label的映射关系
        notice_way_mapping = {"webhook": _("回调")}
        for way in origin_notice_way:
            notice_way_mapping[way["type"]] = way["label"]

        return {
            "alert_way": [{"id": way, "name": notice_way_mapping.get(way, way)} for way in alert_way],
            "alert_detail": list(alert_data.values()),
        }


class AckEventResource(EventPermissionResource):
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


class GetEventResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="事件ID")

    def perform_request(self, validated_request_data):
        try:
            return Event.objects.get(bk_biz_id=validated_request_data["bk_biz_id"], id=validated_request_data["id"])
        except Event.DoesNotExist:
            raise EventNotExist({"event_id": validated_request_data["id"]})


class GetSolutionResource(EventPermissionResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="事件ID")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        event_id = validated_request_data["id"]
        event = resource.alert_events.get_event(bk_biz_id=bk_biz_id, id=event_id)
        metric_id = event.origin_strategy["items"][0]["query_configs"][0]["metric_id"]
        result_data = {"solution": ""}
        try:
            solution = AlertSolution.objects.get(bk_biz_id=bk_biz_id, metric_id=metric_id)
        except AlertSolution.DoesNotExist:
            return result_data

        result_data["solution"] = solution.content
        return result_data


class SaveSolutionResource(EventPermissionResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="事件ID")
        solution = serializers.CharField(required=True, allow_blank=True, label="解决方法")

    def perform_request(self, validated_request_data):
        content = validated_request_data.pop("solution")
        bk_biz_id = validated_request_data["bk_biz_id"]
        event_id = validated_request_data["id"]
        event = resource.alert_events.get_event(bk_biz_id=bk_biz_id, id=event_id)
        metric_id = event.origin_strategy["items"][0]["query_configs"][0]["metric_id"]
        try:
            solution = AlertSolution.objects.get(bk_biz_id=bk_biz_id, metric_id=metric_id)
        except AlertSolution.DoesNotExist:
            AlertSolution.objects.create(bk_biz_id=bk_biz_id, metric_id=metric_id, content=content)
            return

        solution.content = content
        solution.save()


class ListEventLogResource(EventPermissionResource):
    def __init__(self):
        super().__init__()
        self.event = None

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="事件ID")
        offset = serializers.IntegerField(required=False, label="上一页最后一条日志ID")
        limit = serializers.IntegerField(default=10, label="获取的条数")
        operate = serializers.ListField(default=[], label="流转状态")

    def get_ack_content(self, log):
        return {"contents": [_("{}确认了该告警事件并备注：").format(log.username), log.extend_info["message"]]}

    def get_notice_content(self, log: EventAction):
        notice_action = self.event.origin_strategy["actions"][0]
        alarm_interval = notice_action["config"]["alarm_interval"]
        if log.status == EventActionStatus.SHIELDED:
            shield_log = log.shield_log
            shield_message = defaultdict(
                lambda: _("受到相关屏蔽规则影响"),
                {
                    "host_status": _("主机的运营状态为不告警状态"),
                    "host_target": _("存在相同配置的基于静态IP配置的监控策略"),
                    "saas_config": _("受到相关屏蔽策略影响"),
                    "alarm_time": _("不在告警时间段内"),
                },
            )

            return {
                "contents": [
                    _(
                        "已达到发起告警通知条件（告警未恢复及未关闭，每隔{}分钟发送一次通知），但由于{}，系统已将通知屏蔽"
                    ).format(alarm_interval, shield_message[shield_log.get("type")])
                ],
                "shield_snapshot_id": log.id,
                "shield_type": shield_log.get("type", ""),
                "shield_detail": shield_log.get("detail", {}),
            }

        notice_groups = [group["name"] for group in notice_action["notice_group_list"]]
        content = [
            _("已达到发起告警通知的条件（告警未恢复及未关闭，每隔{}分钟发送一次通知），接收通知的告警组").format(
                alarm_interval
            ),
            notice_groups,
            _(", 通知状态"),
            log.status,
        ]

        if log.message:
            content.append(_(", 失败原因: {}").format(log.message))

        return {"contents": content}

    def get_recover_content(self, log):
        return {"contents": [log.message]}

    def get_close_content(self, log):
        return {"contents": [log.message]}

    def get_create_content(self, log):
        anomaly_list = AnomalyRecord.objects.get(anomaly_id=self.event.event_id)
        if not anomaly_list:
            source_time = None
        else:
            source_time = strftime_local(anomaly_list.source_time, "%Y-%m-%d %H:%M:%S")
        anomaly_message = self.event.origin_alarm["anomaly"][str(self.event.level)]["anomaly_message"]
        item = self.event.origin_strategy["items"][0]
        detect = self.event.origin_strategy["detects"][0]
        if self.event.is_no_data:
            continuous = item["no_data_config"]["continuous"]
            append_message = _("达到了触发告警条件（数据连续丢失{}个周期）").format(continuous)
        else:
            trigger_config = detect["trigger_config"]
            append_message = _("达到了触发告警条件（{}周期内满足{}次检测算法）").format(
                trigger_config["check_window"], trigger_config["count"]
            )
        return {"source_time": source_time, "index": 0, "contents": [anomaly_message, append_message]}

    def get_converge_content(self, log):
        extend_info = log.extend_info
        process_time = extend_info["process_time"]
        data_time = extend_info["data_time"]
        is_multiple = process_time["min"] != process_time["max"]
        anomaly_message = extend_info["anomaly_record"]["anomaly"][str(self.event.level)]["anomaly_message"]
        return {
            "index": 0,
            "contents": [anomaly_message],
            "time": utc2biz_str(process_time["max"]),
            "begin_time": utc2biz_str(process_time["min"]),
            "is_multiple": is_multiple,
            "source_time": utc2biz_str(data_time["max"]),
            "begin_source_time": utc2biz_str(data_time["min"]),
        }

    def get_content_handler(self, operate):
        handler_mapping = {
            EventOperate.ACK: self.get_ack_content,
            EventOperate.CREATE: self.get_create_content,
            EventOperate.ANOMALY_NOTICE: self.get_notice_content,
            EventOperate.CONVERGE: self.get_converge_content,
            EventOperate.RECOVER: self.get_recover_content,
            EventOperate.CLOSE: self.get_close_content,
        }
        return handler_mapping[operate]

    def get_before_event_converge(self):
        anomaly_list = AnomalyRecord.objects.filter(
            event_id=self.event.event_id, source_time__lt=self.event.begin_time
        ).order_by("source_time")
        anomaly_list = list(anomaly_list)
        if len(anomaly_list) == 0:
            return

        min_time = strftime_local(anomaly_list[0].source_time, "%Y-%m-%d %H:%M:%S")
        max_time = strftime_local(anomaly_list[-1].source_time, "%Y-%m-%d %H:%M:%S")
        is_multiple = min_time != max_time
        anomaly_message = anomaly_list[-1].origin_alarm["anomaly"][str(self.event.level)]["anomaly_message"]
        return {
            "action_id": -1,
            "operate": EventOperate.CONVERGE,
            "operate_display": _("告警收敛"),
            "index": 0,
            "contents": [anomaly_message],
            "time": strftime_local(anomaly_list[-1].create_time, "%Y-%m-%d %H:%M:%S"),
            "begin_time": strftime_local(anomaly_list[0].create_time, "%Y-%m-%d %H:%M:%S"),
            "is_multiple": is_multiple,
            "source_time": max_time,
            "begin_source_time": min_time,
        }

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        event_id = validated_request_data["id"]
        operate_list = validated_request_data["operate"]
        offset = validated_request_data.get("offset")
        limit = validated_request_data["limit"]
        self.event = resource.alert_events.get_event({"bk_biz_id": bk_biz_id, "id": event_id})
        event_logs = EventAction.objects.filter(event_id=self.event.event_id).order_by("-id")
        if operate_list:
            event_logs = event_logs.filter(operate__in=operate_list)

        if offset:
            event_logs = event_logs.filter(id__lt=offset)

        result_data = []
        for log in event_logs[:limit]:
            log_record = {
                "action_id": log.id,
                "time": strftime_local(log.create_time, "%Y-%m-%d %H:%M:%S"),
                "operate": log.operate,
                "operate_display": log.get_operate_display(),
            }
            content_handler = self.get_content_handler(log.operate)
            content_dict = content_handler(log)
            log_record.update(content_dict)
            result_data.append(log_record)

        # 如果是获取到了告警产生记录，取出产生告警前产生的异常记录
        last_operate_is_create = len(result_data) > 0 and result_data[-1]["operate"] == EventOperate.CREATE
        if EventOperate.CONVERGE in operate_list and last_operate_is_create:
            before_event_converge = self.get_before_event_converge()
            if before_event_converge:
                result_data.append(self.get_before_event_converge())

        return result_data


class ListSearchItemResource(EventPermissionResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_ids = serializers.ListField(required=True, label="业务ID列表")

    @staticmethod
    def get_service_category(bk_biz_id):
        res_service_category = api.cmdb.search_service_category(bk_biz_id=bk_biz_id)
        category_mapping = {}
        for category in res_service_category:
            category_mapping[category["id"]] = category

        category_list = set()
        for category in res_service_category:
            if category.get("bk_parent_id"):
                parent_info = category_mapping.get(category["bk_parent_id"], {})
                label_first = parent_info.get("name", "")
                label_second = category.get("name", "")
                category_list.add(f"{label_first}-{label_second}")

        return list(category_list)

    def perform_request(self, params):
        labels = api.metadata.get_label(label_type=LabelType.ResultTableLabel, level=2, include_admin_only=True)
        date_sources = [
            {
                "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                "source_type": SourceType.BKMONITOR[0],
                "data_type_label": DataTypeLabel.TIME_SERIES,
                "source_name": SourceType.BKMONITOR[1],
            },
            {
                "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                "source_type": SourceType.BASEALARM[0],
                "data_type_label": DataTypeLabel.EVENT,
                "source_name": SourceType.BASEALARM[1],
            },
            {
                "data_source_label": DataSourceLabel.BK_DATA,
                "data_type_label": DataTypeLabel.TIME_SERIES,
                "source_type": SourceType.BKDATA[0],
                "source_name": SourceType.BKDATA[1],
            },
            {
                "data_source_label": DataSourceLabel.CUSTOM,
                "data_type_label": DataTypeLabel.EVENT,
                "source_type": SourceType.CUSTOMEVENT[0],
                "source_name": SourceType.CUSTOMEVENT[1],
            },
            {
                "data_source_label": DataSourceLabel.CUSTOM,
                "data_type_label": DataTypeLabel.TIME_SERIES,
                "source_type": SourceType.CUSTOMTIMINGDATA[0],
                "source_name": SourceType.CUSTOMTIMINGDATA[1],
            },
        ]

        # receiver参数存在代表业务鉴权失败
        if "receiver" in params:
            all_service_categories = []
            strategies = []
        else:
            # 获取服务分类列表
            all_service_categories = []
            for bk_biz_id in params["bk_biz_ids"]:
                service_categories = self.get_service_category(bk_biz_id=bk_biz_id)
                all_service_categories.extend(service_categories)

            if not params["bk_biz_ids"]:
                service_categories = self.get_service_category(bk_biz_id=2)
                all_service_categories.extend(service_categories)

            # 获取策略列表
            strategies = [
                {"id": strategy.id, "name": strategy.name}
                for strategy in StrategyModel.objects.filter(bk_biz_id__in=params["bk_biz_ids"])
            ]

        return [
            {
                "id": "data_source",
                "name": _("数据来源"),
                "children": [
                    {
                        "id": "{}|{}".format(source["data_source_label"], source["data_type_label"]),
                        "name": source["source_name"],
                    }
                    for source in date_sources
                ],
            },
            {
                "id": "scenario",
                "name": _("监控对象"),
                "children": [
                    {"id": label["label_id"], "name": label["label_name"]} for label in labels["result_table_label"]
                ],
            },
            {
                "id": "alert_status",
                "name": _("通知状态"),
                "children": [
                    {"id": EventActionStatus.SUCCESS, "name": _("成功")},
                    {"id": EventActionStatus.FAILED, "name": _("失败")},
                    {"id": EventActionStatus.PARTIAL_SUCCESS, "name": _("部分失败")},
                    {"id": EventActionStatus.SHIELDED, "name": _("已屏蔽")},
                ],
            },
            {
                "id": "event_status",
                "name": _("告警状态"),
                "children": [
                    {"id": EventStatus.ABNORMAL, "name": _("未恢复")},
                    {"id": EventStatus.RECOVERED, "name": _("已恢复")},
                    {"id": EventStatus.ABNORMAL_ACK, "name": _("未恢复(已确认)")},
                    {"id": EventStatus.CLOSED, "name": _("已失效")},
                ],
            },
            {
                "id": "service_category",
                "name": _("服务分类"),
                "children": [{"id": category, "name": category} for category in all_service_categories],
            },
            {"id": "content", "name": _("告警内容"), "children": None},
            {"id": "ip", "name": _("主机IP"), "children": None},
            {"id": "alert_collect_id", "name": _("告警汇总ID"), "children": None},
            {"id": "id", "name": _("事件ID"), "children": None},
            {"id": "metric_id", "name": _("指标ID"), "children": None},
            {
                "id": "level",
                "name": _("告警级别"),
                "children": [{"id": i[0], "name": i[1]} for i in EventLevel.EVENT_LEVEL],
            },
            {"id": "strategy_id", "name": _("触发策略"), "children": strategies},
        ]


class ListConvergeLogResource(EventPermissionResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="事件ID")
        time_range = serializers.CharField(required=True, label="时间范围")

    def perform_request(self, validated_request_data):
        time_range = validated_request_data.pop("time_range")
        event = resource.alert_events.get_event(validated_request_data)
        start, end = parse_time_range(time_range)
        anomaly_records = AnomalyRecord.objects.filter(
            event_id=event.event_id,
            create_time__gte=datetime.datetime.fromtimestamp(start),
            create_time__lte=datetime.datetime.fromtimestamp(end),
        ).order_by("-create_time")
        result_data = []
        # 去掉第一条，应该list_event_log接口已经获取了第一条的信息
        for anomaly in anomaly_records[1:]:
            anomaly_message = anomaly.origin_alarm["anomaly"][str(event.level)]["anomaly_message"]
            result_data.append(
                {
                    "time": strftime_local(anomaly.create_time, "%Y-%m-%d %H:%M:%S"),
                    "operate": EventOperate.CONVERGE,
                    "operate_display": _("告警收敛"),
                    "index": 0,
                    "contents": [anomaly_message],
                    "end_time": None,
                    "is_multiple": False,
                    "source_time": strftime_local(anomaly.source_time, "%Y-%m-%d %H:%M:%S"),
                    "count": anomaly.count,
                }
            )

        return result_data


class ShieldSnapshotResource(EventPermissionResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="事件ID")
        shield_snapshot_id = serializers.IntegerField(required=True, label="事件ID")

    def perform_request(self, validated_request_data):
        event_action = EventAction.objects.get(id=validated_request_data["shield_snapshot_id"])
        # 如果屏蔽类型不是SaaS配置，则返回空字典
        if event_action.shield_log.get("type") != ShieldType.SAAS_CONFIG:
            raise ValidationError("event_action({}) shield type is not saas_config.")

        shield_config = extended_json.loads(event_action.shield_log["detail"])
        shield_status = ConfigChangedStatus.UNCHANGED
        try:
            shield_obj = Shield.objects.get(id=shield_config["id"])
            utc_tz = timezone("UTC")
            snapshot_update_time = shield_config["update_time"]
            snapshot_update_time = snapshot_update_time.replace(tzinfo=utc_tz)
            if shield_obj.update_time != snapshot_update_time:
                shield_status = ConfigChangedStatus.UPDATED
        except Shield.DoesNotExist:
            shield_status = ConfigChangedStatus.DELETED

        result_data = resource.shield.shield_snapshot(config=shield_config)
        result_data.update(shield_status=shield_status)
        return result_data


class EventRelatedInfoResource(EventPermissionResource):
    """
    事件关联信息查询
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        ids = serializers.ListField(child=serializers.IntegerField(), required=True, label="事件ID")

    @staticmethod
    def get_cmdb_related_info(bk_biz_id, events: list[Event]) -> dict[str, dict]:
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

        # 提取事件的主机IP和服务实例ID
        ips = {}
        service_instance_ids = {}
        for event in events:
            if event.target_key.startswith("host|"):
                ip, bk_cloud_id = event.target_key.split("|")[1:]
                ips[event.id] = {"ip": ip, "bk_cloud_id": int(bk_cloud_id)}
                related_infos[event.id]["ip"] = ip
                related_infos[event.id]["bk_cloud_id"] = bk_cloud_id
                related_infos[event.id]["type"] = "host"
            elif event.target_key.startswith("service|"):
                service_instance_ids[event.id] = event.target_key.split("|")[1]

        # 查询主机和服务实例信息
        hosts: list[Host] = api.cmdb.get_host_by_ip(bk_biz_id=bk_biz_id, ips=list(ips.values()))
        service_instances: list[ServiceInstance] = api.cmdb.get_service_instance_by_id(
            bk_biz_id=bk_biz_id, service_instance_ids=list(service_instance_ids.values())
        )

        # 将主机和服务实例转为模块ID
        host_to_module_id = {(host.bk_host_innerip, host.bk_cloud_id): host.bk_module_ids for host in hosts}
        host_to_hostname = {(host.bk_host_innerip, host.bk_cloud_id): host.bk_host_name for host in hosts}
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
        event_to_module_ids = {}
        for event_id, ip in ips.items():
            event_to_module_ids[event_id] = set(host_to_module_id.get((ip["ip"], ip["bk_cloud_id"]), []))
            related_infos[event_id]["hostname"] = host_to_hostname.get((ip["ip"], ip["bk_cloud_id"]), "")

        for event_id, service_instance_id in service_instance_ids.items():
            if service_instance_id in service_to_module_id:
                event_to_module_ids[event_id] = {service_to_module_id[service_instance_id]}

        # 记录事件集群模块描述信息
        for event_id, bk_module_ids in event_to_module_ids.items():
            topo_info = ""
            if not bk_module_ids:
                related_infos[event_id]["topo_info"] = topo_info
                continue

            bk_set_ids = {
                module_to_set[bk_module_id] for bk_module_id in bk_module_ids if bk_module_id in module_to_set
            }

            if bk_set_ids:
                topo_info += _("集群({}) ").format(
                    ",".join([set_names[bk_set_id] for bk_set_id in bk_set_ids if bk_set_id in set_names])
                )

            topo_info += _("模块({})").format(
                ",".join([module_names[bk_module_id] for bk_module_id in bk_module_ids if bk_module_id in module_names])
            )
            related_infos[event_id]["topo_info"] = topo_info

        return related_infos

    @staticmethod
    def get_log_related_info(bk_biz_id, events: list[Event]) -> dict[str, dict]:
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

        for event in events:
            item = event.origin_strategy["items"][0]
            query_config = item["query_configs"][0]
            if query_config["data_source_label"] != DataSourceLabel.BK_LOG_SEARCH:
                continue

            if not query_config.get("index_set_id"):
                continue

            related_infos[event.id] = {
                "type": "log_search",
                "index_set_id": query_config["index_set_id"],
                "query_string": query_config.get("query_string", "*"),
                "agg_condition": query_config["agg_condition"],
            }

        return related_infos

    @staticmethod
    def get_custom_event_related_info(bk_biz_id, events: list[Event]) -> dict[str, dict]:
        """
        自定义事件关联信息

        {
            "type": "custom_event",
            "bk_event_group_id": 1
        }
        """
        related_infos = defaultdict(dict)

        event_groups = CustomEventGroup.objects.filter(bk_biz_id=bk_biz_id)
        table_id_to_group_ids = {event_group.table_id: event_group.bk_event_group_id for event_group in event_groups}

        for event in events:
            item = event.origin_strategy["items"][0]
            query_config = item["query_configs"][0]
            if (query_config["data_source_label"], query_config["data_type_label"]) != (
                DataSourceLabel.CUSTOM,
                DataTypeLabel.EVENT,
            ):
                continue

            if query_config["result_table_id"] in table_id_to_group_ids:
                related_infos[event.id]["type"] = "custom_event"
                related_infos[event.id]["bk_event_group_id"] = table_id_to_group_ids[query_config["result_table_id"]]

        return related_infos

    @staticmethod
    def get_bkdata_related_info(bk_biz_id, events: list[Event]) -> dict[str, dict]:
        """
        计算平台关联信息
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

        for event in events:
            if not event.origin_strategy["items"]:
                continue

            item = event.origin_strategy["items"][0]
            query_config = item["query_configs"][0]
            if query_config["data_source_label"] != DataSourceLabel.BK_DATA:
                continue

            related_infos[event.id] = {
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

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        events = list(Event.objects.filter(id__in=params["ids"]).only("id", "target_key", "origin_config"))
        related_infos = defaultdict(dict)

        related_infos.update(self.get_cmdb_related_info(bk_biz_id, events))
        related_infos.update(self.get_custom_event_related_info(bk_biz_id, events))
        related_infos.update(self.get_bkdata_related_info(bk_biz_id, events))
        related_infos.update(self.get_log_related_info(bk_biz_id, events))

        return related_infos


class GraphPointResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(default=0, label="业务ID")
        id = serializers.IntegerField(required=True, label="事件ID")
        time_range = serializers.CharField(required=False, label="时间范围")

    def perform_request(self, validated_request_data):
        time_range = validated_request_data.get("time_range")
        event_unique_id = validated_request_data["id"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        # event = resource.alert_events.get_event(bk_biz_id=validated_request_data["bk_biz_id"], id=event_unique_id)
        alert = AlertDocument.get(event_unique_id)

        strategy_config = alert.strategy
        origin_alarm = alert.origin_alarm or {}

        item = strategy_config["items"][0]
        query_config = item["query_configs"][0]
        title = query_config.get("metric_field") or query_config.get("metric_id")

        # 检查是否时序数据，如果非时序数据,或者聚合方法是实时数据,则无法出图
        if query_config["data_type_label"] != DataTypeLabel.TIME_SERIES:
            raise NotTimeSeriesError({"event_id": event_unique_id})
        if query_config.get("agg_method") == AGG_METHOD_REAL_TIME:
            raise AggmethodIsRealtimeError({"event_id": event_unique_id})
        detect_algorithm_list = item["algorithms"]
        # 阈值线,暂时只支持静态阈值,以后显示同比环比
        # 用列表是因为同一level下,可以既有静态阈值,又有同比策略
        alert_algorithm_list = [
            algorithm for algorithm in detect_algorithm_list if algorithm["level"] == alert.severity
        ]
        threshold_line = []
        if len(alert_algorithm_list) == 1 and alert_algorithm_list[0]["type"] == AlgorithmType.Threshold:
            threshold_config = alert_algorithm_list[0]["config"]
            if len(threshold_config) == 1 and len(threshold_config[0]) == 1:
                threshold_line.append({"value": threshold_config[0][0]["threshold"], "name": " "})

        # 获取图表查询时间段
        plot_bands = {"from": alert.origin_alarm["data"]["time"] * 1000, "to": None}
        query_result = dict(
            threshold_line=threshold_line,
            plot_bands=[plot_bands],
            series=[],
            title={"text": title},
            level=alert.severity,
            begin_source_timestamp=plot_bands["from"],
        )
        if query_config["data_source_label"] == DataSourceLabel.PROMETHEUS:
            return query_result

        # 拼上产生告警的维度
        event_dimension_detail = origin_alarm["data"]["dimensions"]
        event_config_dimension = query_config["agg_dimension"]
        event_config_condition = query_config["agg_condition"]

        filter_dict = {}
        for filter_item in event_config_dimension:
            try:
                filter_dict.update({filter_item: event_dimension_detail[filter_item]})
            except KeyError:
                pass

        condition_filter_dict = {}
        for filter_item in event_config_condition:
            # 如果存在高级算法，则不加入查询条件
            if filter_item["method"] in AdvanceConditionMethod:
                condition_filter_dict = {}
                break
            if filter_item["key"] not in condition_filter_dict:
                condition_filter_dict["{}__{}".format(filter_item["key"], filter_item["method"])] = filter_item["value"]
        filter_dict.update(condition_filter_dict)

        unit = load_unit(query_config.get("unit", ""))

        extend_fields = query_config.get("extend_fields", {})
        if query_config.get("index_set_id", ""):
            extend_fields["index_set_id"] = query_config["index_set_id"]
            extend_fields["time_field"] = query_config.get("time_field", "")

        # 获取首次异常时间点
        graph_point_request_data = {
            "bk_biz_id": bk_biz_id,
            "monitor_field": query_config["metric_field"],
            "method": query_config["agg_method"],
            "result_table_id": query_config["result_table_id"],
            "filter_dict": filter_dict,
            "unit": unit.suffix,
            "conversion": query_config.get("unit_conversion", 1.0),
            "use_short_series_name": True,
            "interval": query_config["agg_interval"],
            "time_step": query_config["agg_interval"],
            "time_start": None,
            "time_end": None,
            "extend_fields": extend_fields,
            "data_source_label": query_config["data_source_label"],
            "data_type_label": query_config["data_type_label"],
        }
        now_time = int(time.time())
        start_timestamp = alert.begin_time
        if alert.status == EventStatus.RECOVERED:
            graph_end_time = alert.end_time + 60 * 60
            plot_bands["to"] = alert.end_time * 1000
            end_timestamp = graph_end_time if graph_end_time < now_time else now_time
        else:
            end_timestamp = now_time

        if time_range:
            start_timestamp, end_timestamp = parse_time_range(time_range)

        graph_point_request_data.update(dict([("time_start", start_timestamp), ("time_end", end_timestamp)]))
        result = resource.commons.graph_point(**graph_point_request_data)

        # 获取图表title
        metric_info = MetricListCache.objects.filter(
            bk_tenant_id=bk_biz_id_to_bk_tenant_id(bk_biz_id),
            bk_biz_id__in=[0, bk_biz_id],
            metric_field=title,
            data_source_label=query_config["data_source_label"],
            data_type_label=query_config["data_type_label"],
            result_table_id=query_config["result_table_id"],
        ).first()
        if metric_info:
            if metric_info.data_target == DataTarget.HOST_TARGET:
                dimension = origin_alarm.get("dimension_translation", {})
                ip_str = dimension.get("ip", {}).get("display_value", "") or dimension.get("bk_target_ip", {}).get(
                    "display_value", ""
                )
                title = _("主机【{}】").format(ip_str) if ip_str else ""
            elif metric_info.data_target == DataTarget.SERVICE_TARGET:
                service_str = (
                    origin_alarm.get("dimension_translation", {}).get("service_instance", {}).get("display_value", "")
                )
                title = _("服务【{}】").format(service_str) if service_str else ""

            title += (
                f"{metric_info.result_table_id}.{metric_info.metric_field}"
                if get_language() == "en"
                else metric_info.metric_field_name
            )

        # 取出首次异常点，保证首次异常点在图表中
        point_time_list = [point[0] for point in result["series"][0]["data"]]
        first_anomaly_in_time_range = (start_timestamp * 1000) <= plot_bands["from"] <= (end_timestamp * 1000)
        if plot_bands["from"] not in point_time_list and first_anomaly_in_time_range:
            point = [plot_bands["from"], origin_alarm["data"]["value"]]
            position = bisect.bisect(point_time_list, plot_bands["from"])
            result["series"][0]["data"].insert(position, point)

        result.update(
            threshold_line=threshold_line,
            plot_bands=[plot_bands],
            title={"text": title},
            level=alert.severity,
            begin_source_timestamp=plot_bands["from"],
        )
        return result


class IsHostExistsIndex(EventPermissionResource, HostIndexQueryMixin):
    class RequestSerializer(serializers.Serializer):
        bk_host_innerip = serializers.CharField(required=False, label="主机IP")
        bk_cloud_id = serializers.IntegerField(required=False, label="云区域ID")
        bk_host_id = serializers.CharField(required=False, label="主机ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        return bool(self.query_indexes(validated_request_data))


class ListIndexByHost(EventPermissionResource, HostIndexQueryMixin):
    class RequestSerializer(serializers.Serializer):
        bk_host_innerip = serializers.CharField(required=False, label="主机IP")
        bk_cloud_id = serializers.IntegerField(required=False, label="云区域ID")
        bk_host_id = serializers.CharField(required=False, label="主机ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        infos = self.query_indexes(validated_request_data)

        res = []

        for item in infos:
            res.append(
                {
                    "index_set_id": item["index_set_id"],
                    "index_set_name": item["index_set_name"],
                    "log_type": "bk_log",
                    "related_bk_biz_id": validated_request_data["bk_biz_id"],
                }
            )

        return res
