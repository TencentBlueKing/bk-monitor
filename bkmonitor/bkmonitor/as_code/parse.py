"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicabl：qe law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
from itertools import chain

import xxhash
import yaml
from bk_monitor_base.strategy import StrategySerializer, delete_strategies, save_strategy
from rest_framework.exceptions import ValidationError
from schema import SchemaError

from bk_dataview.api import get_or_create_org
from bkmonitor.action.serializers import (
    ActionConfigDetailSlz,
    BatchSaveAssignRulesSlz,
    DutyRuleDetailSlz,
    UserGroupDetailSlz,
)
from bkmonitor.action.utils import (
    get_action_config_rules,
    get_action_config_strategy_dict,
    get_user_group_assign_rules,
    get_user_group_strategies,
)
from bkmonitor.as_code.parse_yaml import (
    ActionConfigParser,
    AssignGroupRuleParser,
    DutyRuleParser,
    NoticeGroupConfigParser,
    StrategyConfigParser,
)
from bkmonitor.models import (
    ActionConfig,
    ActionPlugin,
    AlertAssignGroup,
    AlertAssignRule,
    DutyRule,
    StrategyModel,
    UserGroup,
)
from bkmonitor.utils.dict import nested_update
from constants.action import ActionPluginType
from core.drf_resource import api

logger = logging.getLogger(__name__)


def convert_notices(
    bk_biz_id: int,
    app: str,
    configs: dict[str, dict],
    snippets: dict[str, dict],
    duty_rules: dict[str, dict],
    overwrite: bool = False,
) -> list[dict]:
    """
    1. 渲染snippet配置, sort_keys，计算xxhash (path, snippet, md5, config)
    2. db查询，对应path的md5差异比对
    3. 配置检查 check
    4. 配置转换 convert
    5. 配置写入 save
    """

    user_groups = UserGroup.objects.filter(bk_biz_id=bk_biz_id).only("id", "path", "hash", "name")
    path_user_groups = {user_group.path: user_group for user_group in user_groups.filter(app=app)}
    name_user_groups = {user_group.name.lower(): user_group for user_group in user_groups}

    parser = NoticeGroupConfigParser(bk_biz_id=bk_biz_id, duty_rules=duty_rules, overwrite=overwrite)
    records = []
    duties = []
    for path, config in configs.items():
        snippet = snippets.get(config.pop("snippet", ""), "")
        if snippet:
            config = nested_update(config, snippet)
        hash_str = xxhash.xxh3_128_hexdigest(json.dumps(config))

        old_user_group = path_user_groups.pop(path, None)
        if old_user_group and hash_str == old_user_group.hash:
            continue

        schema_error = parse_error = validate_error = slz = None
        try:
            config = parser.check(config)
        except SchemaError as e:
            schema_error = e

        if not schema_error:
            try:
                config = parser.parse(config)
            except Exception as e:
                logger.exception(e)
                parse_error = e

            if overwrite and config["name"].lower() in name_user_groups:
                old_user_group = name_user_groups[config["name"].lower()]

            if not parse_error:
                if "duties" in config:
                    duties.append(config["duties"])
                instance = None
                if old_user_group:
                    config["id"] = old_user_group.id
                    instance = old_user_group
                slz = UserGroupDetailSlz(data=config, instance=instance)

                try:
                    slz.is_valid(raise_exception=True)
                except ValidationError as e:
                    validate_error = e

        records.append(
            {
                "path": path,
                "obj": slz,
                "hash": hash_str,
                "snippet": snippet,
                "schema_error": schema_error,
                "parse_error": parse_error,
                "validate_error": validate_error,
            }
        )

    return records


