"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from copy import copy
from typing import Any

from django.conf import settings
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Max
from django.utils.translation import gettext as _

from bkm_space.api import SpaceApi
from bkmonitor.utils import shortuuid
from bkmonitor.utils.request import get_request, get_request_tenant_id
from bkmonitor.utils.user import get_global_user
from bkmonitor.views import serializers
from constants.cmdb import TargetNodeType, TargetObjectType
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from core.errors.api import BKAPIError
from core.errors.collecting import (
    CollectConfigNotExist,
    CollectConfigParamsError,
    CollectConfigRollbackError,
    ToggleConfigStatusError,
)
from core.errors.plugin import PluginIDNotExist
from monitor_web.collecting.constant import (
    COLLECT_TYPE_CHOICES,
    CollectStatus,
    OperationResult,
    OperationType,
    Status,
    TaskStatus,
)
from monitor_web.collecting.deploy import get_collect_installer
from monitor_web.collecting.utils import fetch_sub_statistics
from monitor_web.models import CollectConfigMeta, CollectorPluginMeta, DeploymentConfigVersion, PluginVersionHistory
from monitor_web.plugin.constant import PluginType
from monitor_web.plugin.manager import PluginManagerFactory
from monitor_web.strategies.loader.datalink_loader import (
    DatalinkDefaultAlarmStrategyLoader,
)
from monitor_web.tasks import append_metric_list_cache

logger = logging.getLogger(__name__)


