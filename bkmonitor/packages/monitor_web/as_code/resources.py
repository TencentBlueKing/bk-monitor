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
import json
import logging
import os
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin

import arrow
import yaml
from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy as _lazy

from api.grafana.exporter import DashboardExporter
from bkmonitor.action.serializers import (
    ActionConfigDetailSlz,
    AssignRuleSlz,
    DutyRuleDetailSlz,
    UserGroupDetailSlz,
)
from bkmonitor.action.utils import get_assign_rule_related_resource_dict
from bkmonitor.as_code.parse import import_code_config
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
    DutyRuleRelation,
    StrategyActionConfigRelation,
    StrategyModel,
    UserGroup,
)
from bkmonitor.models.as_code import AsCodeImportTask
from bkmonitor.strategy.new_strategy import Strategy
from bkmonitor.views import serializers
from core.drf_resource import Resource, api
from core.drf_resource.tasks import step
from monitor_web.grafana.utils import get_org_id

logger = logging.getLogger("monitor_web")


class ImportConfigResource(Resource):
    """
    导入Code配置
    """

    class RequestSerializer(serializers.Serializer):
        configs = serializers.DictField(required=True, label="文件内容")
        app = serializers.CharField(default="as_code")
        bk_biz_id = serializers.IntegerField()
        overwrite = serializers.BooleanField(default=False)
        incremental = serializers.BooleanField(default=False)

    def perform_request(self, params):
        errors = import_code_config(
            bk_biz_id=params["bk_biz_id"],
            app=params["app"],
            configs=params["configs"],
            overwrite=params["overwrite"],
            incremental=params["incremental"],
        )

        if errors:
            return {"result": False, "data": None, "errors": errors, "message": f"{len(errors)} configs import failed"}
        else:
            return {"result": True, "data": {}, "errors": {}, "message": ""}


