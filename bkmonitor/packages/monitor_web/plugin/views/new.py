"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from copy import deepcopy
from datetime import datetime
from typing import Any, cast

from bk_monitor_base.metric_plugin import (
    CreatePluginVersionParams,
    MetricPluginRemoteCollectDisableError,
    MetricPluginStatus,
    OSType,
    PluginIDExistsError,
    PluginIDInvalidError,
    VersionTuple,
    check_metric_plugin_id,
    count_metric_plugin_type,
    create_metric_plugin_version,
    debug_nodeman_plugin,
    delete_metric_plugin,
    export_metric_plugin_package,
    get_metric_plugin,
    get_metric_plugin_supported_os_types,
    get_nodeman_plugin_debug_log,
    get_virtual_metric_plugin,
    list_metric_plugin_deployments,
    list_metric_plugins,
    refresh_metric_plugin_metrics,
    release_metric_plugin_version,
    stop_nodeman_plugin_debug,
)
from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.iam.drf import BusinessActionPermission, IAMPermission
from bkmonitor.utils.common_utils import safe_int
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.utils.time_tools import utc2biz_str
from bkmonitor.utils.user import get_request_username
from core.drf_resource import api, resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from core.errors.plugin import (
    BizChangedError,
    DeletePermissionDenied,
    EditPermissionDenied,
    PluginIDExist,
    PluginIDFormatError,
    RelatedItemsExist,
    RemoteCollectError,
)
from monitor_web.plugin.constant import OS_TYPE_ID_MAP, SNMP_V3_AUTH_JSON, DebugStatus, PluginType
from monitor_web.plugin.manager.base import check_skip_debug
from monitor_web.plugin.compat import convert_metric_json_to_legacy
from monitor_web.plugin.resources import PluginFileUploadResource, SaveMetricResource
from monitor_web.plugin.serializers import (
    DataDogSerializer,
    ExporterSerializer,
    JmxSerializer,
    PushgatewaySerializer,
    ReleaseSerializer,
    ScriptSerializer,
    SNMPSerializer,
    StartDebugSerializer,
    TaskIdSerializer,
)


class PermissionMixin:
    def get_permissions(self) -> list[permissions.BasePermission]:
        if self.request.method in permissions.SAFE_METHODS:  # type: ignore
            return [BusinessActionPermission([ActionEnum.VIEW_PLUGIN])]
        return [BusinessActionPermission([ActionEnum.MANAGE_PLUGIN])]


def assert_manage_pub_plugin_permission():
    """
    断言当前用户必须要有管理公共插件的权限
    """
    Permission().is_allowed(action=ActionEnum.MANAGE_PUBLIC_PLUGIN, raise_exception=True)