class CollectConfigListResource(Resource):
    """
    获取采集配置列表信息
    """

    def __init__(self):
        super().__init__()
        self.realtime_data = {}  # 采集配置实时数据结果
        self.service_type_data = {}  # 服务分类数据
        self.plugin_release_version = {}  # 插件最新版本，用于检查采集配置是否需要升级
        self.bk_biz_id = None

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
        refresh_status = serializers.BooleanField(required=False, label="是否刷新状态")
        search = serializers.DictField(required=False, label="搜索字段")
        order = serializers.CharField(required=False, label="排序字段")
        disable_service_type = serializers.BooleanField(default=True, label="不需要服务分类")
        page = serializers.IntegerField(required=False, default=1, label="页数")
        limit = serializers.IntegerField(required=False, default=10, label="大小")

    def get_realtime_data(self, config_data_list, bk_tenant_id):
        """
        获取节点管理订阅实时状态
        :param config_data_list: 采集配置数据列表
        :return: self.realtime_data
        """

        subscription_id_config_map, statistics_data = fetch_sub_statistics(config_data_list)
        updated_configs = []

        # 节点管理返回的状态数量
        for subscription_status in statistics_data:
            status_number = {}
            for status_result in subscription_status.get("status", []):
                status_number[status_result["status"]] = status_result["count"]

            error_count = status_number.get(CollectStatus.FAILED, 0)
            total_count = subscription_status.get("instances", 0)
            pending_count = status_number.get(CollectStatus.PENDING, 0)
            running_count = status_number.get(CollectStatus.RUNNING, 0)
            subscription_status_data = {
                "error_instance_count": error_count,
                "total_instance_count": total_count,
                "pending_instance_count": pending_count,
                "running_instance_count": running_count,
            }
            self.realtime_data.update({subscription_status["subscription_id"]: subscription_status_data})

            # 更新任务状态
            config = subscription_id_config_map[subscription_status["subscription_id"]]
            if not config:
                continue
            if error_count == 0:
                operation_result = OperationResult.SUCCESS
            elif error_count == total_count:
                operation_result = OperationResult.FAILED
            elif running_count + pending_count != 0:
                operation_result = OperationResult.DEPLOYING
            else:
                operation_result = OperationResult.WARNING

            # 更新缓存
            cache_data = {
                "error_instance_count": subscription_status_data.get("error_instance_count", 0),
                "total_instance_count": subscription_status_data.get("total_instance_count", 0),
            }
            if config.cache_data != cache_data or config.operation_result != operation_result:
                config.cache_data = cache_data
                config.operation_result = operation_result
                updated_configs.append(config)

        collector_plugins = CollectorPluginMeta.objects.filter(
            bk_tenant_id=bk_tenant_id, plugin_id__in=[config.plugin_id for config in config_data_list]
        ).values("plugin_id", "plugin_type")
        plugin_id_type_map = {plugin["plugin_id"]: plugin["plugin_type"] for plugin in collector_plugins}
        # 更新k8s插件采集配置的状态
        for collect_config in config_data_list:
            # 跳过非k8s插件
            if plugin_id_type_map.get(collect_config.plugin_id) != PluginType.K8S:
                continue

            if collect_config.operation_result not in [OperationResult.PREPARING, OperationResult.DEPLOYING]:
                continue

            error_count, total_count, pending_count, running_count = 0, 0, 0, 0
            installer = get_collect_installer(collect_config)
            for node in installer.status():
                for instance in node["child"]:
                    if instance["status"] == CollectStatus.RUNNING:
                        running_count += 1
                    elif instance["status"] == CollectStatus.PENDING:
                        pending_count += 1
                    elif instance["status"] in [CollectStatus.FAILED, CollectStatus.UNKNOWN]:
                        error_count += 1
                    total_count += 1

            if error_count == total_count:
                operation_result = OperationResult.FAILED
            elif running_count + pending_count != 0:
                operation_result = OperationResult.DEPLOYING
            elif error_count == 0:
                operation_result = OperationResult.SUCCESS
            else:
                operation_result = OperationResult.WARNING

            # 更新缓存
            cache_data = {
                "error_instance_count": error_count,
                "total_instance_count": total_count,
            }
            if collect_config.cache_data != cache_data or collect_config.operation_result != operation_result:
                collect_config.cache_data = cache_data
                collect_config.operation_result = operation_result
                updated_configs.append(collect_config)

        CollectConfigMeta.objects.bulk_update(updated_configs, ["cache_data", "operation_result"])

    def update_cache_data(self, config: CollectConfigMeta):
        # 更新采集配置的缓存数据（总数、异常数）
        subscription_id = config.deployment_config.subscription_id
        realtime_data = self.realtime_data.get(subscription_id)
        if not realtime_data:
            return

        cache_data = {
            "error_instance_count": realtime_data.get("error_instance_count", 0),
            "total_instance_count": realtime_data.get("total_instance_count", 0),
        }
        # 若缓存数据和实际数据不一致，则更新数据库
        if config.cache_data != cache_data:
            config.cache_data = cache_data
            config.save(not_update_user=True, update_fields=["cache_data"])

    @staticmethod
    def update_cache_data_item(conf, field, value):
        """
        更新缓存数据某字段
        :param conf: 采集配置
        :param field: 字段
        :param value: 值
        :return: conf
        """
        if not isinstance(conf.cache_data, dict):
            conf.cache_data = {}
        conf.cache_data[field] = value
        return conf

    def get_status(self, conf):
        # 判断采集配置是否处于自动下发中，返回采集配置状态和任务状态
        status_key = conf.deployment_config.subscription_id
        if self.realtime_data.get(status_key) and self.realtime_data.get(status_key).get("is_auto_deploying"):
            status = {
                "config_status": Status.AUTO_DEPLOYING,
                "task_status": TaskStatus.AUTO_DEPLOYING,
                "running_tasks": self.realtime_data.get(status_key).get("auto_running_tasks"),
            }
        else:
            status = {"config_status": conf.config_status, "task_status": conf.task_status, "running_tasks": []}

        self.update_cache_data_item(conf, "status", conf.config_status)
        self.update_cache_data_item(conf, "task_status", conf.task_status)
        return status

    def _need_upgrade(self, conf: CollectConfigMeta, config_plugin_map, plugin_version_map) -> bool:
        # 判断采集配置是否需要升级，使用config_version缓存，大幅减少查询数据库的次数
        # 如果采集配置处于已停用，或者主机/实例总数为零，则不需要进行升级
        if conf.task_status == TaskStatus.STOPPED or conf.get_cache_data("total_instance_count", 0) == 0:
            return False
        else:
            plugin = config_plugin_map.get(conf.plugin_id)
            config_version = plugin_version_map.get(plugin.plugin_id)
            if not config_version:
                logger.error(
                    f"[CollectConfigList] [need_upgrade] collect config {conf.id} was not found config version."
                )
                return False

            return conf.deployment_config.plugin_version.config_version < config_version

    def need_upgrade(self, conf: CollectConfigMeta, config_plugin_map, plugin_version_map) -> bool:
        # 判断采集配置是否需要升级，使用config_version缓存，大幅减少查询数据库的次数
        # 如果采集配置处于已停用，或者主机/实例总数为零，则不需要进行升级
        is_need_upgrade = self._need_upgrade(conf, config_plugin_map, plugin_version_map)
        self.update_cache_data_item(conf, "need_upgrade", is_need_upgrade)
        return is_need_upgrade

    def exists_by_biz(self, bk_biz_id):
        bk_tenant_id = get_request_tenant_id()
        space = SpaceApi.get_space_detail(bk_biz_id=bk_biz_id)
        data_sources = api.metadata.query_data_source_by_space_uid(
            space_uid_list=[space.space_uid], is_platform_data_id=True
        )
        data_names = [ds["data_name"] for ds in data_sources]
        plugin_ids = []
        global_plugins = CollectorPluginMeta.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=0).values(
            "plugin_type", "plugin_id"
        )
        for plugin in global_plugins:
            data_name = f"{plugin['plugin_type']}_{plugin['plugin_id']}".lower()
            if data_name in data_names:
                plugin_ids.append(plugin["plugin_id"])

        return CollectConfigMeta.objects.filter(
            Q(plugin_id__in=plugin_ids) | Q(bk_biz_id=bk_biz_id), bk_tenant_id=bk_tenant_id
        ).exists()

    def perform_request(self, validated_request_data):
        bk_tenant_id = get_request_tenant_id()
        bk_biz_id = validated_request_data.get("bk_biz_id")
        refresh_status = validated_request_data.get("refresh_status")
        search_dict = validated_request_data.get("search", {})
        order = validated_request_data.get("order")
        self.bk_biz_id = bk_biz_id

        collect_config_fields = [i.attname for i in list(CollectConfigMeta._meta.fields)]
        new_search = []
        for item, value in search_dict.items():
            if item in ["status", "task_status"]:
                # config_status: 启用 STARTED、停用 STOPPED
                # task_status: 异常 WARNING
                new_search.append(Q(cache_data__contains=f'"{item}": "{value}"'))
            elif item == "need_upgrade":
                # need_upgrade: 是否需要升级
                new_search.append(Q(cache_data__contains=f'"{item}": {value}'))
            elif item == "fuzzy":
                new_search.append(Q(id__icontains=value) | Q(name__icontains=value))
            elif item in collect_config_fields:
                new_search.append(Q(**{item: value}))

        # 获取全量的采集配置数据（包含外键数据）filter(**search_dict)
        config_list = (
            CollectConfigMeta.objects.filter(*new_search, bk_tenant_id=bk_tenant_id)
            .select_related("deployment_config__plugin_version")
            .order_by("-id")
        )

        all_space_list = SpaceApi.list_spaces()
        bk_biz_id_space_dict = {space.bk_biz_id: space for space in all_space_list}

        global_plugins = CollectorPluginMeta.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=0).values(
            "plugin_type", "plugin_id"
        )

        # bk_biz_id可以为空，为空则按用户拥有的业务查询
        plugin_ids = []
        user_biz_ids = []
        try:
            if bk_biz_id:
                user_biz_ids = [bk_biz_id]
                space = bk_biz_id_space_dict.get(bk_biz_id)
                data_sources = api.metadata.query_data_source_by_space_uid(
                    space_uid_list=[space.space_uid], is_platform_data_id=True
                )
                data_names = [ds["data_name"] for ds in data_sources]

                for plugin in global_plugins:
                    data_name = f"{plugin['plugin_type']}_{plugin['plugin_id']}".lower()
                    if data_name in data_names:
                        plugin_ids.append(plugin["plugin_id"])
            else:
                # 全业务场景 to be legacy
                user_biz_ids = resource.space.get_bk_biz_ids_by_user(get_request().user)
                space_uid_set = set()
                for biz_id in user_biz_ids:
                    space = bk_biz_id_space_dict.get(biz_id)
                    if space:
                        space_uid_set.add(space.space_uid)

                data_sources = api.metadata.query_data_source_by_space_uid(
                    space_uid_list=list(space_uid_set), is_platform_data_id=True
                )
                data_names = [ds["data_name"] for ds in data_sources]
                for plugin in global_plugins:
                    data_name = f"{plugin['plugin_type']}_{plugin['plugin_id']}".lower()
                    if data_name in data_names:
                        plugin_ids.append(plugin["plugin_id"])
        except BKAPIError as e:
            logger.error(f"get data source error: {e}")

        config_list = config_list.filter(Q(plugin_id__in=plugin_ids) | Q(bk_biz_id__in=user_biz_ids))

        total = len(config_list)
        if total == 0:
            return {"type_list": [], "config_list": [], "total": 0}

        if validated_request_data["page"] != -1:
            paginator = Paginator(config_list, validated_request_data["limit"])
            config_data_list = list(paginator.page(validated_request_data["page"]))
        else:
            config_data_list = list(config_list)

        if refresh_status:
            try:
                self.get_realtime_data(config_data_list, bk_tenant_id)
            except Exception:
                # 尝试实时获取，获取失败就用缓存数据
                pass

        plugin_ids = set(config.plugin_id for config in config_data_list)
        plugins = CollectorPluginMeta.objects.filter(bk_tenant_id=bk_tenant_id, plugin_id__in=plugin_ids)
        config_plugin_map = {plugin.plugin_id: plugin for plugin in plugins}

        version_filter = {
            "bk_tenant_id": bk_tenant_id,
            "plugin_id__in": plugin_ids,
            "stage": PluginVersionHistory.Stage.RELEASE,
            "is_packaged": True,
        }
        # 批量获取到最新的版本
        group_by = ["bk_tenant_id", "plugin_id", "stage", "is_packaged"]
        versions = (
            PluginVersionHistory.objects.filter(**version_filter)
            .values(*group_by)
            .annotate(latest_version=Max("config_version"))
            .values("plugin_id", "latest_version")
            .order_by()
        )
        plugin_version_map = {version["plugin_id"]: version["latest_version"] for version in versions}
        missing_plugin_ids = plugin_ids - set(plugin_version_map.keys())

        # 如果还有缺少的插件id，则去除is_packaged条件再查询一次剩余插件的最新版本
        if missing_plugin_ids:
            version_filter["plugin_id__in"] = missing_plugin_ids
            version_filter.pop("is_packaged")
            group_by.remove("is_packaged")
            versions = (
                PluginVersionHistory.objects.filter(**version_filter)
                .values(*group_by)
                .annotate(latest_version=Max("config_version"))
                .values("plugin_id", "latest_version")
                .order_by()
            )
            plugin_version_map.update({version["plugin_id"]: version["latest_version"] for version in versions})

        search_list = []
        update_configs = []
        for item in config_data_list:
            status = self.get_status(item)
            space = bk_biz_id_space_dict.get(item.bk_biz_id)
            is_need_upgrade = self.need_upgrade(item, config_plugin_map, plugin_version_map)
            update_configs.append(item)
            search_list.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "bk_biz_id": item.bk_biz_id,
                    "space_name": f"{space.space_name}({space.type_name})" if space else "",
                    "collect_type": item.collect_type,
                    "status": status["config_status"],
                    "task_status": status["task_status"],
                    "target_object_type": item.target_object_type,
                    "target_node_type": item.deployment_config.target_node_type,
                    "plugin_id": item.plugin_id,
                    "target_nodes_count": len(item.deployment_config.target_nodes),
                    "need_upgrade": is_need_upgrade,
                    "config_version": item.deployment_config.plugin_version.config_version,
                    "info_version": item.deployment_config.plugin_version.info_version,
                    "error_instance_count": (
                        0
                        if status["task_status"] == TaskStatus.STOPPED
                        else item.get_cache_data("error_instance_count", 0)
                    ),
                    "total_instance_count": item.get_cache_data("total_instance_count", 0),
                    "running_tasks": status["running_tasks"],
                    "label_info": item.label_info,
                    "label": item.label,
                    "update_time": item.update_time,
                    "update_user": item.update_user,
                }
            )

        if update_configs:
            CollectConfigMeta.objects.bulk_update(update_configs, ["cache_data"])

        # 排序
        if order:
            reverse = False
            if order.startswith("-"):
                order = order[1:]
                reverse = True

            try:
                search_list.sort(key=lambda x: x[order], reverse=reverse)
            except KeyError:
                pass

        # 获取插件类型
        type_list = [{"id": item[0], "name": item[1]} for item in COLLECT_TYPE_CHOICES]

        return {"type_list": type_list, "config_list": search_list, "total": total}


