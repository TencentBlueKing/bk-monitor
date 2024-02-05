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

import datetime
from typing import Any, Dict, List, Union

from django.utils import timezone
from elasticsearch_dsl import Q

from bkmonitor.documents import AlertDocument
from bkmonitor.models import ItemModel, StrategyModel
from bkmonitor.models.base import Action, NoticeGroup
from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.time_tools import get_datetime_range, localtime
from bkmonitor.views import serializers
from bkmonitor.views.serializers import BusinessOnlySerializer
from constants.alert import EventStatus
from core.drf_resource.contrib.cache import CacheResource
from monitor_web.overview.tools import (
    MonitorStatus,
    OsMonitorInfo,
    ProcessMonitorInfo,
    ServiceMonitorInfo,
    UptimeCheckMonitorInfo,
)


class AlarmRankResource(CacheResource):
    """
    告警类型排行
    """

    cache_type = CacheType.OVERVIEW

    class RequestSerializer(BusinessOnlySerializer):
        days = serializers.IntegerField(default=7, label="统计天数")

    def get_alarm_item(self, begin_time, end_time, bk_biz_id):
        # 记录当前告警项
        start_ts = int(begin_time.timestamp())
        end_ts = int(end_time.timestamp())

        search = (
            AlertDocument.search(start_time=start_ts, end_time=end_ts)
            .filter(
                (Q("range", end_time={"gte": start_ts}) & Q("range", begin_time={"lte": end_ts}))
                | ~Q("exists", field="end_time")
            )
            .filter("term", **{"event.bk_biz_id": bk_biz_id})[:0]
        )
        search.aggs.bucket("alert_name", "terms", field="alert_name.raw")
        search_result = search.execute()

        if not search_result.aggs:
            return {}

        ret = {bucket.key: bucket.doc_count for bucket in search_result.aggs.alert_name.buckets}
        # ->{name:total,...}
        return ret

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        days = validated_request_data["days"]

        # 判断是否有数据
        days_list = [1, 7, 30]
        for day in days_list:
            if days < day:
                days = day
            begin_time, end_time = get_datetime_range(
                "day",
                days,
                rounding=False,
            )
            this_monitor_item_set = self.get_alarm_item(begin_time, end_time, bk_biz_id)
            if this_monitor_item_set:
                break
        else:
            return {"data": [], "using_example_data": True, "days": days}
        # 记录上次告警项,现在的时间减去days周期的时间
        last_begin_time, last_end_time = get_datetime_range(
            "day", days, rounding=False, now=localtime(timezone.now()) - datetime.timedelta(days=days)
        )
        last_monitor_item_set = self.get_alarm_item(last_begin_time, last_end_time, bk_biz_id)

        default_list = []
        for k, v in list(this_monitor_item_set.items()):
            last_default_count = last_monitor_item_set.get(k, 0)
            # 上次有记录,判断增加还是减少
            if not last_default_count:
                if v > last_default_count:
                    status = 2
                elif k < last_default_count:
                    status = 0
                else:
                    status = 1
            # 上次没有记录,所以肯定是增加
            else:
                status = 2
            default_list.append({"status": status, "text": k, "times": v})
        data = sorted(default_list, key=lambda x: -x["times"])

        return {"data": data, "using_example_data": False, "days": days}


class AlarmCountInfoResource(CacheResource):
    """
    告警数量信息
    """

    RequestSerializer = BusinessOnlySerializer

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]

        search = (
            AlertDocument.search(all_indices=True)
            .filter("term", status=EventStatus.ABNORMAL)
            .filter("term", **{"event.bk_biz_id": bk_biz_id})[:0]
        )
        search.aggs.bucket("severity", "terms", field="severity")
        result = search.execute()

        level_dict = {1: 0, 2: 0, 3: 0}
        total = result.hits.total.value
        if result.aggs:
            for bucket in result.aggs.severity.buckets:
                level_dict[bucket.key] = bucket.doc_count

        result = {
            "levels": [{"level": level, "count": count} for level, count in list(level_dict.items())],
            "unrecovered_count": total,
        }
        return result


