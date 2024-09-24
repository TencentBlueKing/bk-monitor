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
from datetime import datetime
from typing import Dict, List

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.utils.translation import ugettext_lazy as _
from rest_framework import permissions, serializers, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.iam.drf import BusinessActionPermission, IAMPermission
from bkmonitor.middlewares.authentication import NoCsrfSessionAuthentication
from bkmonitor.utils.common_utils import safe_int
from bkmonitor.utils.time_tools import utc2biz_str
from core.drf_resource import api, resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from core.errors.api import BKAPIError
from core.errors.plugin import (
    BizChangedError,
    DeletePermissionDenied,
    EditPermissionDenied,
    NodeManDeleteError,
    PluginIDNotExist,
    RelatedItemsExist,
)
from monitor_web.models import CollectConfigMeta
from monitor_web.models.plugin import (
    CollectorPluginMeta,
    OperatorSystem,
    PluginVersionHistory,
)
from monitor_web.plugin.constant import BUILT_IN_TAGS, PluginType
from monitor_web.plugin.manager import PluginManagerFactory
from monitor_web.plugin.manager.base import check_skip_debug
from monitor_web.plugin.resources import PluginFileUploadResource
from monitor_web.plugin.serializers import (
    ReleaseSerializer,
    StartDebugSerializer,
    TaskIdSerializer,
)
from monitor_web.plugin.signature import Signature


class PermissionMixin:
    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [BusinessActionPermission([ActionEnum.VIEW_PLUGIN])]
        return [BusinessActionPermission([ActionEnum.MANAGE_PLUGIN])]


class CollectorPluginSlz(serializers.ModelSerializer):
    class Meta:
        model = CollectorPluginMeta
        fields = ()


def assert_manage_pub_plugin_permission():
    """
    断言当前用户必须要有管理公共插件的权限
    """
    Permission().is_allowed(action=ActionEnum.MANAGE_PUBLIC_PLUGIN, raise_exception=True)


class DataDogPluginViewSet(PermissionMixin, ResourceViewSet):
    resource_routes = [ResourceRoute("POST", resource.plugin.data_dog_plugin_upload)]


class MetricPluginViewSet(PermissionMixin, ResourceViewSet):
    resource_routes = [ResourceRoute("POST", resource.plugin.save_metric, endpoint="save")]