class ExportConfigResource(Resource):
    """
    导出Code配置
    """

    class RequestSerializer(serializers.Serializer):
        action_ids = serializers.ListField(child=serializers.IntegerField(), allow_null=True, default=None)
        rule_ids = serializers.ListField(child=serializers.IntegerField(), allow_null=True, default=None)
        notice_group_ids = serializers.ListField(child=serializers.IntegerField(), allow_null=True, default=None)
        assign_group_ids = serializers.ListField(child=serializers.IntegerField(), default=None, allow_null=True)
        dashboard_uids = serializers.ListField(child=serializers.CharField(), allow_null=True, default=None)
        bk_biz_id = serializers.IntegerField()

        dashboard_for_external = serializers.BooleanField(label="仪表盘导出", default=False)

    @classmethod
    def export_rules(cls, bk_biz_id: int, rule_ids: Optional[List[int]]) -> Dict[str, str]:
        """
        导出策略配置
        """
        # 如果rule_ids是None就查询全量数据，如果是空就不查询，否则按列表过滤
        rules = StrategyModel.objects.filter(bk_biz_id=bk_biz_id)
        if rule_ids is not None:
            if not rule_ids:
                return
            rules = rules.filter(id__in=rule_ids)

        # 查询关联拓扑信息
        topo_nodes = {}
        for topo_link in api.cmdb.get_topo_tree(bk_biz_id=bk_biz_id).convert_to_topo_link().values():
            topo_link = list(reversed(topo_link[:-1]))
            for index, topo_node in enumerate(topo_link):
                path = "/".join(node.bk_inst_name for node in topo_link[: index + 1])
                topo_nodes[path] = {"bk_obj_id": topo_node.bk_obj_id, "bk_inst_id": topo_node.bk_inst_id}

        service_templates = {
            service_template["name"]: {"bk_obj_id": "SERVICE_TEMPLATE", "bk_inst_id": service_template["id"]}
            for service_template in api.cmdb.get_dynamic_query(bk_biz_id=bk_biz_id, dynamic_type="SERVICE_TEMPLATE")[
                "children"
            ]
        }
        set_templates = {
            set_template["name"]: {"bk_obj_id": "SET_TEMPLATE", "bk_inst_id": set_template["id"]}
            for set_template in api.cmdb.get_dynamic_query(bk_biz_id=bk_biz_id, dynamic_type="SET_TEMPLATE")["children"]
        }

        # 查询关联通知及告警事件
        notice_group_ids = {}
        all_user_groups = UserGroup.objects.filter(bk_biz_id__in=[bk_biz_id, 0]).only("id", "path", "name")
        for user_group in all_user_groups:
            notice_group_ids[user_group.name] = user_group.id

        action_ids = {}
        all_actions = ActionConfig.objects.filter(bk_biz_id__in=[bk_biz_id, 0]).only("id", "path", "name")
        for action in all_actions:
            action_ids[action.name] = action.id

        # 配置生成
        rule_objs = Strategy.from_models(rules)
        for strategy_obj in rule_objs:
            strategy_obj.restore()
        strategy_configs = [s.to_dict() for s in rule_objs]

        # 转换为AsCode配置
        parser = StrategyConfigParser(
            bk_biz_id=bk_biz_id,
            notice_group_ids=notice_group_ids,
            action_ids=action_ids,
            topo_nodes=topo_nodes,
            service_templates=service_templates,
            set_templates=set_templates,
        )
        for strategy_config in strategy_configs:
            name = strategy_config["name"].replace("/", "-")
            if strategy_config["path"]:
                path, filename = os.path.split(strategy_config["path"])
            else:
                path = ""
                filename = f"{name}.yaml"

            yield path, filename, yaml.dump(parser.unparse(strategy_config), allow_unicode=True)

    @classmethod
    def export_notice_groups(cls, bk_biz_id: int, notice_group_ids: Optional[List[int]]):
        """
        导出告警组配置
        """
        # 如果action_ids是None就查询全量数据，如果是空就不查询，否则按列表过滤
        user_groups = UserGroup.objects.filter(bk_biz_id=bk_biz_id)
        if notice_group_ids is not None:
            if not notice_group_ids:
                return
            user_groups = user_groups.filter(id__in=notice_group_ids)

        # 配置生成
        user_group_configs = []
        for user_group in user_groups:
            user_group_configs.append(UserGroupDetailSlz(user_group).data)

        # 查询关联告警组相关的轮值规则
        duty_rules_ids = {}
        duty_rules = DutyRule.objects.filter(bk_biz_id__in=[bk_biz_id, 0]).only("id", "path", "name")
        for duty_rule in duty_rules:
            duty_rules_ids[duty_rule.name] = duty_rule.id

        # 转换为AsCode配置
        parser = NoticeGroupConfigParser(bk_biz_id=bk_biz_id, duty_rules=duty_rules_ids)
        for user_group_config in user_group_configs:
            name = user_group_config["name"].replace("/", "-")

            if user_group_config["path"]:
                path, filename = os.path.split(user_group_config["path"])
            else:
                path = ""
                filename = f"{name}.yaml"

            yield path, filename, yaml.dump(parser.unparse(user_group_config), allow_unicode=True)

    @classmethod
    def export_duties(cls, bk_biz_id: int, duty_rules: Optional[List[int]]):
        """
        导出告警组配置
        """
        # 如果action_ids是None就查询全量数据，如果是空就不查询，否则按列表过滤
        duty_rule_queryset = DutyRule.objects.filter(bk_biz_id=bk_biz_id)
        if duty_rules is []:
            # 如果duty rule为一个空列表，表示没有需要导出的
            return
        if duty_rules:
            duty_rule_queryset = duty_rule_queryset.filter(id__in=duty_rule_queryset)

        # 配置生成
        duty_configs = []
        for duty_rule in duty_rule_queryset:
            duty_configs.append(DutyRuleDetailSlz(duty_rule).data)

        # 转换为AsCode配置
        parser = DutyRuleParser(bk_biz_id=bk_biz_id)
        for config in duty_configs:
            name = config["name"].replace("/", "-")

            if config["path"]:
                path, filename = os.path.split(config["path"])
            else:
                path = ""
                filename = f"{name}.yaml"

            yield path, filename, yaml.dump(parser.unparse(config), allow_unicode=True)

    @classmethod
    def export_actions(cls, bk_biz_id: int, action_ids: Optional[List[int]]):
        """
        导出自愈套餐配置
        """
        # 如果action_ids是None就查询全量数据，如果是空就不查询，否则按列表过滤
        actions = ActionConfig.objects.filter(bk_biz_id=bk_biz_id).exclude(plugin_id=ActionConfig.NOTICE_PLUGIN_ID)
        if action_ids is not None:
            if not action_ids:
                return
            actions = actions.filter(id__in=action_ids)

        # 配置生成
        action_configs = []
        for action in actions:
            action_configs.append(ActionConfigDetailSlz(action).data)

        # 转换为AsCode配置
        parser = ActionConfigParser(bk_biz_id=bk_biz_id, action_plugins=ActionPlugin.objects.all())
        for action_config in action_configs:
            name = action_config["name"].replace("/", "-")
            if action_config["path"]:
                path, filename = os.path.split(action_config["path"])
            else:
                path = ""
                filename = f"{name}.yaml"

            yield path, filename, yaml.dump(parser.unparse(action_config), allow_unicode=True)

    @classmethod
    def export_dashboard(cls, bk_biz_id: int, dashboard_uids: Optional[List[str]], external: bool = False):
        """
        导出grafana仪表盘配置
        """
        if dashboard_uids is not None and not dashboard_uids:
            return

        # 查询业务关联组织ID
        org_id = get_org_id(bk_biz_id)
        if not org_id:
            return

        # 查询数据源实例
        data_sources = None
        if external:
            data_sources = api.grafana.get_all_data_source(org_id=org_id)["data"]

        datasource_mapping = {}
        dashboards = api.grafana.search_folder_or_dashboard(type="dash-db", org_id=org_id)
        for info in dashboards.get("data", []):
            if dashboard_uids is not None and info["uid"] not in dashboard_uids:
                continue

            dashboard = api.grafana.get_dashboard_by_uid(org_id=org_id, uid=info["uid"])["data"]
            dashboard_config = dashboard["dashboard"]
            # 是否按外部使用导出
            if external:
                DashboardExporter(data_sources).make_exportable(dashboard_config, datasource_mapping)

            # 将仪表盘目录设置为导出文件夹目录
            if "folderTitle" in info:
                folder = info["folderTitle"].replace("/", "-")
            else:
                folder = ""

            name = dashboard["meta"]["slug"].replace("/", "-")
            yield folder, f"{name}.json", json.dumps(dashboard_config, ensure_ascii=False, indent=2)

        if datasource_mapping:
            yield "", "datasource_mapping.json", json.dumps(datasource_mapping, ensure_ascii=False, indent=2)

    @classmethod
    def export_assign_groups(cls, bk_biz_id: int, assign_group_ids: Optional[List[int]]) -> Dict[str, str]:
        """
        导出策略配置
        """
        # 如果rule_ids是None就查询全量数据，如果是空就不查询，否则按列表过滤
        assign_groups = AlertAssignGroup.objects.filter(bk_biz_id=bk_biz_id)
        if assign_group_ids is not None:
            if not assign_group_ids:
                return
            assign_groups = assign_groups.filter(id__in=assign_group_ids).only("id", "path", "name", "priority")
        groups_dict = {}
        for group in assign_groups:
            groups_dict[group.id] = {
                "id": group.id,
                "priority": group.priority,
                "name": group.name,
                "path": group.path,
                "rules": [],
            }

        assign_rules = AlertAssignRule.objects.filter(assign_group_id__in=list(groups_dict.keys()))
        assign_rules_data = AssignRuleSlz(instance=assign_rules, many=True).data

        for assign_rule in assign_rules_data:
            groups_dict[assign_rule["assign_group_id"]]["rules"].append(json.loads(json.dumps(assign_rule)))

        # 查询关联通知及告警事件
        notice_group_ids = {}
        all_user_groups = UserGroup.objects.filter(bk_biz_id__in=[bk_biz_id, 0]).only("id", "path", "name")
        for user_group in all_user_groups:
            notice_group_ids[user_group.name] = user_group.id

        action_ids = {}
        all_actions = ActionConfig.objects.filter(bk_biz_id__in=[bk_biz_id, 0]).only("id", "path", "name")
        for action in all_actions:
            action_ids[action.name] = action.id

        # 转换为AsCode配置
        parser = AssignGroupRuleParser(bk_biz_id=bk_biz_id, notice_group_ids=notice_group_ids, action_ids=action_ids)
        for group_config in groups_dict.values():
            name = group_config["name"].replace("/", "-")
            if group_config["path"]:
                path, filename = os.path.split(group_config["path"])
            else:
                path = ""
                filename = f"{name}.yaml"

            yield path, filename, yaml.dump(parser.unparse(group_config), allow_unicode=True)

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        configs = {
            "rule": {
                (f"{x[0]}|{x[1]}" if x[0] else x[1]): x[2] for x in self.export_rules(bk_biz_id, params["rule_ids"])
            },
            "notice": {
                (f"{x[0]}|{x[1]}" if x[0] else x[1]): x[2]
                for x in self.export_notice_groups(bk_biz_id, params["notice_group_ids"])
            },
            "action": {
                (f"{x[0]}|{x[1]}" if x[0] else x[1]): x[2] for x in self.export_actions(bk_biz_id, params["action_ids"])
            },
            "grafana": {
                (f"{x[0]}|{x[1]}" if x[0] else x[1]): x[2]
                for x in self.export_dashboard(bk_biz_id, params["dashboard_uids"], params["dashboard_for_external"])
            },
            "assign_group": {
                (f"{x[0]}|{x[1]}" if x[0] else x[1]): x[2]
                for x in self.export_assign_groups(bk_biz_id, params["assign_group_ids"])
            },
        }
        return configs


