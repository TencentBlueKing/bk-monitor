# -*- coding: utf-8 -*-
from functools import cmp_to_key

import arrow
from django.conf import settings
from elasticsearch_dsl import Q
from monitor.models import GlobalConfig, UserConfig
from rest_framework import serializers

from bkm_space.api import SpaceApi
from bkmonitor.documents import ActionInstanceDocument, AlertDocument, EventDocument
from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.request import get_request_username
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from constants.action import ActionDisplayStatus, ActionPluginType
from constants.alert import EventSeverity, EventStatus
from core.drf_resource import CacheResource, Resource, api, resource

FAVORITE_CONFIG_KEY = "fta_overview:favorite_biz"


class AllBizStatisticsResource(CacheResource):
    cache_type = CacheType.HOME

    class RequestSerializer(serializers.Serializer):
        days = serializers.IntegerField(default=7, label="查询天数", min_value=1, max_value=31)

    def search_event_data(self, start_time, end_time):
        self.event_data = {}

        search = EventDocument.search(all_indices=True).filter("range", time={"gte": start_time, "lte": end_time})

        search.aggs.bucket("bk_biz_id", "terms", field="bk_biz_id", size=10000)

        result = search.params(track_total_hits=True)[:0].execute()

        if result.aggs:
            for bucket in result.aggs.bk_biz_id.buckets:
                self.event_data[str(bucket.key)] = bucket.doc_count

        return self.event_data

    def search_alert_data(self, start_time, end_time):
        self.alert_data = {}

        search = AlertDocument.search(start_time=start_time, end_time=end_time).filter(
            (Q("range", end_time={"gte": start_time}) | ~Q("exists", field="end_time"))
            & Q("range", begin_time={"lte": end_time})
        )

        # 业务统计
        biz_aggs = search.aggs.bucket("bk_biz_id", "terms", field="event.bk_biz_id", size=10000)

        biz_aggs.bucket("has_strategy", "filter", {"exists": {"field": "strategy_id"}}).bucket(
            "fatal",
            "filter",
            {"term": {"severity": EventSeverity.FATAL}},
        )

        biz_aggs.bucket("abnormal", "filter", {"term": {"status": EventStatus.ABNORMAL}}).bucket(
            "severity", "terms", field="severity"
        )

        recover_aggs = biz_aggs.bucket(
            "recover", "filter", {"terms": {"status": [EventStatus.RECOVERED, EventStatus.CLOSED]}}
        ).bucket("duration", "filter", {"range": {"ack_duration": {"gte": 60}}})

        # 大于60s才会统计
        recover_aggs.bucket("ack_duration", "sum", field="ack_duration")

        recover_aggs.bucket("recover_create_time", "sum", field="create_time")
        recover_aggs.bucket("recover_end_time", "sum", field="end_time")

        result = search.params(track_total_hits=True)[:0].execute()

        if result.aggs:
            # 告警各级别数量统计
            for biz_bucket in result.aggs.bk_biz_id.buckets:
                alert_count = {
                    "1": 0,
                    "2": 0,
                    "3": 0,
                }
                for severity_bucket in biz_bucket.abnormal.severity.buckets:
                    if str(severity_bucket.key) in alert_count:
                        alert_count[str(severity_bucket.key)] = severity_bucket.doc_count

                doc_count = biz_bucket.recover.duration.doc_count
                alert_data = {
                    "count": biz_bucket.doc_count,
                    "strategy_alert_count": biz_bucket.has_strategy.doc_count,
                    "fatal_alert_count": biz_bucket.has_strategy.fatal.doc_count,
                    "levels": [
                        {
                            "level": int(level),
                            "count": count,
                        }
                        for level, count in alert_count.items()
                        if count
                    ],
                    "sum_ack_duration": biz_bucket.recover.duration.ack_duration.value,
                    "count_ack_duration": doc_count,
                    "sum_recover_duration": (
                        biz_bucket.recover.duration.recover_end_time.value
                        - biz_bucket.recover.duration.recover_create_time.value
                    )
                    // 1000
                    if biz_bucket.recover.duration.recover_create_time.value
                    else 0,
                    "count_recover_duration": doc_count,
                }

                # MTTA 不能大于 MTTR
                alert_data["sum_ack_duration"] = min(alert_data["sum_ack_duration"], alert_data["sum_recover_duration"])

                self.alert_data[str(biz_bucket.key)] = alert_data

        return self.alert_data

    def search_action_data(self, start_time, end_time):
        self.action_data = {}

        search = (
            ActionInstanceDocument.search(start_time=start_time, end_time=end_time)
            .filter(
                (Q("range", end_time={"gte": start_time}) | ~Q("exists", field="end_time"))
                & Q("range", create_time={"lte": end_time})
            )
            .exclude("term", is_parent_action=True)
            .filter(
                "terms", status=[ActionDisplayStatus.SUCCESS, ActionDisplayStatus.FAILURE, ActionDisplayStatus.RUNNING]
            )
        )

        # 业务统计
        fatal_alert_aggs = search.aggs.bucket("bk_biz_id", "terms", field="bk_biz_id", size=10000).bucket(
            "fatal",
            "filter",
            Q("term", alert_level=EventSeverity.FATAL),
        )
        fatal_alert_aggs.bucket(
            "action_plugin_type",
            "filter",
            ~Q(
                "terms",
                action_plugin_type=[
                    ActionPluginType.NOTICE,
                    ActionPluginType.WEBHOOK,
                    ActionPluginType.ITSM,
                    ActionPluginType.MESSAGE_QUEUE,
                    ActionPluginType.AUTHORIZE,
                    ActionPluginType.COMMON,
                    ActionPluginType.COLLECT,
                ],
            ),
        ).bucket("alert", "cardinality", field="alert_id")

        result = search.params(track_total_hits=True)[:0].execute()

        if result.aggs:
            for bucket in result.aggs.bk_biz_id.buckets:
                self.action_data[str(bucket.key)] = {
                    "count": bucket.doc_count,
                    "auto_recovery_count": bucket.fatal.action_plugin_type.alert.value,
                }

        return self.action_data

    def perform_request(self, validated_request_data):
        days = validated_request_data["days"]
        end_time = arrow.now().timestamp
        start_time = end_time - days * 24 * 60 * 60

        th_list = [
            InheritParentThread(target=func, args=(start_time, end_time))
            for func in [self.search_event_data, self.search_alert_data, self.search_action_data]
        ]
        run_threads(th_list)
        return {
            "update_time": end_time,
            "event": self.event_data,
            "alert": self.alert_data,
            "action": self.action_data,
        }


