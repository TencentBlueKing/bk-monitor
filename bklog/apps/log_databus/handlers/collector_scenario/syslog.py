# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
from django.utils.translation import gettext as _

from apps.log_databus.constants import EtlConfig, LogPluginInfo, PluginParamLogicOpEnum
from apps.log_databus.handlers.collector_scenario import CollectorScenario
from apps.log_databus.handlers.collector_scenario.utils import build_es_option_type


class SysLogScenario(CollectorScenario):
    PLUGIN_NAME = LogPluginInfo.NAME
    PLUGIN_VERSION = LogPluginInfo.VERSION
    CONFIG_NAME = "bkunifylogbeat_syslog"

    def get_subscription_steps(self, data_id, params, collector_config_id=None, data_link_id=None):
        # 判断是否传入监听IP 未传入则使用内网IP
        syslog_monitor_host = params.get("syslog_monitor_host") or "{{ cmdb_instance.host.bk_host_innerip }}"
        syslog_port = str(params["syslog_port"])

        # syslog 过滤规则
        syslog_conditions = params.get("syslog_conditions", [])

        filters = []
        filter_bucket = list()
        for condition in syslog_conditions:
            if not isinstance(condition, dict):
                continue

            key = condition.get("syslog_field", "")
            value = condition.get("syslog_content", "")
            op = condition.get("syslog_op", "include")
            logic_op = condition.get("syslog_logic_op", PluginParamLogicOpEnum.AND.value)

            if not value:
                continue

            # syslog 字段值匹配->当下发配置中定义key字段且key字段值不为空 插件过滤会以key的字段值作为键值 从原始日志中获取对应的value进行过滤 默认是按日志内容过滤
            if logic_op == PluginParamLogicOpEnum.AND.value:
                filter_bucket.append({"key": key, "op": op, "value": value})
            else:
                if len(filter_bucket) > 0:
                    filters.append({"conditions": filter_bucket})
                    filter_bucket = []

                filter_bucket.append({"key": key, "op": op, "value": value})

        if len(filter_bucket) > 0:
            filters.append({"conditions": filter_bucket})

        local_params = {
            "protocol": params.get("syslog_protocol", "").lower(),
            "host": f"{syslog_monitor_host}:{syslog_port}",
            "syslog_filters": filters,
        }
        local_params = self._deal_edge_transport_params(local_params, data_link_id)
        local_params = self._handle_collector_config_overlay(local_params, params)
        return [
            {
                "id": self.PLUGIN_NAME,
                "type": "PLUGIN",
                "config": {
                    "plugin_name": self.PLUGIN_NAME,
                    "plugin_version": self.PLUGIN_VERSION,
                    "config_templates": [{"name": f"{self.CONFIG_NAME}.conf", "version": "latest"}],
                },
                "params": {"context": {"dataid": data_id, "local": [local_params]}},
            }
        ]

    @classmethod
    def parse_steps(cls, steps):
        step, *_ = steps
        config = step["params"]["context"]
        local, *_ = config["local"]
        if local:
            host_list = local["host"].split(":")
            syslog_port = host_list[1] if host_list else 0
            filters = local.get("syslog_filters", [])
            syslog_conditions = list()

            if filters:
                for filter_index, filter_item in enumerate(filters):
                    for condition_index, condition_item in enumerate(filter_item["conditions"]):
                        if filter_index == 0:
                            logic_op = PluginParamLogicOpEnum.AND.value
                        elif condition_index == 0:
                            logic_op = PluginParamLogicOpEnum.OR.value
                        else:
                            logic_op = PluginParamLogicOpEnum.AND.value
                        syslog_conditions.append(
                            {
                                "syslog_content": condition_item.get("value", ""),
                                "syslog_op": condition_item.get("op", "include"),
                                "syslog_field": condition_item.get("key", ""),
                                "syslog_logic_op": logic_op,
                            }
                        )

            return {
                "syslog_protocol": local["protocol"],
                "syslog_port": syslog_port,
                "syslog_conditions": syslog_conditions,
            }
        else:
            return {"syslog_protocol": "", "syslog_port": 0, "syslog_conditions": []}

    @classmethod
    def get_built_in_config(cls, es_version="5.X", etl_config=EtlConfig.BK_LOG_TEXT):
        """
        获取采集器标准字段
        """
        built_in_config = {
            "option": {
                "es_unique_field_list": [
                    "cloudId",
                    "serverIp",
                    "gseIndex",
                    "iterationIndex",
                    "bk_host_id",
                    "dtEventTimeStamp",
                ],
                "separator_node_source": "",
                "separator_node_action": "",
                "separator_node_name": "",
            },
            "fields": [
                {
                    "field_name": "bk_host_id",
                    "field_type": "float",
                    "tag": "dimension",
                    "alias_name": "bk_host_id",
                    "description": _("主机ID"),
                    "option": {"es_type": "integer", "es_include_in_all": False}
                    if es_version.startswith("5.")
                    else {"es_type": "integer"},
                },
                {
                    "field_name": "__ext",
                    "field_type": "object",
                    "tag": "dimension",
                    "alias_name": "ext",
                    "description": _("额外信息字段"),
                    "option": {"es_type": "object", "es_include_in_all": False}
                    if es_version.startswith("5.")
                    else {"es_type": "object"},
                },
                {
                    "field_name": "iterationIndex",
                    "field_type": "float",
                    "tag": "dimension",
                    "alias_name": "iterationindex",
                    "description": "迭代ID",
                    "option": build_es_option_type("integer", es_version),
                },
                {
                    "field_name": "cloudId",
                    "field_type": "float",
                    "tag": "dimension",
                    "alias_name": "cloudid",
                    "description": "云区域ID",
                    "option": build_es_option_type("integer", es_version),
                },
                {
                    "field_name": "serverIp",
                    "field_type": "string",
                    "tag": "dimension",
                    "alias_name": "ip",
                    "description": "ip",
                    "option": build_es_option_type("keyword", es_version),
                },
                {
                    "field_name": "gseIndex",
                    "field_type": "float",
                    "tag": "dimension",
                    "alias_name": "gseindex",
                    "description": "gse索引",
                    "option": build_es_option_type("long", es_version),
                },
            ],
            "time_field": {
                "field_name": "dtEventTimeStamp",
                "field_type": "timestamp",
                "tag": "dimension",
                "alias_name": "utctime",
                "description": "数据时间",
                "option": {
                    "es_type": "date",
                    "es_include_in_all": False,
                    "es_format": "epoch_millis",
                    "time_format": "yyyy-MM-dd HH:mm:ss",
                    "time_zone": 0,
                }
                if es_version.startswith("5.")
                else {
                    "es_type": "date",
                    "es_format": "epoch_millis",
                    "time_format": "yyyy-MM-dd HH:mm:ss",
                    "time_zone": 0,
                },
            },
        }
        if etl_config == EtlConfig.BK_LOG_TEXT:
            built_in_config["fields"].extend(
                [
                    {
                        "field_name": "syslogSource",
                        "field_type": "object",
                        "tag": "dimension",
                        "alias_name": "log",
                        "description": "客户端信息",
                        "option": build_es_option_type("object", es_version),
                    },
                    {
                        "field_name": "syslogLabel",
                        "field_type": "object",
                        "tag": "dimension",
                        "alias_name": "syslog",
                        "description": "严重程度",
                        "option": build_es_option_type("object", es_version),
                    },
                    {
                        "field_name": "syslogEvent",
                        "field_type": "object",
                        "tag": "dimension",
                        "alias_name": "event",
                        "description": "日志级别",
                        "option": build_es_option_type("object", es_version),
                    },
                    {
                        "field_name": "syslogProcess",
                        "field_type": "object",
                        "tag": "dimension",
                        "alias_name": "process",
                        "description": "应用程序",
                        "option": build_es_option_type("object", es_version),
                    },
                ]
            )
        return built_in_config