class ExportConfigFileResource(ExportConfigResource):
    """
    导出配置（压缩包）
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        dashboard_for_external = serializers.BooleanField(label="仪表盘导出", default=False)
        rule_ids = serializers.ListField(child=serializers.IntegerField(), default=None, allow_null=True)
        with_related_config = serializers.BooleanField(label="是否导出关联", default=False)

    @classmethod
    def create_tarfile(cls, configs: Dict[str, Iterable[Tuple[str, str, str]]]) -> str:
        """
        生成配置压缩包
        """
        temp_path = tempfile.mkdtemp()
        configs_path = os.path.join(temp_path, "configs")
        for config_type, files in configs.items():
            config_path = os.path.join(configs_path, config_type)
            for folder, name, file in files:
                # 文件名不支持/，需要替换为-
                folder = folder.replace("/", "-")
                name = name.replace("/", "-")
                # 创建配置文件夹
                Path(os.path.join(config_path, folder)).mkdir(parents=True, exist_ok=True)
                # 如果是仪表盘需要保存为json格式
                with open(os.path.join(config_path, folder, name), "w+") as f:
                    f.write(file)

        tarfile_path = os.path.join(temp_path, "configs.tar.gz")
        with tarfile.open(tarfile_path, "w:gz") as tar:
            tar.add(configs_path, arcname=os.path.basename(configs_path))

        shutil.rmtree(configs_path)
        return tarfile_path

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]

        # 默认导出全部配置，除非传入策略ID列表
        rule_ids = params.get("rule_ids")
        notice_group_ids = None
        action_ids = None
        dashboard_uids = None
        assign_group_ids = None
        duty_rules = None

        if rule_ids:
            notice_group_ids = []
            action_ids = []
            dashboard_uids = []
            assign_group_ids = []
            duty_rules = []

        # 查询关联配置
        if all([rule_ids, assign_group_ids, params.get("with_related_config")]):
            # 当既有rule_ids, 又有分派ID的时候, 才获取部分actions和user_groups
            notice_group_ids = []
            relations = StrategyActionConfigRelation.objects.filter(strategy_id__in=rule_ids)
            for relation in relations:
                if relation.relate_type == StrategyActionConfigRelation.RelateType.ACTION:
                    action_ids.append(relation.config_id)
                else:
                    notice_group_ids.extend(relation.validated_user_groups)
            assign_relations = get_assign_rule_related_resource_dict(assign_group_ids)
            notice_group_ids.extend(assign_relations["user_groups"])
            action_ids.extend(assign_relations["action_ids"])

            notice_group_ids = list(set(notice_group_ids))
            action_ids = list(set(action_ids))
            if notice_group_ids:
                duty_rules = list(
                    DutyRuleRelation.objects.filter(user_group_id__in=notice_group_ids).values_list(
                        "duty_rule_id", flat=True
                    )
                )

        configs = {
            "rule": self.export_rules(bk_biz_id, rule_ids),
            "notice": self.export_notice_groups(bk_biz_id, notice_group_ids),
            "action": self.export_actions(bk_biz_id, action_ids),
            "grafana": self.export_dashboard(bk_biz_id, dashboard_uids, params["dashboard_for_external"]),
            "assign_group": self.export_assign_groups(bk_biz_id, assign_group_ids),
            "duty": self.export_duties(bk_biz_id, duty_rules),
        }

        # 压缩包制作
        tarfile_path = self.create_tarfile(configs)
        path = f"as_code/export/{params['bk_biz_id']}-{arrow.get().strftime('%Y%m%d%H%M%S')}.tar.gz"
        with open(tarfile_path, "rb") as f:
            default_storage.save(path, f)

        download_url = default_storage.url(path)
        if settings.BK_MONITOR_HOST.startswith("https://"):
            download_url = download_url.replace("http://", "https://")

        # 非http链接需要补全监控地址
        if not download_url.startswith("http"):
            download_url = urljoin(settings.BK_MONITOR_HOST, download_url)

        return {"download_url": download_url}


class ExportAllConfigFileResource(ExportConfigFileResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        dashboard_for_external = serializers.BooleanField(label="仪表盘导出", default=False)


class ImportConfigFileResource(Resource):
    """
    导入配置（压缩包）
    """

    class RequestSerializer(serializers.Serializer):
        app = serializers.CharField(default="as_code", label="配置分组")
        bk_biz_id = serializers.IntegerField(label="业务ID")
        overwrite = serializers.BooleanField(default=False, label="是否覆盖其他分组配置")
        file = serializers.FileField(label="配置文件")

        def validate(self, attrs):
            # 校验文件格式
            if not attrs["file"].name.endswith((".tar.gz", ".tgz", ".zip")):
                raise serializers.ValidationError(_("文件格式错误，仅支持tar.gz、tgz、zip格式"))

            # 文件大小限制
            if attrs["file"].size > 1024 * 1024 * 20:
                raise serializers.ValidationError(_("文件大小超过20M"))
            return attrs

    @step(state="MAKE_TASK_RECORD", message=_lazy("创建导入记录..."))
    def create_task_record(self, bk_biz_id: int, app: str, overwrite: bool, file: File):
        return AsCodeImportTask.objects.create(
            bk_biz_id=bk_biz_id,
            file=file,
            params={"app": app, "overwrite": overwrite},
        )

    @step(state="DECOMPRESSION", message=_lazy("解压中..."))
    def decompression_and_read(self, file: File):
        """
        解压文件并读取配置
        """
        with tempfile.TemporaryDirectory() as temp_path:
            # 解压文件
            if file.name.endswith(".zip"):
                with zipfile.ZipFile(file.file, "r") as zip_file:
                    zip_file.extractall(temp_path)
            else:
                with tarfile.open(fileobj=file.file) as tar:
                    tar.extractall(temp_path)

            temp_path = os.path.join(temp_path, "configs/")

            # 读取文件
            configs = {}
            for path, dirs, filenames in os.walk(temp_path):
                if not filenames:
                    continue
                path = str(path)
                relative_path = path[len(temp_path) :]
                for filename in filenames:
                    filename = str(filename)
                    if not filename.endswith((".yaml", ".yml", ".json")):
                        continue
                    f = open(os.path.join(path, filename))
                    configs[f"{relative_path}/{filename}"] = f.read()
                    f.close()
        return configs

    @step(state="IMPORT", message=_lazy("配置导入中..."))
    def import_config(self, bk_biz_id: int, app: str, overwrite: bool, configs: dict):
        return ImportConfigResource().request(
            bk_biz_id=bk_biz_id,
            app=app,
            overwrite=overwrite,
            configs=configs,
        )

    def perform_request(self, params):
        task = self.create_task_record(
            bk_biz_id=params["bk_biz_id"],
            app=params["app"],
            overwrite=params["overwrite"],
            file=params["file"],
        )
        configs = self.decompression_and_read(task.file)
        result = self.import_config(
            bk_biz_id=params["bk_biz_id"],
            app=params["app"],
            overwrite=params["overwrite"],
            configs=configs,
        )
        task.result = result
        task.save()

        return result
