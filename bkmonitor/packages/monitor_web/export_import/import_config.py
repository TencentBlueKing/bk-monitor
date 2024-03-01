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
import logging
import re

from django.db import transaction
from django.utils.translation import ugettext as _
from six.moves import map

from bkmonitor.action.serializers import UserGroupDetailSlz
from bkmonitor.models import ActionConfig, StrategyModel, UserGroup
from bkmonitor.strategy.new_strategy import Strategy
from bkmonitor.utils.local import local
from core.drf_resource import api, resource
from core.errors.collecting import SubscriptionStatusError
from core.errors.export_import import ImportConfigError
from monitor_web.collecting.constant import OperationResult, OperationType
from monitor_web.collecting.resources import update_config_operation_result
from monitor_web.export_import.constant import ConfigType, ImportDetailStatus
from monitor_web.grafana.auth import GrafanaAuthSync
from monitor_web.models import (
    CollectConfigMeta,
    CollectorPluginMeta,
    DeploymentConfigVersion,
    ImportDetail,
    ImportParse,
)
from monitor_web.plugin.manager import PluginManagerFactory
from monitor_web.plugin.resources import CreatePluginResource
from utils import count_md5

logger = logging.getLogger("monitor_web")


def import_plugin(bk_biz_id, plugin_config):
    parse_instance = ImportParse.objects.get(id=plugin_config.parse_id)
    config = parse_instance.config
    plugin_id = config["plugin_id"]
    plugin_type = config["plugin_type"]
    config["bk_biz_id"] = bk_biz_id
    exist_plugin = CollectorPluginMeta.objects.filter(plugin_id=plugin_id).first()
    if exist_plugin:
        # 避免导入包和原插件内容一致，文件名不同
        def handle_collector_json(config_value):
            for config_msg in list(config_value.get("collector_json", {}).values()):
                if isinstance(config_msg, dict):
                    config_msg.pop("file_name", None)
                    config_msg.pop("file_id", None)
            return config_value

        exist_version = exist_plugin.current_version
        now_config_data = copy.deepcopy(exist_version.config.config2dict())
        tmp_config_data = copy.deepcopy(exist_version.config.config2dict(config))
        now_config_data, tmp_config_data = list(map(handle_collector_json, [now_config_data, tmp_config_data]))
        now_info_data = exist_version.info.info2dict()
        tmp_info_data = exist_version.info.info2dict(config)
        old_config_md5, new_config_md5, old_info_md5, new_info_md5 = list(
            map(count_md5, [now_config_data, tmp_config_data, now_info_data, tmp_info_data])
        )
        if all([old_config_md5 == new_config_md5, old_info_md5 == new_info_md5, exist_version.is_release]):
            plugin_config.config_id = exist_version.plugin.plugin_id
            plugin_config.import_status = ImportDetailStatus.SUCCESS
            plugin_config.error_msg = ""
            plugin_config.save()
        else:
            plugin_config.import_status = ImportDetailStatus.FAILED
            plugin_config.error_msg = _("插件ID已存在")
            plugin_config.save()
    else:
        try:
            serializers_obj = CreatePluginResource.SERIALIZERS[config.get("plugin_type")](data=config)
            serializers_obj.is_valid(raise_exception=True)
            with transaction.atomic():
                serializers_obj.save()
                plugin_manager = PluginManagerFactory.get_manager(
                    plugin=plugin_id, plugin_type=plugin_type, operator=local.username
                )
                version, no_use = plugin_manager.create_version(config)
            result = resource.plugin.plugin_register(
                plugin_id=version.plugin.plugin_id,
                config_version=version.config_version,
                info_version=version.info_version,
            )
            plugin_manager.release(
                config_version=version.config_version, info_version=version.info_version, token=result["token"]
            )
            plugin_config.config_id = version.plugin.plugin_id
            plugin_config.import_status = ImportDetailStatus.SUCCESS
            plugin_config.error_msg = ""
            plugin_config.save()
        except Exception as e:
            plugin_config.import_status = ImportDetailStatus.FAILED
            plugin_config.error_msg = str(e)
            plugin_config.save()

    return plugin_config


def import_collect_without_plugin(data):
    result = resource.collecting.save_collect_config(data)
    collect_config = CollectConfigMeta.objects.select_related("deployment_config").get(id=result["id"])
    try:
        update_config_operation_result(collect_config)
    except SubscriptionStatusError as e:
        logger.exception(str(e))
    return result


