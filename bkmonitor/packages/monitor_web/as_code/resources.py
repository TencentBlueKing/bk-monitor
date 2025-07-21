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
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urljoin

import arrow
import yaml
from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from api.grafana.exporter import DashboardExporter
from bk_dataview.models import Dashboard, DataSource
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
from bkmonitor.utils.request import get_request
from bkmonitor.utils.serializers import BkBizIdSerializer
from bkmonitor.views import serializers
from constants.strategy import DATALINK_SOURCE
from core.drf_resource import Resource, api
from core.drf_resource.tasks import step
from monitor_web.commons.report.resources import send_frontend_report_event
from monitor_web.grafana.utils import get_org_id

logger = logging.getLogger("monitor_web")


class ImportConfigResource(Resource):
    """
    导入Code配置
    """

    class RequestSerializer(BkBizIdSerializer):
        configs = serializers.DictField(required=True, label="文件内容")
        app = serializers.CharField(default="as_code")
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

        try:
            username = get_request().user.username if get_request(peaceful=True) else "system"

            # 统计configs里配置的数量
            config_stats_info = defaultdict(int)
            for path in params["configs"].keys():
                config_type = ""
                if path.startswith("rule/") and not path[len("rule/") :].startswith("snippets/"):
                    config_type = "rule"
                elif path.startswith("action/") and not path[len("action/") :].startswith("snippets/"):
                    config_type = "action"
                elif path.startswith("notice/") and not path[len("notice/") :].startswith("snippets/"):
                    config_type = "notice"
                elif path.startswith("assign_group/") and not path[len("assign_group/") :].startswith("snippets/"):
                    config_type = "assign_group"
                elif path.startswith("grafana/") and not path[len("grafana") :].startswith("snippets/"):
                    config_type = "grafana"

                if config_type:
                    config_stats_info[config_type] += 1
            event_content = "导入" + ",".join([f"{count}条{key}" for key, count in config_stats_info.items()])

            send_frontend_report_event(self, params["bk_biz_id"], username, event_content)
        except Exception as e:
            logger.exception(f"send frontend report event failed: {e}")

        if errors:
            return {"result": False, "data": None, "errors": errors, "message": f"{len(errors)} configs import failed"}
        else:
            return {"result": True, "data": {}, "errors": {}, "message": ""}


