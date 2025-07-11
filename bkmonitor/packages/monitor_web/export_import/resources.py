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

import copy
import csv
import datetime
import json
import logging
import os
import shutil
import tarfile
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Dict
from uuid import uuid4

from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models import Q
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

from bk_dataview.api import get_or_create_org
from bkmonitor.models import ItemModel, QueryConfigModel, StrategyModel
from bkmonitor.utils.request import get_request, get_request_tenant_id
from bkmonitor.utils.text import convert_filename
from bkmonitor.utils.time_tools import now
from bkmonitor.utils.user import get_local_username
from bkmonitor.views import serializers
from constants.strategy import TargetFieldType
from core.drf_resource import Resource, api, resource
from core.drf_resource.tasks import step
from core.errors.export_import import (
    AddTargetError,
    ImportConfigError,
    ImportHistoryNotExistError,
    UploadPackageError,
)
from monitor_web.commons.cc.utils import CmdbUtil
from monitor_web.commons.file_manager import ExportImportManager
from monitor_web.commons.report.resources import send_frontend_report_event
from monitor_web.export_import.constant import (
    DIRECTORY_LIST,
    ConfigType,
    ImportDetailStatus,
    ImportHistoryStatus,
)
from monitor_web.export_import.import_config import get_strategy_config, get_view_config
from monitor_web.export_import.parse_config import (
    CollectConfigParse,
    StrategyConfigParse,
    ViewConfigParse,
)
from monitor_web.models import (
    CollectConfigMeta,
    CollectorPluginMeta,
    ImportDetail,
    ImportHistory,
    ImportParse,
    TargetNodeType,
    TargetObjectType,
    UploadedFileInfo,
)
from monitor_web.plugin.manager import PluginManagerFactory
from monitor_web.strategies.serializers import handle_target, is_validate_target
from monitor_web.tasks import import_config, remove_file

logger = logging.getLogger("monitor_web")


class GetAllConfigListResource(Resource):
    """
    获取采集配置、策略配置、视图配置列表
    """

    def __init__(self):
        super(GetAllConfigListResource, self).__init__()
        self.node_manager = None
        self.collect_config_list = None
        self.strategy_config_list = None
        self.view_config_list = None
        self.node_filter_manager = None

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        service_category_id = serializers.IntegerField(required=False, label="服务分类")
        label = serializers.CharField(required=False, label="标签")
        cmdb_node = serializers.CharField(required=False, label="节点信息")
        search_value = serializers.CharField(required=False, label="模糊搜索字段")

    def search_collect_config_by_node(self, cmdb_node):
        # 根据节点信息筛选采集配置
        collect_config_ids = []
        collect_config_meta = self.collect_config_list.select_related("deployment_config")
        for collect_config in collect_config_meta:
            if cmdb_node in [
                "{}|{}".format(x.get("bk_obj_id"), x.get("bk_inst_id"))
                for x in collect_config.deployment_config.target_nodes
            ]:
                collect_config_ids.append(collect_config.deployment_config.config_meta_id)

        self.collect_config_list = self.collect_config_list.filter(id__in=collect_config_ids)

    def search_strategy_config_by_node(self, cmdb_node):
        # 根据节点信息筛选策略配置
        strategy_config_ids = []
        items = ItemModel.objects.filter(strategy_id__in=[strategy.id for strategy in self.strategy_config_list])
        for item in items:
            if not item.target or not item.target[0]:
                continue

            target = item.target[0][0]
            target_node_list = []
            if target.get("field") in [TargetFieldType.host_topo, TargetFieldType.service_topo]:
                target_node_list = [
                    "{}|{}".format(x.get("bk_obj_id"), x.get("bk_inst_id")) for x in target.get("value")
                ]

            if cmdb_node in target_node_list:
                strategy_config_ids.append(item.strategy_id)

        self.strategy_config_list = self.strategy_config_list.filter(id__in=strategy_config_ids)

    def search_config_by_svc_category_id(self, bk_biz_id, service_category_id):
        # 根据服务分类节点筛选配置

        collect_config_ids = []
        strategy_config_ids = []
        for collect_config in self.collect_config_list:
            service_category_ids = []
            if collect_config.deployment_config.target_node_type == TargetNodeType.TOPO:
                service_category_ids = set(
                    self.node_filter_manager.get_category_list(
                        collect_config.bk_biz_id, collect_config.deployment_config.target_nodes
                    )
                )
            if {service_category_id} & set(service_category_ids):
                collect_config_ids.append(collect_config.id)

        items = ItemModel.objects.filter(strategy_id__in=[strategy.id for strategy in self.strategy_config_list])
        for item in items:
            if not item.target or not item.target[0]:
                continue

            target = item.target[0][0]
            if target.get("field") not in [TargetFieldType.host_topo, TargetFieldType.service_topo]:
                continue

            service_category_ids = set(self.node_filter_manager.get_category_list(bk_biz_id, target.get("value")))
            if {service_category_id} & set(service_category_ids):
                strategy_config_ids.append(item.strategy_id)

        self.collect_config_list = self.collect_config_list.filter(id__in=collect_config_ids)
        self.strategy_config_list = self.strategy_config_list.filter(id__in=strategy_config_ids)

    def handle_return_data(self):
        return_data = dict([("collect_config_list", []), ("strategy_config_list", []), ("view_config_list", [])])
        for collect_config in self.collect_config_list:
            return_data["collect_config_list"].append(
                {"id": collect_config.id, "name": collect_config.name, "dependency_plugin": collect_config.plugin_id}
            )

        strategy_ids = [strategy.id for strategy in self.strategy_config_list]
        strategy_items = {item.id: item for item in ItemModel.objects.filter(strategy_id__in=strategy_ids)}
        strategy_query_configs = defaultdict(list)
        for query_config in QueryConfigModel.objects.filter(item_id__in=list(strategy_items.keys())):
            item = strategy_items[query_config.item_id]
            strategy_query_configs[item.strategy_id].append(query_config)

        for strategy_config in self.strategy_config_list:
            query_configs = strategy_query_configs.get(strategy_config.id, [])
            collect_config_list = []
            for query_config in query_configs:
                collect_config_list.extend(
                    [
                        condition.get("bk_collect_config_id")
                        for condition in query_config.config.get("agg_condition", [])
                        if condition.get("bk_collect_config_id")
                    ]
                )

            return_data["strategy_config_list"].append(
                {
                    "id": strategy_config.id,
                    "name": strategy_config.name,
                    "dependency_collect_config": ",".join(
                        list(
                            {collect_config_name for collect_config_name in collect_config_list if collect_config_name}
                        )
                    ),
                }
            )

        for view_config in self.view_config_list:
            collect_config_list = []
            return_data["view_config_list"].append(
                {
                    "id": view_config["uid"],
                    "name": view_config["name"],
                    "dependency_collect_config": collect_config_list,
                }
            )

        return return_data

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        self.node_filter_manager = CmdbUtil(bk_biz_id)
        service_category_id = validated_request_data.get("service_category_id", "")
        label = validated_request_data.get("label", "")
        cmdb_node = validated_request_data.get("cmdb_node", "")
        search_value = validated_request_data.get("search_value", "")
        self.collect_config_list = CollectConfigMeta.objects.filter(bk_biz_id=bk_biz_id, label__icontains=label)
        self.strategy_config_list = StrategyModel.objects.filter(bk_biz_id=bk_biz_id, scenario__icontains=label)
        try:
            self.view_config_list = resource.grafana.get_dashboard_list(bk_biz_id=bk_biz_id)
        except Exception:
            self.view_config_list = []

        if cmdb_node:
            self.search_collect_config_by_node(cmdb_node)
            self.search_strategy_config_by_node(cmdb_node)

        if service_category_id:
            self.search_config_by_svc_category_id(bk_biz_id, service_category_id)

        if search_value:
            self.collect_config_list = self.collect_config_list.filter(
                Q(id__icontains=search_value) | Q(name__icontains=search_value)
            )
            self.strategy_config_list = self.strategy_config_list.filter(
                Q(id__icontains=search_value) | Q(name__icontains=search_value)
            )
            self.view_config_list = [
                view_config
                for view_config in self.view_config_list
                if search_value.lower() in view_config["name"].lower()
                or search_value.lower() in str(view_config["uid"]).lower()
            ]

        return self.handle_return_data()


class ExportPackageRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
    collect_config_ids = serializers.ListField(required=False, allow_empty=True, label="需要导出的采集配置ID列表")
    strategy_config_ids = serializers.ListField(required=False, allow_empty=True, label="需要导出的策略配置ID列表")
    view_config_ids = serializers.ListField(required=False, allow_empty=True, label="需要导出的视图配置ID列表")
    list_data = serializers.ListField(required=False, allow_empty=True, label="需转为csv的列表数据")

    def validate(self, attrs):
        # 如果不是需要列表转csv，则必须传业务ID
        if not attrs.get("list_data") and not attrs.get("bk_biz_id"):
            raise ValidationError(_("业务ID不可为空"))
        return attrs


class ExportPackageResource(Resource):
    """
    导出文件包
    """

    def __init__(self):
        super(ExportPackageResource, self).__init__()
        self.collect_config_ids = []
        self.strategy_config_ids = []
        self.view_config_ids = []
        self.associated_plugin_list = []
        self.associated_collect_config_list = []
        self.list_data = []
        self.bk_biz_id = None
        self.username = ""
        self.tmp_path = os.path.join(settings.MEDIA_ROOT, "export_import", "tmp")
        self.package_path = ""
        self.package_name = ""
        self.file_msg = {}
        self.RequestSerializer = ExportPackageRequestSerializer

    def perform_request(self, validated_request_data):
        self.bk_biz_id = validated_request_data["bk_biz_id"]
        self.package_name = "bk_monitor_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
        self.package_path = os.path.join(self.tmp_path, self.package_name)
        self.collect_config_ids = validated_request_data.get("collect_config_ids", [])
        self.strategy_config_ids = validated_request_data.get("strategy_config_ids", [])
        self.view_config_ids = validated_request_data.get("view_config_ids", [])
        self.list_data = validated_request_data.get("list_data", [])
        if not any([self.collect_config_ids, self.strategy_config_ids, self.view_config_ids, self.list_data]):
            raise ValidationError(_("未选择任何配置"))

        self.file_msg = self.prepare_file()
        filename = self.make_package()
        download_path, download_name = filename.replace(settings.MEDIA_ROOT, "").rsplit("/", 1)

        if settings.USE_CEPH:
            local_tar_file_path = os.path.join(self.package_path, filename)
            tar_file_fd = open(local_tar_file_path, "rb")
            tar_file_path = local_tar_file_path.replace(settings.MEDIA_ROOT, "")
            default_storage.save(tar_file_path, tar_file_fd)
            download_path, download_name = default_storage.url(tar_file_path).rsplit("/", 1)
            tar_file_fd.close()

        # 如果当前PAAS_HOST是以https://开头的，则需要将download_path中的http://替换为https://
        if settings.BK_MONITOR_HOST.startswith("https://"):
            download_path = download_path.replace("http://", "https://")

        # 五分钟后删除文件夹
        remove_file.apply_async(args=(self.package_path,), countdown=300)

        try:
            username = get_local_username() or ""
            event_content = (
                "导出"
                + f"{len(self.collect_config_ids)}条采集配置,"
                + f"{len(self.strategy_config_ids)}个策略配置,"
                + f"{len(self.view_config_ids)}个仪表盘"
            )
            send_frontend_report_event(self, self.bk_biz_id, username, event_content)
        except Exception as e:
            logger.exception(f"send frontend report event error: {e}")

        return {"download_path": download_path, "download_name": download_name}

    @step(state="PREPARE_FILE", message=_("准备文件中..."))
    def prepare_file(self):
        collect_config_file = len(self.collect_config_ids)
        strategy_config_file = len(self.strategy_config_ids)
        view_config_file = len(self.view_config_ids)

        strategy_config_list = StrategyModel.objects.filter(id__in=self.strategy_config_ids)
        for strategy_config in strategy_config_list:
            item_instances = ItemModel.objects.filter(strategy_id=strategy_config.id)
            query_configs = QueryConfigModel.objects.filter(item_id__in=list({item.id for item in item_instances}))
            for query_config in query_configs:
                for condition in query_config.config.get("agg_condition", []):
                    if "bk_collect_config_id" not in list(condition.values()):
                        continue
                    if isinstance(condition["value"], list):
                        self.associated_collect_config_list.extend(condition["value"])
                    else:
                        self.associated_collect_config_list.append(condition["value"].split("(")[0])

        self.associated_collect_config_list = list(set(self.associated_collect_config_list))
        self.associated_collect_config_list = [i for i in self.associated_collect_config_list if i]

        all_collect_ids = list(set(self.collect_config_ids + self.associated_collect_config_list))
        self.associated_plugin_list = list(
            {
                config.plugin_id
                for config in CollectConfigMeta.objects.filter(bk_biz_id=self.bk_biz_id, id__in=all_collect_ids)
            }
        )
        associated_plugin = len(self.associated_plugin_list)
        return {
            "collect_config_file": collect_config_file,
            "strategy_config_file": strategy_config_file,
            "view_config_file": view_config_file,
            "associated_plugin": associated_plugin,
            "associated_collect_config": len(self.associated_collect_config_list),
        }

    def make_collect_config(self):
        self.collect_config_ids.extend(self.associated_collect_config_list)
        all_collect_config_ids = list(set(self.collect_config_ids))
        if not all_collect_config_ids:
            return

        os.makedirs(os.path.join(self.package_path, "collect_config_directory"))
        collect_configs = CollectConfigMeta.objects.select_related("deployment_config").filter(
            bk_biz_id=self.bk_biz_id, id__in=all_collect_config_ids
        )
        for collect_config_meta in collect_configs:
            collect_config_detail = {
                "id": collect_config_meta.id,
                "name": collect_config_meta.name,
                "bk_biz_id": collect_config_meta.bk_biz_id,
                "collect_type": collect_config_meta.collect_type,
                "label": collect_config_meta.label,
                "target_object_type": collect_config_meta.target_object_type,
                "target_node_type": collect_config_meta.deployment_config.target_node_type,
                "target_nodes": collect_config_meta.deployment_config.target_nodes,
                "params": collect_config_meta.deployment_config.params,
                "plugin_id": collect_config_meta.deployment_config.plugin_version.plugin_id,
                "subscription_id": collect_config_meta.deployment_config.subscription_id,
                "label_info": collect_config_meta.label_info,
            }
            collect_config_file_name = collect_config_detail.get("name")

            with open(
                os.path.join(
                    self.package_path,
                    "collect_config_directory",
                    "{}_{}.json".format(convert_filename(collect_config_file_name), collect_config_meta.id),
                ),
                "w",
            ) as fs:
                fs.write(json.dumps(collect_config_detail, indent=4))

    def make_list_to_csv_file(self):
        if not self.list_data:
            return
        os.makedirs(os.path.join(self.package_path, "csv_files"))
        with open(
            os.path.join(
                self.package_path,
                "csv_files",
                "{}.csv".format(uuid.uuid4()),
            ),
            "w",
            encoding="utf-8-sig",
        ) as fs:
            writer = csv.DictWriter(fs, fieldnames=self.list_data[0].keys())
            writer.writeheader()
            for data in self.list_data:
                writer.writerow(data)

    def make_plugin_file(self):
        if not self.associated_plugin_list:
            return
        bk_tenant_id = get_request_tenant_id()
        plugin_file_path = os.path.join(self.package_path, "plugin_directory")
        os.makedirs(plugin_file_path)
        for plugin_id in self.associated_plugin_list:
            plugin = CollectorPluginMeta.objects.filter(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id).first()
            plugin_manager = PluginManagerFactory.get_manager(
                bk_tenant_id=bk_tenant_id, plugin=plugin, tmp_path=plugin_file_path
            )
            plugin_manager.version = plugin.current_version
            plugin_manager.make_package(need_tar=False)

    def make_view_config_file(self):
        if not self.view_config_ids:
            return

        dashboard_file_path = os.path.join(self.package_path, "view_config_directory")
        os.makedirs(dashboard_file_path)

        view_config = get_view_config(self.bk_biz_id, self.view_config_ids)

        # 仪表盘数据导出处理流程
        for uid, config in view_config.items():
            dashboard = config["dashboard"]
            view_config_file_name = dashboard.get("title", "dashboard")

            with open(
                os.path.join(
                    self.package_path,
                    "view_config_directory",
                    "{}_{}.json".format(convert_filename(view_config_file_name), uid),
                ),
                "w",
            ) as fs:
                fs.write(json.dumps(dashboard, indent=2, ensure_ascii=False))

    def make_strategy_config_file(self):
        if not self.strategy_config_ids:
            return

        # 创建策略配置存储目录
        os.makedirs(os.path.join(self.package_path, "strategy_config_directory"))
        # 获取策略配置列表
        strategy_configs = get_strategy_config(self.bk_biz_id, self.strategy_config_ids)

        for config in strategy_configs:
            strategy_config_file_name = config.get("name")
            strategy_id = config.pop("id")
            # 写入处理后的策略配置到文件
            with open(
                os.path.join(
                    self.package_path,
                    "strategy_config_directory",
                    "{}_{}.json".format(convert_filename(strategy_config_file_name), strategy_id),
                ),
                "w",
            ) as fs:
                fs.write(json.dumps(config, indent=4))

    @step(state="MAKE_PACKAGE", message=_("文件打包中..."))
    def make_package(self):
        self.update_state(state="MAKE_PACKAGE", message=_("文件打包中..."), data=self.file_msg)
        os.makedirs(self.package_path)
        self.make_collect_config()
        self.make_plugin_file()
        self.make_strategy_config_file()
        self.make_view_config_file()
        self.make_list_to_csv_file()
        t = tarfile.open(os.path.join(self.package_path, self.package_name + ".tar.gz"), "w:gz")
        for root, dirs, files in os.walk(self.package_path):
            for filename in files:
                full_path = os.path.join(root, filename)
                file_save_path = full_path.replace(self.package_path, "")
                t.add(full_path, arcname=file_save_path)
        t.close()
        return t.name

    @step(state="MAKE_PACKAGE", message=_("文件打包中..."))
    def make_csv_package(self):
        self.update_state(state="MAKE_PACKAGE", message=_("文件打包中..."), data=self.file_msg)
        os.makedirs(self.package_path)
        self.make_list_to_csv_file()
        t = tarfile.open(os.path.join(self.package_path, self.package_name + ".tar.gz"), "w:gz")
        for root, dirs, files in os.walk(self.package_path):
            for filename in files:
                full_path = os.path.join(root, filename)
                file_save_path = full_path.replace(self.package_path, "")
                t.add(full_path, arcname=file_save_path)
        t.close()
        return t.name


