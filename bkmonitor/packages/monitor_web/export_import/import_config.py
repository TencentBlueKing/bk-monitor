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

from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext as _

from api.grafana.exporter import DashboardExporter
from bk_dataview.api import get_or_create_org
from bkmonitor.action.serializers import DutyRuleDetailSlz, UserGroupDetailSlz
from bkmonitor.models import ActionConfig, DutyRule, StrategyModel, UserGroup
from bkmonitor.strategy.new_strategy import Strategy
from bkmonitor.utils.local import local
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from constants.data_source import DataSourceLabel
from core.drf_resource import api, resource
from core.errors.export_import import ImportConfigError
from monitor_web.collecting.constant import OperationResult, OperationType
from monitor_web.collecting.deploy import get_collect_installer
from monitor_web.export_import.constant import ConfigType, ImportDetailStatus
from monitor_web.models import (
    CollectConfigMeta,
    CollectorPluginMeta,
    DeploymentConfigVersion,
    ImportDetail,
    ImportParse,
    TargetObjectType,
)
from monitor_web.plugin.manager import PluginManagerFactory
from monitor_web.plugin.resources import CreatePluginResource
from packages.monitor_web.strategies.default_settings.datalink.v1 import DEFAULT_DATALINK_COLLECTING_FLAG
from utils import count_md5

logger = logging.getLogger("monitor_web")


def import_plugin(bk_biz_id, plugin_config):
    parse_instance = ImportParse.objects.get(id=plugin_config.parse_id)
    config = parse_instance.config
    plugin_id = config["plugin_id"]
    plugin_type = config["plugin_type"]
    config["bk_biz_id"] = bk_biz_id
    bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
    exist_plugin = CollectorPluginMeta.objects.filter(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id).first()
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
                    bk_tenant_id=bk_tenant_id, plugin=plugin_id, plugin_type=plugin_type, operator=local.username
                )
                version, need_debug = plugin_manager.create_version(config)
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


def import_one_log_collect(data, bk_biz_id):
    data.pop("id")
    data["bk_biz_id"] = bk_biz_id
    data["plugin_id"] = "default_log"
    data["target_nodes"] = []
    return resource.collecting.save_collect_config(data)


def import_process_collect(data, bk_biz_id):
    data.pop("id")
    data["bk_biz_id"] = bk_biz_id
    data["target_nodes"] = []
    return resource.collecting.save_collect_config(data)


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

    bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
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

        plugin_obj = CollectorPluginMeta.objects.get(bk_tenant_id=bk_tenant_id, plugin_id=plugin_instance.config_id)
        deployment_config_params = {
            "plugin_version": plugin_obj.packaged_release_version,
            "target_node_type": config["target_node_type"],
            "params": config["params"],
            "target_nodes": [],
            "remote_collecting_host": config.get("remote_collecting_host"),
        }
        try:
            collect_config = CollectConfigMeta(
                bk_biz_id=config["bk_biz_id"],
                name=config["name"],
                last_operation=OperationType.CREATE,
                operation_result=OperationResult.PREPARING,
                collect_type=config["collect_type"],
                plugin_id=plugin_obj.plugin_id,
                target_object_type=config["target_object_type"],
                label=config["label"],
            )
            installer = get_collect_installer(collect_config)
            installer.install(deployment_config_params, operation=OperationType.STOP)

            import_collect_config.config_id = collect_config.id
            import_collect_config.import_status = ImportDetailStatus.SUCCESS
            import_collect_config.error_msg = ""
            import_collect_config.save()
        except Exception as e:
            collect_config.delete()
            DeploymentConfigVersion.objects.filter(config_meta_id=collect_config.id).delete()
            import_collect_config.import_status = ImportDetailStatus.FAILED
            import_collect_config.error_msg = str(e)
            import_collect_config.config_id = None
            import_collect_config.save()