class ExportConfigResource(Resource):
    """
    导出Code配置
    """

    class RequestSerializer(BkBizIdSerializer):
        action_ids = serializers.ListField(child=serializers.IntegerField(), allow_null=True, default=None)
        rule_ids = serializers.ListField(child=serializers.IntegerField(), allow_null=True, default=None)
        notice_group_ids = serializers.ListField(child=serializers.IntegerField(), allow_null=True, default=None)
        assign_group_ids = serializers.ListField(child=serializers.IntegerField(), default=None, allow_null=True)
        dashboard_uids = serializers.ListField(child=serializers.CharField(), allow_null=True, default=None)

        dashboard_for_external = serializers.BooleanField(label="仪表盘导出", default=False)
        lock_filename = serializers.BooleanField(label="锁定文件名", default=False)
        with_id = serializers.BooleanField(label="带上ID", default=False)

    @classmethod
    def transform_configs(cls, parser, configs: list[dict], with_id: bool, lock_filename: bool):
        """
        配置转换为as_code格式
        """
        for config in configs:
            name = config["name"].replace("/", "-")
            if config["path"]:
                path, filename = os.path.split(config["path"])
                # 如果锁定文件名，那么文件名就是配置名称
                if lock_filename:
                    filename = f"{name}.yaml"
            else:
                path = ""
                filename = f"{name}.yaml"

            transformed_config = parser.unparse(config)

            # 是否需要带上ID
            if with_id:
                transformed_config["id"] = config["id"]

            yield path, filename, yaml.dump(transformed_config, allow_unicode=True)

    @classmethod
    def export_rules(
        cls, bk_biz_id: int, rule_ids: list[int] | None, with_id: bool = False, lock_filename: bool = False
    ) -> Iterable[tuple[str, str, str]]:
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
        dynamic_groups: dict[str, dict] = {
            dynamic_group["name"]: {"dynamic_group_id": dynamic_group["id"]}
            for dynamic_group in api.cmdb.search_dynamic_group(bk_biz_id=bk_biz_id, bk_obj_id="host")
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
        # 所有的策略需要非告警状态采集内置策略才可以导出
        rules = [rule for rule in rules if rule.source != DATALINK_SOURCE]
        rule_objs = Strategy.from_models(rules)
        for strategy_obj in rule_objs:
            strategy_obj.restore()
        strategy_configs = [s.to_dict(convert_dashboard=False) for s in rule_objs]

        # 转换为AsCode配置
        parser = StrategyConfigParser(
            bk_biz_id=bk_biz_id,
            notice_group_ids=notice_group_ids,
            action_ids=action_ids,
            topo_nodes=topo_nodes,
            service_templates=service_templates,
            set_templates=set_templates,
            dynamic_groups=dynamic_groups,
        )
        yield from cls.transform_configs(parser, strategy_configs, with_id, lock_filename)

    @classmethod
    def export_notice_groups(
        cls, bk_biz_id: int, notice_group_ids: list[int] | None, with_id: bool = False, lock_filename: bool = False
    ):
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
        yield from cls.transform_configs(parser, user_group_configs, with_id, lock_filename)

    @classmethod
    def export_duties(
        cls, bk_biz_id: int, duty_rules: list[int] | None, with_id: bool = False, lock_filename: bool = False
    ):
        """
        导出告警组配置
        """
        # 如果action_ids是None就查询全量数据，如果是空就不查询，否则按列表过滤
        duty_rule_queryset = DutyRule.objects.filter(bk_biz_id=bk_biz_id)
        if duty_rules == []:
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
        yield from cls.transform_configs(parser, duty_configs, with_id, lock_filename)

    @classmethod
    def export_actions(
        cls, bk_biz_id: int, action_ids: list[int] | None, with_id: bool = False, lock_filename: bool = False
    ):
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
        yield from cls.transform_configs(parser, action_configs, with_id, lock_filename)

    @classmethod
    def export_dashboard(cls, bk_biz_id: int, dashboard_uids: list[str] | None, external: bool = False):
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
            data_sources = DataSource.objects.filter(org_id=org_id).values("name", "type", "uid")

        # 查询文件夹
        folder_id_to_title = {
            folder["id"]: folder["title"]
            for folder in Dashboard.objects.filter(org_id=org_id, is_folder=True).values("id", "title")
        }

        datasource_mapping = {}
        dashboards = Dashboard.objects.filter(org_id=org_id, is_folder=False)
        if dashboard_uids:
            dashboards = dashboards.filter(uid__in=dashboard_uids)

        for dashboard in dashboards:
            dashboard_config = json.loads(dashboard.data)

            # 是否按外部使用导出
            if external:
                DashboardExporter(data_sources).make_exportable(dashboard_config, datasource_mapping)

            # 将仪表盘目录设置为导出文件夹目录
            if dashboard.folder_id in folder_id_to_title:
                folder = folder_id_to_title[dashboard.folder_id].replace("/", "-")
            else:
                folder = ""

            name = dashboard.slug.replace("/", "-")
            yield folder, f"{name}.json", json.dumps(dashboard_config, ensure_ascii=False, indent=2)

        if datasource_mapping:
            yield "", "datasource_mapping.json", json.dumps(datasource_mapping, ensure_ascii=False, indent=2)

    @classmethod
    def export_assign_groups(
        cls, bk_biz_id: int, assign_group_ids: list[int] | None, with_id: bool = False, lock_filename: bool = False
    ) -> Iterable[tuple[str, str, str]]:
        """
        导出策略配置
        """
        # 如果rule_ids是None就查询全量数据，如果是空就不查询，否则按列表过滤
        assign_groups = AlertAssignGroup.objects.filter(bk_biz_id=bk_biz_id).only(
            "id", "path", "name", "priority", "source"
        )
        if assign_group_ids is not None:
            if not assign_group_ids:
                return
            assign_groups = assign_groups.filter(id__in=assign_group_ids)
        groups_dict = {}
        for group in assign_groups:
            if group.source == DATALINK_SOURCE:
                # 内置的，不允许导出
                continue
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
        yield from cls.transform_configs(parser, list(groups_dict.values()), with_id, lock_filename)

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        configs = {
            "rule": {
                (f"{x[0]}|{x[1]}" if x[0] else x[1]): x[2]
                for x in self.export_rules(bk_biz_id, params["rule_ids"], params["with_id"], params["lock_filename"])
            },
            "notice": {
                (f"{x[0]}|{x[1]}" if x[0] else x[1]): x[2]
                for x in self.export_notice_groups(
                    bk_biz_id, params["notice_group_ids"], params["with_id"], params["lock_filename"]
                )
            },
            "action": {
                (f"{x[0]}|{x[1]}" if x[0] else x[1]): x[2]
                for x in self.export_actions(
                    bk_biz_id, params["action_ids"], params["with_id"], params["lock_filename"]
                )
            },
            "grafana": {
                (f"{x[0]}|{x[1]}" if x[0] else x[1]): x[2]
                for x in self.export_dashboard(bk_biz_id, params["dashboard_uids"], params["dashboard_for_external"])
            },
            "assign_group": {
                (f"{x[0]}|{x[1]}" if x[0] else x[1]): x[2]
                for x in self.export_assign_groups(
                    bk_biz_id, params["assign_group_ids"], params["with_id"], params["lock_filename"]
                )
            },
        }
        return configs


class ExportConfigFileResource(ExportConfigResource):
    """
    导出配置（压缩包）
    """

    class RequestSerializer(BkBizIdSerializer):
        dashboard_for_external = serializers.BooleanField(label="仪表盘导出", default=False)
        rule_ids = serializers.ListField(child=serializers.IntegerField(), default=None, allow_null=True)
        with_related_config = serializers.BooleanField(label="是否导出关联", default=False)
        lock_filename = serializers.BooleanField(label="锁定文件名", default=False)
        with_id = serializers.BooleanField(label="带上ID", default=False)

    @classmethod
    def create_tarfile(
        cls, configs: dict[str, Iterable[tuple[str, str, str]]], config_stats_info: dict[str, int]
    ) -> str:
        """
        生成配置压缩包

        同时统计不同配置的数量
        """
        temp_path = tempfile.mkdtemp()
        configs_path = os.path.join(temp_path, "configs")
        for config_type, files in configs.items():
            config_path = os.path.join(configs_path, config_type)
            for folder, name, file in files:
                config_stats_info[config_type] += 1

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
            "rule": self.export_rules(bk_biz_id, rule_ids, params["with_id"], params["lock_filename"]),
            "notice": self.export_notice_groups(
                bk_biz_id, notice_group_ids, params["with_id"], params["lock_filename"]
            ),
            "action": self.export_actions(bk_biz_id, action_ids, params["with_id"], params["lock_filename"]),
            "grafana": self.export_dashboard(bk_biz_id, dashboard_uids, params["dashboard_for_external"]),
            "assign_group": self.export_assign_groups(
                bk_biz_id, assign_group_ids, params["with_id"], params["lock_filename"]
            ),
            "duty": self.export_duties(bk_biz_id, duty_rules, params["with_id"], params["lock_filename"]),
        }

        # 压缩包制作
        config_stats_info = defaultdict(int)
        tarfile_path = self.create_tarfile(
            configs, config_stats_info
        )  # 传入config_stats_info 在里面的生成器中统计不同config的数量
        path = f"as_code/export/{bk_biz_id}-{arrow.get().strftime('%Y%m%d%H%M%S')}.tar.gz"
        with open(tarfile_path, "rb") as f:
            default_storage.save(path, f)

        download_url = default_storage.url(path)
        if settings.BK_MONITOR_HOST.startswith("https://"):
            download_url = download_url.replace("http://", "https://")

        # 非http链接需要补全监控地址
        if not download_url.startswith("http"):
            download_url = urljoin(settings.BK_MONITOR_HOST, download_url)

        try:
            username = get_request().user.username if get_request(peaceful=True) else "system"
            event_content = "导出" + ",".join(
                [f"{count}条{config_type}" for config_type, count in config_stats_info.items()]
            )

            send_frontend_report_event(self, bk_biz_id, username, event_content)
        except Exception as e:
            logger.exception(f"send frontend report event failed: {e}")

        return {"download_url": download_url}


