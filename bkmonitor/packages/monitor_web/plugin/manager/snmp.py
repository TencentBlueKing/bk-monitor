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
import os

import yaml
from django.utils.translation import ugettext as _

from core.errors.plugin import PluginParseError, SNMPMetricNumberError
from monitor_web.plugin.constant import SNMP_MAX_METRIC_NUM
from monitor_web.plugin.manager.base import PluginManager
from monitor_web.plugin.serializers import SNMPSerializer


class SNMPPluginManager(PluginManager):
    """
    SNMP 插件
    """

    config_files = ["env.yaml.tpl", "config.yaml.tpl"]
    templates_dirname = "snmp_templates"
    serializer_class = SNMPSerializer

    def _get_debug_config_context(self, config_version, info_version, param, target_nodes):
        collector_data = param["collector"]
        plugin_data = param["plugin"]
        context = {
            "config.yaml": {
                "community": plugin_data.pop("community", ""),
                "security_level": plugin_data.pop("security_level", ""),
                "context_name": plugin_data.pop("context_name", ""),
                "username": plugin_data.pop("security_name", ""),
                "password": plugin_data.pop("authentication_passphrase", ""),
                "auth_protocol": plugin_data.pop("authentication_protocol", ""),
                "priv_protocol": plugin_data.pop("privacy_protocol", ""),
                "priv_password": plugin_data.pop("privacy_passphrase", ""),
            },
            "env.yaml": {
                "host": collector_data["host"],
                "port": collector_data["port"],
            },
            "bkmonitorbeat_debug.yaml": {
                "host": collector_data["host"],
                "port": collector_data["port"],
                "period": collector_data["period"],
                # todo: snmp支持ipv6
                "target_nodes": [node["ip"] for node in target_nodes],
                "metric_url": "{}:{}/snmp?target=".format(collector_data["host"], collector_data["port"]),
            },
        }
        return context

    # 在SNMP采集时默认使用远程采集，设置远程采集目标主机为"target_nodes", 下发采集配置文件与执行采集任务的主机为"remote_collecting_host"
    def get_deploy_steps_params(self, plugin_version, param, target_nodes):
        collector_params = param["collector"]
        plugin_data = param["plugin"]

        plugin_params = {
            "community": plugin_data.pop("community", ""),
            "security_level": plugin_data.pop("security_level", ""),
            "context_name": plugin_data.pop("context_name", ""),
            "username": plugin_data.pop("security_name", ""),
            "password": plugin_data.pop("authentication_passphrase", ""),
            "auth_protocol": plugin_data.pop("authentication_protocol", ""),
            "priv_protocol": plugin_data.pop("privacy_protocol", ""),
            "priv_password": plugin_data.pop("privacy_passphrase", ""),
            "host": collector_params["host"],
            "port": collector_params["port"],
        }
        collector_params["tasks"] = []
        for node in target_nodes:
            # 修改labels中的内容，将labels中的target_ip改成远程采集的ip
            collector_params["labels"]["$body"]["bk_target_device_ip"] = node["ip"]
            collector_params["tasks"].append(
                {
                    "task_id": collector_params["task_id"],
                    "bk_biz_id": collector_params["bk_biz_id"],
                    "dataid": collector_params["dataid"],
                    "period": "{}".format(collector_params["period"]),
                    "timeout": collector_params.get("timeout", ""),
                    "metric_url": "{}:{}/snmp?target={}:{}".format(
                        collector_params["host"],
                        collector_params["port"],
                        node["ip"],
                        collector_params.get("snmp_port", "161"),
                    ),
                    "config_name": collector_params.get("config_name", ""),
                    "diff_metrics": collector_params.get("diff_metrics", []),
                    "labels": copy.deepcopy(collector_params["labels"]),
                }
            )

        deploy_steps = [
            {
                "id": self.plugin.plugin_id,
                "type": "PLUGIN",
                "config": {
                    "plugin_name": self.plugin.plugin_id,
                    "plugin_version": plugin_version.version,
                    "config_templates": [
                        {
                            "name": "config.yaml",
                            "version": str(plugin_version.config_version),
                        },
                        {
                            "name": "env.yaml",
                            "version": str(plugin_version.config_version),
                        },
                    ],
                },
                "params": {"context": plugin_params},
            },
            self._get_bkmonitorbeat_deploy_step("bkmonitorbeat_prometheus_remote.conf", {"context": collector_params}),
        ]
        return deploy_steps

    def _get_remote_stage(self, meta_dict):
        return True

    def _get_collector_json(self, plugin_params):
        file_name = "config.yaml.tpl"
        config_yaml_path = ""
        for filename in self.filename_list:
            if os.path.basename(filename) == file_name:
                config_yaml_path = os.path.join(self.tmp_path, filename)
                break
        if not config_yaml_path:
            raise PluginParseError({"msg": _("无法获取SNMP对应的配置文件")})

        content = yaml.load(self._read_file(config_yaml_path), Loader=yaml.FullLoader)
        content["if_mib"].pop("auth")
        snmp_collector_json = {
            "snmp_version": content["if_mib"].pop("version"),
            "filename": "snmp.yaml",
            "config_yaml": yaml.dump(content),
        }
        return snmp_collector_json

    def create_version(self, data):
        config_yaml = data["collector_json"]["config_yaml"]
        metric_json = [
            {
                "fields": [],
                "table_name": "base",
                "table_desc": _("默认分类"),
            }
        ]
        for group, item in yaml.load(config_yaml, Loader=yaml.FullLoader).items():
            metrics_list = item["metrics"]
            dimension_set = []
            for metric in metrics_list:
                if metric.get("indexes"):
                    dimension_set.extend([index["labelname"] for index in metric["indexes"]])
                if metric.get("lookups"):
                    dimension_set.extend([index["labelname"] for index in metric["lookups"] if index["labels"]])
                # 当类型为枚举类型时，exporter会默认在指标名里加上_info, 这里进行对齐
                if metric["type"] == "EnumAsInfo":
                    dimension_set.extend(metric["name"])
                    metric["name"] = "{}_info".format(metric["name"])
                metric_json[0]["fields"].append(
                    {
                        "type": "double",
                        "monitor_type": "metric",
                        "name": metric["name"] if metric.get("name") else metric["oid"],
                        "unit": "",
                        "description": metric["help"],
                        "is_active": True,
                        "is_diff_metric": False,
                    }
                )
            for dimension in set(dimension_set):
                metric_json[0]["fields"].append(
                    {
                        "type": "string",
                        "monitor_type": "dimension",
                        "name": dimension,
                        "description": dimension,
                        "is_active": True,
                        "unit": "",
                    }
                )
        data["metric_json"] = metric_json
        return super(SNMPPluginManager, self).create_version(data)

    def parse_snmp_yaml_to_metric(self, config_yaml):
        config = yaml.load(config_yaml, Loader=yaml.FullLoader)
        metric_json = []
        for item in config:
            metrics = config[item]["metrics"]

            for metric in metrics:
                metric_name = metric["name"]
                dimensions = []
                # 当类型为枚举类型时，exporter会默认在指标名里加上_info, 这里进行对齐
                if metric["type"] == "EnumAsInfo":
                    dimensions.append({"dimension_name": metric_name, "dimension_value": ""})
                    metric_name = "{}_info".format(metric_name)
                indexes = metric.get("indexes", [])
                for index in indexes:
                    dimensions.append({"dimension_name": index["labelname"], "dimension_value": ""})
                lookups = metric.get("lookups", [])
                for lookup in lookups:
                    dimensions.append({"dimension_name": lookup["labelname"], "dimension_value": ""})
                metric_json.append({"metric_name": metric_name, "metric_value": 0, "dimensions": dimensions})
            if len(metric_json) > SNMP_MAX_METRIC_NUM:
                raise SNMPMetricNumberError(snmp_max_metric_num=SNMP_MAX_METRIC_NUM)
        return metric_json

    def query_debug(self, task_id):
        """
        获取snmp主动采集调试信息，则指标以snmp.yaml文件为准
        """
        debug_result = super(SNMPPluginManager, self).query_debug(task_id)
        if debug_result.get("metric_json"):
            debug_result["metric_json"] = self.parse_snmp_yaml_to_metric(
                self.version.config.collector_json["config_yaml"]
            )
        return debug_result