def import_one_log_collect(data, bk_biz_id):
    data.pop("id")
    data["bk_biz_id"] = bk_biz_id
    data["plugin_id"] = "default_log"
    data["target_nodes"] = []
    return import_collect_without_plugin(data)


def import_process_collect(data, bk_biz_id):
    data.pop("id")
    data["bk_biz_id"] = bk_biz_id
    data["target_nodes"] = []
    return import_collect_without_plugin(data)


def check_and_change_bkdata_table_id(query_config, bk_biz_id):
    if query_config.get("data_source_label") == "bk_data" and query_config.get("data_type_label") == "time_series":
        query_config["result_table_id"] = str(bk_biz_id) + "_" + query_config["result_table_id"].split("_", 1)[-1]


import_handler = {
    CollectConfigMeta.CollectType.PROCESS: import_process_collect,
    CollectConfigMeta.CollectType.LOG: import_one_log_collect,
}


def import_collect(bk_biz_id, import_history_instance, collect_config_list):
    def handle_collect_without_plugin(import_collect_obj, config_dict, target_bk_biz_id, handle_func):
        try:
            handle_result = handle_func(config_dict, target_bk_biz_id)
        except Exception as e:
            import_collect_obj.import_status = ImportDetailStatus.FAILED
            import_collect_obj.error_msg = str(e)
            import_collect_obj.config_id = None
            import_collect_obj.save()
        else:
            import_collect_obj.config_id = handle_result["id"]
            import_collect_obj.import_status = ImportDetailStatus.SUCCESS
            import_collect_obj.error_msg = ""
            import_collect_obj.save()

    for import_collect_config in collect_config_list:
        parse_instance = ImportParse.objects.get(id=import_collect_config.parse_id)
        config = parse_instance.config
        if config["collect_type"] in [CollectConfigMeta.CollectType.PROCESS, CollectConfigMeta.CollectType.LOG]:
            handler = import_handler[config["collect_type"]]
            handle_collect_without_plugin(import_collect_config, config, bk_biz_id, handler)
            continue

        config["bk_biz_id"] = bk_biz_id
        config["target_nodes"] = []
        plugin_instance = ImportDetail.objects.filter(
            history_id=import_history_instance.id, type=ConfigType.PLUGIN, name=config["plugin_id"]
        ).first()
        if not plugin_instance:
            import_collect_config.import_status = ImportDetailStatus.FAILED
            import_collect_config.error_msg = _("关联插件不存在")
            import_collect_config.save()
            continue

        plugin_instance = import_plugin(bk_biz_id, plugin_instance)
        if plugin_instance.import_status == ImportDetailStatus.FAILED:
            import_collect_config.import_status = ImportDetailStatus.FAILED
            import_collect_config.error_msg = _("关联插件导入失败")
            import_collect_config.save()
            continue

        plugin_obj = CollectorPluginMeta.objects.get(plugin_id=plugin_instance.config_id)
        deployment_config_params = {
            "plugin_version": plugin_obj.packaged_release_version,
            "target_node_type": config["target_node_type"],
            "params": config["params"],
            "target_nodes": [],
            "remote_collecting_host": config.get("remote_collecting_host"),
            "config_meta_id": 0,
        }
        collect_config = None
        deployment_config = None
        try:
            deployment_config = DeploymentConfigVersion.objects.create(**deployment_config_params)
            collect_config = CollectConfigMeta(
                bk_biz_id=config["bk_biz_id"],
                name=config["name"],
                last_operation=OperationType.CREATE,
                operation_result=OperationResult.PREPARING,
                collect_type=config["collect_type"],
                plugin=plugin_obj,
                target_object_type=config["target_object_type"],
                deployment_config=deployment_config,
                label=config["label"],
            )
            collect_config.deployment_config_id = deployment_config.id
            collect_config.save()
            deployment_config.config_meta_id = collect_config.id
            deployment_config.save()
            result = collect_config.create_subscription()
            if result["task_id"]:
                deployment_config.subscription_id = result["subscription_id"]
                collect_config.operation_result = OperationResult.PREPARING
                deployment_config.task_ids = [result["task_id"]]
                deployment_config.save()
                collect_config.last_operation = OperationType.STOP
                collect_config.save()
            import_collect_config.config_id = collect_config.id
            import_collect_config.import_status = ImportDetailStatus.SUCCESS
            import_collect_config.error_msg = ""
            import_collect_config.save()
        except Exception as e:
            if collect_config:
                collect_config.is_deleted = True
                collect_config.save()
            if deployment_config:
                deployment_config.is_deleted = True
                deployment_config.save()
            import_collect_config.import_status = ImportDetailStatus.FAILED
            import_collect_config.error_msg = str(e)
            import_collect_config.config_id = None
            import_collect_config.save()