class CollectorPluginViewSet(PermissionMixin, viewsets.ModelViewSet):
    queryset = CollectorPluginMeta.objects.all()
    serializer_class = Serializer

    def get_authenticators(self):
        authenticators = super(CollectorPluginViewSet, self).get_authenticators()
        authenticators = [
            authenticator for authenticator in authenticators if not isinstance(authenticator, SessionAuthentication)
        ]
        authenticators.append(NoCsrfSessionAuthentication())
        return authenticators

    def get_permissions(self):
        try:
            bk_biz_id = int(self.request.biz_id)
        except Exception:
            bk_biz_id = 0
        if self.request.method not in permissions.SAFE_METHODS and not bk_biz_id:
            # 业务ID为0是全局插件，使用全局权限判断
            return [IAMPermission([ActionEnum.MANAGE_PUBLIC_PLUGIN])]
        return super(CollectorPluginViewSet, self).get_permissions()

    @staticmethod
    def get_virtual_plugins(plugin_id: str = "", with_detail: bool = False) -> List[Dict]:
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
            public_config.update({"stage": PluginVersionHistory.Stage.RELEASE, "signature": ""})

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

    def list(self, request, *args, **kwargs):
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 10))
        bk_biz_id = int(request.query_params.get("bk_biz_id", 0))
        search_key = request.query_params.get("search_key", "").strip()
        search_type = request.query_params.get("plugin_type", "").strip()
        labels = request.query_params.get("labels", "").strip()
        order = request.query_params.get("order", "").strip()
        status = request.query_params.get("status")
        # 是否包含虚拟插件
        with_virtual = request.query_params.get("with_virtual", "false").lower() == "true"

        # 获取全量的插件数据（包含外键数据）
        all_versions = (
            PluginVersionHistory.objects.exclude(plugin__plugin_type__in=CollectorPluginMeta.VIRTUAL_PLUGIN_TYPE)
            .select_related("plugin", "config", "info")
            .defer("info__metric_json", "info__description_md")
        )
        if bk_biz_id:
            all_versions = all_versions.filter(plugin__bk_biz_id__in=[0, bk_biz_id])
        else:
            assert_manage_pub_plugin_permission()

        exact_search_map = {
            "stage": status,
        }
        if labels:
            exact_search_map.update({"plugin__label__in": labels.split(",")})

        for k, v in list(exact_search_map.items()):
            if v:
                all_versions = all_versions.filter((k, v))

        fuzzy_search_list = ["plugin.plugin_id", "plugin.create_user", "plugin.update_user", "info.plugin_display_name"]
        return_version = []
        for fuzzy_key in fuzzy_search_list:
            for v in all_versions:
                if search_key in getattr(getattr(v, fuzzy_key.split(".")[0]), fuzzy_key.split(".")[1]):
                    return_version.append(v)

        # 取出每个plugin的最新版本
        plugin_dict = {}
        for version in return_version:
            plugin_id = version.plugin.plugin_id
            # 当前面有一条release版本，后面的一定都是旧版本。debug和unregister不能共存，且只能有一条
            if plugin_id not in plugin_dict or version.is_release:
                plugin_dict[plugin_id] = version

        return_version = list(plugin_dict.values())
        return_version.sort(key=lambda x: x.update_time, reverse=True)
        # 排序
        if order:
            reverse = False
            if order.startswith("-"):
                order = order[1:]
                reverse = True
            if order == "status":
                try:
                    return_version.sort(key=lambda x: getattr(x, "stage"), reverse=reverse)
                except KeyError:
                    pass
            else:
                try:
                    return_version.sort(key=lambda x: getattr(getattr(x, "plugin"), order), reverse=reverse)
                except KeyError:
                    pass

        type_count = {plugin_type[0]: 0 for plugin_type in CollectorPluginMeta.PLUGIN_TYPE_CHOICES}
        for version in return_version:
            type_count[version.plugin.plugin_type] += 1

        if search_type:
            return_version = [version for version in return_version if version.plugin.plugin_type == search_type]

        # 生成用于查询的新的集合
        if page != -1:
            # fmt: off
            return_version = return_version[(page - 1) * page_size: page * page_size]
            # fmt: on

        # 生产插件采集的统计值和插件发布版本数量的统计值
        plugin_ids = list({item.plugin.plugin_id for item in return_version})
        plugin_queryset = CollectConfigMeta.objects.filter(plugin_id__in=plugin_ids)
        if bk_biz_id:
            plugin_queryset = plugin_queryset.filter(bk_biz_id=bk_biz_id)
        plugin_count_queryset = plugin_queryset.values("plugin_id").annotate(count=Count("plugin_id"))
        plugin_counts = {item["plugin_id"]: item["count"] for item in plugin_count_queryset}
        version_count_queryset = (
            PluginVersionHistory.objects.filter(plugin_id__in=plugin_ids, stage=PluginVersionHistory.Stage.RELEASE)
            .values("plugin_id")
            .annotate(count=Count("plugin_id"))
        )
        version_counts = {item["plugin_id"]: item["count"] for item in version_count_queryset}

        search_list = []
        for value in return_version:
            # 提取搜索需要的字段生成新的list
            search_list.append(
                {
                    "plugin_id": value.plugin.plugin_id,
                    "plugin_display_name": value.info.plugin_display_name,
                    "plugin_type": value.plugin.plugin_type,
                    "tag": value.plugin.tag,
                    "bk_biz_id": value.plugin.bk_biz_id,
                    "related_conf_count": plugin_counts.get(value.plugin.plugin_id, 0),
                    "status": "normal" if value.is_release else "draft",
                    "create_user": value.plugin.create_user,
                    "create_time": utc2biz_str(value.plugin.create_time),
                    "update_user": value.update_user,
                    "update_time": utc2biz_str(value.update_time),
                    "config_version": value.config_version,
                    "info_version": value.info_version,
                    "edit_allowed": value.plugin.edit_allowed if not value.is_official else False,
                    # 没有被任何采集关联的插件才可以被删除（旧逻辑使用delete_allowed属性）
                    "delete_allowed": plugin_counts.get(value.plugin.plugin_id, 0) == 0,
                    "export_allowed": version_counts.get(value.plugin.plugin_id, 0),
                    "label_info": resource.commons.get_label_msg(value.plugin.label),
                    "logo": value.info.logo_content,
                    "is_official": value.is_official,
                    "is_safety": value.is_safety,
                }
            )

        # 添加虚拟插件
        if with_virtual:
            search_list.extend(self.get_virtual_plugins())

        search_result = {"count": type_count, "list": search_list}

        return Response(search_result)

    def retrieve(self, request, *args, **kwargs):
        if kwargs["pk"] in ["snmp_v1", "snmp_v2c", "snmp_v3"]:
            plugin_manager = PluginManagerFactory.get_manager(plugin=kwargs["pk"], plugin_type=PluginType.SNMP_TRAP)
            return Response(plugin_manager.get_default_trap_plugin())

        # 腾讯云指标采集插件
        if kwargs["pk"] == settings.TENCENT_CLOUD_METRIC_PLUGIN_ID:
            plugins = self.get_virtual_plugins(plugin_id=kwargs["pk"], with_detail=True)
            if plugins:
                return Response(plugins[0])

        instance: CollectorPluginMeta = self.get_object()
        # 刷新metric json
        instance.refresh_metric_json()
        return Response(instance.get_plugin_detail())

    @action(methods=["POST"], detail=False)
    def upload_file(self, request, *args, **kwargs):
        result_data = PluginFileUploadResource().request(request.data)
        return Response(result_data)

    @action(methods=["GET"], detail=False)
    def operator_system(self, request, *args, **kwargs):
        sys_list = OperatorSystem.objects.all()
        result_list = [{"os_type": item.os_type, "os_type_id": item.os_type_id} for item in sys_list]
        return Response(result_list)

    def create(self, request, *args, **kwargs):
        params = request.data
        bk_biz_id = safe_int(request.data.get("bk_biz_id", 0))

        # 创建全业务插件时,判断当前请求用户是否有权限
        if not bk_biz_id:
            assert_manage_pub_plugin_permission()

        result_data = resource.plugin.create_plugin(params)
        return Response(result_data)

    @action(methods=["POST"], detail=True)
    def edit(self, request, *args, **kwargs):
        """
        插件编辑接口，两种情况：
        1. 普通编辑，file_data 参数为空
        2. 导入覆盖后编辑 file_data 参数不为空
        """

        instance = self.get_object()
        bk_biz_id = instance.bk_biz_id
        new_bk_biz_id = int(request.data.get("bk_biz_id", 0))
        is_changed_biz = bk_biz_id != new_bk_biz_id
        # 不支持单业务之间的切换
        if bk_biz_id and new_bk_biz_id and is_changed_biz:
            raise BizChangedError
        # 涉及全业务插件编辑时,判断当前请求用户是否有权限
        if not (bk_biz_id and new_bk_biz_id):
            assert_manage_pub_plugin_permission()

            # 全业务插件 》 单业务插件，判断是否有关联项
            if not bk_biz_id and new_bk_biz_id:
                collect_config = CollectConfigMeta.objects.filter(plugin__plugin_id=instance.plugin_id)
                if collect_config and [x for x in collect_config if x.bk_biz_id != new_bk_biz_id]:
                    raise RelatedItemsExist({"msg": _("存在其余业务的关联项")})

        current_config_version = instance.current_version.config_version
        current_info_version = instance.current_version.info_version

        plugin_manager = PluginManagerFactory.get_manager(plugin=instance)
        self.serializer_class = plugin_manager.serializer_class
        serializer = self.serializer_class(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            plugin_obj = serializer.save()
            plugin_manager.plugin = plugin_obj
            version, need_debug = plugin_manager.update_version(serializer.validated_data)

            # 检查插件的编辑权限
            if not instance.edit_allowed:
                if current_config_version != version.config_version or current_info_version != version.info_version:
                    raise EditPermissionDenied({"plugin_id": instance.plugin_id})

        # 若是导入覆盖的插件：判断采集配置是否前后一致，一致则可跳过debug
        import_plugin_config = request.data.get("import_plugin_config", {})
        if import_plugin_config:
            rules = [
                request.data["collector_json"] == import_plugin_config["collector_json"],
                request.data["config_json"] == import_plugin_config["config_json"],
                request.data["is_support_remote"] == import_plugin_config["is_support_remote"],
            ]
            if all(rules):
                need_debug = False

        serializer.validated_data["config_version"] = version.config_version
        serializer.validated_data["info_version"] = version.info_version
        serializer.validated_data["os_type_list"] = version.os_type_list
        serializer.validated_data["stage"] = version.stage
        serializer.validated_data["need_debug"] = check_skip_debug(need_debug)
        serializer.validated_data["signature"] = Signature(version.signature).dumps2yaml()
        return Response(serializer.validated_data)

    @action(methods=["POST"], detail=False)
    def delete(self, request, *args, **kwargs):
        param = request.data
        plugin_ids = param["plugin_ids"]
        # TODO: 检查是否存在关联项
        plugins = CollectorPluginMeta.objects.filter(plugin_id__in=plugin_ids)
        for plugin in plugins:
            # 检查插件的删除权限
            if not plugin.delete_allowed:
                raise DeletePermissionDenied({"plugin_id": plugin.plugin_id})

        with transaction.atomic():
            for plugin_id in plugin_ids:
                plugin = CollectorPluginMeta.origin_objects.filter(plugin_id=plugin_id)
                if plugin.first():
                    PluginVersionHistory.origin_objects.filter(plugin=plugin.first()).delete()
                    plugin.delete()
                    try:
                        api.node_man.delete_plugin(name=plugin_id)
                    except BKAPIError:
                        raise NodeManDeleteError

        return Response({"result": True})

    @action(methods=["GET"], detail=False)
    def tag_options(self, request, *args, **kwargs):
        tags = [item["tag"] for item in self.queryset.values("tag") if item["tag"]]
        tags += BUILT_IN_TAGS
        real_tags = list(set(tags))
        return Response(real_tags)

    @action(methods=["POST"], detail=False)
    def import_plugin(self, request, *args, **kwargs):
        # 导入全业务插件时,判断当前请求用户是否为超级管理员
        if not request.data.get("bk_biz_id"):
            assert_manage_pub_plugin_permission()
        plugin_data = resource.plugin.plugin_import(request.data)
        return Response(plugin_data)

    @action(methods=["POST"], detail=False)
    def replace_plugin(self, request, *args, **kwargs):
        instance = CollectorPluginMeta.objects.get(plugin_id=request.data["plugin_id"])
        current_config_version = instance.current_version.config_version
        current_info_version = instance.current_version.info_version
        plugin_manager = PluginManagerFactory.get_manager(plugin=instance)
        self.serializer_class = plugin_manager.serializer_class
        serializer = self.serializer_class(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            plugin_obj = serializer.save()
            plugin_manager.plugin = plugin_obj
            version, need_debug = plugin_manager.update_version(serializer.validated_data)

            # 检查插件的编辑权限
            if not instance.edit_allowed:
                if current_config_version != version.config_version or current_info_version != version.info_version:
                    raise EditPermissionDenied({"plugin_id": instance.plugin_id})

        serializer.validated_data["config_version"] = version.config_version
        serializer.validated_data["info_version"] = version.info_version
        serializer.validated_data["os_type_list"] = version.os_type_list
        serializer.validated_data["stage"] = version.stage
        serializer.validated_data["need_debug"] = check_skip_debug(need_debug)
        serializer.validated_data["signature"] = Signature(version.signature).dumps2yaml()
        return Response(serializer.validated_data)

    @action(methods=["GET"], detail=True)
    def export_plugin(self, request, *args, **kwargs):
        instance: CollectorPluginMeta = self.get_object()
        plugin_manager = PluginManagerFactory.get_manager(plugin=instance)
        release_version = instance.release_version
        if not release_version.is_packaged:
            with transaction.atomic():
                register_info = {
                    "plugin_id": plugin_manager.plugin.plugin_id,
                    "config_version": release_version.config_version,
                    "info_version": release_version.info_version,
                }
                ret = resource.plugin.plugin_register(**register_info)
                plugin_manager.release(
                    config_version=release_version.config_version,
                    info_version=release_version.info_version,
                    token=ret["token"],
                    debug=False,
                )

        # 刷新metric json
        instance.refresh_metric_json()
        return Response({"download_url": plugin_manager.run_export()})

    @action(methods=["GET"], detail=False)
    def check_id(self, request, *args, **kwargs):
        return Response(resource.plugin.check_plugin_id(request.query_params))

    @action(methods=["POST"], detail=True)
    def start_debug(self, request, *args, **kwargs):
        # 参数校验
        serializer = StartDebugSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # 获取plugin_manager
        instance = self.get_object()
        plugin_manager = PluginManagerFactory.get_manager(plugin=instance)
        # 开始调试
        result = plugin_manager.start_debug(**serializer.validated_data)
        return Response(result)

    @action(methods=["POST"], detail=True)
    def stop_debug(self, request, *args, **kwargs):
        serializer = TaskIdSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task_id = serializer.validated_data["task_id"]
        instance = self.get_object()
        plugin_manager = PluginManagerFactory.get_manager(plugin=instance)
        result = plugin_manager.stop_debug(task_id)
        return Response(result)

    @action(methods=["GET"], detail=True)
    def fetch_debug_log(self, request, *args, **kwargs):
        serializer = TaskIdSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        task_id = serializer.validated_data["task_id"]
        instance = self.get_object()
        plugin_manager = PluginManagerFactory.get_manager(plugin=instance)
        result = plugin_manager.query_debug(task_id)
        return Response(result)

    @action(methods=["POST"], detail=True)
    def release(self, request, *args, **kwargs):
        serializer = ReleaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            plugin = CollectorPluginMeta.objects.get(plugin_id=kwargs.get("pk"))
        except CollectorPluginMeta.DoesNotExist:
            raise PluginIDNotExist

        plugin_manager = PluginManagerFactory.get_manager(plugin=plugin)
        release_version = plugin_manager.release(**serializer.validated_data)
        return Response(resource.plugin.update_collect_plugin_version(release_version=release_version))

    @action(methods=["POST"], detail=False)
    def plugin_import_without_frontend(self, request, *args, **kwargs):
        # 导入全业务插件时,判断当前请求用户是否为超级管理员
        if not request.data.get("bk_biz_id"):
            assert_manage_pub_plugin_permission()
        request.data["operator"] = request.user.username
        plugin_data = resource.plugin.plugin_import_without_frontend(request.data)
        return Response(plugin_data)


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


class PluginTypeViewSet(PermissionMixin, ResourceViewSet):
    """
    获取已有的插件类型
    """

    resource_routes = [ResourceRoute("GET", resource.plugin.plugin_type)]