class CollectConfigDetailResource(Resource):
    """
    获取采集配置详细信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")

    @staticmethod
    def password_convert(collect_config_meta):
        """
        将密码类型的参数转换为一个bool值，用于规避f12可以看到明文密码
        @param collect_config_meta:
        @return:
        """
        config_json = collect_config_meta.deployment_config.plugin_version.config.config_json
        params = collect_config_meta.deployment_config.params
        for item in config_json:
            if item["mode"] != "collector":
                item["mode"] = "plugin"
            value = params.get(item["mode"], {}).get(item.get("key", item["name"])) or item["default"]
            # 获取敏感信息时采用bool值表示用户是否设置密码
            if item["type"] in ["password", "encrypt"]:
                params[item["mode"]][item["name"]] = bool(value)

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        config_id = validated_request_data["id"]
        try:
            collect_config_meta = CollectConfigMeta.objects.select_related("deployment_config").get(
                id=config_id, bk_biz_id=bk_biz_id
            )
        except CollectConfigMeta.DoesNotExist:
            raise CollectConfigNotExist({"msg": config_id})

        # 请求IP选择器接口，获取采集目标
        if (
            collect_config_meta.target_object_type == TargetObjectType.HOST
            and collect_config_meta.deployment_config.target_node_type == TargetNodeType.INSTANCE
        ):
            target_result = resource.commons.get_host_instance_by_ip(
                {
                    "bk_biz_id": collect_config_meta.bk_biz_id,
                    "bk_biz_ids": [collect_config_meta.bk_biz_id],
                    "ip_list": collect_config_meta.deployment_config.target_nodes,
                }
            )
        elif (
            collect_config_meta.target_object_type == TargetObjectType.HOST
            and collect_config_meta.deployment_config.target_node_type == TargetNodeType.TOPO
        ):
            node_list = []
            for item in collect_config_meta.deployment_config.target_nodes:
                item.update({"bk_biz_id": collect_config_meta.bk_biz_id})
                node_list.append(item)
            target_result = resource.commons.get_host_instance_by_node(
                {"bk_biz_id": collect_config_meta.bk_biz_id, "node_list": node_list}
            )
        elif collect_config_meta.target_object_type in [
            TargetObjectType.HOST,
            TargetObjectType.SERVICE,
        ] and collect_config_meta.deployment_config.target_node_type in [
            TargetNodeType.SERVICE_TEMPLATE,
            TargetNodeType.SET_TEMPLATE,
        ]:
            target_result = []
            templates = {
                template["bk_inst_id"]: template["bk_inst_name"]
                for template in resource.commons.get_template(
                    dict(
                        bk_biz_id=collect_config_meta.bk_biz_id,
                        bk_obj_id=collect_config_meta.deployment_config.target_node_type,
                        bk_inst_type=collect_config_meta.target_object_type,
                    )
                ).get("children", [])
            }
            for item in collect_config_meta.deployment_config.target_nodes:
                item.update({"bk_biz_id": collect_config_meta.bk_biz_id})
                item.update({"bk_inst_name": templates.get(item["bk_inst_id"])})
                target_result.append(item)
        elif (
            collect_config_meta.target_object_type == TargetObjectType.HOST
            and collect_config_meta.deployment_config.target_node_type == TargetNodeType.DYNAMIC_GROUP
        ):
            bk_inst_ids = []
            for item in collect_config_meta.deployment_config.target_nodes:
                bk_inst_ids.append(item["bk_inst_id"])
            target_result = api.cmdb.search_dynamic_group(
                bk_biz_id=collect_config_meta.bk_biz_id,
                bk_obj_id="host",
                dynamic_group_ids=bk_inst_ids,
                with_count=True,
            )

        else:
            node_list = []
            for item in collect_config_meta.deployment_config.target_nodes:
                item.update({"bk_biz_id": collect_config_meta.bk_biz_id})
                node_list.append(item)
            target_result = resource.commons.get_service_instance_by_node(
                {"bk_biz_id": collect_config_meta.bk_biz_id, "node_list": node_list}
            )
        config_version = collect_config_meta.deployment_config.plugin_version.config_version
        release_version = collect_config_meta.plugin.get_release_ver_by_config_ver(config_version)
        # 密码转为非明文
        self.password_convert(collect_config_meta)
        result = {
            "id": collect_config_meta.id,
            "deployment_id": collect_config_meta.deployment_config_id,
            "name": collect_config_meta.name,
            "bk_biz_id": collect_config_meta.bk_biz_id,
            "collect_type": collect_config_meta.collect_type,
            "label": collect_config_meta.label,
            "target_object_type": collect_config_meta.target_object_type,
            "target_node_type": collect_config_meta.deployment_config.target_node_type,
            "target_nodes": collect_config_meta.deployment_config.target_nodes,
            "params": collect_config_meta.deployment_config.params,
            "remote_collecting_host": collect_config_meta.deployment_config.remote_collecting_host,
            "plugin_info": release_version.get_plugin_version_detail(),
            "target": target_result,
            "subscription_id": collect_config_meta.deployment_config.subscription_id,
            "label_info": collect_config_meta.label_info,
            "create_time": collect_config_meta.create_time,
            "create_user": collect_config_meta.create_user,
            "update_time": collect_config_meta.update_time,
            "update_user": collect_config_meta.update_user,
        }
        return result


class RenameCollectConfigResource(Resource):
    """
    编辑采集配置的名称
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")
        name = serializers.CharField(label="名称")

    def perform_request(self, params: dict):
        CollectConfigMeta.objects.filter(id=params["id"], bk_biz_id=params["bk_biz_id"]).update(name=params["name"])
        return "success"