def import_strategy(bk_biz_id, import_history_instance, strategy_config_list, is_overwrite_mode=False):
    # 已导入的采集配置，原有ID与创建ID映射，用于更改策略配置的监控条件中关联采集配置
    import_collect_configs = ImportDetail.objects.filter(
        type=ConfigType.COLLECT, history_id=import_history_instance.id, import_status=ImportDetailStatus.SUCCESS
    )
    import_config_id_map = dict()
    for import_config_instance in import_collect_configs:
        parse_instance = ImportParse.objects.get(id=import_config_instance.parse_id)
        import_config_id_map[parse_instance.config["id"]] = int(import_config_instance.config_id)

    # 已存在的策略名，防止重名
    existed_name_to_id = {
        strategy_dict["name"]: strategy_dict["id"]
        for strategy_dict in list(StrategyModel.objects.filter(bk_biz_id=bk_biz_id).values("name", "id"))
    }

    for strategy_config in strategy_config_list:
        try:
            parse_instance = ImportParse.objects.get(id=strategy_config.parse_id)
            create_config = copy.deepcopy(parse_instance.config)

            # 覆盖模式使用原配置策略id
            if is_overwrite_mode and create_config["name"] in existed_name_to_id:
                create_config["id"] = existed_name_to_id[create_config["name"]]
            else:
                # 策略重名增加后缀
                while create_config["name"] in existed_name_to_id:
                    create_config["name"] = f"{create_config['name']}_clone"

            create_config = Strategy.convert_v1_to_v2(create_config)
            create_config["bk_biz_id"] = bk_biz_id

            # 创建新通知组或覆盖已有通知组
            user_groups_mapping = {}
            action_list = create_config["actions"] + [create_config["notice"]]
            user_groups_dict = {}
            user_group_ids = []
            user_groups_new = []
            for action_detail in action_list:
                for group_detail in action_detail.get("user_group_list", []):
                    if group_detail["id"] not in user_group_ids:
                        user_group_ids.append(group_detail["id"])
                        user_groups_dict[group_detail["name"]] = group_detail

                    for duty_arrange in group_detail.get("duty_arranges") or []:
                        duty_arrange.pop("id", None)
                        duty_arrange.pop("user_group_id", None)
                        duty_arrange.pop("duty_rule_id", None)

            # TODO(crayon) 目前导入功能没有考虑轮值，预设方案：
            # 1. 导出：group_detail["duty_rules_info"] 增加 duty_arranges 信息
            # 1. 创建用户组之前，要把 group_detail["duty_rules_info"] 先创建好，得到 duty_rule_id old - new ID 映射关系
            # 2. 将 group_detail["duty_rules"]: List[int] 按映射关系进行替换

            qs = UserGroup.objects.filter(name__in=list(user_groups_dict.keys()), bk_biz_id=bk_biz_id)
            for user_group in qs:
                group_detail = user_groups_dict[user_group.name]
                origin_id = group_detail.pop("id", None)
                group_detail["bk_biz_id"] = bk_biz_id
                user_group_serializer = UserGroupDetailSlz(user_group, data=group_detail)
                user_group_serializer.is_valid(True)
                instance = user_group_serializer.save()
                if origin_id:
                    user_groups_mapping[origin_id] = instance.id
                else:
                    user_groups_new.append(instance.id)
                user_groups_dict.pop(user_group.name, None)

            for name, group_detail in user_groups_dict.items():
                origin_id = group_detail.pop("id", None)
                group_detail["bk_biz_id"] = bk_biz_id
                user_group_serializer = UserGroupDetailSlz(data=group_detail)
                user_group_serializer.is_valid(True)
                instance = user_group_serializer.save()
                if origin_id:
                    user_groups_mapping[origin_id] = instance.id
                else:
                    user_groups_new.append(instance.id)

            for action in action_list:
                if action.get("user_groups", []):
                    action["user_groups"] = [user_groups_mapping[group_id] for group_id in action["user_groups"]]
                if user_groups_new:
                    action["user_groups"].extend(user_groups_new)

            # 创建新处理套餐或覆盖已有处理套餐
            for action in create_config["actions"]:
                config = action["config"]
                action.pop("id", None)
                config.pop("id", None)
                config["bk_biz_id"] = bk_biz_id
                action_config_instance, created = ActionConfig.objects.update_or_create(
                    name=config["name"], bk_biz_id=bk_biz_id, defaults=config
                )
                action["config_id"] = action_config_instance.id

            # 替换agg_condition中关联采集配置相关信息
            for query_config in create_config["items"][0]["query_configs"]:
                # 对计算平台数据源进行处理
                check_and_change_bkdata_table_id(query_config, bk_biz_id)

                agg_condition = query_config.get("agg_condition", [])
                for condition_msg in agg_condition:
                    if "bk_collect_config_id" in list(condition_msg.values()):
                        old_config_id_desc = condition_msg["value"]
                        new_config_ids = []
                        # 兼容condition数据为非列表数据
                        if not isinstance(old_config_id_desc, list):
                            old_config_id_desc = [old_config_id_desc]

                        for old_config_id in old_config_id_desc:
                            # 兼容原来采集配置ID包含采集名称的情况
                            re_match = re.match(r"(\d+).*", str(old_config_id))
                            old_config_id = re_match.groups()[0] if re_match.groups() else 0
                            if not import_config_id_map.get(int(old_config_id)):
                                raise ImportConfigError({"msg": _("关联采集配置{}未导入成功").format(old_config_id)})
                            new_config_ids.append(str(import_config_id_map[int(old_config_id)]))
                        condition_msg["value"] = new_config_ids

            result = resource.strategies.save_strategy_v2(**create_config)
            if result.get("id"):
                StrategyModel.objects.filter(id=result["id"]).update(is_enabled=False)
                strategy_config.config_id = result["id"]
                strategy_config.import_status = ImportDetailStatus.SUCCESS
                strategy_config.error_msg = ""
                strategy_config.save()
                existed_name_to_id[create_config["name"]] = result["id"]
            else:
                strategy_config.import_status = ImportDetailStatus.FAILED
                strategy_config.error_msg = str(result)
                strategy_config.save()

        except Exception as e:
            logger.exception(e)
            strategy_config.import_status = ImportDetailStatus.FAILED
            strategy_config.error_msg = str(e)
            strategy_config.save()