class StatisticsResource(Resource):
    """
    统计数据
    """

    class RequestSerializer(serializers.Serializer):
        search = serializers.CharField(required=False, label="搜索关键字")
        days = serializers.IntegerField(default=7, label="查询天数", min_value=1, max_value=31)
        page = serializers.IntegerField(default=1, label="页数")
        page_size = serializers.IntegerField(default=10, label="每页数量")
        favorite_only = serializers.BooleanField(default=False, label="仅显示收藏")
        sticky_only = serializers.BooleanField(default=False, label="仅显示置顶")
        allowed_only = serializers.BooleanField(default=True, label="仅显示有权限")
        alert_filter = serializers.ChoiceField(required=False, label="告警过滤", choices=["has_alert", "no_alert"])
        life_cycle = serializers.ChoiceField(required=False, label="生命周期", choices=[1, 2])
        bk_biz_id = serializers.IntegerField(required=False, label="当前业务")

    @classmethod
    def alert_sort_func(cls, all_data):
        def sort_func(x, y):
            x = {
                level["level"]: level["count"]
                for level in all_data["alert"].get(
                    str(x.bk_biz_id),
                    {"levels": []},
                )["levels"]
            }
            y = {
                level["level"]: level["count"]
                for level in all_data["alert"].get(
                    str(y.bk_biz_id),
                    {"levels": []},
                )["levels"]
            }

            for i in range(1, 4):
                if x.get(i, 0) > y.get(i, 0):
                    return -1
                if x.get(i, 0) < y.get(i, 0):
                    return 1
            return 0

        return sort_func

    def perform_request(self, validated_request_data):
        username = get_request_username()

        biz_list = api.cmdb.get_business(all=True)
        filtered_biz_list = biz_list
        permission = Permission(username)
        allowed_bizs = permission.filter_business_list_by_action(
            action=ActionEnum.VIEW_BUSINESS, business_list=filtered_biz_list
        )
        allowed_biz_ids = {biz.bk_biz_id for biz in allowed_bizs}

        user_config = UserConfig.objects.filter(username=username, key=FAVORITE_CONFIG_KEY).first()

        if user_config:
            biz_ids = set(user_config.value)
        else:
            biz_ids = set()

        filtered_biz_list = self._filter_by_favorite_only(validated_request_data, filtered_biz_list, biz_ids)
        filtered_biz_list = self._filter_by_allowed_only(validated_request_data, filtered_biz_list, allowed_biz_ids)

        search = validated_request_data.get("search")
        if search:
            # 按关键字过滤
            filtered_biz_list = [
                business
                for business in filtered_biz_list
                if search == str(business.bk_biz_id) or search.lower() in business.bk_biz_name.lower()
            ]

        # 获取全局配置置顶列表
        try:
            sticky_biz_ids = GlobalConfig.objects.get(key="biz_sticky").value
        except GlobalConfig.DoesNotExist:
            sticky_biz_ids = []

        filtered_biz_list = self._filter_by_sticky_only(validated_request_data, filtered_biz_list, sticky_biz_ids)
        filtered_biz_list = self._filter_by_life_cycle(validated_request_data, filtered_biz_list)

        # 过滤有无告警配置
        all_data = resource.home.all_biz_statistics(days=validated_request_data["days"])
        filtered_biz_list = self._filter_by_alert_filter(validated_request_data, filtered_biz_list, all_data)

        # 把demo业务排在后面
        filtered_biz_list.sort(key=lambda b: b.bk_biz_id == int(settings.DEMO_BIZ_ID))

        # 将有权限的业务排在前面
        filtered_biz_list.sort(key=lambda b: b.bk_biz_id in allowed_biz_ids, reverse=True)

        # 调整置顶业务位置
        flag = 0
        for index, business in enumerate(filtered_biz_list):
            if business.bk_biz_id in sticky_biz_ids:
                filtered_biz_list.insert(flag, filtered_biz_list.pop(index))
                flag += 1

        if validated_request_data.get("bk_biz_id"):
            # 固定将当前业务置顶
            filtered_biz_list.sort(key=lambda b: b.bk_biz_id == validated_request_data["bk_biz_id"], reverse=True)

        page = validated_request_data["page"]
        page_size = validated_request_data["page_size"]
        if page != 0:
            filtered_biz_list = filtered_biz_list[(page - 1) * page_size : page * page_size]

        filtered_biz_ids = {business.bk_biz_id for business in filtered_biz_list}

        overview_data = {
            "biz_count": 0,
            "event_count": 0,
            "alert_count": 0,
            "strategy_alert_count": 0,
            "action_count": 0,
            "fatal_alert_count": 0,
            "auto_recovery_count": 0,
            "sum_ack_duration": 0,
            "count_ack_duration": 0,
            "sum_recover_duration": 0,
            "count_recover_duration": 0,
        }

        detail_map = self._get_detail_map(
            biz_list, all_data, allowed_biz_ids, overview_data, filtered_biz_ids, biz_ids, sticky_biz_ids
        )

        result = {
            "update_time": all_data["update_time"],
            "overview": {
                "business": {
                    "count": overview_data["biz_count"],
                },
                "event": {
                    "count": overview_data["event_count"],
                },
                "alert": {
                    "count": overview_data["alert_count"],
                },
                "action": {
                    "count": overview_data["action_count"],
                },
                "noise_reduction_ratio": (
                    (1 - overview_data["alert_count"] / overview_data["event_count"])
                    if overview_data["event_count"]
                    else None
                ),
                "auto_recovery_ratio": (
                    min(1, overview_data["auto_recovery_count"] / overview_data["fatal_alert_count"])
                    if overview_data["fatal_alert_count"]
                    else None
                ),
                "mtta": (
                    overview_data["sum_ack_duration"] / overview_data["count_ack_duration"]
                    if overview_data["count_ack_duration"]
                    else None
                ),
                "mttr": (
                    overview_data["sum_recover_duration"] / overview_data["count_recover_duration"]
                    if overview_data["count_recover_duration"]
                    else None
                ),
            },
            "details": [detail_map.get(business.bk_biz_id) for business in filtered_biz_list],
        }

        return result

    def _filter_by_allowed_only(
        self, validated_request_data: dict, filtered_biz_list: list, allowed_biz_ids: set
    ) -> list:
        if validated_request_data["allowed_only"]:
            # 过滤无权限业务
            # 有一种例外，当前业务，无论有无权限都要被过滤出来
            filtered_biz_list = [
                business
                for business in filtered_biz_list
                if (
                    business.bk_biz_id in allowed_biz_ids
                    or business.bk_biz_id == validated_request_data.get("bk_biz_id")
                )
            ]

        return filtered_biz_list

    def _filter_by_favorite_only(self, validated_request_data: dict, filtered_biz_list: list, biz_ids: set) -> list:
        if validated_request_data["favorite_only"]:
            # 过滤收藏配置
            filtered_biz_list = [business for business in filtered_biz_list if business.bk_biz_id in biz_ids]

        return filtered_biz_list

    def _filter_by_sticky_only(
        self, validated_request_data: dict, filtered_biz_list: list, sticky_biz_ids: list
    ) -> list:
        if validated_request_data["sticky_only"]:
            # 过滤置顶配置
            filtered_biz_list = [business for business in filtered_biz_list if business.bk_biz_id in sticky_biz_ids]

        return filtered_biz_list

    def _filter_by_life_cycle(self, validated_request_data: dict, filtered_biz_list: list) -> list:
        if validated_request_data.get("life_cycle"):
            # 过滤cmdb生命周期属性
            filtered_biz_list = [
                business
                for business in filtered_biz_list
                if business.life_cycle == str(validated_request_data["life_cycle"])
            ]
        return filtered_biz_list

    def _filter_by_alert_filter(self, validated_request_data: dict, filtered_biz_list: list, all_data: dict) -> list:
        if validated_request_data.get("alert_filter"):
            if validated_request_data["alert_filter"] == "has_alert":
                filtered_biz_list = [
                    business
                    for business in filtered_biz_list
                    if len(
                        all_data["alert"].get(
                            str(business.bk_biz_id),
                            {"levels": []},
                        )["levels"]
                    )
                    != 0
                ]
                # 告警按照等级、数量进行排序
                alert_sort_func = self.alert_sort_func(all_data)
                filtered_biz_list.sort(key=cmp_to_key(alert_sort_func))
            else:
                filtered_biz_list = [
                    business
                    for business in filtered_biz_list
                    if len(
                        all_data["alert"].get(
                            str(business.bk_biz_id),
                            {"levels": []},
                        )["levels"]
                    )
                    == 0
                ]
        return filtered_biz_list

    @staticmethod
    def _get_detail_map(
        biz_list: list,
        all_data: dict,
        allowed_biz_ids: set,
        overview_data: dict,
        filtered_biz_ids: set,
        biz_ids: set,
        sticky_biz_ids: list,
    ) -> dict:
        detail_map = {}
        for business in biz_list:
            bk_biz_id = str(business.bk_biz_id)

            biz_event_data = all_data["event"].get(bk_biz_id, 0)
            biz_alert_data = all_data["alert"].get(
                bk_biz_id,
                {
                    "count": 0,
                    "strategy_alert_count": 0,
                    "fatal_alert_count": 0,
                    "levels": [],
                    "sum_ack_duration": 0,
                    "count_ack_duration": 0,
                    "sum_recover_duration": 0,
                    "count_recover_duration": 0,
                },
            )
            biz_action_data = all_data["action"].get(
                bk_biz_id,
                {
                    "count": 0,
                    "auto_recovery_count": 0,
                },
            )

            if business.bk_biz_id in allowed_biz_ids and business.bk_biz_id != int(settings.DEMO_BIZ_ID):
                # 累加总览信息，只统计有权限的业务，且不是demo的业务
                overview_data["biz_count"] += 1
                overview_data["event_count"] += biz_event_data
                overview_data["alert_count"] += biz_alert_data["count"]
                overview_data["strategy_alert_count"] += biz_alert_data["strategy_alert_count"]
                overview_data["action_count"] += biz_action_data["count"]
                overview_data["fatal_alert_count"] += biz_alert_data["fatal_alert_count"]
                overview_data["auto_recovery_count"] += biz_action_data["auto_recovery_count"]
                overview_data["sum_ack_duration"] += biz_alert_data["sum_ack_duration"]
                overview_data["count_ack_duration"] += biz_alert_data["count_ack_duration"]
                overview_data["sum_recover_duration"] += biz_alert_data["sum_recover_duration"]
                overview_data["count_recover_duration"] += biz_alert_data["count_recover_duration"]

            if business.bk_biz_id not in filtered_biz_ids:
                continue

            # 展示过滤业务
            biz_data = {
                "bk_biz_id": business.bk_biz_id,
                "bk_biz_name": business.bk_biz_name,
                "is_favorite": business.bk_biz_id in biz_ids,
                "is_demo": business.bk_biz_id == int(settings.DEMO_BIZ_ID),
                "is_sticky": business.bk_biz_id in sticky_biz_ids,
                "is_allowed": business.bk_biz_id in allowed_biz_ids,
            }

            if business.bk_biz_id in allowed_biz_ids:
                biz_data.update(
                    {
                        "event": {
                            "count": biz_event_data,
                        },
                        "alert": {
                            "count": biz_alert_data["count"],
                            "strategy_alert_count": biz_alert_data["strategy_alert_count"],
                            "levels": biz_alert_data["levels"],
                        },
                        "action": {
                            "count": biz_action_data["count"],
                        },
                        "noise_reduction_ratio": (
                            (1 - min(biz_alert_data["count"] / biz_event_data, 1)) if biz_event_data else None
                        ),
                        "auto_recovery_ratio": (
                            min(1, biz_action_data["auto_recovery_count"] / biz_alert_data["fatal_alert_count"])
                            if biz_alert_data.get("fatal_alert_count")
                            else None
                        ),
                        "mtta": (
                            biz_alert_data["sum_ack_duration"] / biz_alert_data["count_ack_duration"]
                            if biz_alert_data["count_ack_duration"]
                            else None
                        ),
                        "mttr": (
                            biz_alert_data["sum_recover_duration"] / biz_alert_data["count_recover_duration"]
                            if biz_alert_data["count_recover_duration"]
                            else None
                        ),
                        "space_info": SpaceApi.get_space_detail(bk_biz_id=business.bk_biz_id).to_dict(),
                    }
                )

            detail_map[business.bk_biz_id] = biz_data

        return detail_map


