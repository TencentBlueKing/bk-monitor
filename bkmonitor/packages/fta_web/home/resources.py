# -*- coding: utf-8 -*-
import logging
from functools import cmp_to_key
from typing import Any, Dict, List, Optional, Set, Union

import arrow
from django.conf import settings
from elasticsearch_dsl import Q
from rest_framework import serializers

from api.cmdb.define import Business
from bkm_space.api import SpaceApi
from bkmonitor.documents import ActionInstanceDocument, AlertDocument, EventDocument
from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.request import get_request_username
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from constants.action import ActionDisplayStatus, ActionPluginType
from constants.alert import EventSeverity, EventStatus
from core.drf_resource import CacheResource, Resource, api, resource
from monitor.models import GlobalConfig, UserConfig

FAVORITE_CONFIG_KEY = "fta_overview:favorite_biz"

logger = logging.getLogger(__name__)


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
    def alert_sort_func(cls, all_data: Dict[str, Any]):
        def sort_func(x: int, y: int):
            x_level__count__map: Dict[int, int] = {
                level["level"]: level["count"] for level in all_data["alert"].get(str(x), {"levels": []})["levels"]
            }
            y_level__count__map: Dict[int, int] = {
                level["level"]: level["count"] for level in all_data["alert"].get(str(y), {"levels": []})["levels"]
            }

            # 按 level count 降序
            for level in range(1, 4):
                if x_level__count__map.get(level, 0) > y_level__count__map.get(level, 0):
                    return -1
                if x_level__count__map.get(level, 0) < y_level__count__map.get(level, 0):
                    return 1
            return 0

        return sort_func

    @classmethod
    def is_simple_search(cls, request_data: Dict[str, Any]) -> bool:
        # 同时满足以下条件，认为该统计是简单查询：无需关键字搜索、分页
        if all([not request_data.get("search"), request_data["page"] != 0 and request_data["page_size"] <= 15]):
            return True

    @classmethod
    def get_space_data_by_api(cls) -> Dict[str, Any]:
        space_list: List[Dict[str, Any]] = []
        try:
            space_list = resource.commons.list_spaces()
        except Exception:  # noqa
            logger.exception("[StatisticsResource] list_spaces failed")

        biz_id__space_map: Dict[int, Dict[str, Any]] = {space["bk_biz_id"]: space for space in space_list}
        allowed_biz_ids: Set[int] = set(biz_id__space_map.keys())

        return {"biz_id__space_map": biz_id__space_map, "allowed_biz_ids": allowed_biz_ids}

    @classmethod
    def get_space_data_by_cache(cls) -> Dict[str, Any]:
        username: str = get_request_username()
        allowed_biz_ids = set(resource.cc.fetch_allow_biz_ids_by_user(username))
        return {"biz_id__space_map": {}, "allowed_biz_ids": allowed_biz_ids}

    @classmethod
    def collect_biz_id__space_map(cls, bk_biz_id: int, biz_id__space_map: Dict[int, Dict[str, Any]]):
        try:
            space: Dict[str, Any] = SpaceApi.get_space_detail(bk_biz_id=bk_biz_id).to_dict()
        except Exception:  # noqa
            return
        biz_id__space_map[bk_biz_id] = space

    def perform_request(self, validated_request_data):
        username = get_request_username()

        # 优化思路： pi.cmdb.get_business 存在对象 <-> dict 来回转换的性能损失
        # 监控目前的管理粒度为「空间」，采用请求耗时较短的 list_spaces 替换
        # 逻辑优化：空间总量可能过万，大部分用户都非超管，拉取全部业务 -> 改为拉取有权限的空间，减少带宽损失
        # ---
        # 缓存优化（get_space_data_by_cache）：对于简单查询来说，仅需空间 ID 和单页的空间信息
        # 中间件（TrackSiteVisitMiddleware）提前预热「有权限空间 ID 列表」缓存，执行排序分页后拉取单页空间信息，节省全量拉空间的时间消耗

        if self.is_simple_search(validated_request_data):
            space_data: Dict[str, Any] = self.get_space_data_by_cache()
        else:
            space_data: Dict[str, Any] = self.get_space_data_by_api()

        allowed_biz_ids: Set[int] = space_data["allowed_biz_ids"]
        biz_id__space_map: Dict[int, Dict[str, Any]] = space_data["biz_id__space_map"]

        # 依赖数据获取
        favorite_biz_ids: Set[int] = set()
        user_config: Optional[UserConfig] = UserConfig.objects.filter(
            username=username, key=FAVORITE_CONFIG_KEY
        ).first()
        if user_config:
            favorite_biz_ids: Set[int] = set(user_config.value)

        try:
            # 获取全局配置置顶列表
            sticky_biz_ids: Set[int] = set(GlobalConfig.objects.get(key="biz_sticky").value)
        except GlobalConfig.DoesNotExist:
            sticky_biz_ids: Set[int] = set()

        all_data: Dict[str, Any] = resource.home.all_biz_statistics(days=validated_request_data["days"])

        filtered_biz_ids: Set[int] = allowed_biz_ids
        filtered_biz_ids: Set[int] = self._filter_by_favorite_only(
            validated_request_data, filtered_biz_ids, favorite_biz_ids
        )
        filtered_biz_ids: Set[int] = self._filter_by_allowed_only(
            validated_request_data, filtered_biz_ids, allowed_biz_ids
        )
        filtered_biz_ids = self._filter_by_search_keyword(validated_request_data, filtered_biz_ids, biz_id__space_map)
        filtered_biz_ids = self._filter_by_sticky_only(validated_request_data, filtered_biz_ids, sticky_biz_ids)
        filtered_biz_ids = self._filter_by_life_cycle(validated_request_data, filtered_biz_ids)
        filtered_biz_ids = self._filter_by_alert_filter(validated_request_data, filtered_biz_ids, all_data)

        # 排序：当前业务 > 置顶业务 > 有权限的任务 > 普通业务 > DEMO 业务
        def _get_biz_weight(_biz_id: int):
            if validated_request_data.get("bk_biz_id") == _biz_id:
                return 0
            elif _biz_id in sticky_biz_ids:
                return 1
            elif _biz_id == int(settings.DEMO_BIZ_ID or 0):
                # 先判断 DEMO 业务，避免「有权限」「Demo」业务同时成立的场景下，优先命中「有权限」导致排序前置
                return 4
            else:
                return (3, 2)[_biz_id in allowed_biz_ids]

        ordered_filtered_biz_ids: List[int] = sorted(
            list(filtered_biz_ids), key=lambda _biz_id: _get_biz_weight(_biz_id)
        )

        page: int = validated_request_data["page"]
        page_size: int = validated_request_data["page_size"]
        if page != 0:
            ordered_filtered_biz_ids = ordered_filtered_biz_ids[(page - 1) * page_size : page * page_size]

        # 补偿拉取不在列表中的空间
        th_list: List[InheritParentThread] = [
            InheritParentThread(target=self.collect_biz_id__space_map, args=(biz_id, biz_id__space_map))
            for biz_id in ordered_filtered_biz_ids
            if biz_id not in biz_id__space_map
        ]
        if th_list:
            run_threads(th_list)

        overview_data: Dict[str, Union[float]] = {
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
            all_data,
            allowed_biz_ids,
            ordered_filtered_biz_ids,
            overview_data,
            filtered_biz_ids,
            favorite_biz_ids,
            sticky_biz_ids,
            biz_id__space_map,
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
                # 平均应答时间：确认总时长 / 事件总数
                "mtta": (
                    overview_data["sum_ack_duration"] / overview_data["count_ack_duration"]
                    if overview_data["count_ack_duration"]
                    else None
                ),
                # 平均修复时间：持续总时长 / 事件总数
                "mttr": (
                    overview_data["sum_recover_duration"] / overview_data["count_recover_duration"]
                    if overview_data["count_recover_duration"]
                    else None
                ),
            },
            "details": [detail_map.get(biz_id) for biz_id in ordered_filtered_biz_ids],
        }

        return result

    @classmethod
    def _filter_by_allowed_only(
        cls, validated_request_data: Dict[str, Any], bk_biz_ids: Set[int], allowed_biz_ids: Set[int]
    ) -> Set[int]:
        """按有权限业务过滤"""
        if validated_request_data["allowed_only"]:
            # 过滤出「当前业务」及「有权限的业务」
            current_biz_ids: Set[int] = set()
            if validated_request_data.get("bk_biz_id"):
                current_biz_ids.add(validated_request_data["bk_biz_id"])
            return bk_biz_ids & allowed_biz_ids | current_biz_ids
        return bk_biz_ids

    @classmethod
    def _filter_by_search_keyword(
        cls, validated_request_data: Dict[str, Any], bk_biz_ids: Set[int], biz_id__space_map: Dict[int, Dict[str, Any]]
    ) -> Set[int]:
        """按搜索关键字过滤"""
        search: Optional[str] = validated_request_data.get("search")
        if not search:
            return bk_biz_ids

        filtered_biz_ids: Set[int] = set()
        for bk_biz_id in bk_biz_ids:
            try:
                space: Dict[str, Any] = biz_id__space_map[bk_biz_id]
            except KeyError:
                # 数据不同步或传参错误时的极小概率事件，记录日志并跳过
                logger.warning("[_filter_by_search_keyword] bk_biz_id not found: %s", bk_biz_id)
                continue

            if search == space["space_id"] or search.lower() in space["space_name"]:
                filtered_biz_ids.add(bk_biz_id)

        return filtered_biz_ids

    @classmethod
    def _filter_by_favorite_only(
        cls, validated_request_data: Dict[str, Any], bk_biz_ids: Set[int], favorite_biz_ids: Set[int]
    ) -> Set[int]:
        """按收藏业务过滤"""
        if validated_request_data["favorite_only"]:
            return bk_biz_ids & favorite_biz_ids
        return bk_biz_ids

    @classmethod
    def _filter_by_sticky_only(
        cls, validated_request_data: Dict[str, Any], bk_biz_ids: Set[int], sticky_biz_ids: Set[int]
    ) -> Set[int]:
        """按指定业务过滤"""
        if validated_request_data["sticky_only"]:
            return bk_biz_ids & sticky_biz_ids
        return bk_biz_ids

    @classmethod
    def _filter_by_life_cycle(cls, validated_request_data: Dict[str, Any], bk_biz_ids: Set[int]) -> Set[int]:
        """按 cc 业务生命周期过滤"""
        life_cycle: Optional[int] = validated_request_data.get("life_cycle")
        # 下面的查询较为耗时，没有业务列表的情况下直接返回
        if not life_cycle or not bk_biz_ids:
            return bk_biz_ids

        # 极少数场景的筛选场景，用到了再去拉业务列表
        # 空间没有生命周期，不需要加 all=True 把空间也拉回来
        biz_list: List[Business] = api.cmdb.get_business()
        life_cycle_filtered_biz_ids: Set[int] = {biz.bk_biz_id for biz in biz_list if biz.life_cycle == str(life_cycle)}
        return life_cycle_filtered_biz_ids & bk_biz_ids

    def _filter_by_alert_filter(
        self, validated_request_data: Dict[str, Any], bk_biz_ids: Set[int], all_data: Dict[str, Any]
    ) -> Set[int]:
        """按告警级别过滤"""
        alert_filter: Optional[str] = validated_request_data.get("alert_filter")
        if not alert_filter:
            return bk_biz_ids

        if validated_request_data["alert_filter"] == "has_alert":
            # 仅过滤出有告警的业务
            filtered_biz_list: List[int] = [
                bk_biz_id
                for bk_biz_id in bk_biz_ids
                if len(all_data["alert"].get(str(bk_biz_id), {"levels": []})["levels"]) != 0
            ]
            # 告警按照等级、数量进行排序
            filtered_biz_list.sort(key=cmp_to_key(self.alert_sort_func(all_data)))
        else:
            filtered_biz_list: List[int] = [
                bk_biz_id
                for bk_biz_id in bk_biz_ids
                if len(all_data["alert"].get(str(bk_biz_id), {"levels": []})["levels"]) == 0
            ]
        return set(filtered_biz_list)

    @staticmethod
    def _get_detail_map(
        all_data: Dict[str, Any],
        allowed_biz_ids: Set[int],
        ordered_filtered_biz_ids: List[int],
        overview_data: Dict[str, Union[int, float]],
        filtered_biz_ids: Set[int],
        favorite_biz_ids: Set[int],
        sticky_biz_ids: Set[int],
        biz_id__space_map: Dict[int, Dict[str, Any]],
    ) -> Dict[int, Dict[str, Any]]:
        detail_map: Dict[int, Dict[str, Any]] = {}

        for biz_id in filtered_biz_ids:
            biz_id_str: str = str(biz_id)
            biz_event_count: int = all_data["event"].get(biz_id_str, 0)
            biz_alert_data: Dict[str, Union[List[Any], float, int]] = all_data["alert"].get(
                biz_id_str,
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
            biz_action_data: Dict[str, int] = all_data["action"].get(biz_id_str, {"count": 0, "auto_recovery_count": 0})

            # 仅统计有权限且非 DEMO 业务的总数
            if biz_id in allowed_biz_ids and biz_id != int(settings.DEMO_BIZ_ID or 0):
                overview_data["biz_count"] += 1
                overview_data["event_count"] += biz_event_count
                overview_data["alert_count"] += biz_alert_data["count"]
                overview_data["strategy_alert_count"] += biz_alert_data["strategy_alert_count"]
                overview_data["action_count"] += biz_action_data["count"]
                overview_data["fatal_alert_count"] += biz_alert_data["fatal_alert_count"]
                overview_data["auto_recovery_count"] += biz_action_data["auto_recovery_count"]
                overview_data["sum_ack_duration"] += biz_alert_data["sum_ack_duration"]
                overview_data["count_ack_duration"] += biz_alert_data["count_ack_duration"]
                overview_data["sum_recover_duration"] += biz_alert_data["sum_recover_duration"]
                overview_data["count_recover_duration"] += biz_alert_data["count_recover_duration"]

            if biz_id not in ordered_filtered_biz_ids or biz_id not in biz_id__space_map:
                continue

            space: Dict[str, Any] = biz_id__space_map[biz_id]

            # 展示过滤业务
            biz_data: Dict[str, Any] = {
                "bk_biz_id": space["bk_biz_id"],
                "bk_biz_name": space["space_name"],
                "is_favorite": biz_id in favorite_biz_ids,
                "is_demo": biz_id == int(settings.DEMO_BIZ_ID or 0),
                "is_sticky": biz_id in sticky_biz_ids,
                "is_allowed": biz_id in allowed_biz_ids,
            }

            if biz_id in allowed_biz_ids:
                biz_data.update(
                    {
                        "event": {
                            "count": biz_event_count,
                        },
                        "alert": {
                            "count": biz_alert_data["count"],
                            "strategy_alert_count": biz_alert_data["strategy_alert_count"],
                            "levels": biz_alert_data["levels"],
                        },
                        "action": {"count": biz_action_data["count"]},
                        "noise_reduction_ratio": (
                            (1 - min(biz_alert_data["count"] / biz_event_count, 1)) if biz_event_count else None
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
                        "space_info": space,
                    }
                )

            detail_map[biz_id] = biz_data

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