class HistoryListResource(Resource):
    """
    查看导入历史列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        start_time = now() - datetime.timedelta(days=50)
        history_instances = (
            ImportHistory.objects.filter(bk_biz_id=bk_biz_id, create_time__gte=start_time)
            .exclude(status=ImportHistoryStatus.UPLOAD)
            .order_by("-create_time")
        )
        return_data = []
        for history in history_instances:
            result_data = {
                "id": history.id,
                "create_user": history.create_user,
                "create_time": history.create_time,
            }
            result_data.update(history.history_detail)

            return_data.append(result_data)
        return return_data


class HistoryDetailResource(Resource):
    """
    查看导入历史详情
    """

    class RequestSerializer(serializers.Serializer):
        import_history_id = serializers.IntegerField(required=True, label="导入历史ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def get_count_msg(self, config_list, action_type):
        config_list = [config for config in config_list if config["type"] != "plugin"]
        all_count = dict([("total", 0), ("success", 0), ("failed", 0)])
        plugin_count = dict([("total", 0), ("success", 0), ("failed", 0)])
        collect_count = dict([("total", 0), ("success", 0), ("failed", 0)])
        strategy_count = dict([("total", 0), ("success", 0), ("failed", 0)])
        view_count = dict([("total", 0), ("success", 0), ("failed", 0)])
        type_to_count_map = {
            "plugin": plugin_count,
            "collect": collect_count,
            "strategy": strategy_count,
            "view": view_count,
        }
        if action_type != ImportHistoryStatus.UPLOAD:
            all_count["importing"] = 0
            plugin_count["importing"] = 0
            collect_count["importing"] = 0
            strategy_count["importing"] = 0
            view_count["importing"] = 0

        for config in config_list:
            all_count["total"] += 1
            if config.get("file_status"):
                all_count[config["file_status"]] += 1
                type_to_count_map[config["type"]]["total"] += 1
                type_to_count_map[config["type"]][config["file_status"]] += 1
            else:
                all_count[config["import_status"]] += 1
                type_to_count_map[config["type"]]["total"] += 1
                type_to_count_map[config["type"]][config["import_status"]] += 1

        return all_count, plugin_count, collect_count, strategy_count, view_count

    def perform_request(self, validated_request_data):
        history_id = validated_request_data["import_history_id"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        history_instance = ImportHistory.objects.filter(id=history_id, bk_biz_id=bk_biz_id).first()
        if not history_instance:
            raise ImportHistoryNotExistError

        config_list = list(
            ImportDetail.objects.filter(history_id=history_id).values(
                "id", "name", "type", "import_status", "error_msg", "label", "config_id", "parse_id"
            )
        )
        collect_ids = [
            config["config_id"]
            for config in config_list
            if config["type"] == ConfigType.COLLECT and config["import_status"] == ImportDetailStatus.SUCCESS
        ]
        strategy_ids = [
            config["config_id"]
            for config in config_list
            if config["type"] == ConfigType.STRATEGY and config["import_status"] == ImportDetailStatus.SUCCESS
        ]

        collect_instances = CollectConfigMeta.objects.filter(bk_biz_id=bk_biz_id, id__in=collect_ids).select_related(
            "deployment_config"
        )
        strategy_instances = StrategyModel.objects.filter(id__in=strategy_ids)
        item_instances = ItemModel.objects.filter(strategy_id__in=strategy_ids)
        strategy_to_items = {}
        for item_instance in item_instances:
            strategy_to_items[item_instance.strategy_id] = item_instance
        target_map = {ConfigType.COLLECT: {}, ConfigType.STRATEGY: {}}
        for instance in collect_instances:
            target_map[ConfigType.COLLECT][str(instance.id)] = {
                "target_type": instance.target_object_type,
                "exist_target": True if instance.deployment_config.target_nodes else False,
            }
        for instance in strategy_instances:
            target = strategy_to_items[instance.id].target
            target_map[ConfigType.STRATEGY][str(instance.id)] = {
                "target_type": instance.target_type,
                "exist_target": target and target[0],
            }

        for config in config_list:
            config["uuid"] = ImportParse.objects.get(id=config["parse_id"]).uuid
            config.update(target_map.get(config["type"], {}).get(config["config_id"], {}))

        label_map = {}
        for config in config_list:
            if config["type"] == ConfigType.VIEW:
                break
            if not label_map.get(config["label"]):
                label_msg = resource.commons.get_label_msg(config["label"])
                label_info = "{}-{}".format(label_msg["first_label_name"], label_msg["second_label_name"])
                label_map[config["label"]] = label_info
            config["label"] = label_map[config["label"]]
            config.pop("id", "config_id")

        all_count, plugin_count, collect_count, strategy_count, view_count = self.get_count_msg(
            config_list, history_instance.status
        )

        return {
            "config_list": config_list,
            "all_count": all_count,
            "collect_count": collect_count,
            "strategy_count": strategy_count,
            "view_count": view_count,
            "import_history_id": history_id,
        }


class UploadPackageResource(Resource):
    """
    上传文件包接口
    """

    def __init__(self):
        super(UploadPackageResource, self).__init__()
        self.file_manager = None
        self.file_id = None
        uuid_str = str(uuid4())
        self.all_count = dict([("total", 0), ("success", 0), ("failed", 0)])
        self.plugin_count = dict([("total", 0), ("success", 0), ("failed", 0)])
        self.collect_count = dict([("total", 0), ("success", 0), ("failed", 0)])
        self.strategy_count = dict([("total", 0), ("success", 0), ("failed", 0)])
        self.view_count = dict([("total", 0), ("success", 0), ("failed", 0)])
        self.type_map = {
            "plugin": self.plugin_count,
            "collect": self.collect_count,
            "strategy": self.strategy_count,
            "view": self.view_count,
        }
        self.parse_path = os.path.join(settings.MEDIA_ROOT, "export_import", "parse", uuid_str)

    class RequestSerializer(serializers.Serializer):
        file_data = serializers.FileField(required=True, label="文件内容")

    def un_tar_package(self):
        file_instance = self.file_manager.file_obj
        t = None
        try:
            t = tarfile.open(fileobj=file_instance.file_data.file)
            t.extractall(path=self.parse_path, filter='data')
        except Exception as e:
            logger.exception("压缩包解压失败: {}".format(e))
            raise UploadPackageError({"msg": _("导入文件格式不正确，需要是.tar.gz/.tgz/.tar.bz2/.tbz2等后缀(gzip或bzip2压缩)")})
        finally:
            if t is not None:
                t.close()
        if not any(list([x in os.listdir(self.parse_path) for x in DIRECTORY_LIST])):
            raise UploadPackageError({"msg": _("导入包目录结构不对")})

    def parse_collect_config(self):
        collect_config_dir = os.path.join(self.parse_path, "collect_config_directory")
        if not os.path.exists(collect_config_dir):
            return

        collect_filenames = os.listdir(collect_config_dir)
        for filename in collect_filenames:
            # 避免用户通过ide编辑配置，遗留ide缓存文件
            if filename.startswith("."):
                logger.info(f"collect_config parse ignore: {filename}")
                continue
            parse_manager = CollectConfigParse(file_path=os.path.join(collect_config_dir, filename))
            parse_result = parse_manager.parse_msg()

            if parse_result["file_status"] == ImportDetailStatus.SUCCESS:
                ImportParse.objects.create(
                    name=parse_result["collect_config"]["name"],
                    label=parse_result["collect_config"].get("label", ""),
                    uuid=str(uuid4()),
                    type=ConfigType.COLLECT,
                    config=parse_result["collect_config"],
                    file_status=ImportDetailStatus.SUCCESS,
                    file_id=self.file_id,
                )
                try:
                    ImportParse.objects.update_or_create(
                        file_id=self.file_id,
                        type=ConfigType.PLUGIN,
                        name=parse_result["plugin_config"]["plugin_id"],
                        defaults={
                            "name": parse_result["plugin_config"]["plugin_id"],
                            "type": ConfigType.PLUGIN,
                            "label": parse_result["plugin_config"]["label"],
                            "uuid": str(uuid4()),
                            "config": parse_result["plugin_config"],
                            "file_status": ImportDetailStatus.SUCCESS,
                            "file_id": self.file_id,
                        },
                    )
                except KeyError:
                    # 日志关键字类导入不存储插件信息，在创建时需要新建（它是虚拟插件）
                    pass
            else:
                ImportParse.objects.create(
                    name=parse_result["name"],
                    label=parse_result["collect_config"].get("label", ""),
                    uuid=str(uuid4()),
                    type=ConfigType.COLLECT,
                    config=parse_result["collect_config"],
                    file_status=ImportDetailStatus.FAILED,
                    error_msg=parse_result.get("error_msg", ""),
                    file_id=self.file_id,
                )

    def parse_strategy_config(self):
        strategy_config_dir = os.path.join(self.parse_path, "strategy_config_directory")
        if not os.path.exists(strategy_config_dir):
            return

        strategy_filenames = os.listdir(strategy_config_dir)
        import_collect_configs = ImportParse.objects.filter(
            type=ConfigType.COLLECT, file_id=self.file_id, file_status=ImportDetailStatus.SUCCESS
        )
        import_collect_config_ids = [collect_config_msg.config["id"] for collect_config_msg in import_collect_configs]
        for filename in strategy_filenames:
            # 避免用户通过ide编辑配置，遗留ide缓存文件
            if filename.startswith("."):
                logger.info(f"strategy parse ignore: {filename}")
                continue
            parse_manager = StrategyConfigParse(file_path=os.path.join(strategy_config_dir, filename))
            parse_result, bk_collect_config_ids = parse_manager.parse_msg()

            if not set(bk_collect_config_ids).issubset(set(import_collect_config_ids)):
                parse_result.update({"file_status": ImportDetailStatus.FAILED, "error_msg": _("关联采集配置未发现")})

            ImportParse.objects.create(
                name=parse_result["name"],
                label=parse_result["config"].get("scenario", ""),
                uuid=str(uuid4()),
                type=ConfigType.STRATEGY,
                config=parse_result["config"],
                file_status=parse_result["file_status"],
                error_msg=parse_result.get("error_msg", ""),
                file_id=self.file_id,
            )

    def parse_view_config(self):
        view_config_dir = os.path.join(self.parse_path, "view_config_directory")
        if not os.path.exists(view_config_dir):
            return

        dashboard_filenames = os.listdir(view_config_dir)
        for filename in dashboard_filenames:
            # 避免用户通过ide编辑配置，遗留ide缓存文件
            if filename.startswith("."):
                logger.info(f"view parse ignore: {filename}")
                continue
            parse_manager = ViewConfigParse(file_path=os.path.join(view_config_dir, filename))
            parse_result = parse_manager.parse_msg()

            ImportParse.objects.create(
                name=parse_result["name"],
                label="view",
                uuid=str(uuid4()),
                type=ConfigType.VIEW,
                config=parse_result["config"],
                file_status=parse_result["file_status"],
                error_msg=parse_result.get("error_msg", ""),
                file_id=self.file_id,
            )

    def parse_package(self):
        self.parse_collect_config()
        self.parse_strategy_config()
        self.parse_view_config()

    def handle_return_data(self, model_obj):
        if model_obj.type == ConfigType.VIEW:
            label_info = model_obj.label
        else:
            label_msg = resource.commons.get_label_msg(model_obj.label)
            label_info = "{}-{}".format(label_msg["first_label_name"], label_msg["second_label_name"])
        self.all_count["total"] += 1
        self.type_map[model_obj.type]["total"] += 1
        if model_obj.file_status == ImportDetailStatus.SUCCESS:
            self.all_count["success"] += 1
            self.type_map[model_obj.type]["success"] += 1
        else:
            self.all_count["failed"] += 1
            self.type_map[model_obj.type]["failed"] += 1

        return {
            "name": model_obj.name,
            "uuid": model_obj.uuid,
            "file_status": model_obj.file_status,
            "error_msg": model_obj.error_msg,
            "label": label_info,
            "type": model_obj.type,
        }

    def perform_request(self, validated_request_data):
        if not os.path.exists(self.parse_path):
            os.makedirs(self.parse_path)

        try:
            file_data = validated_request_data["file_data"]
            file_name = file_data.name
            if file_data.size > 500 * 1024 * 1024:
                raise UploadPackageError({"msg": _("插件包不能大于500M")})

            upload_file_ids = set(UploadedFileInfo.objects.values_list("id", flat=True))
            validated_request_data.setdefault("file_name", file_name)
            self.file_manager = ExportImportManager.save_file(**validated_request_data)
            self.file_id = self.file_manager.file_obj.id
            if self.file_id not in upload_file_ids:
                # 解压导入的文件包
                self.un_tar_package()
                # 解析插件包
                self.parse_package()

            config_list = list(map(self.handle_return_data, ImportParse.objects.filter(file_id=self.file_id)))
            return {
                "config_list": config_list,
                "all_count": self.all_count,
                "plugin_count": self.plugin_count,
                "collect_count": self.collect_count,
                "strategy_count": self.strategy_count,
                "view_count": self.view_count,
                "import_history_id": 0,
            }

        except Exception as e:
            if self.file_manager:
                file_instance = self.file_manager.file_obj
                file_instance.file_data.delete()
                file_instance.is_deleted = True
                file_instance.save()

            if isinstance(e, UploadPackageError):
                raise e
            logger.exception(e)
            raise UploadPackageError({"msg": str(e)})
        finally:
            shutil.rmtree(self.parse_path)


class ImportConfigResource(Resource):
    """
    导入配置接口
    """

    def __init__(self):
        super(ImportConfigResource, self).__init__()
        self.uuid_list = []
        self.import_history_instance = None

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        uuid_list = serializers.ListField(required=True, label="配置的uuid")
        import_history_id = serializers.IntegerField(required=False, label="导入历史ID")
        # 覆盖模式下，如果存在同名的策略、告警组、处理套餐将会被覆盖。
        # 非覆盖模式下，如果存在同名的策略、告警组、处理套餐，将会给名称加上"_clone"后缀，然后新建。
        is_overwrite_mode = serializers.BooleanField(required=False, label="是否覆盖同名的策略、告警组、处理套餐", default=False)

    def perform_request(self, validated_request_data):
        username = get_request().user.username
        self.uuid_list = validated_request_data["uuid_list"]
        import_history_id = validated_request_data.get("import_history_id", "")
        bk_biz_id = validated_request_data["bk_biz_id"]

        # 校验解析文件有效性
        parse_instances = ImportParse.objects.filter(uuid__in=self.uuid_list, file_status=ImportDetailStatus.SUCCESS)
        if not parse_instances:
            raise ImportConfigError({"msg": _("没有找到对应的解析文件内容")})

        parse_ids = [parse_obj.id for parse_obj in parse_instances]
        if import_history_id:
            # 校验已有导入历史记录
            self.import_history_instance = ImportHistory.objects.filter(
                id=import_history_id, bk_biz_id=bk_biz_id
            ).first()
            if not self.import_history_instance:
                raise ImportHistoryNotExistError

            # 获取需要重新导入的配置（排除已成功/正在导入的）
            all_config_list = ImportDetail.objects.filter(
                history_id=self.import_history_instance.id, parse_id__in=parse_ids
            ).exclude(import_status__in=[ImportDetailStatus.SUCCESS, ImportDetailStatus.IMPORTING])
        else:
            # 创建新的导入历史记录和详情记录
            self.import_history_instance = ImportHistory.objects.create(
                status=ImportHistoryStatus.IMPORTING, bk_biz_id=bk_biz_id
            )
            create_detail_data = []
            for parse_instance in parse_instances:
                create_detail_data.append(
                    ImportDetail(
                        name=parse_instance.name,
                        type=parse_instance.type,
                        label=parse_instance.label,
                        history_id=self.import_history_instance.id,
                        import_status=ImportDetailStatus.IMPORTING,
                        parse_id=parse_instance.id,
                    )
                )

            ImportDetail.objects.bulk_create(create_detail_data)
            all_config_list = ImportDetail.objects.filter(
                history_id=self.import_history_instance.id, parse_id__in=parse_ids
            )

        collect_config_list = all_config_list.filter(type=ConfigType.COLLECT)
        strategy_config_list = all_config_list.filter(type=ConfigType.STRATEGY)
        view_config_list = all_config_list.filter(type=ConfigType.VIEW)

        if not any([collect_config_list, strategy_config_list, view_config_list]):
            raise ImportConfigError({"msg": _("未选择任何配置")})

        if any([collect_config_list, strategy_config_list, view_config_list]):
            import_config.delay(
                username,
                bk_biz_id,
                self.import_history_instance,
                collect_config_list,
                strategy_config_list,
                view_config_list,
                validated_request_data["is_overwrite_mode"],
            )

            # 执行导入的配置和导入历史状态置为importing
            self.import_history_instance.status = ImportDetailStatus.IMPORTING
            self.import_history_instance.save()
            collect_parse_instances = ImportParse.objects.filter(
                id__in=[config.parse_id for config in collect_config_list]
            )
            plugin_id_list = [config.config["plugin_id"] for config in collect_parse_instances]
            ImportDetail.objects.filter(
                name__in=plugin_id_list, type=ConfigType.PLUGIN, history_id=self.import_history_instance.id
            ).exclude(import_status=ImportDetailStatus.SUCCESS).update(import_status=ImportDetailStatus.IMPORTING)
            collect_config_list.update(import_status=ImportDetailStatus.IMPORTING)
            strategy_config_list.update(import_status=ImportDetailStatus.IMPORTING)
            view_config_list.update(import_status=ImportDetailStatus.IMPORTING)

        # 发送审计上报
        try:
            event_content = (
                f"导入{len(collect_config_list)}条采集配置, {len(strategy_config_list)}个策略配置, {len(view_config_list)}个仪表盘"
            )
            send_frontend_report_event(self, bk_biz_id, username, event_content)
        except Exception as e:
            logger.exception(f"send frontend report event error: {e}")

        return {"import_history_id": self.import_history_instance.id}


class AddMonitorTargetResource(Resource):
    class RequestSerializer(serializers.Serializer):
        import_history_id = serializers.IntegerField(required=True, label="导入历史ID")
        target = serializers.ListField(required=True, label="监控目标")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

        def validate_target(self, value):
            is_validate_target(value)
            return handle_target(value)

    def perform_request(self, validated_request_data):
        field_target_map = {
            TargetFieldType.host_ip: TargetObjectType.HOST,
            TargetFieldType.host_target_ip: TargetObjectType.HOST,
            TargetFieldType.host_topo: TargetObjectType.HOST,
            TargetFieldType.service_topo: TargetObjectType.SERVICE,
            TargetFieldType.service_service_template: TargetObjectType.SERVICE,
            TargetFieldType.service_set_template: TargetObjectType.SERVICE,
            TargetFieldType.host_service_template: TargetObjectType.HOST,
            TargetFieldType.host_set_template: TargetObjectType.HOST,
            TargetFieldType.dynamic_group: TargetObjectType.HOST,
        }
        taget_node_type_map = {
            TargetFieldType.host_target_ip: TargetNodeType.INSTANCE,
            TargetFieldType.service_service_template: TargetNodeType.SERVICE_TEMPLATE,
            TargetFieldType.host_service_template: TargetNodeType.SERVICE_TEMPLATE,
            TargetFieldType.service_set_template: TargetNodeType.SET_TEMPLATE,
            TargetFieldType.host_set_template: TargetNodeType.SET_TEMPLATE,
            TargetFieldType.dynamic_group: TargetNodeType.DYNAMIC_GROUP,
        }

        bk_biz_id = validated_request_data["bk_biz_id"]
        history_id = validated_request_data["import_history_id"]
        target = validated_request_data["target"]
        history_instance = ImportHistory.objects.filter(id=history_id).first()
        if not history_instance:
            raise ImportHistoryNotExistError

        target_type_result = history_instance.get_target_type()
        if target_type_result.get("error_msg"):
            raise AddTargetError({"msg": target_type_result["error_msg"]})

        target_type = target_type_result["target_type"]
        target_field = target[0][0]["field"]
        if field_target_map[target_field] != target_type:
            raise AddTargetError({"msg": _("所选目标与配置需求目标不一致")})

        strategy_config_ids = [
            int(config.config_id)
            for config in ImportDetail.objects.filter(
                history_id=history_id, type=ConfigType.STRATEGY, import_status=ImportDetailStatus.SUCCESS
            )
        ]
        collect_config_ids = [
            int(config.config_id)
            for config in ImportDetail.objects.filter(
                history_id=history_id, type=ConfigType.COLLECT, import_status=ImportDetailStatus.SUCCESS
            )
        ]
        # 添加采集配置目标
        target_node_type = taget_node_type_map.get(target_field, TargetNodeType.TOPO)
        params_list = []
        for instance in CollectConfigMeta.objects.filter(id__in=collect_config_ids, bk_biz_id=bk_biz_id):
            params = {
                "bk_biz_id": bk_biz_id,
                "id": instance.id,
                "name": instance.name,
                "collect_type": instance.collect_type,
                "plugin_id": instance.plugin.plugin_id,
                "target_object_type": instance.target_object_type,
                "target_node_type": target_node_type,
                "target_nodes": target[0][0]["value"],
                "params": instance.deployment_config.params,
                "remote_collecting_host": instance.deployment_config.remote_collecting_host,
                "label": instance.label,
            }
            if target_node_type != TargetNodeType.DYNAMIC_GROUP:
                params["target_object_type"] = instance.target_object_type
            params_list.append(params)

        with ThreadPoolExecutor(max_workers=5) as executor:
            for params in params_list:
                executor.submit(resource.collecting.save_collect_config, **params)

        # 添加策略配置目标
        strategy_target = copy.deepcopy(target)
        for target_list in strategy_target:
            for target_detail in target_list:
                if target_detail["field"] == TargetFieldType.dynamic_group:
                    target_detail["value"] = [{"dynamic_group_id": x["bk_inst_id"]} for x in target_detail["value"]]
        resource.strategies.update_partial_strategy_v2(
            bk_biz_id=bk_biz_id, ids=strategy_config_ids, edit_data={"target": strategy_target}
        )
        StrategyModel.objects.filter(id__in=strategy_config_ids).update(is_enabled=True)

        return "success"


class ExportConfigToBusinessResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="当前业务ID")
        strategy_config_ids = serializers.ListField(required=False, default=[], label="需要导出的策略配置ID列表")
        view_config_ids = serializers.ListField(required=False, default=[], label="需要导出的视图配置ID列表")
        target_bk_biz_id = serializers.IntegerField(required=True, label="目标业务ID")

        def validate(self, attrs):
            # 检查当前业务ID和目标业务ID是否相同
            if attrs.get("bk_biz_id") == attrs.get("target_bk_biz_id"):
                raise ValidationError(_("当前业务ID和目标业务ID不能相同"))
            return attrs

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_biz_id = None
        self.bk_biz_id = None
        self.strategy_config_ids = []
        self.view_config_ids = []
        self.uuids = []
        self.parse_objs = []
        self.all_count = dict([("total", 0), ("success", 0), ("failed", 0)])
        self.strategy_count = dict([("total", 0), ("success", 0), ("failed", 0)])
        self.view_count = dict([("total", 0), ("success", 0), ("failed", 0)])
        self.type_map = {
            ConfigType.STRATEGY: self.strategy_count,
            ConfigType.VIEW: self.view_count,
        }
        self.suffix = "_imported"
        self.existed_folders = set()
        self.existed_folders_info = {}
        # 忽略的策略，当前仅支持导入未配置处理套餐的策略
        self.ignore_strategies = []

    def perform_request(self, validated_request_data):
        self.bk_biz_id = validated_request_data["bk_biz_id"]
        self.target_biz_id = validated_request_data["target_bk_biz_id"]
        self.strategy_config_ids = validated_request_data["strategy_config_ids"]
        self.view_config_ids = validated_request_data["view_config_ids"]

        if not any([self.view_config_ids, self.strategy_config_ids]):
            raise ValidationError(_("未选择任何配置"))

        self.parse_view_config()
        self.parse_strategy_config()

        result = resource.export_import.import_config({"bk_biz_id": self.target_biz_id, "uuid_list": self.uuids})

        config_list = list(map(self.handle_return_data, self.parse_objs))
        config_list.extend(self.ignore_strategies)
        return {
            "config_list": config_list,
            "all_count": self.all_count,
            "strategy_count": self.strategy_count,
            "view_count": self.view_count,
            "import_history_id": result["import_history_id"],
        }

    def parse_view_config(self):
        """
        解析仪表盘配置，并保存到数据库
        """
        if not self.view_config_ids:
            return
        view_config = get_view_config(self.bk_biz_id, self.view_config_ids)
        org_id = get_or_create_org(self.target_biz_id)["id"]

        for config in view_config.values():
            self.create_folder(config, org_id)
            dashboard = config.get("dashboard")
            # 为新导入的仪表盘名称添加后缀
            dashboard["title"] = (
                dashboard.get("title") + self.suffix if dashboard.get("title") else dashboard.get("title")
            )

            parse_manager = ViewConfigParse(file_path=None)
            parse_manager.file_content = dashboard
            parse_result = parse_manager.check_msg()

            unique_id = str(uuid4())
            self.uuids.append(unique_id)

            parse_obj = ImportParse.objects.create(
                name=parse_result["name"],
                label="view",
                uuid=unique_id,
                type=ConfigType.VIEW,
                config=parse_result["config"],
                file_status=parse_result["file_status"],
                error_msg=parse_result.get("error_msg", ""),
                file_id=0,  # 没有保存对应的UploadedFileInfo,所以这里设置为0
            )
            self.parse_objs.append(parse_obj)

    def parse_strategy_config(self):
        """解析策略配置文件并创建对应数据库记录"""
        if not self.strategy_config_ids:
            return

        strategy_configs = get_strategy_config(self.bk_biz_id, self.strategy_config_ids)

        for config in strategy_configs:
            # 暂时只导入没有配置处理套餐的策略
            if config.get("actions", []):
                info = {
                    "name": config.get("name"),
                    "uuid": "",
                    "file_status": ImportDetailStatus.FAILED,
                    "error_msg": "该策略已配置处理套餐，无法导入",
                    "label": config.get("labels", ""),
                    "type": ConfigType.STRATEGY,
                }
                self.all_count["total"] += 1
                self.all_count["failed"] += 1
                self.strategy_count["total"] += 1
                self.strategy_count["failed"] += 1

                self.ignore_strategies.append(info)
                continue

            config.pop("id")
            self.change_name_and_biz_id(config)
            parse_manager = StrategyConfigParse(file_path=None)
            parse_manager.file_content = config
            parse_result, _ = parse_manager.check_msg()

            unique_id = str(uuid4())
            self.uuids.append(unique_id)

            # 创建策略配置解析记录
            parse_obj = ImportParse.objects.create(
                name=parse_result["name"],
                label=parse_result["config"].get("scenario", ""),
                uuid=unique_id,
                type=ConfigType.STRATEGY,
                config=parse_result["config"],
                file_status=parse_result["file_status"],
                error_msg=parse_result.get("error_msg", ""),
                file_id=0,  # 没有保存对应的UploadedFileInfo,所以这里设置为0
            )
            self.parse_objs.append(parse_obj)

    def create_folder(self, view_config: Dict, org_id: int):
        """创建仪表盘目录"""
        dashboard = view_config.get("dashboard")

        folder_title = view_config.get("meta", {}).get("folderTitle")
        if not folder_title:
            return

        folder_title = folder_title + self.suffix
        if folder_title in self.existed_folders:
            dashboard["folderId"] = self.existed_folders_info[folder_title]
            return

        result = api.grafana.create_folder(org_id=org_id, title=folder_title)
        # code 409表示目录已存在
        if result["result"] or result["code"] == 409:
            if result["code"] == 409:
                folders = api.grafana.search_folder_or_dashboard(
                    org_id=org_id, query=folder_title, delete=False, limit=1000
                )
                # 获取已存在的目录的id
                for r in folders.get("data", []):
                    if r["title"] == folder_title:
                        dashboard["folderId"] = r["id"]
                        break
                else:
                    # 没找到已存在的目录
                    return

            else:
                dashboard["folderId"] = result["data"]["id"]

            self.existed_folders.add(folder_title)
            self.existed_folders_info[folder_title] = dashboard["folderId"]

    def change_name_and_biz_id(self, config: Dict):
        """修改名称和业务ID"""

        def change(d):
            if not isinstance(d, dict):
                return
            if not d.get("name", "").endswith(self.suffix):
                d["name"] = d.get("name", "") + self.suffix
            d["bk_biz_id"] = self.target_biz_id

        change(config)
        for gp in config.get("notice", {}).get("user_group_list", []):
            # 告警组名称加后缀
            change(gp)
            for duty_rule in gp.get("duty_rules_info", []):
                # 值班规则名称加后缀
                change(duty_rule)

    def handle_return_data(self, model_obj: ImportParse):
        # 返回文件解析的结果
        if model_obj.type == ConfigType.VIEW:
            label_info = model_obj.label
        else:
            label_msg = resource.commons.get_label_msg(model_obj.label)
            label_info = "{}-{}".format(label_msg["first_label_name"], label_msg["second_label_name"])
        self.all_count["total"] += 1
        self.type_map[model_obj.type]["total"] += 1
        if model_obj.file_status == ImportDetailStatus.SUCCESS:
            self.all_count["success"] += 1
            self.type_map[model_obj.type]["success"] += 1
        else:
            self.all_count["failed"] += 1
            self.type_map[model_obj.type]["failed"] += 1

        return {
            "name": model_obj.name,
            "uuid": model_obj.uuid,
            "file_status": model_obj.file_status,
            "error_msg": model_obj.error_msg,
            "label": label_info,
            "type": model_obj.type,
        }
