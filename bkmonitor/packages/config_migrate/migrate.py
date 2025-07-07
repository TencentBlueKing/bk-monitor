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
import os.path
import re
import tarfile
import tempfile
import time
from collections import defaultdict
from typing import IO, Dict, List, Union

import MySQLdb
import requests
import yaml
from django.core.files import File

from bkmonitor.as_code.parse import import_code_config
from bkmonitor.as_code.parse_yaml import StrategyConfigParser
from bkmonitor.strategy.new_strategy import Strategy
from constants.action import ActionSignal
from core.drf_resource import api, resource
from monitor_web.models import (
    CollectConfigMeta,
    CollectorPluginMeta,
    CustomEventGroup,
    CustomTSTable,
)


class ConfigMigrator:
    """
    策略配置集，包含策略，通知组及仪表盘
    bk_env: o.bk.tencent.com, bk.iegcom.com
    """

    BK_ENVS = ["o.bk.tencent.com", "bk.iegcom.com"]

    def __init__(self, bk_env: str, old_bk_biz_id: int, new_bk_biz_id: int, mysql_config: Dict):
        self.bk_env = bk_env
        self.bk_biz_id = new_bk_biz_id
        self.old_bk_biz_id = old_bk_biz_id

        # 数据库连接
        self.connect = MySQLdb.connect(
            host=mysql_config["host"],
            port=mysql_config["port"],
            user=mysql_config["user"],
            password=mysql_config["password"],
            database=mysql_config["database"],
        )

        # cmdb id偏移及日志索引集映射
        self.cmdb_id_offset: int = 0
        self.index_set_mapping: Dict[int, int] = {}
        self.get_third_party_mapping()

        # 配置
        self.strategies: Dict[int, Dict] = {}
        self.notice_groups: Dict[int, Dict] = {}
        self.dashboards: Dict[str, Dict] = {}
        self.actions: Dict[str, Dict] = {}
        self.code_configs: Dict[str, str] = {}

        # 自定义上报/采集配置
        self.plugins = []
        self.custom_metrics = []
        self.custom_events = {}
        self.collects = []

        # 自定义上报/采集配置映射
        self.custom_metric_table_mapping: Dict[str, str] = {}
        self.custom_event_table_mapping: Dict[str, str] = {}
        self.collect_id_mapping: Dict[int, int] = {}

        # yaml mapping
        self.notice_group_name_to_id: Dict[str, int] = {}
        self.actions_name_to_id: Dict[str, int] = {}

        self.config_types = {
            "strategy": self.strategies,
            "notice_group": self.notice_groups,
            "dashboard": self.dashboards,
            "custom_metric": self.custom_metrics,
            "custom_event": self.custom_events,
            "collect": self.collects,
            "plugin": self.plugins,
        }

    def create_table(self):
        """
        创建中转数据表
        """
        cur = self.connect.cursor()
        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS `bk_monitor_configs` (
          `id` int(11) NOT NULL auto_increment,
          `old_bk_biz_id` int(11) NOT NULL,
          `bk_biz_id` int(11) NOT NULL,
          `config_type` varchar(32) NOT NULL,
          `filename`  varchar(128) NULL,
          `config` longtext NULL,
           PRIMARY KEY  (`id`)
        ) charset=utf8"""
        )

        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS `bk_monitor_resource_mapping` (
          `id` int(11) NOT NULL auto_increment,
          `old_bk_biz_id` int(11) NOT NULL,
          `bk_biz_id` int(11) NOT NULL,
          `config_type` varchar(32) NOT NULL,
          `old_key`  varchar(128) NULL,
          `new_key` varchar(128) NULL,
           PRIMARY KEY  (`id`)
        ) charset=utf8"""
        )
        cur.close()

    def read_from_config_and_save_to_db(self, path_or_file: Union[str, IO[bytes]]):
        """
        从配置中读取策略配置集
        """
        tempdir = tempfile.TemporaryDirectory()
        if isinstance(path_or_file, str):
            tar = tarfile.open(path_or_file, "r:gz")
        else:
            tar = tarfile.open(fileobj=path_or_file, mode="r:gz")
        tar.extractall(path=tempdir.name)
        tar.close()

        cur = self.connect.cursor()

        # 清空该业务下的所有配置
        cur.execute("delete from bk_monitor_configs where bk_biz_id=%s", (self.bk_biz_id,))

        # 读取配置
        for config_type in self.config_types.keys():
            for filename in os.listdir(os.path.join(tempdir.name, config_type)):
                if not filename.endswith(".json"):
                    continue
                with open(os.path.join(tempdir.name, config_type, filename), "r") as f:
                    config = f.read()
                    print(f"reading {config_type}/{filename}, length: {len(config)}")
                    sql = (
                        "insert into bk_monitor_configs (old_bk_biz_id, bk_biz_id, config_type, filename, config) "
                        "values (%s, %s, %s, %s, %s)"
                    )
                    args = (self.old_bk_biz_id, self.bk_biz_id, config_type, filename, config)
                    cur.execute(sql, args)

        self.connect.commit()
        tempdir.cleanup()
        cur.close()

    def read_from_mysql(self):
        """
        从数据库读取配置
        """
        for config_type in self.config_types.keys():
            self.config_types[config_type].clear()

        cur = self.connect.cursor()
        cur.execute(
            "select config_type, filename, config from bk_monitor_configs where bk_biz_id=%s", (self.bk_biz_id,)
        )

        for config_type, filename, config in cur.fetchall():
            config = json.loads(config)
            configs = self.config_types[config_type]

            if isinstance(configs, list):
                if isinstance(config, list):
                    configs.extend(config)
                else:
                    configs.append(config)
            elif isinstance(configs, dict):
                if config_type in ["strategy", "notice_group"]:
                    configs[config["id"]] = config
                elif config_type == "dashboard":
                    folder = config.get("folderTitle", "").replace("/", "-")
                    if folder:
                        name = f"{folder}/{filename}"
                    else:
                        name = filename
                    configs[name] = config
                elif config_type == "custom_event":
                    configs[config["bk_event_group_id"]] = config
                elif config_type == "custom_metric":
                    configs[config["time_series_group_id"]] = config
        cur.close()

    def get_third_party_mapping(self):
        """
        读取第三方配置映射
        """
        cur = self.connect.cursor()

        try:
            # 查询业务映射
            cur.execute("select bk_new_biz_id from cc_envbizmap where bk_old_biz_id=%s", (self.old_bk_biz_id,))
            bk_biz_id = int(cur.fetchall()[0][0])
            if bk_biz_id != self.bk_biz_id:
                raise Exception(f"业务映射错误，old_bk_biz_id: {self.old_bk_biz_id}, bk_biz_id: {bk_biz_id}")
        except IndexError:
            print(f"业务{self.old_bk_biz_id}不存在，cmdb数据未进行官方迁移，后续涉及cmdb的数据将无法正确映射")

        # todo: 日志的索引集需要支持bk_env
        try:
            cur.execute("select index_set_id, origin_index_set_id from bk_log_search_resource_mapping")
            for index_set_id, origin_index_set_id in cur.fetchall():
                self.index_set_mapping[int(origin_index_set_id)] = int(index_set_id)
        except MySQLdb.ProgrammingError:
            pass

        try:
            # cmdb 拓扑ID 偏移量
            cur.execute("select offset from cc_EnvIDOffset where env=%s", (self.bk_env,))
            self.cmdb_id_offset = int(cur.fetchall()[0][0])
        except IndexError:
            print(f"业务{self.old_bk_biz_id}不存在，无法进行cmdb节点映射")

        cur.close()

    def convert_notice_group_to_yaml(self):
        """
        转换通知组配置为yaml格式
        """
        notice_groups = {}
        for notice_group_id, notice_group in self.notice_groups.items():
            self.notice_group_name_to_id[notice_group["name"]] = notice_group_id

            wxwork_chatids = defaultdict(list)
            for level, chatids in notice_group["wxwork_group"].items():
                if not chatids:
                    continue
                wxwork_chatids[level].extend(chatids.split(","))

            notice_groups[notice_group_id] = {
                "name": notice_group["name"],
                "description": notice_group["message"],
                "users": notice_group["notice_receiver"],
                "alert": {"00:00--23:59": {}},
                "action": {
                    "00:00--23:59": {
                        "execute": {"type": ["weixin", "mail"]},
                        "execute_failed": {"type": ["weixin", "mail"]},
                        "execute_success": {"type": ["weixin", "mail"]},
                    }
                },
            }

            level_mapping = {"remind": "3", "warning": "2", "fatal": "1"}
            for level_name, level in level_mapping.items():
                if level in wxwork_chatids:
                    notice_groups[notice_group_id]["alert"]["00:00--23:59"][level_name] = {
                        "type": notice_group["notice_way"][level],
                        "chatids": wxwork_chatids[level],
                    }
                else:
                    notice_groups[notice_group_id]["alert"]["00:00--23:59"][level_name] = {
                        "type": notice_group["notice_way"][level]
                    }

            # 如果有webhook，则添加webhook动作套餐
            if notice_group.get("webhook_url"):
                action_name = "[webhook] {}".format(notice_group["name"])
                self.actions[action_name] = {
                    "name": action_name,
                    "type": "webhook",
                    "template_detail": {
                        "method": "POST",
                        "url": notice_group["webhook_url"],
                        "headers": [],
                        "authorize": {"auth_type": "none", "auth_config": {}},
                        "body": {
                            "data_type": "raw",
                            "params": [],
                            "content": "{{alarm.callback_message}}",
                            "content_type": "json",
                        },
                        "query_params": [],
                        "need_poll": True,
                        "notify_interval": 2 * 60,  # 默认2小时回调一次
                        "failed_retry": {
                            "is_enabled": True,
                            "max_retry_times": 3,
                            "retry_interval": 3,
                            "timeout": 3,
                        },
                    },
                    "timeout": 600,
                }
        self.notice_groups = notice_groups

    def convert_strategy_to_yaml(self):
        # 获取cmdb信息
        topo_nodes = {}
        for topo_link in api.cmdb.get_topo_tree(bk_biz_id=self.bk_biz_id).convert_to_topo_link().values():
            topo_link = list(reversed(topo_link[:-1]))
            for index, topo_node in enumerate(topo_link):
                path = "/".join(node.bk_inst_name for node in topo_link[: index + 1])
                topo_nodes[path] = {"bk_obj_id": topo_node.bk_obj_id, "bk_inst_id": topo_node.bk_inst_id}

        service_templates = {
            service_template["name"]: {"bk_obj_id": "SERVICE_TEMPLATE", "bk_inst_id": service_template["id"]}
            for service_template in api.cmdb.get_dynamic_query(
                bk_biz_id=self.bk_biz_id, dynamic_type="SERVICE_TEMPLATE"
            )["children"]
        }
        set_templates = {
            set_template["name"]: {"bk_obj_id": "SET_TEMPLATE", "bk_inst_id": set_template["id"]}
            for set_template in api.cmdb.get_dynamic_query(bk_biz_id=self.bk_biz_id, dynamic_type="SET_TEMPLATE")[
                "children"
            ]
        }

        # 将策略配置转换为yaml格式
        p = StrategyConfigParser(
            bk_biz_id=2,
            notice_group_ids=self.notice_group_name_to_id,
            action_ids={},
            topo_nodes=topo_nodes,
            service_templates=service_templates,
            set_templates=set_templates,
        )

        strategies = {}
        # 插入webhook动作配置
        for strategy_id, strategy in self.strategies.items():
            strategies[strategy_id] = p.unparse(strategy)
            for user_group in strategies[strategy_id]["notice"]["user_groups"]:
                if f"[webhook] {user_group}" not in self.actions_name_to_id:
                    continue
                strategies[strategy_id].setdefault("actions", []).append(
                    {
                        "action": f"[webhook] {user_group}",
                        "signal": ["abnormal", "recovery"],
                        "converge": {"count": 1, "func": "skip_when_success", "interval": 1},
                    }
                )
        self.strategies = strategies

    def convert_to_yaml(self):
        self.convert_notice_group_to_yaml()
        self.convert_strategy_to_yaml()

        configs = {}
        for strategy_id, strategy in self.strategies.items():
            configs[f"rule/{strategy_id}.yaml"] = yaml.dump(strategy, allow_unicode=True)
        for action_id, action in self.actions.items():
            configs[f"action/{action_id}.yaml"] = yaml.dump(action, allow_unicode=True)
        for notice_group_id, notice_group in self.notice_groups.items():
            configs[f"notice/{notice_group_id}.yaml"] = yaml.dump(notice_group, allow_unicode=True)
        for dashboard_name, dashboard in self.dashboards.items():
            if "dashboard" in dashboard and "meta" in dashboard:
                dashboard = dashboard["dashboard"]
            configs[f"grafana/{dashboard_name}"] = json.dumps(dashboard, ensure_ascii=False)

        self.code_configs = configs

    def write_yaml(self, path: str):
        self.convert_to_yaml()
        os.makedirs(path, exist_ok=True)
        for filename, config in self.code_configs.items():
            os.makedirs(os.path.join(path, os.path.dirname(filename)), exist_ok=True)
            with open(os.path.join(path, filename), "w") as f:
                if filename.endswith(".yaml"):
                    yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
                else:
                    json.dump(config, f, indent=2, ensure_ascii=False)

    def replace_strategy_config(self, strategies: Dict):
        """
        1. 替换策略监控目标
        2. 替换策略表名，日志索引集ID，数据平台表名，自定义上报表名
        3. 替换策略条件中的采集配置ID
        """
        # 替换策略监控目标
        for strategy in strategies.values():
            for item in strategy["items"]:
                for query_config in item["query_configs"]:
                    data_source = (query_config["data_source_label"], query_config["data_type_label"])

                    # 日志平台索引集ID替换
                    if "index_set_id" in query_config and int(query_config["index_set_id"]) in self.index_set_mapping:
                        query_config["index_set_id"] = self.index_set_mapping[int(query_config["index_set_id"])]

                    # 数据平台表名替换业务ID前缀
                    if data_source[0] == "bk_data" and query_config["result_table_id"].startswith(
                        f"{self.old_bk_biz_id}_"
                    ):
                        query_config[
                            "result_table_id"
                        ] = f"{self.bk_biz_id}_{query_config['result_table_id'][len(str(self.old_bk_biz_id)) + 1:]}"

                    # 自定义指标表名替换
                    if data_source == ("custom", "time_series"):
                        query_config["result_table_id"] = self.custom_metric_table_mapping.get(
                            query_config["result_table_id"], query_config["result_table_id"]
                        )

                    # 自定义事件表名替换
                    if data_source == ("custom", "event"):
                        query_config["result_table_id"] = self.custom_event_table_mapping.get(
                            query_config["result_table_id"], query_config["result_table_id"]
                        )

    def replace_dashboard_config(self, old_dashboards: Dict):
        """
        替换仪表盘配置
        """
        for name, dashboard in old_dashboards.items():
            dashboard = json.dumps(dashboard)
            for old_table, new_table in self.custom_metric_table_mapping.items():
                dashboard = dashboard.replace(old_table, new_table)
            for old_table, new_table in self.custom_event_table_mapping.items():
                dashboard = dashboard.replace(old_table, new_table)

            dashboard = re.sub(rf'(bk_data\.|"){self.old_bk_biz_id}_', rf"\g<1>{self.bk_biz_id}_", dashboard)
            self.dashboards[name] = json.loads(dashboard)

    def import_plugins(self, plugins: List[Dict]):
        """
        导入插件
        """
        exists_plugin_ids = list(
            CollectorPluginMeta.objects.filter(bk_biz_id=self.bk_biz_id).values_list("plugin_id", flat=True)
        )

        for plugin in plugins:
            plugin_id = plugin["plugin_id"]

            # 如果插件已经存在，则跳过
            if plugin_id in exists_plugin_ids:
                continue

            # 获取插件信息
            info = api.node_man.plugin_info({"name": plugin_id})[0]

            # 获取插件包
            param = {
                "category": "gse_plugin",
                "query_params": {"project": info["project"], "version": info["version"]},
                "creator": "admin",
            }
            package_result = api.node_man.export_raw_package(param)
            job_id = package_result["job_id"]
            i = 0
            download_url = ""
            while i < 15:
                query_result = api.node_man.export_query_task({"job_id": job_id})
                if query_result["is_finish"]:
                    download_url = query_result["download_url"]
                    break
                if query_result["is_failed"]:
                    raise Exception(f"下载插件{plugin_id}失败: {query_result['error_message']}")
                time.sleep(1)
            if not download_url:
                raise Exception(f"下载插件{plugin_id}失败: 请求超时")

            # 下载并导入插件包
            with tempfile.TemporaryDirectory() as temp_dir:
                # 下载插件包
                package_path = os.path.join(temp_dir, f"{plugin_id}.tgz")
                r = requests.get(download_url, stream=True)
                with open(package_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)

                # 导入插件包
                with open(package_path, "rb") as f:
                    resource.plugin.plugin_import_without_frontend(
                        {
                            "bk_biz_id": self.bk_biz_id,
                            "file_data": File(f),
                            "operator": "system",
                            "metric_json": plugin["metric_json"],
                        }
                    )

    def import_collect_config(self, collect_configs: List[Dict]):
        """
        导入采集配置
        如果拓扑不存在怎么办(跳过/报错)
        """
        # 查询存量采集配置
        exists_collect_names = list(
            CollectConfigMeta.objects.filter(bk_biz_id=self.bk_biz_id).values_list("name", flat=True)
        )

        cur = self.connect.cursor()

        # 导入采集配置
        for collect_config in collect_configs:
            if collect_config["name"] in exists_collect_names:
                continue
            collect_config_copy = json.loads(json.dumps(collect_config))
            collect_config_copy.pop("id", None)
            collect_config_copy["bk_biz_id"] = self.bk_biz_id

            # cmdb拓扑ID偏移
            for target_node in collect_config_copy["target_nodes"]:
                if "bk_inst_id" in target_node:
                    target_node["bk_inst_id"] += self.cmdb_id_offset

                if "bk_cloud_id" in target_node:
                    target_node["bk_cloud_id"] += self.cmdb_id_offset

            result = resource.collecting.save_collect_config(collect_config_copy)
            cur.execute(
                "INSERT INTO bk_monitor_resource_mapping (old_bk_biz_id, bk_biz_id, config_type, old_key, new_key) "
                "VALUES (%s, %s, %s, %s, %s)",
                (self.old_bk_biz_id, self.bk_biz_id, "collect", collect_config["id"], result["id"]),
            )

        cur.close()

    def import_custom_report(self, custom_metrics: List[Dict], custom_events: List[Dict]):
        """
        导入自定义上报
        @param custom_metrics: 自定义指标
        @param custom_events: 自定义事件
        """
        cur = self.connect.cursor()

        env_index = self.BK_ENVS.index(self.bk_env)

        # 查询存量自定义指标
        exists_metric_names = list(
            CustomTSTable.objects.filter(bk_biz_id=self.bk_biz_id).values_list("name", flat=True)
        )
        exists_metric_names_tables = {
            custom_metric["name"]: custom_metric["table_id"]
            for custom_metric in CustomTSTable.objects.filter(bk_biz_id=self.bk_biz_id).values("name", "table_id")
        }
        for custom_metric in custom_metrics:
            # 如果指标已经存在，则跳过
            if custom_metric["name"] in exists_metric_names:
                self.custom_metric_table_mapping[custom_metric["table_id"]] = exists_metric_names_tables[
                    custom_metric["name"]
                ]
                continue

            # 保存自定义指标
            result = resource.custom_report.create_custom_time_series(
                bk_biz_id=self.bk_biz_id,
                name=custom_metric["name"],
                scenario=custom_metric["scenario"],
                data_label=f"m{env_index}{custom_metric['bk_data_id']}",
                desc=custom_metric["desc"],
            )
            record = CustomTSTable.objects.get(time_series_group_id=result["time_series_group_id"])
            # 保存自定义指标字段
            cur.execute(
                "INSERT INTO bk_monitor_resource_mapping (old_bk_biz_id, bk_biz_id, config_type, old_key, new_key) "
                "VALUES (%s, %s, %s, %s, %s)",
                (self.old_bk_biz_id, self.bk_biz_id, "custom_metric", custom_metric["table_id"], record.table_id),
            )
            self.custom_metric_table_mapping[custom_metric["table_id"]] = record.table_id

        # 查询存量自定义事件
        exists_event_names = list(
            CustomEventGroup.objects.filter(bk_biz_id=self.bk_biz_id).values_list("name", flat=True)
        )
        exists_event_names_tables = {
            custom_event["name"]: custom_event["table_id"]
            for custom_event in CustomEventGroup.objects.filter(bk_biz_id=self.bk_biz_id).values("name", "table_id")
        }
        for custom_event in custom_events:
            # 如果事件已经存在，则跳过
            if custom_event["name"] in exists_event_names:
                self.custom_event_table_mapping[custom_event["table_id"]] = exists_event_names_tables[
                    custom_event["name"]
                ]
                continue

            # 保存自定义事件
            result = resource.custom_report.create_custom_event_group(
                bk_biz_id=self.bk_biz_id,
                name=custom_event["name"],
                scenario=custom_event["scenario"],
                data_label=f"e{env_index}{custom_event['bk_data_id']}",
            )
            record = CustomEventGroup.objects.get(bk_event_group_id=result["bk_event_group_id"])
            # 保存自定义事件字段
            cur.execute(
                "INSERT INTO bk_monitor_resource_mapping (old_bk_biz_id, bk_biz_id, config_type, old_key, new_key) "
                "VALUES (%s, %s, %s, %s, %s)",
                (self.old_bk_biz_id, self.bk_biz_id, "custom_event", custom_event["table_id"], record.table_id),
            )
            self.custom_metric_table_mapping[custom_event["table_id"]] = record.table_id

        cur.close()

    def normalize_strategy(self, strategies: Dict[int, Dict]):
        """
        配置标准化
        """

        # 将旧版策略配置转为新版
        for strategy_id in list(strategies.keys()):
            strategy = strategies[strategy_id]

            if "item_list" not in strategy:
                if strategy["actions"] and strategy["actions"][0]["type"] == "notice":
                    action = strategy["actions"][0]
                    strategy["actions"] = []

                    signal = [ActionSignal.ABNORMAL, ActionSignal.NO_DATA]

                    if action["config"].get("send_recovery_alarm"):
                        signal.append(ActionSignal.RECOVERED)

                    strategy["notice"] = {
                        "user_groups": action["notice_group_ids"],
                        "signal": signal,
                        "options": {
                            "converge_config": {
                                "need_biz_converge": True,
                            },
                        },
                        "config": {
                            "notify_interval": int(action.get("alarm_interval", 120)) * 60,
                            "interval_notify_mode": "standard",
                            "template": [
                                {
                                    "signal": ActionSignal.ABNORMAL,
                                    "message_tmpl": action["notice_template"].get("anomaly_template", ""),
                                    "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}",
                                },
                                {
                                    "signal": ActionSignal.RECOVERED,
                                    "message_tmpl": action["notice_template"].get("recovery_template", ""),
                                    "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}",
                                },
                                {
                                    "signal": ActionSignal.CLOSED,
                                    "message_tmpl": action["notice_template"].get("anomaly_template", ""),
                                    "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}",
                                },
                            ],
                        },
                    }
                strategies[strategy_id] = Strategy(**strategy).to_dict()
                continue

            # 将自定义事件ID转换为表名/指标名
            item = strategy["item_list"][0]
            if "bk_event_group_id" in item:
                if item["bk_event_group_id"] not in self.custom_events:
                    strategies.pop(strategy_id)
                    continue

                item["result_table_id"] = self.custom_events[item["bk_event_group_id"]]["table_id"]
                item["metric_field"] = item["extend_fields"]["custom_event_name"] or "__INDEX__"

            # 配置转换
            strategies[strategy_id] = Strategy.from_dict_v1(strategy).to_dict()

        # 监控目标配置增加偏移量
        for strategy in strategies.values():
            for item in strategy["items"]:
                target = item["target"]
                if not target or not target[0]:
                    continue
                for node in target[0][0]["value"]:
                    if "bk_inst_id" in node and node["bk_inst_id"] < self.cmdb_id_offset:
                        node["bk_inst_id"] += self.cmdb_id_offset
                    if "bk_cloud_id" in node and node["bk_cloud_id"] < self.cmdb_id_offset:
                        node["bk_cloud_id"] += self.cmdb_id_offset

    def upload_config(self, path_or_file: Union[str, IO[bytes]]):
        """
        上传旧版配置
        """
        # 0. 中间表初始化
        self.create_table()

        # 1. 将导出的业务配置数据写入到数据库
        self.read_from_config_and_save_to_db(path_or_file)

    def migrate(self):
        """
        配置迁移
        """
        # 0. 中间表初始化
        self.read_from_mysql()

        # 1. 配置标准化
        self.normalize_strategy(self.strategies)

        # 2. 从节点管理同步业务插件
        # 可能导致中断的异常: 不存在的插件记录，导入插件失败。
        # 可重入: 通过插件表记录跳过已存在的同id插件，避免重复执行
        self.import_plugins(self.plugins)

        # 3. 导入采集插件并记录映射ID
        # 可能导致中断的异常: 导入失败报错
        # 可重入: 通过采集表记录跳过已存在的同名采集配置，也可以通过映射ID表判断，避免重复执行
        # 问题: 如何处理不存在的监控目标
        self.import_collect_config(self.collects)

        # 4. 生成自定义指标/事件并记录映射ID
        # 可能导致中断的异常: metadata接口报错
        # 可重入: 通过自定义指标/事件表记录跳过已存在的同名指标/事件，也可以通过映射ID表判断，避免重复执行
        self.import_custom_report(self.custom_metrics, list(self.custom_events.values()))

        # 5. 根据映射关系，将策略/仪表盘中的配置进行替换
        # 可能导致中断的异常: 逻辑错误导致的处理错误
        # 直接对数据库中的配置进行操作
        self.replace_strategy_config(self.strategies)
        self.replace_dashboard_config(self.dashboards)

        # 6. 导入策略/通知组/仪表盘配置
        # 可能导致中断的异常: 重名导致导入失败，目标映射失败导致导入失败，环境API调用失败
        # 可重入: 通过ascode的能力本身实现可重入
        # 问题: 如何处理不存在的监控目标
        self.convert_to_yaml()

        errors = import_code_config(self.bk_biz_id, "default", self.code_configs, overwrite=True)
        if errors:
            print("导入配置存在错误:")
            print(json.dumps(errors, indent=2, ensure_ascii=False))