class CollectorPluginViewSet(PermissionMixin, viewsets.ViewSet):
    # 使用plugin_id作为key
    lookup_field = "plugin_id"

    SERIALIZERS: dict[str, type[Serializer]] = {
        PluginType.EXPORTER: ExporterSerializer,
        PluginType.JMX: JmxSerializer,
        PluginType.SCRIPT: ScriptSerializer,
        PluginType.PUSHGATEWAY: PushgatewaySerializer,
        PluginType.DATADOG: DataDogSerializer,
        PluginType.SNMP: SNMPSerializer,
    }

    # 显示的插件类型
    display_plugin_types = [
        PluginType.EXPORTER,
        PluginType.SCRIPT,
        PluginType.JMX,
        PluginType.DATADOG,
        PluginType.PUSHGATEWAY,
        PluginType.SNMP,
    ]

    def get_permissions(self):
        """插件接口权限判断"""
        view_permissions: list[permissions.BasePermission] = []
        try:
            bk_biz_id = int(getattr(self.request, "biz_id"))
        except Exception:
            bk_biz_id = 0
        if self.request.method not in permissions.SAFE_METHODS and not bk_biz_id:
            # 业务ID为0是全局插件，使用全局权限判断
            view_permissions.append(IAMPermission([ActionEnum.MANAGE_PUBLIC_PLUGIN]))
            return view_permissions
        return super().get_permissions()

    @staticmethod
    def get_virtual_plugins(plugin_id: str = "", with_detail: bool = False) -> list[dict[str, Any]]:
        """获取虚拟插件

        Args:
            plugin_id: 插件ID
            with_detail: 是否包含详细信息

        Returns:
            list[dict]: 虚拟插件列表
        """

        plugin_configs = []
        now_time: str = utc2biz_str(datetime.now())

        public_config = {
            "is_official": True,
            "is_safety": True,
            "config_version": 1,
            "info_version": 1,
            "edit_allowed": False,
            "delete_allowed": False,
            "export_allowed": False,
            "bk_biz_id": 0,
            "related_conf_count": 0,
            "status": "normal",
            "create_user": "system",
            "create_time": now_time,
            "update_user": "system",
            "update_time": now_time,
        }

        if with_detail:
            public_config.update({"stage": MetricPluginStatus.RELEASE, "signature": ""})

        if plugin_id in ["snmp_v1", "snmp_v2c", "snmp_v3"]:
            plugin = get_virtual_metric_plugin(bk_tenant_id=cast(str, get_request_tenant_id()), plugin_id=plugin_id)
            plugin_config = {
                "plugin_id": plugin_id,
                "plugin_display_name": plugin.name,
                "plugin_type": PluginType.SNMP_TRAP,
                "tag": "",
                "label": plugin.label,
                "status": "normal",
                "logo": "",
                "collector_json": "",
                "config_json": {},
                "metric_json": "",
                "description_md": "",
                "config_version": 1,
                "info_version": 1,
                "stage": "release",
                "bk_biz_id": 0,
                "signature": "",
                "is_support_remote": True,
                "is_official": False,
                "is_safety": True,
                "create_user": "admin",
                "update_user": "admin",
                "os_type_list": [],
                "create_time": "",
                "update_time": "",
                "related_conf_count": 0,
                "edit_allowed": False,
            }
            if with_detail:
                params = [param.model_dump() for param in plugin.params]
                if plugin_id == "snmp_v3":
                    params.insert(
                        len(params) - 1,
                        {
                            "auth_json": deepcopy(SNMP_V3_AUTH_JSON),
                            "template_auth_json": deepcopy(SNMP_V3_AUTH_JSON),
                        },
                    )
                plugin_config["config_json"] = params
            plugin_configs.append(plugin_config)

        # 腾讯云指标采集插件
        if settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG and (
            not plugin_id or plugin_id == settings.TENCENT_CLOUD_METRIC_PLUGIN_ID
        ):
            qcloud_plugin_config = settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG
            label = qcloud_plugin_config.get("label", "os")
            plugin_config = {
                "plugin_id": settings.TENCENT_CLOUD_METRIC_PLUGIN_ID,
                "plugin_display_name": _(qcloud_plugin_config["plugin_display_name"]),
                "plugin_type": PluginType.K8S,
                "tag": qcloud_plugin_config.get("tag", ""),
                "label_info": resource.commons.get_label_msg(label),
                "logo": qcloud_plugin_config.get("logo", ""),
                **public_config,
            }

            # 是否包含详细信息
            if with_detail:
                plugin_config.update(
                    {
                        "label": label,
                        "collector_json": qcloud_plugin_config["collector_json"],
                        "config_json": qcloud_plugin_config.get("config_json", []),
                        "enable_field_blacklist": True,
                        "metric_json": [],
                        "description_md": qcloud_plugin_config.get("description_md", ""),
                        "is_support_remote": False,
                        "os_type_list": [],
                        "is_split_measurement": True,
                    }
                )

            plugin_configs.append(plugin_config)
        return plugin_configs

    @action(methods=["POST"], detail=False)
    def upload_file(self, request: Request):
        result_data = PluginFileUploadResource().request(request.data)
        return Response(result_data)

    def list(self, request: Request) -> Response:
        """指标插件列表接口

        # 放弃对status字段的过滤

        出参:
        {
            "count": {
                "Exporter": 28,
                "Script": 58,
                "JMX": 4,
                "DataDog": 7,
                "Pushgateway": 30,
                "Built-In": 0,
                "Log": 0,
                "Process": 0,
                "SNMP_Trap": 0,
                "SNMP": 1,
                "K8S": 0
            },
            "list": [
                {
                    "plugin_id": "liang_test_09",
                    "plugin_display_name": "liang_test_09",
                    "plugin_type": "Script",
                    "tag": "",
                    "bk_biz_id": 2,
                    "related_conf_count": 5,
                    "status": "normal",
                    "create_user": "liangling",
                    "create_time": "2026-01-26 14:46:14",
                    "update_user": "bondliu",
                    "update_time": "2026-03-03 11:59:17",
                    "config_version": 2,
                    "info_version": 5,
                    "edit_allowed": true,
                    "delete_allowed": false,
                    "export_allowed": 6,
                    "label_info": {
                        "first_label": "hosts",
                        "first_label_name": "\u4e3b\u673a&\u4e91\u5e73\u53f0",
                        "second_label": "os",
                        "second_label_name": "\u64cd\u4f5c\u7cfb\u7edf"
                    },
                    "logo": "",
                    "is_official": false,
                    "is_safety": true
                }
            ]
        }
        """
        bk_tenant_id = cast(str, get_request_tenant_id())
        params = request.query_params

        page = int(params.get("page", 1))
        page_size = int(params.get("page_size", 10))
        bk_biz_id = int(params.get("bk_biz_id", 0))
        search_key = params.get("search_key", "").strip()
        search_type = params.get("plugin_type", "").strip()
        labels = params.get("labels", "").strip()
        label_filters = [label for label in labels.split(",") if label] or None
        order = params.get("order", "").strip()

        # 是否包含虚拟插件
        with_virtual = params.get("with_virtual", "false").lower() == "true"

        # 获取插件类型列表
        plugin_types: list[str] | None = self.display_plugin_types
        if search_type:
            plugin_types = [search_type]

        # 分页参数适配
        offset, limit = 0, page_size
        if page == -1:
            offset = None
        else:
            offset = (page - 1) * page_size

        # 获取插件列表
        plugins, _ = list_metric_plugins(
            bk_tenant_id=bk_tenant_id,
            bk_biz_ids=[bk_biz_id],
            labels=label_filters,
            search=search_key,
            plugin_types=plugin_types,
            bk_biz_id_with_global=True,
            with_deployment_count=True,
            limit=limit,
            offset=offset,
            order=order,
        )

        # 统计插件类型数量
        raw_type_count = count_metric_plugin_type(
            bk_tenant_id=bk_tenant_id,
            bk_biz_ids=[bk_biz_id],
            labels=label_filters,
            search=search_key,
            plugin_types=self.display_plugin_types,
            bk_biz_id_with_global=True,
        )
        type_count = {plugin_type: raw_type_count.get(plugin_type, 0) for plugin_type in self.display_plugin_types}

        search_list = []
        for plugin in plugins:
            # 获取插件版本号
            config_version = 1
            debug_version = 1
            if plugin["release_version"]:
                config_version = plugin["release_version"].major
                debug_version = plugin["release_version"].minor
            elif plugin["debug_version"]:
                config_version = plugin["debug_version"].major
                debug_version = plugin["debug_version"].minor

            search_list.append(
                {
                    "plugin_id": plugin["id"],
                    "plugin_display_name": plugin["name"],
                    "plugin_type": plugin["type"],
                    "tag": "",
                    "bk_biz_id": plugin["bk_biz_id"],
                    "related_conf_count": plugin["deployment_count"],
                    "status": "normal" if plugin["release_version"] else "draft",
                    "create_user": plugin["created_by"],
                    "create_time": utc2biz_str(plugin["created_at"]),
                    "update_user": plugin["updated_by"],
                    "update_time": utc2biz_str(plugin["updated_at"]),
                    "config_version": config_version,
                    "info_version": debug_version,
                    "edit_allowed": not plugin["is_internal"],
                    # 没有被任何采集关联的插件才可以被删除（旧逻辑使用delete_allowed属性）
                    "delete_allowed": plugin["deployment_count"] == 0,
                    "export_allowed": int(bool(plugin["release_version"])),
                    "label_info": resource.commons.get_label_msg(plugin["label"]),
                    "logo": plugin["logo"],
                    "is_official": plugin["is_global"],
                    "is_safety": True,
                }
            )

        # 添加虚拟插件
        if with_virtual:
            search_list.extend(self.get_virtual_plugins())

        search_result = {"count": type_count, "list": search_list}

        return Response(search_result)

    def retrieve(self, request: Request, plugin_id: str):
        bk_tenant_id = cast(str, get_request_tenant_id())
        operator = cast(str, get_request_username())
        bk_biz_id = int(request.query_params["bk_biz_id"])

        # 虚拟插件处理
        plugins = self.get_virtual_plugins(plugin_id=plugin_id, with_detail=True)
        if plugins:
            return Response(plugins[0])

        # 其他插件
        plugin = get_metric_plugin(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)
        refresh_metric_plugin_metrics(
            bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=plugin.version, operator=operator
        )
        group_result = api.metadata.query_time_series_group(
            bk_biz_id=0, time_series_group_name=f"{plugin.type}_{plugin.id}".lower()
        )
        _, related_conf_count = list_metric_plugin_deployments(
            bk_tenant_id=bk_tenant_id, bk_biz_ids=[bk_biz_id], plugin_ids=[plugin_id], limit=1, offset=0
        )
        return Response(
            {
                "plugin_id": plugin.id,
                "plugin_display_name": plugin.name,
                "plugin_type": plugin.type,
                "tag": "",
                "label": plugin.label,
                "status": "normal" if plugin.status == MetricPluginStatus.RELEASE else "draft",
                "logo": plugin.logo,
                "collector_json": plugin.define,
                "config_json": [param.model_dump() for param in plugin.params],
                "enable_field_blacklist": plugin.enable_metric_discovery,
                "metric_json": convert_metric_json_to_legacy(plugin.metrics),
                "description_md": plugin.description_md,
                "config_version": plugin.version.major,
                "info_version": plugin.version.minor,
                "stage": plugin.status.value,
                "bk_biz_id": plugin.bk_biz_id,
                "signature": "",
                "is_support_remote": plugin.is_support_remote,
                "is_official": plugin.is_global,
                "is_safety": True,
                "create_user": plugin.created_by,
                "update_user": plugin.updated_by,
                "os_type_list": get_metric_plugin_supported_os_types(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id),
                "create_time": utc2biz_str(plugin.created_at),
                "update_time": utc2biz_str(plugin.updated_at),
                "related_conf_count": related_conf_count,
                "edit_allowed": not plugin.is_internal,
                "is_split_measurement": bool(group_result),
            }
        )

    def create(self, request: Request):
        params = cast(dict[str, Any], request.data)
        bk_biz_id = safe_int(params.get("bk_biz_id", 0))

        # 创建全业务插件时,判断当前请求用户是否有权限
        if not bk_biz_id:
            assert_manage_pub_plugin_permission()

        result_data = resource.plugin.create_plugin(params)
        return Response(result_data)

    @action(methods=["POST"], detail=True)
    def edit(self, request: Request, plugin_id: str):
        bk_tenant_id = cast(str, get_request_tenant_id())
        operator = cast(str, get_request_username())
        current_plugin = get_metric_plugin(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)
        params = cast(dict[str, Any], request.data)

        # 不支持单业务之间的切换
        bk_biz_id = current_plugin.bk_biz_id
        new_bk_biz_id = int(params.get("bk_biz_id", 0))
        is_changed_biz = bk_biz_id != new_bk_biz_id
        if bk_biz_id and new_bk_biz_id and is_changed_biz:
            raise BizChangedError

        # 涉及全业务插件编辑时,判断当前请求用户是否有权限
        if not (bk_biz_id and new_bk_biz_id):
            assert_manage_pub_plugin_permission()

            # 全业务插件 》 单业务插件，判断是否有关联项
            if not bk_biz_id and new_bk_biz_id:
                deployments, _ = list_metric_plugin_deployments(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_ids=None,
                    plugin_ids=[plugin_id],
                )
                if [deployment for deployment in deployments if deployment.bk_biz_id != new_bk_biz_id]:
                    raise RelatedItemsExist({"msg": "存在其余业务的关联项"})

        serializer_class = self.SERIALIZERS[current_plugin.type]
        serializer = serializer_class(data=params, partial=True)
        serializer.is_valid(raise_exception=True)
        validated_request_data = {
            "plugin_id": plugin_id,
            "plugin_type": current_plugin.type,
            "bk_biz_id": new_bk_biz_id,
            "plugin_display_name": current_plugin.name,
            "description_md": current_plugin.description_md,
            "label": current_plugin.label,
            "logo": current_plugin.logo,
            "config_json": [param.model_dump() for param in current_plugin.params],
            "collector_json": current_plugin.define,
            "metric_json": [metric.model_dump() for metric in current_plugin.metrics],
            "is_support_remote": current_plugin.is_support_remote,
            "version_log": current_plugin.version_log,
            "enable_field_blacklist": current_plugin.enable_metric_discovery,
        }
        validated_request_data.update(cast(dict[str, Any], serializer.validated_data))

        with transaction.atomic():
            try:
                _, version = create_metric_plugin_version(
                    bk_tenant_id=bk_tenant_id,
                    plugin_id=plugin_id,
                    operator=operator,
                    params=CreatePluginVersionParams(
                        name=validated_request_data["plugin_display_name"],
                        description_md=validated_request_data["description_md"],
                        label=validated_request_data["label"],
                        logo=validated_request_data["logo"],
                        metrics=SaveMetricResource._build_metric_groups(validated_request_data["metric_json"]),
                        enable_metric_discovery=validated_request_data["enable_field_blacklist"],
                        params=validated_request_data["config_json"],
                        define=validated_request_data["collector_json"],
                        is_support_remote=validated_request_data["is_support_remote"],
                        version=current_plugin.version if current_plugin.status != MetricPluginStatus.RELEASE else None,
                        status=MetricPluginStatus.DEBUG,
                        version_log=validated_request_data["version_log"],
                    ),
                )
            except MetricPluginRemoteCollectDisableError as error:
                raise RemoteCollectError({"msg": str(error)})

            # 内置插件不能编辑
            if current_plugin.is_internal and version != current_plugin.version:
                raise EditPermissionDenied({"plugin_id": plugin_id})

            if version == current_plugin.version:
                stage = current_plugin.status.value
                need_debug = current_plugin.status != MetricPluginStatus.RELEASE
            elif version.major == current_plugin.version.major:
                release_metric_plugin_version(
                    bk_tenant_id=bk_tenant_id,
                    plugin_id=plugin_id,
                    version=version,
                    operator=operator,
                    apply_data_link=False,
                )
                stage = MetricPluginStatus.RELEASE.value
                need_debug = False
            else:
                stage = MetricPluginStatus.DEBUG.value
                need_debug = True

        # 若是导入覆盖的插件：判断采集配置是否前后一致，一致则可跳过debug
        import_plugin_config = params.get("import_plugin_config", {})
        if import_plugin_config:
            rules = [
                params["collector_json"] == import_plugin_config["collector_json"],
                params["config_json"] == import_plugin_config["config_json"],
                params["is_support_remote"] == import_plugin_config["is_support_remote"],
            ]
            if all(rules):
                need_debug = False

        response_data = dict(validated_request_data)
        response_data["config_version"] = version.major
        response_data["info_version"] = version.minor
        response_data["os_type_list"] = get_metric_plugin_supported_os_types(
            bk_tenant_id=bk_tenant_id, plugin_id=plugin_id
        )
        response_data["stage"] = stage
        response_data["need_debug"] = check_skip_debug(need_debug)
        # TODO: base 侧尚未承接 signature 的持久化与版本联动。
        # 当前先保留接口字段，继续透传请求值，避免前端协议在这轮迁移里被打断。
        response_data["signature"] = validated_request_data.get("signature", params.get("signature", ""))
        response_data["enable_field_blacklist"] = validated_request_data["enable_field_blacklist"]
        return Response(response_data)

    @action(methods=["POST"], detail=False)
    def plugin_import_without_frontend(self, request, *args, **kwargs):
        # 导入全业务插件时,判断当前请求用户是否为超级管理员
        if not request.data.get("bk_biz_id"):
            assert_manage_pub_plugin_permission()
        request.data["operator"] = request.user.username
        plugin_data = resource.plugin.plugin_import_without_frontend(request.data)
        return Response(plugin_data)

    @action(methods=["POST"], detail=False)
    def import_plugin(self, request):
        # 导入全业务插件时,判断当前请求用户是否为超级管理员
        if not request.data.get("bk_biz_id"):
            assert_manage_pub_plugin_permission()
        plugin_data = resource.plugin.plugin_import(request.data)
        return Response(plugin_data)

    @action(methods=["GET"], detail=False)
    def operator_system(self, request: Request):
        """
        获取操作系统类型列表
        出参: [{"os_type": "linux", "os_type_id": 1}]
        """
        return Response([{"os_type": os_type.value, "os_type_id": OS_TYPE_ID_MAP[os_type]} for os_type in OSType])

    @action(methods=["POST"], detail=False)
    def delete(self, request: Request):
        params: dict[str, Any] = cast(dict[str, Any], request.data)

        # 参数提取
        bk_tenant_id = cast(str, get_request_tenant_id())
        plugin_ids: list[str] = params["plugin_ids"]
        bk_biz_id: int = params["bk_biz_id"]
        username: str = cast(str, get_request_username())

        plugins, _ = list_metric_plugins(
            bk_tenant_id=bk_tenant_id,
            plugin_ids=plugin_ids,
            bk_biz_ids=[bk_biz_id],
            with_deployment_count=True,
        )

        # 检查插件是否能够删除
        # 如果插件是内置插件或存在部署项，则不能删除
        for plugin in plugins:
            # 内置插件不能删除
            if plugin["is_internal"]:
                raise DeletePermissionDenied({"plugin_id": plugin["id"]})

            # 存在部署项，则不能删除
            deployment_count = cast(int, plugin["deployment_count"])
            if deployment_count > 0:
                raise RelatedItemsExist({"msg": "插件还存在采集配置，无法删除"})

        # 删除插件
        for plugin in plugins:
            with transaction.atomic():
                delete_metric_plugin(bk_tenant_id=bk_tenant_id, plugin_id=plugin["id"], operator=username)

        return Response({"result": True})

    @action(methods=["GET"], detail=True)
    def export_plugin(self, request: Request, plugin_id: str):
        bk_tenant_id = cast(str, get_request_tenant_id())
        operator: str = cast(str, get_request_username())

        download_url = export_metric_plugin_package(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            operator=operator,
        )
        return Response({"download_url": download_url})

    @action(methods=["GET"], detail=False)
    def check_id(self, request, *args, **kwargs):
        """检查插件ID是否存在

        入参: plugin_id: str
        出参: None | raise PluginIDExist
        """
        bk_tenant_id = cast(str, get_request_tenant_id())
        plugin_id: str = request.query_params["plugin_id"]

        try:
            check_metric_plugin_id(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)
        except PluginIDExistsError:
            raise PluginIDExist({"msg": plugin_id})
        except PluginIDInvalidError as e:
            raise PluginIDFormatError({"msg": str(e)})

        return Response()

    @action(methods=["POST"], detail=True)
    def start_debug(self, request, plugin_id: str):
        """开始插件调试

        入参: StartDebugSerializer
        出参: str 调试任务ID
        """
        bk_tenant_id = cast(str, get_request_tenant_id())

        # 参数校验
        serializer = StartDebugSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data: dict[str, Any] = cast(dict[str, Any], serializer.validated_data)

        config_version: int = validated_data["config_version"]
        info_version: int = validated_data["info_version"]
        param: dict[str, Any] = validated_data["param"]
        host_info: dict[str, Any] = validated_data["host_info"]
        target_nodes: list[dict[str, Any]] = validated_data.get("target_nodes", [])
        operator: str = cast(str, get_request_username())

        result = debug_nodeman_plugin(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            version=VersionTuple(config_version, info_version),
            collect_params=param["collector"],
            plugin_params=param["plugin"],
            collect_host=host_info,
            target_nodes=target_nodes,
            operator=operator,
        )
        return Response({"task_id": result["task_id"]})

    @action(methods=["POST"], detail=True)
    def stop_debug(self, request: Request, plugin_id: str):
        """停止插件调试

        入参: TaskIdSerializer
        """
        serializer = TaskIdSerializer(data=request.query_params or request.data)
        serializer.is_valid(raise_exception=True)

        bk_tenant_id = cast(str, get_request_tenant_id())
        validated_data: dict[str, Any] = cast(dict[str, Any], serializer.validated_data)
        task_id: int = validated_data["task_id"]
        operator: str = cast(str, get_request_username())

        stop_nodeman_plugin_debug(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            task_id=task_id,
            operator=operator,
        )
        return Response()

    @action(methods=["GET"], detail=True)
    def fetch_debug_log(self, request: Request, plugin_id: str):
        """
        获取插件调试日志

        入参: TaskIdSerializer
        出参: {
            "status": "INSTALL", # DebugStatus枚举
            "log_content": "xxxx",
            "metric_json": [
                {
                    "metric_name": "disk_usage",
                    "metric_value": 0.8,
                    "dimensions": [
                        {
                            "dimension_name": "disk_name",
                            "dimension_value": "/data"
                        }
                    ]
                }
            ],
            "last_time": "2026-03-01 17:25:00"
        }
        """
        # 参数校验
        serializer = TaskIdSerializer(data=request.query_params or request.data)
        serializer.is_valid(raise_exception=True)

        # 参数提取
        bk_tenant_id = cast(str, get_request_tenant_id())
        validated_data: dict[str, Any] = cast(dict[str, Any], serializer.validated_data)
        task_id: int = validated_data["task_id"]
        operator: str = cast(str, get_request_username())

        # 获取调试日志
        result = get_nodeman_plugin_debug_log(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            task_id=task_id,
            operator=operator,
        )

        # 状态字段转换
        # 兼容旧接口语义：一旦已经抓到指标，就应进入 FETCH_DATA 阶段，
        # 即使 nodeman 调试任务整体仍处于 running。
        if result["status"] == "failed":
            status = DebugStatus.FAILED
        elif result["metric_json"]:
            status = DebugStatus.FETCH_DATA
        elif result["status"] == "running":
            status = DebugStatus.INSTALL
        else:
            status = DebugStatus.SUCCESS

        return Response(
            {
                "status": status,
                "metric_json": result["metric_json"],
                "last_time": result["last_time"],
                "log_content": result["log"],
            }
        )

    @action(methods=["POST"], detail=True)
    def release(self, request: Request, plugin_id: str):
        """发布插件

        入参: ReleaseSerializer {"config_version":2,"info_version":2,"token":["7b0c5b708cd95f55abac85c17f277662"],"bk_biz_id":2}
        出参: None
        """
        serializer = ReleaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data: dict[str, Any] = cast(dict[str, Any], serializer.validated_data)
        bk_tenant_id = cast(str, get_request_tenant_id())
        config_version: int = validated_data["config_version"]
        info_version: int = validated_data["info_version"]
        operator: str = cast(str, get_request_username())

        release_metric_plugin_version(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            version=VersionTuple(config_version, info_version),
            operator=operator,
            md5_list=validated_data["token"],
        )
        return Response()