def import_strategy(bk_biz_id, import_history_instance, strategy_config_list, is_overwrite_mode=False):
    """
    :param is_overwrite_mode:  是否覆盖，默认为False。
        - 覆盖模式下，如果存在同名的策略、告警组、处理套餐将会被覆盖。
        - 非覆盖模式下，如果存在同名的策略、告警组、处理套餐，将会给名称加上"_clone"后缀，然后新建。
    :return:
    """
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

    # 已存在的用户组
    existed_user_group_names = set(UserGroup.objects.filter(bk_biz_id=bk_biz_id).values_list("name", flat=True))
    # 新创建的用户组
    newly_created_user_groups = {}  # {user_group.name: user_group}

    # 已存在的处理套餐
    existed_action_names = set(ActionConfig.objects.filter(bk_biz_id=bk_biz_id).values_list("name", flat=True))
    # 新创建的处理套餐
    newly_created_actions = {}  # {action.name: action}

    # 已存在的轮值规则
    existed_hash_to_rule = {
        duty_rule.hash: duty_rule for duty_rule in DutyRule.objects.filter(bk_biz_id=bk_biz_id, hash__isnull=False)
    }

    # 已经创建了轮值规则的hash
    created_hash_of_rule = set()

    for strategy_config in strategy_config_list:
        try:
            parse_instance = ImportParse.objects.get(id=strategy_config.parse_id)
            create_config = copy.deepcopy(parse_instance.config)

            if is_overwrite_mode and create_config["name"] in existed_name_to_id:
                create_config["id"] = existed_name_to_id[create_config["name"]]
            else:
                # 策略重名增加后缀
                while create_config["name"] in existed_name_to_id:
                    create_config["name"] = f"{create_config['name']}_clone"

            create_config = Strategy.convert_v1_to_v2(create_config)
            create_config["bk_biz_id"] = bk_biz_id

            action_list = create_config["actions"] + [create_config["notice"]]
            imported_user_groups_dict = {}  # 新导入的告警组信息 {group.name:group}

            for action_detail in action_list:
                for group_detail in action_detail.get("user_group_list", []):
                    imported_user_groups_dict[group_detail["name"]] = group_detail

            # 创建用户组关联的 duty_rules 及规则关联的 duty_arranges
            for name, group_detail in imported_user_groups_dict.items():
                rule_id_mapping = {}
                for rule_info in group_detail.get("duty_rules_info") or []:
                    # 优先沿用 hash 相同的旧 duty_rule 记录
                    rule = existed_hash_to_rule.get(rule_info["hash"])
                    # 避免重复创建轮值规则
                    if rule_info["hash"] in created_hash_of_rule:
                        rule_id_mapping[rule_info["id"]] = rule.id
                        continue

                    rule_serializer = DutyRuleDetailSlz(instance=rule, data=rule_info)
                    rule_serializer.is_valid(raise_exception=True)
                    new_rule = rule_serializer.save()

                    # 记录新创建的轮值规则与旧hash的映射
                    existed_hash_to_rule[rule_info["hash"]] = new_rule
                    created_hash_of_rule.add(rule_info["hash"])
                    # 记录新旧 id 对应关系
                    rule_id_mapping[rule_info["id"]] = new_rule.id

                # 更新用户组与规则的关联
                group_detail["duty_rules"] = (
                    [rule_id_mapping.get(old_id, old_id) for old_id in group_detail["duty_rules"]]
                    if "duty_rules" in group_detail
                    else []
                )

            if is_overwrite_mode:
                # 覆盖模式下，如果告警组名称已经存在当前业务下，则进行覆盖
                qs = UserGroup.objects.filter(name__in=list(imported_user_groups_dict.keys()), bk_biz_id=bk_biz_id)
                exited_user_groups = {user_group.name: user_group for user_group in qs}
            else:
                exited_user_groups = {}
            # 关联的告警组ID
            related_group_ids = []

            for name, group_detail in imported_user_groups_dict.items():
                group_detail.pop("id", None)
                group_detail["bk_biz_id"] = bk_biz_id
                user_group = exited_user_groups.get(name)

                if not is_overwrite_mode:
                    while group_detail["name"] in existed_user_group_names:
                        group_detail["name"] = f"{group_detail['name']}_clone"

                if group_detail["name"] in newly_created_user_groups:
                    related_group_ids.append(newly_created_user_groups[group_detail["name"]].id)
                    continue

                user_group_serializer = UserGroupDetailSlz(user_group, data=group_detail)
                user_group_serializer.is_valid(raise_exception=True)
                instance = user_group_serializer.save()
                related_group_ids.append(instance.id)
                newly_created_user_groups[group_detail["name"]] = instance

            # 更新处理套餐关联的告警组ID
            for action in action_list:
                if action.get("user_groups", []):
                    action["user_groups"] = related_group_ids

            for action in create_config["actions"]:
                config = action["config"]
                action.pop("id", None)
                config.pop("id", None)
                config["bk_biz_id"] = bk_biz_id

                if not is_overwrite_mode:
                    while config["name"] in existed_action_names:
                        config["name"] = f"{config['name']}_clone"

                # 避免重复创建处理套餐
                if config["name"] in newly_created_actions:
                    action["config_id"] = newly_created_actions[config["name"]].id
                    continue

                action_config_instance, created = ActionConfig.objects.update_or_create(
                    name=config["name"], bk_biz_id=bk_biz_id, defaults=config
                )
                action["config_id"] = action_config_instance.id
                newly_created_actions[config["name"]] = action_config_instance

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
    org_id = get_or_create_org(bk_biz_id)["id"]

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
            folder_id = create_config.pop("folderId", None)
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

            params = {
                "dashboard": create_config,
                "org_id": org_id,
                "inputs": inputs,
                "overwrite": True,
            }
            if folder_id is not None:
                params["folderId"] = folder_id

            result = api.grafana.import_dashboard(**params)
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