def convert_actions(
    bk_biz_id: int,
    app: str,
    configs: dict[str, dict],
    snippets: dict[str, dict],
    overwrite: bool = False,
) -> list[dict]:
    """
    动作配置转换导入
    """

    actions = ActionConfig.objects.filter(bk_biz_id=bk_biz_id).only("id", "path", "hash", "name")
    path_actions = {action.path: action for action in actions.filter(app=app)}
    name_actions = {action.name.lower(): action for action in actions}

    parser = ActionConfigParser(bk_biz_id=bk_biz_id, action_plugins=ActionPlugin.objects.all())

    records = []
    for path, config in configs.items():
        snippet = snippets.get(config.pop("snippet", ""), "")
        if snippet:
            config = nested_update(config, snippet)

        hash_str = xxhash.xxh3_128_hexdigest(json.dumps(config))

        old_action = path_actions.get(path)

        if old_action and hash_str == old_action.hash:
            continue

        schema_error = parse_error = validate_error = slz = None
        try:
            config = parser.check(config)
        except SchemaError as e:
            schema_error = e

        if not schema_error:
            try:
                config = parser.parse(config)
            except Exception as e:
                logger.exception(e)
                parse_error = e

            if overwrite and config["name"].lower() in name_actions:
                old_action = name_actions[config["name"].lower()]

            if not parse_error:
                if old_action:
                    config["id"] = old_action.id
                slz = ActionConfigDetailSlz(data=config, instance=old_action)

                try:
                    slz.is_valid(raise_exception=True)
                except ValidationError as e:
                    validate_error = e

        records.append(
            {
                "path": f"{path}",
                "obj": slz,
                "hash": hash_str,
                "snippet": snippet,
                "schema_error": schema_error,
                "parse_error": parse_error,
                "validate_error": validate_error,
            }
        )

    return records


def convert_rules(
    bk_biz_id: int,
    app: str,
    configs: dict[str, dict],
    snippets: dict[str, dict],
    notice_group_ids: dict[str, int],
    action_ids: dict[str, int],
    overwrite: bool = False,
) -> list[dict]:
    """
    1. 渲染snippet配置, sort_keys，计算xxhash (path, snippet, md5, config)
    2. db查询，对应path的md5差异比对
    3. 配置检查 check
    4. 配置转换 convert
    5. 配置写入 save
    """
    strategies = StrategyModel.objects.filter(bk_biz_id=bk_biz_id).only("id", "path", "hash", "name")
    path_strategies = {strategy.path: strategy for strategy in strategies.filter(app=app)}
    name_strategies = {strategy.name.lower(): strategy for strategy in strategies}

    topo_nodes: dict[str, dict] = {}
    for topo_link in api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id).convert_to_topo_link().values():
        topo_link = list(reversed(topo_link[:-1]))
        for index, topo_node in enumerate(topo_link):
            path = "/".join(node.bk_inst_name for node in topo_link[: index + 1])
            topo_nodes[path] = {"bk_obj_id": topo_node.bk_obj_id, "bk_inst_id": topo_node.bk_inst_id}

    service_templates: dict[str, dict] = {
        service_template["name"]: {"bk_obj_id": "SERVICE_TEMPLATE", "bk_inst_id": service_template["id"]}
        for service_template in api.cmdb.get_dynamic_query(bk_biz_id=bk_biz_id, dynamic_type="SERVICE_TEMPLATE")[
            "children"
        ]
    }
    set_templates: dict[str, dict] = {
        set_template["name"]: {"bk_obj_id": "SET_TEMPLATE", "bk_inst_id": set_template["id"]}
        for set_template in api.cmdb.get_dynamic_query(bk_biz_id=bk_biz_id, dynamic_type="SET_TEMPLATE")["children"]
    }
    dynamic_groups: dict[str, dict] = {
        dynamic_group["name"]: {"dynamic_group_id": dynamic_group["id"]}
        for dynamic_group in api.cmdb.search_dynamic_group(bk_biz_id=bk_biz_id, bk_obj_id="host")
    }
    parser = StrategyConfigParser(
        bk_biz_id=bk_biz_id,
        notice_group_ids=notice_group_ids,
        action_ids=action_ids,
        topo_nodes=topo_nodes,
        service_templates=service_templates,
        set_templates=set_templates,
        dynamic_groups=dynamic_groups,
    )

    records = []
    for path, config in configs.items():
        snippet = snippets.get(config.pop("snippet", ""), "")
        if snippet:
            config = nested_update(config, snippet)

        hash_str = xxhash.xxh3_128_hexdigest(json.dumps(config))

        old_strategy = path_strategies.get(path)
        if old_strategy and hash_str == old_strategy.hash:
            continue

        schema_error = parse_error = validate_error = obj = None
        try:
            config = parser.check(config)
        except SchemaError as e:
            schema_error = e

        if not schema_error:
            try:
                config = parser.parse(config)
            except Exception as e:
                logger.exception(e)
                parse_error = e

            if overwrite and config["name"].lower() in name_strategies:
                old_strategy = name_strategies[config["name"].lower()]

            if not parse_error:
                if old_strategy:
                    config["id"] = old_strategy.pk

                serializer = StrategySerializer(data=config)
                try:
                    serializer.is_valid(raise_exception=True)
                    obj = config
                except ValidationError as e:
                    validate_error = e

        records.append(
            {
                "path": f"{path}",
                "obj": obj,
                "hash": hash_str,
                "snippet": snippet,
                "schema_error": schema_error,
                "parse_error": parse_error,
                "validate_error": validate_error,
            }
        )

    return records


