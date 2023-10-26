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


import functools
import json
import operator
import re

from django.db.models import Max, Q

from bkmonitor.models import Alert, AnomalyRecord, Event, StrategyModel, QueryConfigModel
from bkmonitor.utils.event_notify_status import NotifyStatusResult
from constants.strategy import TargetFieldType
from monitor_web.alert_events.constant import EventStatus
from monitor_web.commons.cc.utils import CmdbUtil


class EventFilterManager(object):
    def __init__(self, time_range, event_queryset=None):
        """
        Event:
        业务id
        时间范围
        事件状态

        Strategy:
        监控对象
        数据来源
        模糊匹配

        EventAction:
        通知状态

        alerts:
        模糊匹配

        alerts:
        接收人

        :param event_queryset:
        """
        if event_queryset is not None:
            self.queryset = event_queryset
        else:
            self.queryset = Event.objects.filter()

        self.time_range = time_range

        self.filters = [
            {
                "fields": ["bk_biz_id", "strategy_id", "ip", "event_status", "id", "level", "content"],
                "filter": EventFilter,
            },
            {"fields": [], "filter": AnomalyFilter},
            {"fields": ["scenario", "data_source", "service_category", "metric_id"], "filter": StrategyFilter},
            {"fields": ["receiver", "alert_collect_id"], "filter": AlertFilter},
            {"fields": ["alert_status"], "filter": EventActionFilter},
            {"fields": ["query"], "filter": QueryFilter},
        ]

    def filter(self, conditions):
        self.handle_conditions(conditions)
        for selector in self.filters:
            surplus_conditions = []
            requisite_conditions = []
            for condition in conditions:
                if "key" in condition and condition["key"] in selector["fields"]:
                    requisite_conditions.append(condition)
                else:
                    surplus_conditions.append(condition)

            conditions = surplus_conditions
            if requisite_conditions:
                self.queryset = selector["filter"](self.queryset, self).filter(requisite_conditions)

    @staticmethod
    def handle_conditions(conditions):
        for condition in conditions:
            if condition["key"] == "event_status":
                break
        else:
            conditions.append(
                {"value": [EventStatus.ABNORMAL, EventStatus.RECOVERED, EventStatus.CLOSED], "key": "event_status"}
            )


class BaseFilter(object):
    field_mapping = {}

    def __init__(self, queryset, manager):
        self.origin_queryset = queryset
        self.sub_queryset = queryset
        self.specified_filter = {}
        self.manager = manager

    @staticmethod
    def handle_kwargs(key, value):
        if isinstance(value, list):
            kwargs = {"{}__in".format(key): value}
        else:
            kwargs = {key: value}

        return kwargs

    def filter(self, conditions):
        kwargs = {}
        for condition in conditions:
            condition_key = condition["key"]
            if condition_key in self.specified_filter:
                filter_func = self.specified_filter[condition_key]
                filter_func(condition)
                continue

            field = self.field_mapping.get(condition_key, condition_key)
            kwargs.update(self.handle_kwargs(field, condition["value"]))

        if kwargs:
            self.simple_filter(kwargs)

        return self.result_queryset

    def simple_filter(self, kwargs):
        self.sub_queryset = self.sub_queryset.filter(**kwargs)

    @property
    def result_queryset(self):
        return self.sub_queryset


class EventFilter(BaseFilter):
    field_mapping = {}

    def __init__(self, queryset, manager):
        super(EventFilter, self).__init__(queryset, manager)
        self.specified_filter = {
            "event_status": self.event_status_filter,
            "ip": self.ip_filter,
            "content": self.content_filter,
            "id": self.id_filter,
        }

    def id_filter(self, kwargs):
        search_input = kwargs["value"]
        if not search_input:
            return
        ids = [value for value in search_input if value.isdigit()]
        self.sub_queryset = self.sub_queryset.filter(id__in=ids)

    def content_filter(self, kwargs):
        # 先将last_anomaly_id列表取到内存中，减少子查询的层级
        search_input = kwargs["value"]
        if not search_input:
            return

        if isinstance(search_input, list):
            search_input = search_input[0]

        search_str = json.dumps(search_input)[1:-1]
        self.sub_queryset = self.sub_queryset.filter(origin_alarm__icontains=search_str)

    def event_status_filter(self, kwargs):
        if EventStatus.ABNORMAL_ACK in kwargs["value"]:
            self.sub_queryset = self.sub_queryset.filter(
                Q(status__in=kwargs["value"]) | Q(status=EventStatus.ABNORMAL, is_ack=True)
            )
        else:
            self.sub_queryset = self.sub_queryset.filter(status__in=kwargs["value"])

    def ip_filter(self, kwargs):
        search_input = kwargs["value"]
        if not search_input:
            return

        host_keys = []
        for ip in search_input:
            if "|" not in ip:
                ip += "|"
            key = Event.TargetKeyGenerator.Host.get_key(*ip.split("|"))
            host_keys.append(key)

        query_filter = functools.reduce(operator.or_, (Q(target_key__icontains=_ip) for _ip in host_keys))
        self.sub_queryset = self.sub_queryset.filter(query_filter)


