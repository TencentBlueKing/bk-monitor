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

import yaml
from django.conf import settings
from django.utils.translation import gettext as _

from core.errors.plugin import PluginIDNotExist
from monitor_web.plugin.constant import (
    DEFAULT_TRAP_CONFIG,
    DEFAULT_TRAP_V3_CONFIG,
    PluginType,
)
from monitor_web.plugin.manager.log import LogPluginManager
from monitor_web.plugin.serializers import SNMPTrapSerializer

logger = logging.getLogger("monitor_web")


class SNMPTrapPluginManager(LogPluginManager):
    serializer_class = SNMPTrapSerializer
    # 内置的默认维度
    DEFAULT_DIMENSIONS = [
        "version",
        "community",
        "enterprise",
        "generic_trap",
        "specific_trap",
        "snmptrapoid",
        "display_name",
        "agent_address",
        "agent_port",
        "server_ip",
        "server_port",
    ]

    @staticmethod
    def get_params(plugin_id, bk_biz_id, label, **kwargs):
        params = LogPluginManager.get_params(plugin_id, bk_biz_id, label, **kwargs)
        params.update(
            {
                "plugin_type": PluginType.SNMP_TRAP,
                "plugin_display_name": _("SNMP Trap 服务"),
            }
        )
        return params

    def full_request_data(self, data):
        metric_json = [
            {
                "fields": [
                    {
                        "type": "double",
                        "monitor_type": "metric",
                        "name": "event.count",
                        "unit": "",
                        "description": "event_count",
                        "is_active": True,
                        "is_diff_metric": False,
                    },
                ],
                "table_name": "base",
                "table_desc": _("默认分类"),
            }
        ]
        data["metric_json"] = metric_json

    def create_version(self, data):
        event_list = self.get_dimensions(data["yaml"])
        self.full_request_data(data)
        return self._create_version(data, event_list)

    def update_version(self, data, target_config_version: int = None, target_info_version: int = None):
        event_list = self.get_dimensions(data["yaml"])
        self.full_request_data(data)
        return self._update_version(data, event_list)

    def get_dimensions(self, params):
        dimensions = [
            {
                # 创建事件组参数
                "event_name": "TrapOID",
                "dimension_list": self.DEFAULT_DIMENSIONS,
            }
        ]
        return dimensions

    @staticmethod
    def release_collector_plugin(current_version):
        current_version.stage = "release"
        current_version.is_packaged = True
        current_version.save()

    def _get_debug_config_context(self, config_version, info_version, param, target_nodes):
        return {}

    # 组装snmp trap参数
    def get_deploy_steps_params(self, plugin_version, param, target_nodes):
        data = yaml.load(param["snmp_trap"]["yaml"]["value"], Loader=yaml.FullLoader)
        oids_list = []
        report_oid_dimensions = []
        raw_byte_oids = []
        encode = ""
        hide_agent_port = False
        for item in list(data.values()):
            oids_list.extend(item.get("metrics", []))
            report_oid_dimensions.extend(item.get("report_oid_dimensions", []))
            raw_byte_oids.extend(item.get("raw_byte_oids", []))
            encode = item.get("encode", "")
            hide_agent_port = item.get("hide_agent_port", False)
        translate_oid = settings.TRANSLATE_SNMP_TRAP_DIMENSIONS

        collector_params = {
            "tasks": [
                {
                    "task_id": param["collector"]["task_id"],
                    "bk_biz_id": param["collector"]["bk_biz_id"],
                    "dataid": param["collector"]["dataid"],
                    "community": param["snmp_trap"].get("community", ""),
                    "listen_ip": param["snmp_trap"]["listen_ip"],
                    "listen_port": param["snmp_trap"]["server_port"],
                    "snmp_version": param["snmp_trap"]["version"],
                    "aggregate": param["snmp_trap"]["aggregate"],
                    "period": "{}s".format(param["collector"]["period"]),
                    "oids": {oid["oid"]: oid["name"] for oid in oids_list},
                    "report_oid_dimensions": report_oid_dimensions,
                    "raw_byte_oids": raw_byte_oids,
                    "use_display_name_oid": translate_oid,
                    "encode": encode,
                    "hide_agent_port": hide_agent_port,
                    "usm_info": [
                        {
                            "context_name": i.get("context_name", ""),
                            "msg_flags": i.get("security_level", ""),
                            "usm_config": {
                                "username": i.get("security_name", ""),
                                "authentication_protocol": i.get("authentication_protocol", ""),
                                "authentication_passphrase": i.get("authentication_passphrase", ""),
                                "privacy_protocol": i.get("privacy_protocol", ""),
                                "privacy_passphrase": i.get("privacy_passphrase", ""),
                                "authoritative_engineID": i.get("authoritative_engineID", ""),
                                # authoritative_engineboots,authoritative_enginetime为预留默认参数
                                "authoritative_engineboots": 1,
                                "authoritative_enginetime": 1,
                            },
                        }
                        for i in param["snmp_trap"].get("auth_info", DEFAULT_TRAP_V3_CONFIG["auth_info"])
                    ],
                    "labels": param["collector"]["labels"],
                    "target": self.get_target(param["target_object_type"]),
                }
            ]
        }
        deploy_steps = [
            {
                "id": "bkmonitorlog",
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "bkmonitorbeat",
                    "plugin_version": "latest",
                    "config_templates": [{"name": "bkmonitorbeat_snmptrap.conf", "version": "latest"}],
                },
                "params": {"context": collector_params},
            }
        ]
        return deploy_steps

    def _get_collector_json(self, plugin_params):
        return None

    @staticmethod
    def get_target(object_type):
        if object_type == "SERVICE":
            target = "{{ cmdb_instance.service.id }}"
        else:
            target = (
                "{{ '{}:{}'.format(cmdb_instance.host.bk_cloud_id[0].id, cmdb_instance.host.bk_host_innerip) "
                "if cmdb_instance.host.bk_cloud_id is iterable and cmdb_instance.host.bk_cloud_id is not string "
                "else '{}:{}'.format(cmdb_instance.host.bk_cloud_id, cmdb_instance.host.bk_host_innerip) }}"
            )
        return target

    def get_default_trap_plugin(self):
        default_config = copy.deepcopy(DEFAULT_TRAP_CONFIG)
        plugin_id = self.plugin.plugin_id
        chioces = ("v1", "2c", "v2", "v2c", "v3")
        if not plugin_id.endswith(chioces):
            return PluginIDNotExist({"msg": _("SNMP Trap插件版本错误，请重新检查插件版本")})
        if plugin_id.endswith("v3"):
            default_config.update(DEFAULT_TRAP_V3_CONFIG)
        default_trap_config = self.plugin.get_config_json(default_config)
        plugin_detail = {
            "plugin_id": plugin_id,
            "plugin_display_name": "snmp trap {}".format(plugin_id.split("_")[1]),
            "plugin_type": PluginType.SNMP_TRAP,
            "tag": "",
            "label": "hardware",
            "status": "normal",
            "logo": "",
            "collector_json": "",
            "config_json": default_trap_config,
            "metric_json": "",
            "description_md": "",
            "config_version": 1,
            "info_version": 1,
            "stage": "release",
            "bk_biz_id": 0,
            "signature": "",
            "is_support_remote": True,
            "is_official": False,
            "is_safety": True,
            "create_user": "admin",
            "update_user": "admin",
            "os_type_list": [],
            "create_time": "",
            "update_time": "",
            "related_conf_count": 0,
            "edit_allowed": False,
        }
        return plugin_detail