class ToggleCollectConfigStatusResource(Resource):
    """
    启停采集配置
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(required=True, label="采集配置ID")
        action = serializers.ChoiceField(required=True, choices=["enable", "disable"], label="启停配置")

    def perform_request(self, params: dict):
        config_id = params["id"]
        action = params["action"]

        try:
            collect_config = CollectConfigMeta.objects.select_related("deployment_config").get(
                bk_biz_id=params["bk_biz_id"], id=config_id
            )
        except CollectConfigMeta.DoesNotExist:
            raise CollectConfigNotExist({"msg": config_id})

        # 使用安装器启停采集配置
        installer = get_collect_installer(collect_config)
        if action == "enable":
            if collect_config.last_operation == OperationType.START:
                raise ToggleConfigStatusError({"msg": _("采集配置已处于启用状态，无需重复执行启用操作")})
            installer.start()
        else:
            if collect_config.last_operation == OperationType.STOP:
                raise ToggleConfigStatusError({"msg": _("采集配置已处于停用状态，无需重复执行停止操作")})
            installer.stop()

        return "success"


class DeleteCollectConfigResource(Resource):
    """
    删除采集配置
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")

    def perform_request(self, data):
        # 获取采集配置
        try:
            collect_config = CollectConfigMeta.objects.select_related("deployment_config").get(
                id=data["id"], bk_biz_id=data["bk_biz_id"]
            )
        except CollectConfigMeta.DoesNotExist:
            raise CollectConfigNotExist({"msg": data["id"]})

        # 删除采集配置
        installer = get_collect_installer(collect_config)
        installer.uninstall()

        # 内置链路健康策略处理
        # 如果用户还创建了其他的采集配置，则不会从告警组中移除
        username = get_global_user()
        bk_biz_id = collect_config.bk_biz_id
        configs_exist = CollectConfigMeta.objects.filter(bk_biz_id=bk_biz_id, create_user=username).exists()
        loader = DatalinkDefaultAlarmStrategyLoader(collect_config=collect_config, user_id=username)
        loader.delete(remove_user_from_group=not configs_exist)
        return None