def import_view(bk_biz_id, view_config_list, is_overwrite_mode=False):
    # 已存在的视图名，防止重名
    existed_dashboards = resource.grafana.get_dashboard_list(bk_biz_id=bk_biz_id)
    existed_names = {dashboard["name"] for dashboard in existed_dashboards}
    org_id = GrafanaAuthSync.get_or_create_org_id(bk_biz_id)

    data_sources = {
        data_source["type"]: {
            "type": "datasource",
            "pluginId": data_source["type"],
            "value": data_source.get("uid", ""),
        }
        for data_source in api.grafana.get_all_data_source(org_id=org_id)["data"]
    }

    for view_config in view_config_list:
        try:
            parse_instance = ImportParse.objects.get(id=view_config.parse_id)
            create_config = copy.deepcopy(parse_instance.config)
            # 导入仪表盘，清理配置id
            create_config.pop("id", None)
            uid = create_config.pop("uid", "")
            logger.info(str(create_config))
            # 非覆盖模式，视图重名增加后缀
            if not is_overwrite_mode:
                while create_config["title"] in existed_names:
                    create_config["title"] = f"{create_config['title']}_clone"

            # 对计算平台数据源进行处理
            for panel in create_config.get("panels", []):
                for target in panel.get("targets", []):
                    for query_config in target.get("query_configs", []):
                        check_and_change_bkdata_table_id(query_config, bk_biz_id)

            inputs = []
            for input_field in create_config.get("__inputs", []):
                if input_field["type"] != "datasource":
                    raise ValueError(
                        f"dashboard({create_config['title']}) input type({input_field['type']}) is unknown"
                    )

                if input_field["pluginId"] not in data_sources:
                    raise ValueError(
                        f"dashboard({create_config['title']}) input datasource({input_field['pluginId']}) is unknown"
                    )

                inputs.append({"name": input_field["name"], **data_sources[input_field["pluginId"]]})

            result = api.grafana.import_dashboard(dashboard=create_config, org_id=org_id, inputs=inputs, overwrite=True)
            if result["result"]:
                view_config.config_id = uid
                view_config.import_status = ImportDetailStatus.SUCCESS
                view_config.error_msg = ""
                view_config.save()
                existed_names.add(create_config["title"])
            else:
                logger.exception(result["message"])
                view_config.import_status = ImportDetailStatus.FAILED
                view_config.error_msg = str(result["message"])
                view_config.save()
        except Exception as e:
            logger.exception(e)
            view_config.import_status = ImportDetailStatus.FAILED
            view_config.error_msg = str(e)
            view_config.save()