def get_strategy_config(bk_biz_id: int, strategy_ids: list[int]) -> list[dict]:
    """
    获取策略配置列表（包含用户组详细信息）
    """
    strategy_configs: list[dict] = resource.strategies.get_strategy_list_v2(
        bk_biz_id=bk_biz_id,
        conditions=[
            {"key": "id", "value": strategy_ids},
            {"key": "source__neq", "value": DEFAULT_DATALINK_COLLECTING_FLAG},
        ],
        page=0,
        page_size=0,
        with_user_group=True,
        with_user_group_detail=True,
        # 导出时保留原始配置不转换grafana相关配置
        convert_dashboard=False,
    )["strategy_config_list"]

    # 目标类型与维度映射关系（用于指标拆分策略处理）
    target_type_to_dimensions = {
        TargetObjectType.HOST: ["bk_target_ip", "bk_target_cloud_id"],
        TargetObjectType.SERVICE: ["bk_target_service_instance_id"],
    }

    # 遍历处理每个策略配置
    for result_data in strategy_configs:
        strategy_id = result_data.get("id")

        # 处理指标拆分策略配置
        for item_msg in result_data["items"]:
            item_msg["target"] = [[]]  # 重置目标配置
            for query_config in item_msg["query_configs"]:
                # 处理CMDB层级指标的特殊配置
                if query_config.get("result_table_id", "").endswith("_cmdb_level"):
                    # 还原原始配置并扩展维度信息
                    extend_msg = query_config["origin_config"]
                    strategy_instance = StrategyModel.objects.get(id=strategy_id)
                    target_type = strategy_instance.target_type
                    query_config["result_table_id"] = extend_msg["result_table_id"]
                    query_config["agg_dimension"] = extend_msg["agg_dimension"]
                    query_config["extend_fields"] = {}
                    # 添加目标类型对应的默认维度
                    query_config["agg_dimension"].extend(target_type_to_dimensions[target_type])

                # 处理数据标签导出配置（自定义上报和插件采集类型）
                data_label = query_config.get("data_label", None)
                if (
                    settings.ENABLE_DATA_LABEL_EXPORT
                    and data_label
                    and (
                        query_config.get("data_source_label", None)
                        in [DataSourceLabel.BK_MONITOR_COLLECTOR, DataSourceLabel.CUSTOM]
                    )
                ):
                    # 替换结果表ID为数据标签
                    query_config["metric_id"] = re.sub(
                        rf"\b{query_config['result_table_id']}\b", data_label, query_config["metric_id"]
                    )
                    query_config["result_table_id"] = data_label

    return strategy_configs


def get_view_config(bk_biz_id: int, view_ids: list[str]) -> dict[str, dict]:
    """
    获取仪表盘配置:
    """
    uid_config_mapping = {}

    org_id = get_or_create_org(bk_biz_id)["id"]
    data_sources = api.grafana.get_all_data_source(org_id=org_id)["data"]

    # 仪表盘数据导出处理流程
    for view_config_id in view_ids:
        # 通过Grafana API获取仪表盘配置
        result = api.grafana.get_dashboard_by_uid(uid=view_config_id, org_id=org_id)

        # 校验API响应数据结构有效性
        if result["result"] and result["data"].get("dashboard"):
            dashboard = result["data"]["dashboard"]
            # 数据格式转换处理
            DashboardExporter(data_sources).make_exportable(dashboard)
            uid_config_mapping[view_config_id] = result["data"]

    return uid_config_mapping