class CloneCollectConfigResource(Resource):
    """
    克隆采集配置
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")

    def perform_request(self, data):
        # 获取采集配置
        data = resource.collecting.collect_config_detail(data)
        if (
            data["collect_type"] == CollectConfigMeta.CollectType.LOG
            or data["collect_type"] == CollectConfigMeta.CollectType.SNMP_TRAP
        ):
            #  判断重名
            new_name = name = data["name"] + "_copy"
            i = 1
            while CollectConfigMeta.objects.filter(bk_biz_id=data["bk_biz_id"], name=new_name):
                new_name = f"{name}({i})"  # noqa
                i += 1
            data["name"] = new_name
            data.pop("id")
            # 日志类的插件id在创建时是default_log
            data["plugin_id"] = "default_log"
            # 克隆任务不克隆目标节点
            data["target_nodes"] = []

            resource.collecting.save_collect_config(data)
            return

        try:
            collect_config = CollectConfigMeta.objects.select_related("deployment_config").get(
                id=data["id"], bk_biz_id=data["bk_biz_id"]
            )
        except CollectConfigMeta.DoesNotExist:
            raise CollectConfigNotExist({"msg": data["id"]})

        with transaction.atomic():
            # 克隆部署配置
            deployment_config = copy(collect_config.deployment_config)
            deployment_config.id = None
            # 克隆任务不克隆目标节点
            deployment_config.target_nodes = []
            deployment_config.subscription_id = 0
            deployment_config.save()
            # 克隆采集配置
            collect_config.id = None
            collect_config.deployment_config = deployment_config

            #  判断重名
            new_name = name = collect_config.name + "_copy"
            i = 1
            while CollectConfigMeta.objects.filter(bk_biz_id=data["bk_biz_id"], name=new_name):
                new_name = f"{name}({i})"
                i += 1
            collect_config.name = new_name

            # 清除目标节点统计
            collect_config.cache_data = {}
            # 设置任务状态为“正常”
            collect_config.last_operation = OperationType.CREATE
            collect_config.operation_result = OperationResult.SUCCESS
            collect_config.save()


class RetryTargetNodesResource(Resource):
    """
    重试部分实例或主机
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(required=True, label="采集配置ID")
        instance_id = serializers.CharField(required=True, label="需要重试的实例id")

    def perform_request(self, params: dict[str, Any]):
        try:
            collect_config = CollectConfigMeta.objects.select_related("deployment_config").get(
                id=params["id"], bk_biz_id=params["bk_biz_id"]
            )
        except CollectConfigMeta.DoesNotExist:
            raise CollectConfigNotExist({"msg": params["id"]})

        # 使用安装器重试实例
        installer = get_collect_installer(collect_config)
        installer.retry(instance_ids=[params["instance_id"]])

        return "success"


class RevokeTargetNodesResource(Resource):
    """
    终止部分部署中的实例
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")
        instance_ids = serializers.ListField(label="需要终止的实例ID")

    def perform_request(self, params: dict[str, Any]):
        try:
            collect_config = CollectConfigMeta.objects.select_related("deployment_config").get(
                id=params["id"], bk_biz_id=params["bk_biz_id"]
            )
        except CollectConfigMeta.DoesNotExist:
            raise CollectConfigNotExist({"msg": params["id"]})

        # 主动触发节点管理终止任务
        installer = get_collect_installer(collect_config)
        installer.revoke(instance_ids=params["instance_ids"])

        return "success"


class RunCollectConfigResource(Resource):
    """
    主动执行部分实例或节点
    """

    class RequestSerializer(serializers.Serializer):
        class ScopeParams(serializers.Serializer):
            node_type = serializers.ChoiceField(required=True, label="采集对象类型", choices=["TOPO", "INSTANCE"])
            nodes = serializers.ListField(required=True, label="节点列表")

        scope = ScopeParams(label="事件订阅监听的范围", required=False)
        action = serializers.CharField(label="操作", default="install")
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")

    def perform_request(self, params: dict[str, Any]):
        try:
            collect_config = CollectConfigMeta.objects.select_related("deployment_config").get(
                id=params["id"], bk_biz_id=params["bk_biz_id"]
            )
        except CollectConfigMeta.DoesNotExist:
            raise CollectConfigNotExist({"msg": params["id"]})

        # 主动触发节点管理终止任务
        installer = get_collect_installer(collect_config)
        installer.run(params["action"], params.get("scope"))

        return "success"


class BatchRevokeTargetNodesResource(Resource):
    """
    批量终止采集配置的部署中的实例
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")

    def perform_request(self, params: dict[str, Any]):
        try:
            collect_config = CollectConfigMeta.objects.select_related("deployment_config").get(
                id=params["id"], bk_biz_id=params["bk_biz_id"]
            )
        except CollectConfigMeta.DoesNotExist:
            raise CollectConfigNotExist({"msg": params["id"]})

        # 主动触发节点管理终止任务
        installer = get_collect_installer(collect_config)
        installer.revoke()

        return "success"


class GetCollectLogDetailResource(Resource):
    """
    获取采集下发单台主机/实例的详细日志信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")
        instance_id = serializers.CharField(label="主机/实例id")
        task_id = serializers.IntegerField(label="任务id")

    def perform_request(self, params: dict[str, Any]):
        try:
            config = CollectConfigMeta.objects.select_related("deployment_config").get(
                id=params["id"], bk_biz_id=params["bk_biz_id"]
            )
        except CollectConfigMeta.DoesNotExist:
            raise CollectConfigNotExist({"msg": params["id"]})

        installer = get_collect_installer(config)
        return installer.instance_status(params["instance_id"])


class BatchRetryConfigResource(Resource):
    """
    重试所有失败的实例
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(label="采集配置ID")

    def perform_request(self, params: dict[str, Any]):
        try:
            config = CollectConfigMeta.objects.select_related("deployment_config").get(
                id=params["id"], bk_biz_id=params["bk_biz_id"]
            )
        except CollectConfigMeta.DoesNotExist:
            raise CollectConfigNotExist({"msg": params["id"]})

        installer = get_collect_installer(config)
        installer.retry()

        return "success"