class FavoriteResource(Resource):
    """
    业务收藏
    """

    class RequestSerializer(serializers.Serializer):
        op_type = serializers.ChoiceField(default="add", choices=["add", "remove"], label="操作类型")
        bk_biz_ids = serializers.ListField(child=serializers.IntegerField(), label="业务ID列表", allow_empty=False)

    def perform_request(self, validated_request_data):
        # 获取用户配置
        username = get_request_username()
        user_config = UserConfig.objects.filter(username=username, key=FAVORITE_CONFIG_KEY).first()

        if user_config:
            biz_ids = user_config.value
        else:
            biz_ids = []

        biz_ids = set(biz_ids)
        new_biz_ids = set(validated_request_data["bk_biz_ids"])

        # 与当前收藏的业务ID做运算
        if validated_request_data["op_type"] == "remove":
            biz_ids = biz_ids - new_biz_ids
        else:
            biz_ids = biz_ids | new_biz_ids

        biz_ids = list(biz_ids)

        # 保存配置
        UserConfig.objects.update_or_create(username=username, key=FAVORITE_CONFIG_KEY, defaults={"value": biz_ids})
        return {"bk_biz_ids": biz_ids}


class StickyResource(Resource):
    """
    业务置顶
    """

    class RequestSerializer(serializers.Serializer):
        op_type = serializers.ChoiceField(default="add", choices=["add", "remove"], label="操作类型")
        bk_biz_ids = serializers.ListField(child=serializers.IntegerField(), label="业务ID列表", allow_empty=False)

    def perform_request(self, validated_request_data):
        # 取消置顶
        sticky_config, result = GlobalConfig.objects.get_or_create(key="biz_sticky")
        if result:
            sticky_config.value = []
        if validated_request_data["op_type"] == "add":
            sticky_config.value.extend(validated_request_data["bk_biz_ids"])
        else:
            sticky_config.value = [
                biz_id for biz_id in sticky_config.value if biz_id not in validated_request_data["bk_biz_ids"]
            ]
        sticky_config.save()
        return {"bk_biz_ids": validated_request_data["bk_biz_ids"]}