def sync_grafana_dashboards(bk_biz_id: int, dashboards: dict[str, dict]):
    """
    同步Grafana仪表盘配置
    """
    org_id = get_or_create_org(bk_biz_id)["id"]
    folders = api.grafana.search_folder_or_dashboard(type="dash-folder", org_id=org_id)["data"]
    folder_names_to_ids = {folder["title"].replace("/", "-"): folder["id"] for folder in folders}

    datasources: list = api.grafana.get_all_data_source(org_id=org_id)["data"]

    # 获取数据源信息
    datasource_types = {}
    datasource_uids = {}
    for data_source in datasources:
        record = {
            "type": "datasource",
            "pluginId": data_source["type"],
            "value": data_source["uid"],
        }
        datasource_types[data_source["type"]] = record
        datasource_uids[data_source["uid"]] = record

    # 获取数据源映射，并检查uid是否存在
    datasource_mapping = dashboards.pop("datasources.yaml", {})
    for uid in datasource_mapping.values():
        if uid not in datasource_uids:
            raise ValueError(f"datasource({uid}) is not exist")

    for path, dashboard in dashboards.items():
        if "/" in path:
            folder, path = path.split("/")
        else:
            folder = ""

        if not folder:
            folder_id = 0
        elif folder in folder_names_to_ids:
            folder_id = folder_names_to_ids[folder]
        else:
            result = api.grafana.create_folder(org_id=org_id, title=folder)
            if not result["result"]:
                raise ValueError(f"create folder{folder} failed, {result['message']}")
            folder_id = result["data"]["id"]
            folder_names_to_ids[folder] = folder_id

        inputs = []
        for input_field in dashboard.get("__inputs", []):
            if input_field["type"] != "datasource":
                raise ValueError(f"dashboard({dashboard['title']}) input type({input_field['type']}) is unknown")

            uid = datasource_mapping.get(input_field["name"])
            if uid:
                datasource = datasource_uids[uid]
            else:
                if input_field["pluginId"] not in datasource_types:
                    raise ValueError(
                        f"dashboard({dashboard['title']}) input datasource({input_field['pluginId']}) is unknown"
                    )
                datasource = datasource_types[input_field["pluginId"]]
            inputs.append({"name": input_field["name"], **datasource})

        dashboard.pop("id", None)
        api.grafana.import_dashboard(
            dashboard=dashboard, org_id=org_id, inputs=inputs, overwrite=True, folderId=folder_id
        )