class DataDogPluginViewSet(PermissionMixin, ResourceViewSet):
    resource_routes = [ResourceRoute("POST", resource.plugin.data_dog_plugin_upload)]


class MetricPluginViewSet(PermissionMixin, ResourceViewSet):
    resource_routes = [ResourceRoute("POST", resource.plugin.save_metric, endpoint="save")]


class RegisterPluginViewSet(PermissionMixin, ResourceViewSet):
    resource_routes = [ResourceRoute("POST", resource.plugin.plugin_register)]


class SaveAndReleasePluginViewSet(PermissionMixin, ResourceViewSet):
    resource_routes = [ResourceRoute("POST", resource.plugin.save_and_release_plugin)]


class GetReservedWordViewSet(PermissionMixin, ResourceViewSet):
    """
    获取关键字列表
    """

    resource_routes = [ResourceRoute("GET", resource.plugin.get_reserved_word)]


class PluginUpgradeInfoViewSet(PermissionMixin, ResourceViewSet):
    """
    获取插件参数配置版本发行历史
    """

    resource_routes = [ResourceRoute("GET", resource.plugin.plugin_upgrade_info)]


class ProcessCollectorDebugViewSet(PermissionMixin, ResourceViewSet):
    """
    进程数据采集器
    """

    resource_routes = [ResourceRoute("POST", resource.plugin.process_collector_debug)]
