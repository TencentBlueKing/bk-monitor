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
import json

from django.utils.translation import gettext as _

from apps.log_databus.constants import EtlConfig, KafkaInitialOffsetEnum, LogPluginInfo
from apps.log_databus.handlers.collector_scenario.base import CollectorScenario
from apps.log_databus.handlers.collector_scenario.utils import (
    build_es_option_type,
    deal_collector_scenario_param,
)
from apps.utils.log import logger


class KafkaScenario(CollectorScenario):
    """
    kafka 数据采集
    """

    PLUGIN_NAME = LogPluginInfo.NAME
    PLUGIN_VERSION = LogPluginInfo.VERSION
    CONFIG_NAME = "bkunifylogbeat_kafka"

    def get_subscription_steps(self, data_id, params, collector_config_id=None, data_link_id=None):
        """
        params内包含的参数
        kafka_hosts: ['127.0.0.1:9092', '127.0.0.2:9093']
        kafka_username: "admin",
        kafka_password: "xxxxx",
        kafka_topics: ['topic_1', 'topic_2'],
        kafka_group_id: 'group_1',
        kafka_initial_offset: 'newest'
        """
        filters, params = deal_collector_scenario_param(params)

        kafka_ssl_params = params.get("kafka_ssl_params", {})

        if kafka_ssl_params:
            kafka_ssl_params.update({"enabled": True})
        else:
            kafka_ssl_params.update({"enabled": False})

        local_params = {
            "hosts": json.dumps(params.get("kafka_hosts", [])),
            "topics": json.dumps(params.get("kafka_topics", [])),
            "username": params.get("kafka_username", ""),
            "password": params.get("kafka_password", ""),
            "group_id": params.get("kafka_group_id", data_id),
            "initial_offset": params.get("kafka_initial_offset", KafkaInitialOffsetEnum.NEWEST.value),
            "ssl": json.dumps(kafka_ssl_params),
            "filters": filters,
            "delimiter": params["conditions"].get("separator") or "",
        }
        local_params = self._add_labels(local_params, params, collector_config_id)
        local_params = self._add_ext_meta(local_params, params)
        local_params = self._deal_edge_transport_params(local_params, data_link_id)
        local_params = self._handle_collector_config_overlay(local_params, params)
        steps = [
            {
                "id": f"main:{self.PLUGIN_NAME}",
                "type": "PLUGIN",
                "config": {
                    "job_type": "MAIN_INSTALL_PLUGIN",
                    "check_and_skip": True,
                    "is_version_sensitive": False,
                    "plugin_name": self.PLUGIN_NAME,
                    "plugin_version": self.PLUGIN_VERSION,
                    "config_templates": [{"name": f"{self.PLUGIN_NAME}.conf", "version": "latest", "is_main": True}],
                },
                "params": {"context": {}},
            },
            {
                "id": self.PLUGIN_NAME,  # 这里的ID不能随意变更，需要同步修改解析的逻辑(parse_steps)
                "type": "PLUGIN",
                "config": {
                    "plugin_name": self.PLUGIN_NAME,
                    "plugin_version": self.PLUGIN_VERSION,
                    "config_templates": [{"name": f"{self.CONFIG_NAME}.conf", "version": "latest"}],
                },
                "params": {
                    "context": {
                        "dataid": data_id,
                        "local": [local_params],
                    }
                },
            },
        ]
        return steps

    @classmethod
    def parse_steps(cls, steps):
        """
        解析订阅步骤至参数，
        :param steps: 订阅步骤
        [
            {
                "config": {
                    "config_templates": [
                        {
                            "version": "7.0.11",
                            "name": "bklogbeat.conf"
                        }
                    ],
                    "plugin_name": "bklogbeat",
                    "plugin_version": "7.0.11"
                },
                "type": "PLUGIN",
                "id": "bklogbeat",
                "params": {
                    "context": {
                        "dataid": 123,
                        "local": [{
                            "paths": [],
                            "encoding": "utf-8",
                            "filters": [{
                                "fieldindex": 1,
                                "word": "",
                                "op": "=",
                            }],
                            "delimiter": "|"
                        }]
                    }
                }
            }
        ]
        :return:
        """
        try:
            for step in steps:
                if step["id"] == cls.PLUGIN_NAME:
                    config = step["params"]["context"]
                    break
            else:
                config = steps[0]["params"]["context"]

            try:
                separator_filters = []
                # 如果是逻辑或，会拆成多个配置下发
                logic_op = "and" if len(config["local"][0]["filters"]) <= 1 else "or"
                for filter_item in config["local"][0]["filters"]:
                    for condition_item in filter_item["conditions"]:
                        separator_filters.append(
                            {
                                "fieldindex": condition_item["index"],
                                "word": condition_item["key"],
                                "op": condition_item["op"],
                                "logic_op": logic_op,
                            }
                        )
            except (IndexError, KeyError, ValueError):
                separator_filters = []

            match_content = ""
            match_type = "include"
            if separator_filters and separator_filters[0]["fieldindex"] == "-1":
                _type = "match"
                match_content = separator_filters[0].get("word", "")
                match_type = separator_filters[0].get("op", "=")
                # 兼容历史数据（历史数据match_type固定为 '=' ）
                if match_type == "=":
                    match_type = "include"
                separator_filters = []
            elif not separator_filters:
                _type = "none"
            else:
                _type = "separator"

            conditions = (
                {
                    "separator": config["local"][0]["delimiter"],
                    "separator_filters": separator_filters,
                    "type": _type,
                    "match_type": match_type,
                    "match_content": match_content,
                }
                if _type != "none"
                else {"type": _type}
            )

            ssl_params = config["local"][0]["ssl"]

            params = {
                "conditions": conditions,
                "kafka_hosts": config["local"][0]["hosts"],
                "kafka_topics": config["local"][0]["topics"],
                "kafka_username": config["local"][0]["username"],
                "kafka_password": config["local"][0]["password"],
                "kafka_group_id": config["local"][0]["group_id"],
                "kafka_initial_offset": config["local"][0]["initial_offset"],
                "kafka_ssl_params": ssl_params if isinstance(ssl_params, str) else ssl_params,
            }

        except (IndexError, KeyError, ValueError) as e:
            logger.exception(f"解析订阅步骤失败，参数:{steps}，错误:{e}")
            params = {
                "conditions": [],
                "kafka_hosts": [],
                "kafka_topics": [],
                "kafka_username": "",
                "kafka_password": "",
                "kafka_group_id": "",
                "kafka_initial_offset": "",
                "kafka_ssl_params": {},
            }
        return params

    @classmethod
    def get_built_in_config(cls, es_version="5.X", etl_config=EtlConfig.BK_LOG_TEXT):
        """
        获取采集器标准字段
        """
        return {
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
                    "field_name": "cloudId",
                    "field_type": "float",
                    "tag": "dimension",
                    "alias_name": "cloudid",
                    "description": _("云区域ID"),
                    "option": {"es_type": "integer", "es_include_in_all": False}
                    if es_version.startswith("5.")
                    else {"es_type": "integer"},
                },
                {
                    "field_name": "serverIp",
                    "field_type": "string",
                    "tag": "dimension",
                    "alias_name": "ip",
                    "description": "ip",
                    "option": {"es_type": "keyword", "es_include_in_all": True}
                    if es_version.startswith("5.")
                    else {"es_type": "keyword"},
                },
                {
                    "field_name": "gseIndex",
                    "field_type": "float",
                    "tag": "dimension",
                    "alias_name": "gseindex",
                    "description": _("gse索引"),
                    "option": {"es_type": "long", "es_include_in_all": False}
                    if es_version.startswith("5.")
                    else {"es_type": "long"},
                },
                {
                    "field_name": "iterationIndex",
                    "field_type": "float",
                    "tag": "dimension",
                    "alias_name": "iterationindex",
                    "description": _("迭代ID"),
                    "flat_field": True,
                    "option": {"es_type": "integer", "es_include_in_all": False}
                    if es_version.startswith("5.")
                    else {"es_type": "integer"},
                },
                {
                    "field_name": "kafka",
                    "field_type": "object",
                    "tag": "dimension",
                    "alias_name": "kafka",
                    "description": "kafka消息属性",
                    "option": build_es_option_type("object", es_version),
                },
            ],
            "time_field": {
                "field_name": "dtEventTimeStamp",
                "field_type": "timestamp",
                "tag": "dimension",
                "alias_name": "utctime",
                "description": _("数据时间"),
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
