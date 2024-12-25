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
import itertools
from typing import Any, Dict, Iterable, List, Set, Tuple, Union

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.translation import gettext_lazy as _lazy
from elasticsearch_dsl import Q

from apm_web.constants import COLLECT_SERVICE_CONFIG_KEY
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.models.application import ApmMetaConfig, Application
from bk_dataview.models import Dashboard, Org, Star, User
from bk_dataview.permissions import GrafanaRole
from bkm_space.api import SpaceApi
from bkmonitor.documents import AlertDocument
from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import filter_data_by_permission
from bkmonitor.iam.resource import ResourceEnum
from bkmonitor.models import ItemModel, StrategyModel
from bkmonitor.models.base import Action, NoticeGroup, Shield
from bkmonitor.models.home import HomeAlarmGraphConfig
from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.request import get_request
from bkmonitor.utils.time_tools import get_datetime_range, localtime
from bkmonitor.views import serializers
from bkmonitor.views.serializers import BusinessOnlySerializer
from constants.alert import EventStatus
from core.drf_resource import Resource
from core.drf_resource.contrib.cache import CacheResource
from monitor.models import UserConfig
from monitor_web.grafana.permissions import DashboardPermission
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
            items: Iterable[ItemModel] = ItemModel.objects.filter(strategy_id__in=list(id__strategy_map.keys())).only(
                "strategy_id", "target"
            )
            for item in items:
                if (item.target and item.target[0]) or item.strategy_id not in id__strategy_map:
                    continue
                no_target_strategies.append(
                    {"strategy_id": item.strategy_id, "strategy_name": id__strategy_map[item.strategy_id]["name"]}
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


class GetFunctionShortcutResource(CacheResource):
    """
    获取首页功能入口
    """

    cache_type = CacheType.BIZ

    function_name_map = {
        "dashboard": _lazy("仪表盘"),
        "apm_service": _lazy("APM服务"),
        "log_retrieve": _lazy("日志检索"),
    }

    class RequestSerializer(serializers.Serializer):
        type = serializers.ChoiceField(choices=["recent", "favorite"], label="类型")
        # dashboard, apm_service, log_retrieve
        functions = serializers.ListField(child=serializers.CharField(), label="功能列表", allow_empty=False)
        limit = serializers.IntegerField(label="限制", default=10)

    @classmethod
    def get_recent_shortcuts(cls, username: str, functions: List[str], limit: int = 10):
        """
        获取最近访问的快捷方式
        """
        result = []

        # 获取最近访问记录
        config = UserConfig.objects.filter(
            username=username,
            key=UserConfig.Keys.FUNCTION_ACCESS_RECORD,
        ).first()
        function_access_records = config.value if config else {}

        # 访问记录不需要按权限过滤，如果没有权限，提示用户申请权限即可。todo: 不过目前没有增加权限字段，用户跳转后才知道是否有权限
        # 如果访问记录对应的资源不存在，则需要跳过
        for function in functions:
            access_records = function_access_records.get(function, [])
            items = []
            name = str(cls.function_name_map.get(function, function))

            if function == "dashboard":
                # 查询仪表盘信息
                dashboard_uids = {access_record["dashboard_uid"] for access_record in access_records}
                dashboards = Dashboard.objects.filter(uid__in=dashboard_uids)

                # 获取业务ID与 Grafana Org 的映射
                org_ids = {dashboard.org_id for dashboard in dashboards}
                org_ids_to_biz_id = {org.id: org.name for org in Org.objects.filter(id__in=org_ids)}

                # 确定已存在的仪表盘
                exists_dashboard_set: Set[Tuple[str, str]] = {
                    (org_ids_to_biz_id[dashboard.org_id], dashboard.uid)
                    for dashboard in dashboards
                    if dashboard.org_id in org_ids_to_biz_id
                }

                for access_record in access_records:
                    # 如果仪表盘不存在，则跳过
                    if (str(access_record["bk_biz_id"]), access_record["dashboard_uid"]) not in exists_dashboard_set:
                        continue

                    items.append(
                        {
                            "bk_biz_id": access_record["bk_biz_id"],
                            "dashboard_uid": access_record["dashboard_uid"],
                            "dashboard_title": dashboards.get(uid=access_record["dashboard_uid"]).title,
                        }
                    )

                    # limit 限制
                    if len(items) == limit:
                        break
            elif function == "apm_service":
                app_ids = {access_record["application_id"] for access_record in access_records}
                apps = {app.application_id: app for app in Application.objects.filter(application_id__in=app_ids)}

                # 获取服务信息
                app_services: Dict[int, Set[str]] = {}
                for app in apps.values():
                    services = ServiceHandler.list_services(app)
                    app_services[app.application_id] = {service["topo_key"] for service in services}

                for access_record in access_records:
                    # 判断应用是否存在
                    if access_record["application_id"] not in apps:
                        continue
                    app = apps[access_record["application_id"]]

                    # 判断服务是否存在
                    if access_record["service_name"] not in app_services[access_record["application_id"]]:
                        continue

                    items.append(
                        {
                            "bk_biz_id": app.bk_biz_id,
                            "app_name": app.app_name,
                            "service_name": access_record["service_name"],
                            "application_id": app.application_id,
                            "app_alias": app.app_alias,
                        }
                    )

                    # limit 限制
                    if len(items) >= limit:
                        break
            else:
                continue

            result.append({"function": function, "name": name, "items": items})

        return result

    @classmethod
    def get_favorite_shortcuts(cls, username: str, functions: List[str], limit: int = 10):
        """
        获取收藏的快捷方式
        """
        request = get_request(peaceful=True)
        if not request:
            return []

        result = []

        # 收藏原则上不展示无权限
        for function in functions:
            items = []
            name = str(cls.function_name_map.get(function, function))

            if function == "dashboard":
                # 获取用户信息
                user = User.objects.filter(login=username).first()
                if not user:
                    continue

                # 获取收藏的仪表盘
                starred_dashboard_ids = Star.objects.filter(user_id=user.id).values_list("dashboard_id", flat=True)
                dashboards = Dashboard.objects.filter(id__in=starred_dashboard_ids)

                # 获取业务ID与 Grafana Org 的映射
                org_id_to_biz_id: Dict[int, int] = {
                    org.id: int(org.name)
                    for org in Org.objects.filter(id__in=[dashboard.org_id for dashboard in dashboards])
                    if org.name.strip().lstrip('-').isdigit()
                }

                # 获取仪表盘权限
                allowed_bk_biz_ids: Set[int] = set()
                allowed_dashboard_ids: Set[Tuple[int, str]] = set()
                for bk_biz_id in org_id_to_biz_id.values():
                    ok, role, dashboard_permissions = DashboardPermission.has_permission(request, None, bk_biz_id)
                    if not ok:
                        continue
                    if role >= GrafanaRole.Viewer:
                        allowed_bk_biz_ids.add(bk_biz_id)
                    else:
                        allowed_dashboard_ids.update([(bk_biz_id, uid) for uid in dashboard_permissions.keys()])

                for dashboard in dashboards:
                    # 如果业务ID不存在，则跳过
                    if dashboard.org_id not in org_id_to_biz_id:
                        continue

                    # 判断是否有权限
                    bk_biz_id = org_id_to_biz_id[dashboard.org_id]
                    if bk_biz_id not in allowed_bk_biz_ids and (bk_biz_id, dashboard.uid) not in allowed_dashboard_ids:
                        continue

                    items.append(
                        {
                            "bk_biz_id": bk_biz_id,
                            "dashboard_uid": dashboard.uid,
                            "dashboard_title": dashboard.title,
                            "dashboard_slug": dashboard.slug,
                        }
                    )

                    # limit 限制
                    if len(items) == limit:
                        break
            elif function == "apm_service":
                # 获取服务收藏记录
                apm_configs = ApmMetaConfig.objects.filter(
                    config_level=ApmMetaConfig.APPLICATION_LEVEL,
                    config_key=COLLECT_SERVICE_CONFIG_KEY,
                )

                # 获取应用名称
                apps: Dict[int, Application] = {
                    app.application_id: app
                    for app in Application.objects.filter(
                        application_id__in=[int(config.level_key) for config in apm_configs]
                    )
                }

                # 获取当前服务，去除过期服务
                app_services: Dict[int, Set[str]] = {}
                for app in apps.values():
                    services = ServiceHandler.list_services(app)
                    app_services[app.application_id] = {service["topo_key"] for service in services}

                for apm_config in apm_configs:
                    # 判断应用是否存在
                    app_id = int(apm_config.level_key)
                    if app_id not in apps:
                        continue

                    # 获取服务名称
                    service_names = apm_config.config_value
                    for service_name in service_names:
                        if service_name not in app_services[app_id]:
                            continue

                        items.append(
                            {
                                "bk_biz_id": app.bk_biz_id,
                                "app_name": app.app_name,
                                "service_name": service_name,
                                "application_id": app.application_id,
                                "app_alias": app.app_alias,
                            }
                        )

                # 过滤无权限的应用
                items = filter_data_by_permission(
                    data=items,
                    actions=[ActionEnum.VIEW_APM_APPLICATION],
                    resource_meta=ResourceEnum.APM_APPLICATION,
                    id_field=lambda d: d["application_id"],
                    instance_create_func=ResourceEnum.APM_APPLICATION.create_instance_by_info,
                    mode="any",
                )[:limit]
            else:
                continue

            result.append({"function": function, "name": name, "items": items})

        return result

    def perform_request(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        返回结果示例
        [{
            "function": "dashboard",
            "name": "仪表盘",
            "items": [
                {
                    "bk_biz_id": 2,
                    "bk_biz_name": "蓝鲸",
                    "dashboard_uid": "1234567890",
                    "dashboard_title": "主机查看",
                    "dashboard_slug": "host-view",
                }
            ]
        }]
        """
        request = get_request(peaceful=True)
        if not request:
            return []

        username = request.user.username
        shortcut_type = params.get("type", "recent")

        if shortcut_type == "recent":
            result = self.get_recent_shortcuts(username, params["functions"])
        else:
            result = self.get_favorite_shortcuts(username, params["functions"])

        # 批量获取业务名称
        bk_biz_ids: Set[int] = {item["bk_biz_id"] for record in result for item in record["items"]}
        biz_id_name_map = {}
        for biz_id in bk_biz_ids:
            space = SpaceApi.get_space_detail(bk_biz_id=biz_id)
            if space:
                biz_id_name_map[biz_id] = space.space_name

        for record in result:
            for item in record["items"]:
                item["bk_biz_name"] = biz_id_name_map[item["bk_biz_id"]]

        return result


class AddAccessRecordResource(Resource):
    """
    添加访问记录
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        # dashboard, apm_service
        function = serializers.CharField(label="功能")
        config = serializers.JSONField(label="实例信息")

        class DashboardConfigSerializer(serializers.Serializer):
            dashboard_uid = serializers.CharField(label="仪表盘ID")

        class ApmServiceConfigSerializer(serializers.Serializer):
            application_id = serializers.IntegerField(label="应用ID")
            service_name = serializers.CharField(label="服务名称")

        class MetricRetrieveConfigSerializer(serializers.Serializer):
            favorite_record_id = serializers.IntegerField(label="收藏记录ID")

        def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
            if attrs["function"] == "dashboard":
                attrs["config"] = self.DashboardConfigSerializer(data=attrs["config"]).validate(attrs["config"])
                attrs["id"] = attrs["config"]["dashboard_uid"]
            elif attrs["function"] == "apm_service":
                attrs["config"] = self.ApmServiceConfigSerializer(data=attrs["config"]).validate(attrs["config"])
                attrs["id"] = f"{attrs['config']['application_id']}-{attrs['config']['service_name']}"
            else:
                raise serializers.ValidationError(f"unsupported function: {attrs['function']}")
            return attrs

    def perform_request(self, params: Dict[str, Any]) -> None:
        request = get_request(peaceful=True)
        if not request:
            return

        with transaction.atomic():
            # 获取访问记录
            config = (
                UserConfig.objects.select_for_update()
                .filter(
                    username=request.user.username,
                    key=UserConfig.Keys.FUNCTION_ACCESS_RECORD,
                )
                .first()
            )
            if not config:
                config = UserConfig(
                    username=request.user.username, key=UserConfig.Keys.FUNCTION_ACCESS_RECORD, value={}
                )

            # 记录访问
            value = config.value
            value.setdefault(params["function"], [])

            # 更新访问时间
            for item in value[params["function"]]:
                if item.get("id") == params["id"] and item["bk_biz_id"] == params["bk_biz_id"]:
                    item["time"] = int(timezone.now().timestamp())
                    break
            else:
                # 新增访问记录
                value[params["function"]].append(
                    {
                        "id": params["id"],
                        "bk_biz_id": params["bk_biz_id"],
                        "time": int(timezone.now().timestamp()),
                        **params["config"],
                    }
                )

            # 按时间排序
            value[params["function"]].sort(key=lambda x: x["time"], reverse=True)

            # 保留最近10条记录
            value[params["function"]] = value[params["function"]][:10]

            config.value = value
            config.save()


class GetAlarmGraphConfigResource(Resource):
    """
    首页告警图配置
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=False)

    def perform_request(self, params: Dict[str, Any]) -> None:
        request = get_request(peaceful=True)
        if not request:
            return

        query = HomeAlarmGraphConfig.objects.filter(username=request.user.username)

        # 获取指定业务配置
        config = None
        bk_biz_id = params.get("bk_biz_id")
        if params.get("bk_biz_id"):
            config = query.filter(bk_biz_id=params["bk_biz_id"]).first()

        # 获取第一个配置
        if not config:
            config = query.order_by("index").first()

        if config:
            bk_biz_id = config.bk_biz_id
            config = config.config

            # 查询已屏蔽策略
            shield_configs = Shield.objects.filter(category="strategy", failure_time__gte=timezone.now())
            shielded_strategy_ids = set(
                itertools.chain.from_iterable(
                    [shield_config.dimension_config.get("strategy_id", []) for shield_config in shield_configs]
                )
            )

            # 补充策略状态, status: deleted, disabled, shielded, normal
            strategies = StrategyModel.objects.filter(
                bk_biz_id=bk_biz_id,
                id__in=set(itertools.chain.from_iterable([item["strategy_ids"] for item in config])),
            )
            strategy_id_to_strategy = {(strategy.id, strategy.bk_biz_id): strategy for strategy in strategies}
            for item in config:
                strategy_ids = item["strategy_ids"]
                strategy_names = item["strategy_names"]
                status = []

                for strategy_id, strategy_name in zip(strategy_ids, strategy_names):
                    strategy = strategy_id_to_strategy.get((strategy_id, bk_biz_id))

                    strategy_status = "normal"
                    if not strategy:
                        strategy_status = "deleted"
                    elif not strategy.is_enabled:
                        strategy_status = "disabled"
                    elif strategy.id in shielded_strategy_ids:
                        strategy_status = "shielded"

                    status.append(
                        {
                            "strategy_id": strategy_id,
                            "name": strategy.name if strategy else strategy_name,
                            "status": strategy_status,
                        }
                    )
                item["status"] = status
        return {
            "bk_biz_id": bk_biz_id,
            "config": config,
            "tags": [
                {
                    "bk_biz_id": tag.bk_biz_id,
                    "bk_biz_name": SpaceApi.get_space_detail(bk_biz_id=tag.bk_biz_id).space_name,
                }
                for tag in query.order_by("index")
            ],
        }


class SaveAlarmGraphConfigResource(Resource):
    """
    保存首页告警图配置
    """

    class RequestSerializer(serializers.Serializer):
        class ConfigSerializer(serializers.Serializer):
            name = serializers.CharField(label="名称")
            strategy_ids = serializers.ListField(child=serializers.IntegerField(), label="策略ID", allow_empty=False)

        bk_biz_id = serializers.IntegerField(label="业务ID")
        config = ConfigSerializer(label="配置", many=True)

        def validate(self, attrs):
            # 获取策略名称
            strategy_id_to_name = {
                strategy.id: strategy.name
                for strategy in StrategyModel.objects.filter(
                    id__in=list(itertools.chain.from_iterable([item["strategy_ids"] for item in attrs["config"]])),
                    bk_biz_id=attrs["bk_biz_id"],
                )
            }

            # 补充策略名称
            for item in attrs["config"]:
                strategy_names = []
                for strategy_id in item["strategy_ids"]:
                    strategy_names.append(strategy_id_to_name.get(strategy_id, "Unknown Strategy"))
                item["strategy_names"] = strategy_names

            return attrs

    def perform_request(self, params: Dict[str, Any]) -> None:
        request = get_request(peaceful=True)
        if not request:
            return

        config = HomeAlarmGraphConfig.objects.filter(
            username=request.user.username,
            bk_biz_id=params["bk_biz_id"],
        ).first()
        if not config:
            # 获取最大index
            max_index = (
                HomeAlarmGraphConfig.objects.filter(
                    username=request.user.username,
                ).aggregate(
                    max_index=Max("index")
                )["max_index"]
                or 0
            )

            config = HomeAlarmGraphConfig(
                username=request.user.username,
                bk_biz_id=params["bk_biz_id"],
                # 排到最后面
                index=max_index + 1,
            )
        config.config = params["config"]
        config.save()


class DeleteAlarmGraphConfigResource(Resource):
    """
    删除首页告警图配置
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    def perform_request(self, params: Dict[str, Any]) -> None:
        request = get_request(peaceful=True)
        if not request:
            return

        HomeAlarmGraphConfig.objects.filter(
            username=request.user.username,
            bk_biz_id=params["bk_biz_id"],
        ).delete()


class SaveAlarmGraphBizIndexResource(Resource):
    """
    保存首页告警图业务排序
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_ids = serializers.ListField(child=serializers.IntegerField(), label="业务ID列表")

    def perform_request(self, params: Dict[str, Any]) -> None:
        request = get_request(peaceful=True)
        if not request:
            return

        query = HomeAlarmGraphConfig.objects.filter(username=request.user.username)

        # 更新排序
        for index, bk_biz_id in enumerate(params["bk_biz_ids"]):
            query.filter(bk_biz_id=bk_biz_id).update(index=index)

        # 剩余的配置排到最后面
        max_index = query.aggregate(max_index=Max("index"))["max_index"] or 0
        for index, config in enumerate(query.exclude(bk_biz_id__in=params["bk_biz_ids"]).order_by("index")):
            config.index = index + max_index + 1
            config.save()