class BizWithAlertStatisticsResource(Resource):
    """
    统计一段周期内有数据的业务信息
    """

    class RequestSerializer(serializers.Serializer):
        days = serializers.IntegerField(default=31, label="查询天数", min_value=1, max_value=31)

    @staticmethod
    def get_all_business_list():
        business_list = {
            biz.bk_biz_id: {"bk_biz_id": biz.bk_biz_id, "bk_biz_name": biz.bk_biz_name}
            for biz in api.cmdb.get_business(all=True)
        }
        all_bk_biz_ids = list(business_list.keys())
        authorized_business_list = Permission().filter_biz_ids_by_action(
            action=ActionEnum.VIEW_EVENT, bk_biz_ids=all_bk_biz_ids
        )
        business_with_permission = [business_list[bk_biz_id] for bk_biz_id in authorized_business_list]
        unauthorized_biz_ids = set(all_bk_biz_ids) - set(authorized_business_list)
        business_data = {
            "business_with_permission": business_with_permission,
            "business_list": business_list,
            "unauthorized_biz_ids": unauthorized_biz_ids,
        }
        return business_data

    def perform_request(self, validated_request_data):
        business_info = self.get_all_business_list()
        unauthorized_biz_ids = business_info["unauthorized_biz_ids"]
        business_list = business_info["business_list"]
        response_data = {
            "business_with_alert": [],
            "business_with_permission": business_info["business_with_permission"],
            "business_list": list(business_list.values()),
        }
        request_username = get_request_username()
        if unauthorized_biz_ids:
            if validated_request_data.get("days"):
                end_time = arrow.now().timestamp
                start_time = end_time - validated_request_data["days"] * 24 * 60 * 60
                search_object = AlertDocument.search(start_time=start_time, end_time=end_time)
            else:
                search_object = AlertDocument.search(all_indices=True)
            search_object = search_object.filter(
                Q("term", assignee=request_username) | Q("term", appointee=request_username)
            )
            search_object = search_object.filter("terms", **{"event.bk_biz_id": list(unauthorized_biz_ids)})
            search_object.aggs.bucket("biz_overview", "terms", field="event.bk_biz_id", size=10000)
            search_result = search_object.execute()
            business_with_alert = [
                business_list[int(bucket["key"])] for bucket in search_result.aggs.biz_overview.buckets
            ]
            response_data.update({"business_with_alert": business_with_alert})
        return response_data