class SaveCollectConfigResource(Resource):
    """
    新增或编辑采集配置
    """

    class RequestSerializer(serializers.Serializer):
        class RemoteCollectingSlz(serializers.Serializer):
            ip = serializers.CharField(required=False)
            bk_cloud_id = serializers.IntegerField(required=False)
            bk_host_id = serializers.IntegerField(required=False)
            bk_supplier_id = serializers.IntegerField(required=False)
            is_collecting_only = serializers.BooleanField(required=True)

            def validate(self, attrs):
                if "bk_host_id" not in attrs and not ("ip" in attrs and "bk_cloud_id" in attrs):
                    raise serializers.ValidationError(_("主机id和ip/bk_cloud_id不能同时为空"))
                return attrs

        class MetricRelabelConfigSerializer(serializers.Serializer):
            """指标重新标记配置对应的模板变量序列化器。

            对应模板
            {% if metric_relabel_configs %}
                metric_relabel_configs:
            {% for config in metric_relabel_configs %}
                 - source_labels: [{{ config.source_labels | join("', '") }}]
                    {% if config.regex %}regex: '{{ config.regex }}'{% endif %}
                    action: {{ config.action }}
                    {% if config.target_label %}target_label: '{{ config.target_label }}'{% endif %}
                    {% if config.replacement %}replacement: '{{ config.replacement }}'{% endif %}
            {% endfor %}
            {% endif %}
            """

            source_labels = serializers.ListField(child=serializers.CharField(), label="源标签列表")
            regex = serializers.CharField(label="正则表达式")
            action = serializers.CharField(required=False, label="操作类型")
            target_label = serializers.CharField(required=False, label="目标标签")
            replacement = serializers.CharField(required=False, label="替换内容")

        id = serializers.IntegerField(required=False, label="采集配置ID")
        name = serializers.CharField(required=True, label="采集配置名称")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        collect_type = serializers.ChoiceField(
            required=True, label="采集方式", choices=CollectConfigMeta.COLLECT_TYPE_CHOICES
        )
        target_object_type = serializers.ChoiceField(
            required=True, label="采集对象类型", choices=CollectConfigMeta.TARGET_OBJECT_TYPE_CHOICES
        )
        target_node_type = serializers.ChoiceField(
            required=True, label="采集目标类型", choices=DeploymentConfigVersion.TARGET_NODE_TYPE_CHOICES
        )
        plugin_id = serializers.CharField(required=True, label="插件ID")
        target_nodes = serializers.ListField(required=True, label="节点列表", allow_empty=True)
        remote_collecting_host = RemoteCollectingSlz(
            required=False, allow_null=True, default=None, label="远程采集配置"
        )
        params = serializers.DictField(required=True, label="采集配置参数")
        label = serializers.CharField(required=True, label="二级标签")
        operation = serializers.ChoiceField(default="EDIT", choices=["EDIT", "ADD_DEL"], label="操作类型")
        # 供第三方接口调用
        metric_relabel_configs = MetricRelabelConfigSerializer(many=True, default=list, label="指标重新标记配置")

        def validate(self, attrs):
            # 校验采集对象类型和采集目标类型搭配是否正确，且不同类型的节点列表字段正确
            # 校验业务拓扑和服务拓扑
            target_type = (attrs["target_object_type"], attrs["target_node_type"])
            if target_type in [
                (TargetObjectType.HOST, TargetNodeType.TOPO),
                (TargetObjectType.SERVICE, TargetNodeType.TOPO),
            ]:
                for node in attrs["target_nodes"]:
                    if not ("bk_inst_id" in node and "bk_obj_id" in node):
                        raise serializers.ValidationError("target_nodes needs bk_inst_id and bk_obj_id")
            # 校验主机实例
            elif target_type == (TargetObjectType.HOST, TargetNodeType.INSTANCE):
                for node in attrs["target_nodes"]:
                    if "bk_target_ip" in node and "bk_target_cloud_id" in node:
                        node["ip"] = node.pop("bk_target_ip")
                        node["bk_cloud_id"] = node.pop("bk_target_cloud_id")

                    if not ("ip" in node and "bk_cloud_id" in node) and "bk_host_id" not in node:
                        raise serializers.ValidationError("target_nodes needs ip, bk_cloud_id or bk_host_id")
            # 校验服务模板、集群模板
            elif target_type in [
                (TargetObjectType.HOST, TargetNodeType.SERVICE_TEMPLATE),
                (TargetObjectType.HOST, TargetNodeType.SET_TEMPLATE),
                (TargetObjectType.SERVICE, TargetNodeType.SET_TEMPLATE),
                (TargetObjectType.SERVICE, TargetNodeType.SERVICE_TEMPLATE),
            ]:
                for node in attrs["target_nodes"]:
                    if not ("bk_inst_id" in node and "bk_obj_id" in node):
                        raise serializers.ValidationError("target_nodes needs bk_inst_id, bk_obj_id")
            elif target_type == (TargetObjectType.CLUSTER, TargetNodeType.CLUSTER):
                for node in attrs["target_nodes"]:
                    if "bcs_cluster_id" not in node:
                        raise serializers.ValidationError("target_nodes needs bcs_cluster_id")
            elif attrs["target_node_type"] == TargetNodeType.DYNAMIC_GROUP:
                for node in attrs["target_nodes"]:
                    if not ("bk_inst_id" in node and "bk_obj_id" in node):
                        raise serializers.ValidationError("target_nodes needs bk_inst_id, bk_obj_id")
            else:
                raise serializers.ValidationError(
                    "{} {} is not supported".format(attrs["target_object_type"], attrs["target_node_type"])
                )

            # 目标字段整理
            target_nodes = []
            for node in attrs["target_nodes"]:
                if "bk_host_id" in node:
                    target_nodes.append({"bk_host_id": node["bk_host_id"]})
                elif "bk_inst_id" in node and "bk_obj_id" in node:
                    target_nodes.append({"bk_inst_id": node["bk_inst_id"], "bk_obj_id": node["bk_obj_id"]})
                    if "bk_biz_id" in node:
                        target_nodes[-1]["bk_biz_id"] = node["bk_biz_id"]
                elif "bcs_cluster_id" in node:
                    target_nodes.append({"bcs_cluster_id": node["bcs_cluster_id"]})
            attrs["target_nodes"] = target_nodes

            # 日志关键字规则名称去重
            if attrs["collect_type"] == CollectConfigMeta.CollectType.LOG:
                rules = attrs["params"]["log"]["rules"]

                name_set = set()
                for rule in rules:
                    rule_name = rule["name"]
                    if rule_name in name_set:
                        raise CollectConfigParamsError(msg=f"Duplicate keyword rule name({rule_name})")
                    name_set.add(rule_name)

            # 克隆时 插件 bk-pull 密码不能为bool
            if not attrs.get("id") and attrs["collect_type"] == CollectConfigMeta.CollectType.PUSHGATEWAY:
                password = attrs["params"]["collector"].get("password")
                if password is True:
                    raise serializers.ValidationError("Please reset your password")  # 表示需要重置密码
                elif password is False:
                    # 将如果密码为空则设为空密码
                    attrs["params"]["collector"]["password"] = ""

            return attrs

    def perform_request(self, data):
        try:
            collector_plugin = self.get_collector_plugin(data)
        except CollectorPluginMeta.DoesNotExist:
            raise PluginIDNotExist

        data["params"]["target_node_type"] = data["target_node_type"]
        data["params"]["target_object_type"] = data["target_object_type"]
        data["params"]["collector"]["metric_relabel_configs"] = data.pop("metric_relabel_configs")

        # 获取或新建采集配置
        if data.get("id"):
            try:
                collect_config = CollectConfigMeta.objects.get(bk_biz_id=data["bk_biz_id"], id=data["id"])
            except CollectConfigMeta.DoesNotExist:
                raise CollectConfigNotExist({"msg": data["id"]})
            # 密码字段处理
            self.update_password_inplace(data, collect_config)
            collect_config.name = data["name"]
        else:
            collect_config = CollectConfigMeta(
                bk_tenant_id=get_request_tenant_id(),
                bk_biz_id=data["bk_biz_id"],
                name=data["name"],
                last_operation=OperationType.CREATE,
                operation_result=OperationResult.PREPARING,
                collect_type=data["collect_type"],
                plugin_id=collector_plugin.plugin_id,
                target_object_type=data["target_object_type"],
                label=data["label"],
            )
            data["operation"] = OperationType.CREATE

        # 部署
        installer = get_collect_installer(collect_config)
        try:
            result = installer.install(data, data["operation"])
        except Exception as err:
            logger.error(err)

            # 如果是新建采集配置，需要尝试回滚结果表
            if collect_config.last_operation == OperationType.CREATE:
                self.roll_back_result_table(collector_plugin)
            raise err

        # 添加完成采集配置，主动更新指标缓存表
        self.update_metric_cache(collector_plugin)

        # 采集配置完成
        try:
            DatalinkDefaultAlarmStrategyLoader(collect_config=collect_config, user_id=get_global_user()).run()
        except Exception as error:
            logger.error(f"自动创建默认告警策略 DatalinkDefaultAlarmStrategyLoader error {str(error)}")

        return result

    @staticmethod
    def update_password_inplace(data: dict, config_meta: "CollectConfigMeta") -> None:
        """将密码参数的值替换为实际值。"""
        config_params = config_meta.plugin.current_version.config.config_json
        deployment_params = config_meta.deployment_config.params

        for param in config_params:
            if param["type"] not in ["password", "encrypt"]:
                continue

            param_name = param["name"]
            param_mode = "plugin" if param["mode"] != "collector" else "collector"
            received_password = data["params"][param_mode].get(param_name)

            # mode 为 "plugin" 时，如果密码不改变，不会传入，获取到 None
            # mode 为 "collector" 时，如果密码不改变，传入值为 bool 类型（由详情接口返回的）
            # 这两种情况要替换为实际值（默认值兜底）
            if isinstance(received_password, type(None) | bool):
                default_password = param["default"]
                actual_password = deployment_params[param_mode].get(param_name, default_password)
                data["params"][param_mode][param_name] = actual_password

    @staticmethod
    def get_collector_plugin(data) -> CollectorPluginMeta:
        bk_tenant_id = get_request_tenant_id()
        plugin_id = data["plugin_id"]
        # 虚拟日志采集器
        if data["collect_type"] == CollectConfigMeta.CollectType.LOG:
            label = data["label"]
            bk_biz_id = data["bk_biz_id"]
            rules = data["params"]["log"]["rules"]
            if "id" not in data:
                plugin_id = "log_" + str(shortuuid.uuid())
                plugin_manager = PluginManagerFactory.get_manager(
                    bk_tenant_id=bk_tenant_id, plugin=plugin_id, plugin_type=PluginType.LOG
                )
                params = plugin_manager.get_params(plugin_id, bk_biz_id, label, rules=rules)
                resource.plugin.create_plugin(params)
            else:
                plugin_manager = PluginManagerFactory.get_manager(
                    bk_tenant_id=bk_tenant_id, plugin=plugin_id, plugin_type=PluginType.LOG
                )
                params = plugin_manager.get_params(plugin_id, bk_biz_id, label, rules=rules)
                plugin_manager.update_version(params)
        # 虚拟进程采集器
        elif data["collect_type"] == CollectConfigMeta.CollectType.PROCESS:
            plugin_manager = PluginManagerFactory.get_manager(
                bk_tenant_id=bk_tenant_id, plugin="bkprocessbeat", plugin_type=PluginType.PROCESS
            )
            # 全局唯一
            plugin_manager.touch()
            plugin_id = plugin_manager.plugin.plugin_id
        elif data["collect_type"] == CollectConfigMeta.CollectType.SNMP_TRAP:
            plugin_id = resource.collecting.get_trap_collector_plugin(data)
        elif data["collect_type"] == CollectConfigMeta.CollectType.K8S:
            qcloud_exporter_plugin_id = f"{settings.TENCENT_CLOUD_METRIC_PLUGIN_ID}_{data['bk_biz_id']}"

            # 仅支持腾讯云指标采集
            if plugin_id not in [settings.TENCENT_CLOUD_METRIC_PLUGIN_ID, qcloud_exporter_plugin_id]:
                raise ValueError(f"Only support {settings.TENCENT_CLOUD_METRIC_PLUGIN_ID} k8s collector")

            plugin_id = qcloud_exporter_plugin_id

            # 检查是否配置了腾讯云指标插件配置
            if not settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG:
                raise ValueError("TENCENT_CLOUD_METRIC_PLUGIN_CONFIG is not set, please contact administrator")

            plugin_config: dict[str, Any] = settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG
            plugin_params = {
                "plugin_id": plugin_id,
                "bk_biz_id": data["bk_biz_id"],
                "plugin_type": PluginType.K8S,
                "label": plugin_config.get("label", "os"),
                "plugin_display_name": _(plugin_config.get("plugin_display_name", "腾讯云指标采集")),
                "description_md": plugin_config.get("description_md", ""),
                "logo": plugin_config.get("logo", ""),
                "version_log": plugin_config.get("version_log", ""),
                "metric_json": [],
                "collector_json": plugin_config["collector_json"],
                "config_json": plugin_config.get("config_json", []),
                "data_label": settings.TENCENT_CLOUD_METRIC_PLUGIN_ID,
            }

            # 检查是否已经创建了腾讯云指标采集插件
            if CollectorPluginMeta.objects.filter(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id).exists():
                # 更新插件
                plugin_manager = PluginManagerFactory.get_manager(
                    bk_tenant_id=bk_tenant_id, plugin=plugin_id, plugin_type=PluginType.K8S
                )
                plugin_manager.update_version(plugin_params)
            else:
                # 创建插件
                resource.plugin.create_plugin(plugin_params)

        return CollectorPluginMeta.objects.get(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)

    @staticmethod
    def roll_back_result_table(collector_plugin: CollectorPluginMeta):
        plugin_type = collector_plugin.plugin_type
        if plugin_type in collector_plugin.VIRTUAL_PLUGIN_TYPE and plugin_type != PluginType.K8S:
            plugin_manager = PluginManagerFactory.get_manager(plugin=collector_plugin, plugin_type=plugin_type)
            plugin_manager.delete_result_table(collector_plugin.release_version)

    @staticmethod
    def update_metric_cache(collector_plugin: CollectorPluginMeta):
        plugin_type = collector_plugin.plugin_type
        if plugin_type not in collector_plugin.VIRTUAL_PLUGIN_TYPE:
            version = collector_plugin.current_version
            metric_json = version.info.metric_json
            result_table_id_list = [
                "{}_{}.{}".format(
                    collector_plugin.plugin_type.lower(), collector_plugin.plugin_id, metric_msg["table_name"]
                )
                for metric_msg in metric_json
            ]
            append_metric_list_cache.delay(collector_plugin.bk_tenant_id, result_table_id_list)