def convert_assign_groups(
    bk_biz_id: int,
    app: str,
    configs: dict[str, dict],
    snippets: dict[str, dict],
    notice_group_ids: dict[str, int],
    action_ids: dict[str, int],
    overwrite: bool = False,
):
    """
    1. 渲染snippet配置, sort_keys，计算xxhash (path, snippet, md5, config)
    2. db查询，对应path的md5差异比对
    3. 配置检查 check
    4. 配置转换 convert
    5. 配置写入 save
    """
    rule_groups = AlertAssignGroup.objects.filter(bk_biz_id=bk_biz_id).only("id", "path", "hash", "name")
    path_rule_groups = {rule_group.path: rule_group for rule_group in rule_groups.filter(app=app)}
    name_rule_groups = {rule_group.name.lower(): rule_group for rule_group in rule_groups}

    parser = AssignGroupRuleParser(bk_biz_id=bk_biz_id, notice_group_ids=notice_group_ids, action_ids=action_ids)

    records = []
    for path, config in configs.items():
        snippet = snippets.get(config.pop("snippet", ""), "")
        if snippet:
            config = nested_update(config, snippet)

        hash_str = xxhash.xxh3_128_hexdigest(json.dumps(config))

        old_rule_group = path_rule_groups.get(path)
        if old_rule_group and hash_str == old_rule_group.hash:
            continue

        schema_error = parse_error = validate_error = obj = None
        try:
            config = parser.check(config)
        except SchemaError as e:
            schema_error = e

        if not schema_error:
            try:
                config = parser.parse(config)
            except Exception as e:
                logger.exception(e)
                parse_error = e

            if not parse_error:
                if overwrite and config["name"].lower() in name_rule_groups:
                    old_rule_group = name_rule_groups[config["name"].lower()]

                if old_rule_group:
                    config["assign_group_id"] = old_rule_group.id

                serializer = BatchSaveAssignRulesSlz(data=config)
                try:
                    serializer.is_valid(raise_exception=True)
                    obj = serializer
                except ValidationError as e:
                    validate_error = e

        records.append(
            {
                "path": f"{path}",
                "obj": obj,
                "hash": hash_str,
                "snippet": snippet,
                "schema_error": schema_error,
                "parse_error": parse_error,
                "validate_error": validate_error,
            }
        )

    return records


def convert_duty_rules(
    bk_biz_id: int, app: str, configs: dict[str, dict], snippets: dict[str, dict], overwrite: bool = False
):
    """
    转换轮值规则
    """
    duty_rules = DutyRule.objects.filter(bk_biz_id=bk_biz_id).only("id", "path", "code_hash", "name")
    path_duty_rules = {rule.path: rule for rule in duty_rules.filter(app=app)}
    name_rules = {duty_rule.name.lower(): duty_rule for duty_rule in duty_rules}
    parser = DutyRuleParser(bk_biz_id)
    records = []
    for path, config in configs.items():
        snippet = snippets.get(config.get("snippet", ""), "")
        if snippet:
            config = nested_update(config, snippet)
            config["snippet"] = snippet
        hash_str = xxhash.xxh3_128_hexdigest(json.dumps(config))
        old_rule = path_duty_rules.get(path)
        if old_rule and hash_str == old_rule.code_hash:
            continue
        schema_error = parse_error = validate_error = obj = None
        try:
            config = parser.check(config)
        except SchemaError as e:
            schema_error = e

        if not schema_error:
            try:
                config = parser.parse(config)
            except Exception as e:
                logger.exception(e)
                parse_error = e

            if not parse_error:
                config["app"] = app
                config["code_hash"] = hash_str
                config["path"] = path
                if overwrite and config["name"].lower() in name_rules:
                    old_rule = name_rules[config["name"].lower()]
                serializer = DutyRuleDetailSlz(data=config, instance=old_rule)
                try:
                    serializer.is_valid(raise_exception=True)
                    obj = serializer
                except ValidationError as e:
                    validate_error = e

        records.append(
            {
                "path": path,
                "obj": obj,
                "hash": hash_str,
                "snippet": snippet,
                "schema_error": schema_error,
                "parse_error": parse_error,
                "validate_error": validate_error,
            }
        )
    return records


def get_errors(records) -> dict[str, str]:
    errors = {}
    for record in records:
        if not record["schema_error"] and not record["parse_error"] and not record["validate_error"]:
            continue

        errors[record["path"]] = str(record["schema_error"] or record["parse_error"] or record["validate_error"])
    return errors