class ExportAllConfigFileResource(ExportConfigFileResource):
    class RequestSerializer(BkBizIdSerializer):
        dashboard_for_external = serializers.BooleanField(label="仪表盘导出", default=False)
        lock_filename = serializers.BooleanField(label="锁定文件名", default=False)
        with_id = serializers.BooleanField(label="带上ID", default=False)


class ImportConfigFileResource(Resource):
    """
    导入配置（压缩包）
    """

    class RequestSerializer(BkBizIdSerializer):
        app = serializers.CharField(default="as_code", label="配置分组")
        overwrite = serializers.BooleanField(default=False, label="是否覆盖其他分组配置")
        file = serializers.FileField(label="配置文件")
        incremental = serializers.BooleanField(default=False)

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

    @staticmethod
    def parse_config_file_name(file_name: str) -> str | None:
        """
        解析配置文件名
        """
        # 判断路径前缀
        if file_name.startswith("./configs/"):
            file_name = file_name[len("./configs/") :]
        elif file_name.startswith("configs/"):
            file_name = file_name[len("configs/") :]
        else:
            return None

        # 判断文件后缀
        if file_name.endswith((".yaml", ".yml", ".json")):
            return file_name

    @step(state="DECOMPRESSION", message=_lazy("解压中..."))
    def decompression_and_read(self, file: File):
        """
        直接读取压缩包中的文件内容而不解压
        """
        if not file.name:
            raise serializers.ValidationError(_("文件名不能为空"))

        configs = {}
        if file.name.endswith(".zip"):
            with zipfile.ZipFile(file.file, "r") as zip_file:
                for file_info in zip_file.infolist():
                    config_name = self.parse_config_file_name(file_info.filename)
                    if not config_name:
                        continue
                    with zip_file.open(file_info) as f:
                        configs[config_name] = f.read().decode("utf-8")
        elif file.name.endswith((".tar.gz", ".tgz")):
            with tarfile.open(fileobj=file.file) as tar:
                for member in tar.getmembers():
                    # 判断是否是文件
                    if not member.isfile():
                        continue

                    config_name = self.parse_config_file_name(member.name)
                    if not config_name:
                        continue
                    f = tar.extractfile(member)
                    if f:
                        configs[config_name] = f.read().decode("utf-8")
        else:
            raise serializers.ValidationError(_("文件格式错误，仅支持zip、tar.gz、tgz格式"))
        return configs

    @step(state="IMPORT", message=_lazy("配置导入中..."))
    def import_config(self, bk_biz_id: int, app: str, overwrite: bool, configs: dict, incremental: bool = False):
        return ImportConfigResource().request(
            bk_biz_id=bk_biz_id,
            app=app,
            overwrite=overwrite,
            configs=configs,
            incremental=incremental,
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
            incremental=params["incremental"],
        )
        task.result = result
        task.save()

        return result
