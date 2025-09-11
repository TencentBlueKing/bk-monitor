"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import itertools
import logging
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from requests.exceptions import MissingSchema

from apm_web.constants import COLLECT_SERVICE_CONFIG_KEY
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.models.application import ApmMetaConfig, Application
from bk_dataview.models import Dashboard, Org, Star, User
from bk_dataview.permissions import GrafanaRole
from bkm_space.api import SpaceApi
from bkm_space.define import Space
from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import filter_data_by_permission
from bkmonitor.iam.resource import ResourceEnum
from bkmonitor.models import StrategyModel
from bkmonitor.models.base import Shield
from bkmonitor.models.home import HomeAlarmGraphConfig
from bkmonitor.utils.request import get_request, get_request_tenant_id
from bkmonitor.views import serializers
from core.drf_resource import Resource, api
from core.errors.api import BKAPIError
from monitor.models import UserConfig
from monitor_web.grafana.permissions import DashboardPermission

logger = logging.getLogger("monitor_web")


class GetFunctionShortcutResource(Resource):
    """
    获取首页功能入口
    """

    RECENT_INDEX_SET_RECORD_LIMIT = 200

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
    def get_recent_shortcuts(cls, username: str, functions: list[str], limit: int = 10):
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
                exists_dashboards: dict[tuple[str, str], Dashboard] = {
                    (org_ids_to_biz_id[dashboard.org_id], dashboard.uid): dashboard
                    for dashboard in dashboards
                    if dashboard.org_id in org_ids_to_biz_id
                }

                for access_record in access_records:
                    dashboard = exists_dashboards.get((str(access_record["bk_biz_id"]), access_record["dashboard_uid"]))
                    if not dashboard:
                        continue

                    items.append(
                        {
                            "bk_biz_id": access_record["bk_biz_id"],
                            "dashboard_uid": access_record["dashboard_uid"],
                            "dashboard_title": dashboard.title,
                            "folder_id": dashboard.folder_id,
                        }
                    )

                    # limit 限制
                    if len(items) == limit:
                        break

                # 获取并补充文件夹信息
                folder_ids = {item["folder_id"] for item in items if item["folder_id"]}
                folders = Dashboard.objects.filter(id__in=folder_ids, is_folder=True)
                folder_id_to_name = {folder.id: folder.title for folder in folders}
                for item in items:
                    item["folder_title"] = folder_id_to_name.get(item["folder_id"], "General")
            elif function == "apm_service":
                app_ids = {access_record["application_id"] for access_record in access_records}
                apps = {app.application_id: app for app in Application.objects.filter(application_id__in=app_ids)}

                # 获取服务信息
                app_services: dict[int, set[str]] = {}
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
            elif function == "log_retrieve":
                try:
                    # 由于访问记录的索引集可能是重复的，这里的 limit 没法直接使用
                    records = api.log_search.get_user_recent_index_set(
                        username=username, limit=cls.RECENT_INDEX_SET_RECORD_LIMIT
                    )
                except (BKAPIError, MissingSchema) as e:
                    logger.exception("get user recent index set error: %s", e)
                    continue

                index_set_ids = set()
                for record in records:
                    # 如果索引集已经存在，则跳过
                    if record["index_set_id"] in index_set_ids:
                        continue
                    index_set_ids.add(record["index_set_id"])

                    space = SpaceApi.get_space_detail(space_uid=record["space_uid"])
                    items.append(
                        {
                            "bk_biz_id": space.bk_biz_id,
                            "bk_biz_name": space.space_name,
                            "index_set_id": record["index_set_id"],
                            "index_set_name": record["index_set_name"],
                            "space_uid": space.space_uid,
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
    def get_favorite_shortcuts(cls, username: str, functions: list[str], limit: int = 10):
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
                org_id_to_biz_id: dict[int, int] = {
                    org.id: int(org.name)
                    for org in Org.objects.filter(id__in=[dashboard.org_id for dashboard in dashboards])
                    if org.name.strip().lstrip("-").isdigit()
                }

                # 获取仪表盘权限
                allowed_bk_biz_ids: set[int] = set()
                allowed_dashboard_ids: set[tuple[int, str]] = set()
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
                apps: dict[int, Application] = {
                    app.application_id: app
                    for app in Application.objects.filter(
                        application_id__in=[int(config.level_key) for config in apm_configs]
                    )
                }

                # 获取当前服务，去除过期服务
                app_services: dict[int, set[str]] = {}
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
                    bk_tenant_id=get_request_tenant_id(),
                    data=items,
                    actions=[ActionEnum.VIEW_APM_APPLICATION],
                    resource_meta=ResourceEnum.APM_APPLICATION,
                    id_field=lambda d: d["application_id"],
                    instance_create_func=ResourceEnum.APM_APPLICATION.create_instance_by_info,
                    mode="any",
                )[:limit]
            elif function == "log_retrieve":
                try:
                    records = api.log_search.get_user_favorite_index_set(username=username, limit=limit)
                except (BKAPIError, MissingSchema) as e:
                    logger.exception("get user favorite index set error: %s", e)
                    continue

                for record in records:
                    space: Space = SpaceApi.get_space_detail(space_uid=record["space_uid"])
                    items.append(
                        {
                            "bk_biz_id": space.bk_biz_id,
                            "bk_biz_name": space.space_name,
                            "index_set_id": record["index_set_id"],
                            "index_set_name": record["index_set_name"],
                            "space_uid": space.space_uid,
                        }
                    )
            else:
                continue

            result.append({"function": function, "name": name, "items": items})
        return result

    def perform_request(self, params: dict[str, Any]) -> list[dict[str, Any]]:
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
        bk_biz_ids: set[int] = {item["bk_biz_id"] for record in result for item in record["items"]}
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

        def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
            if attrs["function"] == "dashboard":
                attrs["config"] = self.DashboardConfigSerializer(data=attrs["config"]).validate(attrs["config"])
                attrs["id"] = attrs["config"]["dashboard_uid"]
            elif attrs["function"] == "apm_service":
                attrs["config"] = self.ApmServiceConfigSerializer(data=attrs["config"]).validate(attrs["config"])
                attrs["id"] = f"{attrs['config']['application_id']}-{attrs['config']['service_name']}"
            else:
                raise serializers.ValidationError(f"unsupported function: {attrs['function']}")
            return attrs

    def perform_request(self, params: dict[str, Any]) -> None:
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

    def perform_request(self, params: dict[str, Any]) -> None:
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
            shield_configs = Shield.objects.filter(
                category="strategy", failure_time__gte=timezone.now(), bk_biz_id=bk_biz_id
            )
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
            "biz_limit": settings.HOME_PAGE_ALARM_GRAPH_BIZ_LIMIT,
            "graph_limit": settings.HOME_PAGE_ALARM_GRAPH_LIMIT,
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

            # 检查图表数量限制
            if len(attrs["config"]) > settings.HOME_PAGE_ALARM_GRAPH_LIMIT:
                raise serializers.ValidationError(_("超过图表数量限制，请删除多余的配置"))

            return attrs

    def perform_request(self, params: dict[str, Any]) -> None:
        request = get_request(peaceful=True)
        if not request:
            return

        config = HomeAlarmGraphConfig.objects.filter(
            username=request.user.username,
            bk_biz_id=params["bk_biz_id"],
        ).first()
        if not config:
            # 检查数量限制
            count = HomeAlarmGraphConfig.objects.filter(
                username=request.user.username,
            ).count()
            if count >= settings.HOME_PAGE_ALARM_GRAPH_BIZ_LIMIT:
                raise serializers.ValidationError(_("超过业务数量限制，请删除多余的配置"))

            # 获取最大index
            max_index = (
                HomeAlarmGraphConfig.objects.filter(
                    username=request.user.username,
                ).aggregate(max_index=Max("index"))["max_index"]
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

    def perform_request(self, params: dict[str, Any]) -> None:
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

    def perform_request(self, params: dict[str, Any]) -> None:
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