class UpgradeCollectPluginResource(Resource):
    """
    采集配置插件升级
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(required=True, label="采集配置id")
        params = serializers.DictField(required=True, label="采集配置参数")
        realtime = serializers.BooleanField(required=False, default=False, label=_("是否实时刷新缓存"))

    def perform_request(self, data):
        # 判断是否需要实时刷新缓存
        if data["realtime"]:
            # 调用 collect_config_list 接口刷新采集配置的缓存，避免外部调接口可能会无法更新插件
            resource.collecting.collect_config_list(
                page=-1, refresh_status=True, search={"id": data["id"]}, bk_biz_id=data["bk_biz_id"]
            )

        try:
            collect_config = CollectConfigMeta.objects.select_related("deployment_config").get(
                pk=data["id"], bk_biz_id=data["bk_biz_id"]
            )
            SaveCollectConfigResource.update_password_inplace(data, collect_config)
        except CollectConfigMeta.DoesNotExist:
            raise CollectConfigNotExist({"msg": data["id"]})

        # 安装器执行升级操作
        installer = get_collect_installer(collect_config)
        result = installer.upgrade(data["params"])

        # 升级采集配置，主动更新指标缓存表
        result_table_id_list = [
            "{}_{}.{}".format(collect_config.collect_type.lower(), collect_config.plugin_id, metric_msg["table_name"])
            for metric_msg in collect_config.plugin.current_version.info.metric_json
        ]
        append_metric_list_cache.delay(get_request_tenant_id(), result_table_id_list)

        return result


class RollbackDeploymentConfigResource(Resource):
    """
    采集配置回滚
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(required=True, label="采集配置id")

    def perform_request(self, data):
        try:
            collect_config = CollectConfigMeta.objects.select_related("deployment_config").get(
                bk_biz_id=data["bk_biz_id"], pk=data["id"]
            )
        except CollectConfigMeta.DoesNotExist:
            raise CollectConfigNotExist({"msg": data["id"]})

        # 判断是否支持回滚
        if not collect_config.allow_rollback:
            raise CollectConfigRollbackError({"msg": _("当前操作不支持回滚，或采集配置正处于执行中")})

        installer = get_collect_installer(collect_config)
        result = installer.rollback()

        return result


class GetMetricsResource(Resource):
    """
    获取对应插件版本的指标参数
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        id = serializers.IntegerField(required=True, label="采集配置id")

    def perform_request(self, validated_request_data):
        try:
            collect_config = CollectConfigMeta.objects.select_related("deployment_config").get(
                bk_biz_id=validated_request_data["bk_biz_id"], id=validated_request_data["id"]
            )
        except CollectConfigMeta.DoesNotExist:
            raise CollectConfigNotExist({"msg": validated_request_data["id"]})
        return collect_config.deployment_config.metrics


class CollectConfigInfoResource(Resource):
    """
    提供给kernel api使用，查询collect_config_meta表的信息
    """

    def perform_request(self, data):
        return list(CollectConfigMeta.objects.all().values())


class BatchRetryResource(BatchRetryConfigResource):
    """详情页"""

    pass