def import_code_config(bk_biz_id: int, app: str, configs: dict[str, str], overwrite: bool = False, incremental=False):
    # 配置分类
    rule_configs = {}
    rule_snippets = {}

    notice_configs = {}
    notice_snippets = {}

    action_configs = {}
    action_snippets = {}

    dashboards = {}

    assign_configs = {}
    assign_snippets = {}
    duty_snippets = {}
    duty_configs = {}

    for path, data in configs.items():
        if path.endswith(".yaml") or path.endswith(".yml"):
            config = yaml.safe_load(data)
        elif path.endswith(".json"):
            config = json.loads(data)
        else:
            raise ValueError(f"parse {path} error, only allow yaml or json files")

        if path.startswith("rule/snippets/"):
            rule_snippets[path[len("rule/snippets/") :]] = config
        elif path.startswith("rule/"):
            rule_configs[path[len("rule/") :]] = config
        elif path.startswith("duty/snippets/"):
            duty_snippets[path[len("duty/snippets/") :]] = config
        elif path.startswith("duty/"):
            duty_configs[path[len("duty/") :]] = config
        elif path.startswith("notice/snippets/"):
            notice_snippets[path[len("notice/snippets/") :]] = config
        elif path.startswith("notice/"):
            notice_configs[path[len("notice/") :]] = config
        elif path.startswith("action/snippets"):
            action_snippets[path[len("action/snippets") :]] = config
        elif path.startswith("action/"):
            action_configs[path[len("action/") :]] = config
        elif path.startswith("grafana/"):
            dashboards[path[len("grafana/") :]] = config
        elif path.startswith("assign_group/"):
            assign_configs[path[len("assign_group/") :]] = config
        elif path.startswith("assign_group/snippets"):
            assign_snippets[path[len("assign_group/snippets") :]] = config

    # 配置转换及检查
    # 轮值规则
    duty_records = convert_duty_rules(
        bk_biz_id=bk_biz_id, app=app, snippets=duty_snippets, configs=duty_configs, overwrite=overwrite
    )
    errors: dict[str, str] = get_errors(duty_records)
    if errors:
        return errors

    for record in duty_records:
        record["obj"].save()

    duty_rules = {}
    for duty_rule in DutyRule.objects.filter(bk_biz_id=bk_biz_id).only("name", "id", "path"):
        if duty_rule.path and duty_rule.app == app:
            duty_rules[duty_rule.path] = duty_rule.id
        duty_rules[duty_rule.name] = duty_rule.id

    # 通知组
    notice_records = convert_notices(
        bk_biz_id=bk_biz_id,
        app=app,
        snippets=notice_snippets,
        configs=notice_configs,
        duty_rules=duty_rules,
        overwrite=overwrite,
    )

    # 处理套餐
    action_records = convert_actions(
        bk_biz_id=bk_biz_id, app=app, snippets=action_snippets, configs=action_configs, overwrite=overwrite
    )

    errors: dict[str, str] = get_errors(chain(notice_records, action_records))
    if errors:
        return errors

    for record in chain(notice_records, action_records):
        record["obj"].save()
        record["obj"].instance.path = record["path"]
        record["obj"].instance.app = app
        record["obj"].instance.hash = record["hash"]
        record["obj"].instance.snippet = record["snippet"]
        record["obj"].instance.save()

    # 策略关联通知组及动作配置
    notice_group_ids = {}
    all_user_groups = UserGroup.objects.filter(bk_biz_id__in=[bk_biz_id, 0]).only("id", "path", "name")
    for user_group in all_user_groups:
        if user_group.path and user_group.app == app:
            notice_group_ids[user_group.path] = user_group.id
        notice_group_ids[user_group.name] = user_group.id

    action_ids = {}
    # 告警分派只需要流程服务的action就行
    itsm_action_ids = {}
    try:
        itsm_plugin_id = str(ActionPlugin.objects.get(plugin_key=ActionPluginType.ITSM).id)
    except ActionPlugin.DoesNotExist:
        # 如果不存在直接忽略
        itsm_plugin_id = 0
    all_actions = ActionConfig.objects.filter(bk_biz_id__in=[bk_biz_id, 0]).only("id", "path", "name", "plugin_id")
    for action in all_actions:
        if action.path and action.app == app:
            action_ids[action.path] = action.id
            if action.plugin_id == itsm_plugin_id:
                itsm_action_ids[action.path] = action.id
        action_ids[action.name] = action.id
        if action.plugin_id == itsm_plugin_id:
            itsm_action_ids[action.name] = action.id

    rule_records = convert_rules(
        bk_biz_id=bk_biz_id,
        app=app,
        snippets=rule_snippets,
        configs=rule_configs,
        notice_group_ids=notice_group_ids,
        action_ids=action_ids,
        overwrite=overwrite,
    )

    errors = get_errors(rule_records)
    if errors:
        return errors

    for record in rule_records:
        record["obj"].update(
            {
                "app": app,
                "snippet": record["snippet"],
                "hash": record["hash"],
                "path": record["path"],
            }
        )
        save_strategy(bk_biz_id, record["obj"], "system")

    assign_group_records = convert_assign_groups(
        bk_biz_id=bk_biz_id,
        app=app,
        configs=assign_configs,
        snippets=assign_snippets,
        notice_group_ids=notice_group_ids,
        action_ids=itsm_action_ids,
        overwrite=overwrite,
    )

    errors = get_errors(assign_group_records)
    if errors:
        return errors

    # 保存
    for record in assign_group_records:
        if not isinstance(record["obj"], BatchSaveAssignRulesSlz):
            continue
        data = record["obj"].save(record["obj"].data)
        AlertAssignGroup.objects.filter(bk_biz_id=bk_biz_id, id=data["assign_group_id"]).update(
            app=app, snippet=record["snippet"], hash=record["hash"], path=record["path"]
        )
    # 删除多余策略
    if not incremental:
        # 不是增量更新，需要删除多余无用的资源
        old_strategy_ids = list(
            StrategyModel.objects.filter(bk_biz_id=bk_biz_id, app=app)
            .exclude(path__in=list(rule_configs.keys()))
            .values_list("id", flat=True)
        )
        delete_strategies(bk_biz_id, old_strategy_ids, "system")

        # 删除旧的告警分派组和规则
        old_rule_group_ids = list(
            AlertAssignGroup.objects.filter(bk_biz_id=bk_biz_id, app=app)
            .exclude(path__in=list(assign_configs.keys()))
            .values_list("id", flat=True)
        )
        if old_rule_group_ids:
            AlertAssignGroup.objects.filter(id__in=old_rule_group_ids).delete()
            AlertAssignRule.objects.filter(assign_group_id__in=old_rule_group_ids).delete()

        # 删除多余的通知组和套餐
        all_user_group_ids = UserGroup.objects.filter(bk_biz_id=bk_biz_id, app=app).values_list("id", flat=True)
        app_user_group_ids = list(get_user_group_strategies(all_user_group_ids).keys())
        app_user_group_ids.extend(list(get_user_group_assign_rules(all_user_group_ids).keys()))
        empty_user_group_ids = {
            user_group_id for user_group_id in all_user_group_ids if user_group_id not in app_user_group_ids
        }
        no_empty_user_group_ids = set(all_user_group_ids) - empty_user_group_ids
        all_action_ids = ActionConfig.objects.filter(bk_biz_id=bk_biz_id, app=app).values_list("id", flat=True)
        app_action_ids = list(get_action_config_strategy_dict(all_action_ids).keys())
        app_assign_action_ids = list(get_action_config_rules(all_action_ids, bk_biz_id).keys())
        app_action_ids.extend(app_assign_action_ids)
        empty_action_ids = {action_id for action_id in all_action_ids if action_id not in app_action_ids}
        no_empty_action_ids = set(all_action_ids) - empty_action_ids

        # 删除空用户组
        UserGroup.objects.filter(bk_biz_id=bk_biz_id, app=app, id__in=empty_user_group_ids).exclude(
            path__in=list(notice_configs.keys())
        ).delete()
        UserGroup.objects.filter(bk_biz_id=bk_biz_id, app=app, id__in=no_empty_user_group_ids).exclude(
            path__in=list(notice_configs.keys())
        ).update(app="", snippet="", hash="", path="")
        ActionConfig.objects.filter(bk_biz_id=bk_biz_id, app=app, id__in=empty_action_ids).exclude(
            path__in=list(action_configs.keys())
        ).delete()
        ActionConfig.objects.filter(bk_biz_id=bk_biz_id, app=app, id__in=no_empty_action_ids).exclude(
            path__in=list(action_configs.keys())
        ).update(app="", snippet="", hash="", path="")

    if dashboards:
        sync_grafana_dashboards(bk_biz_id, dashboards)