class MonitorInfoResource(CacheResource):
    """
    业务监控状态总览
    """

    cache_type = CacheType.OVERVIEW

    class RequestSerializer(BusinessOnlySerializer):
        days = serializers.IntegerField(default=30, label="统计天数")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        begin_time, end_time = get_datetime_range(
            "day",
            validated_request_data["days"],
            rounding=False,
        )
        start_ts = int(begin_time.timestamp())
        end_ts = int(end_time.timestamp())

        modules = {
            "uptimecheck": UptimeCheckMonitorInfo,
            "service": ServiceMonitorInfo,
            "process": ProcessMonitorInfo,
            "os": OsMonitorInfo,
        }

        # 拉取未恢复的事件
        module_alert = {}

        search = (
            AlertDocument.search(start_time=start_ts, end_time=end_ts)
            .filter("term", status=EventStatus.ABNORMAL)
            .filter("term", **{"event.bk_biz_id": bk_biz_id})
            .filter("exists", field="strategy_id")
        )

        abnormal_alerts = [hit.to_dict() for hit in search.scan()]

        for alert in abnormal_alerts:
            # 判断当条数据属于哪个模块
            for key, module in list(modules.items()):
                if module.check_alert(alert):
                    module_key = key
                    module_alert.setdefault(module_key, []).append(alert)
                    break

        # 获取每个模块的监控信息
        result_data = {}
        for key, module in list(modules.items()):
            alerts = module_alert.get(key, [])
            info = module(bk_biz_id, alerts).get_info()
            info.update(name=key)
            result_data[key] = info

        # 如果所有模块均正常，返回综合描述
        if all([item["status"] == MonitorStatus.NORMAL for item in list(result_data.values())]):
            id__strategy_map: Dict[int, Any] = {}
            disabled_strategies: List[Dict[str, Union[str, int]]] = []
            no_target_strategies: List[Dict[str, Union[str, int]]] = []
            time_warning_strategies: List[Dict[str, Union[str, int]]] = []
            notice_warning_strategies: List[Dict[str, Union[str, int]]] = []
            for strategy in StrategyModel.objects.filter(bk_biz_id=bk_biz_id).values("id", "name", "is_enabled"):
                id__strategy_map[strategy["id"]] = strategy
                # 检查策略是否禁用
                if not strategy["is_enabled"]:
                    disabled_strategies.append({"strategy_id": strategy["id"], "strategy_name": strategy["name"]})

            # 检查无监控目标策略
            items: List[Dict[str, Any]] = ItemModel.objects.filter(
                strategy_id__in=list(id__strategy_map.keys())
            ).values("strategy_id", "target")
            for item in items:
                if (item["target"] and item["target"][0]) or item["strategy_id"] not in id__strategy_map:
                    continue
                no_target_strategies.append(
                    {"strategy_id": item["strategy_id"], "strategy_name": id__strategy_map[item["strategy_id"]]["name"]}
                )

            # TODO: 这里需要根据新版自愈进行调整
            # 检查通知时间
            action_list: List[Dict[str, Any]] = Action.objects.filter(
                strategy_id__in=list(id__strategy_map.keys())
            ).values("strategy_id", "config")
            for action in action_list:
                action_config = action["config"]
                if action_config.get("alarm_start_time", "") == action_config.get("alarm_end_time", ""):
                    strategy_id = action["strategy_id"]
                    time_warning_strategies.append(
                        {"strategy_id": action["strategy_id"], "strategy_name": id__strategy_map[strategy_id]["name"]}
                    )

            # 检查通知方式
            notice_groups: List[Dict[str, Any]] = NoticeGroup.objects.filter(bk_biz_id=bk_biz_id).values(
                "id", "name", "notice_way"
            )
            for group in notice_groups:
                # 导入可能导致通知方式为空的情况出现
                if group["notice_way"]:
                    serious_notice = set(group["notice_way"]["1"])
                    if not ({"sms", "voice"} & serious_notice):
                        notice_warning_strategies.append({"group_id": group["id"], "group_name": group["name"]})

            result_data.update(
                summary={
                    "time_warning_strategies": time_warning_strategies,
                    "notice_warning_strategies": notice_warning_strategies,
                    "disabled_strategies": disabled_strategies,
                    "no_target_strategies": no_target_strategies,
                }
            )

        return result_data