class StrategyFilter(BaseFilter):
    def __init__(self, queryset, manager):
        super(StrategyFilter, self).__init__(queryset, manager)
        self.sub_queryset = StrategyModel.objects.filter()
        self.specified_filter = {
            "data_source": self.data_source_filter,
            "service_category": self.service_category_filter,
            "metric_id": self.metric_id_filter,
        }

    def metric_id_filter(self, kwargs):
        metric_id = kwargs["value"]
        strategy_ids = tuple(
            QueryConfigModel.objects.filter(metric_id__in=metric_id).values_list("strategy_id", flat=True).distinct()
        )
        self.sub_queryset = self.sub_queryset.filter(id__in=strategy_ids)

    def data_source_filter(self, kwargs):
        data_source = kwargs["value"]
        if isinstance(data_source, list):
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

            strategy_ids = (
                QueryConfigModel.objects.filter(data_source_where).values_list("strategy_id", flat=True).distinct()
            )
            self.sub_queryset = self.sub_queryset.filter(id__in=strategy_ids)

    def service_category_filter(self, kwargs):
        bk_biz_ids = kwargs["bk_biz_ids"]
        service_categories = kwargs["value"]
        node_manager = CmdbUtil(bk_biz_ids)

        def get_node_type(config):
            if len(config[0]) == 0:
                return None

            front_config = config[0][0]
            node_type_map = {
                TargetFieldType.host_target_ip: "INSTANCE",
                TargetFieldType.host_ip: "INSTANCE",
                TargetFieldType.host_topo: "TOPO",
                TargetFieldType.service_topo: "TOPO",
            }
            return node_type_map[front_config.get("field")]

        category_ids = set()
        # 根据服务分类名称，找到服务分类id
        for category in service_categories:
            match_obj = re.match(r"^(\S+?)-(\S+)$", category)
            if not match_obj:
                continue

            for bk_biz_id in bk_biz_ids:
                service_category_id = node_manager.get_category_id(bk_biz_id, match_obj.groups())
                if service_category_id:
                    category_ids.add(service_category_id)
                    break

        # 搜索符合条件的策略。找到策略关联的服务分类列表，看查询的服务分类是否在该列表里
        strategy_ids = []
        strategy_list = [item for item in self.sub_queryset if get_node_type(item.target) == "TOPO"]
        for strategy in strategy_list:
            service_category_ids = node_manager.get_category_list(
                strategy.bk_biz_id, strategy.target[0][0].get("value", [])
            )
            if category_ids & set(service_category_ids):
                strategy_ids.append(strategy.id)

        self.sub_queryset = self.sub_queryset.filter(id__in=strategy_ids)

    @property
    def result_queryset(self):
        return self.origin_queryset.filter(strategy_id__in=tuple(self.sub_queryset.values_list("id", flat=True)))


class AlertFilter(BaseFilter):
    field_mapping = {
        "receiver": "username",
    }

    def __init__(self, queryset, manager):
        super(AlertFilter, self).__init__(queryset, manager)
        self.sub_queryset = Alert.objects.filter()

    @property
    def result_queryset(self):
        return self.origin_queryset.filter(event_id__in=self.sub_queryset.values_list("event_id", flat=True).distinct())


class EventActionFilter(BaseFilter):
    def __init__(self, queryset, manager):
        super(EventActionFilter, self).__init__(queryset, manager)
        self.specified_filter = {"alert_status": self.alert_status_filter}

    def alert_status_filter(self, kwargs):
        alert_status_value = NotifyStatusResult.get_query_conditions(kwargs["value"])
        self.sub_queryset = self.sub_queryset.filter(notify_status__in=alert_status_value)


class AnomalyFilter(BaseFilter):
    def __init__(self, queryset, manager):
        super(AnomalyFilter, self).__init__(queryset, manager)
        self.sub_queryset = AnomalyRecord.objects.filter()
        self.specified_filter = {"content": self.content_filter}

    @property
    def result_queryset(self):
        return self.origin_queryset.filter(event_id__in=self.sub_queryset.values_list("event_id", flat=True).distinct())

    def content_filter(self, kwargs):
        # 先将last_anomaly_id列表取到内存中，减少子查询的层级
        search_input = kwargs["value"]
        if not search_input:
            return

        event_ids = self.origin_queryset.values_list("event_id", flat=True)
        last_anomaly_ids = tuple(
            AnomalyRecord.objects.filter(event_id__in=event_ids)
            .values("event_id")
            .annotate(Max("id"))
            .values_list("id__max", flat=True)
        )
        if isinstance(search_input, list):
            search_input = search_input[0]

        search_str = json.dumps(search_input)[1:-1]
        self.sub_queryset = self.sub_queryset.filter(id__in=last_anomaly_ids, origin_alarm__icontains=search_str)


class QueryFilter(BaseFilter):
    def __init__(self, queryset, manager):
        super(QueryFilter, self).__init__(queryset, manager)
        self.specified_filter = {"query": self.query_filter}
        self.sub_queryset = {}

    def query_filter(self, kwargs):
        value = kwargs["value"]
        # 查询内容
        condition = {"key": "content", "value": value}
        event_filter = EventFilter(self.origin_queryset, self.manager)
        event_filter.content_filter(condition)
        event_queryset = event_filter.sub_queryset.values_list("event_id", flat=True).distinct()

        # 如果关键字是数字，则尝试过滤汇总ID
        alert_filter = AlertFilter(self.origin_queryset, self.manager)
        try:
            alert_queryset = (
                alert_filter.filter([{"key": "alert_collect_id", "value": int(value)}])
                .values_list("event_id", flat=True)
                .distinct()
            )
        except (ValueError, TypeError):
            alert_queryset = []

        # 按事件ID过滤
        event_ids = set(event_queryset) | set(alert_queryset)

        # 如果关键字是数字，则尝试过滤事件ID
        try:
            event = Event.objects.get(id=int(value))
            event_ids.add(event.event_id)
        except (ValueError, TypeError, Event.DoesNotExist):
            pass

        # 查询策略名
        strategy_queryset = tuple(StrategyModel.objects.filter(name__icontains=value).values_list("id", flat=True))

        self.sub_queryset = Q(event_id__in=event_ids) | Q(strategy_id__in=strategy_queryset)

    @property
    def result_queryset(self):
        return self.origin_queryset.filter(self.sub_queryset)
