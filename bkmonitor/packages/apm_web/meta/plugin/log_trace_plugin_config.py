# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from core.drf_resource import api

COLLECTOR_ROW_PACKAGE_COUNT = 100
IGNORE_OLDER = 2678400
MAX_BYTES = 204800
DATA_TYPE = "log_v2"
OUTPUT_TYPE = "otlp_trace"


class LogPluginInfo(object):
    """
    采集插件信息
    """

    NAME = "bkunifylogbeat"
    VERSION = "latest"


class LogTracePluginConfig(object):
    """
    行日志采集
    """

    PLUGIN_NAME = LogPluginInfo.NAME
    PLUGIN_VERSION = LogPluginInfo.VERSION

    def get_subscription_steps(self, params, output_param):
        host = output_param["host"]
        local = {
            "paths": params["paths"],
            "filters": [],
            "encoding": params["data_encoding"],
            "tail_files": True,
            "ignore_older": IGNORE_OLDER,
            "max_bytes": MAX_BYTES,
            "package_count": COLLECTOR_ROW_PACKAGE_COUNT,
            "delimiter": "",
            "output": {
                "type": "output.bkcollector",
                "param": {
                    "otlp_bk_data_token": output_param["token"],
                    "otlp_grpc_host": f"{host}:4317",
                    "data_type": DATA_TYPE,
                    "output_type": OUTPUT_TYPE,
                },
            },
        }
        steps = [
            {
                "id": self.PLUGIN_NAME,  # 这里的ID不能随意变更，需要同步修改解析的逻辑(parse_steps)
                "type": "PLUGIN",
                "config": {
                    "plugin_name": self.PLUGIN_NAME,
                    "plugin_version": self.PLUGIN_VERSION,
                    "config_templates": [{"name": f"{self.PLUGIN_NAME}.conf", "version": "latest"}],
                },
                "params": {
                    "context": {
                        "dataid": params["bk_data_id"],
                        "local": [local],
                    }
                },
            },
        ]
        return steps

    def release_log_trace_config(self, plugin_config, output_param):
        steps = self.get_subscription_steps(plugin_config, output_param)
        subscription_params = {
            "scope": {
                "bk_biz_id": plugin_config["bk_biz_id"],
                "node_type": plugin_config["target_node_type"],
                "object_type": plugin_config["target_object_type"],
                "nodes": plugin_config["target_nodes"],
            },
            "steps": steps,
        }
        if plugin_config.get("subscription_id"):
            # 修改订阅配置
            subscription_params["subscription_id"] = plugin_config["subscription_id"]
            api.node_man.update_subscription(subscription_params)

        else:
            # 创建订阅配置
            plugin_config["subscription_id"] = api.node_man.create_subscription(subscription_params)["subscription_id"]
            api.node_man.switch_subscription({"subscription_id": plugin_config["subscription_id"], "action": "enable"})
        self.run_subscription_task(plugin_config["subscription_id"])
        return plugin_config

    @classmethod
    def run_subscription_task(cls, subscription_id, action=None):
        params = {"subscription_id": subscription_id}
        if action:
            params.update({"actions": {LogPluginInfo.NAME: action}})
        return api.node_man.run_subscription(params)


class EncodingsEnum(object):
    """
    字符编码枚举
    """

    UTF = "UTF-8"
    GBK = "GBK"

    @classmethod
    def get_choices(cls):
        return [key.upper() for key in ENCODINGS]

    @classmethod
    def get_choices_list_dict(cls):
        return [{"id": key.upper(), "name": key.upper()} for key in ENCODINGS if key]


# 日志编码
ENCODINGS = [
    "utf-8",
    "gbk",
    "gb18030",
    "big5",
    # 8bit char map encodings
    "iso8859-6e",
    "iso8859-6i",
    "iso8859-8e",
    "iso8859-8i",
    "iso8859-1",  # latin-1
    "iso8859-2",  # latin-2
    "iso8859-3",  # latin-3
    "iso8859-4",  # latin-4
    "iso8859-5",  # latin/cyrillic
    "iso8859-6",  # latin/arabic
    "iso8859-7",  # latin/greek
    "iso8859-8",  # latin/hebrew
    "iso8859-9",  # latin-5
    "iso8859-10",  # latin-6
    "iso8859-13",  # latin-7
    "iso8859-14",  # latin-8
    "iso8859-15",  # latin-9
    "iso8859-16",  # latin-10
    # ibm codepages
    "cp437",
    "cp850",
    "cp852",
    "cp855",
    "cp858",
    "cp860",
    "cp862",
    "cp863",
    "cp865",
    "cp866",
    "ebcdic-037",
    "ebcdic-1040",
    "ebcdic-1047",
    # cyrillic
    "koi8r",
    "koi8u",
    # macintosh
    "macintosh",
    "macintosh-cyrillic",
    # windows
    "windows1250",  # central and eastern european
    "windows1251",  # russian, serbian cyrillic
    "windows1252",  # legacy
    "windows1253",  # modern greek
    "windows1254",  # turkish
    "windows1255",  # hebrew
    "windows1256",  # arabic
    "windows1257",  # estonian, latvian, lithuanian
    "windows1258",  # vietnamese
    "windows874",
    # utf16 bom codecs (seekable data source required)
    "utf-16-bom",
    "utf-16be-bom",
    "utf-16le-bom",
]
