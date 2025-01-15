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


import os

from django.utils.translation import gettext_lazy as _

BUILT_IN_TAGS = [_("主机"), _("消息中间件"), _("HTTP服务"), _("数据库"), _("办公应⽤"), _("其他")]

HEARTBEAT_MESSAGE_ID = 101178

BEAT_RUN_ERR = 4001  # 脚本运行报错
BEAT_PARAMS_ERR = 4002  # 脚本命令不合法
BEAT_FORMAT_OUTPUT_ERR = 4003  # 解析脚本标准输出报错

BEAT_ERR = {
    BEAT_RUN_ERR: _("脚本运行报错,原因是{}"),
    BEAT_PARAMS_ERR: _("脚本命令不合法,原因是{}"),
    BEAT_FORMAT_OUTPUT_ERR: _("解析脚本标准输出报错,原因是{}"),
}

OS_TYPE_TO_DIRNAME = {
    "windows": "external_plugins_windows_x86_64",
    "linux": "external_plugins_linux_x86_64",
    "linux_aarch64": "external_plugins_linux_aarch64",
    "aix": "external_plugins_aix_powerpc",
}
OS_TYPE_TO_SCRIPT_SUFFIX = {"shell": ".sh", "bat": ".bat", "custom": ""}

INNER_DIMENSIONS = [
    "bk_biz_id",
    "bk_target_ip",
    "bk_target_cloud_id",
    "bk_target_topo_level",
    "bk_target_topo_id",
    "bk_target_service_category_id",
    "bk_target_service_instance_id",
    "bk_collect_config_id",
]

PLUGIN_TEMPLATES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugin_templates")


# config_json 字段类型选项
class ParamMode(object):
    # 采集器参数
    COLLECTOR = "collector"
    # 命令行选项参数
    OPT_CMD = "opt_cmd"
    # 命令行位置参数
    POS_CMD = "pos_cmd"
    # 环境变量
    ENV = "env"
    # 维度注入
    DMS_INSERT = "dms_insert"


PARAM_MODE_CHOICES = [
    ParamMode.COLLECTOR,
    ParamMode.OPT_CMD,
    ParamMode.POS_CMD,
    ParamMode.ENV,
    ParamMode.DMS_INSERT,
]

SCRIPT_TYPE_CHOICES = (
    "shell",
    "bat",
    "python",
    "perl",
    "powershell",
    "vbs",
    "custom",
)

PROCESS_MATCH_TYPE_CHOICES = (
    "pid",
    "command",
)


class NodemanRegisterStatus(object):
    FAILED = "FAILED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"


class DebugStatus(object):
    INSTALL = "INSTALL"
    FETCH_DATA = "FETCH_DATA"
    FAILED = "FAILED"
    SUCCESS = "SUCCESS"


class PluginType(object):
    EXPORTER = "Exporter"
    SCRIPT = "Script"
    JMX = "JMX"
    DATADOG = "DataDog"
    PUSHGATEWAY = "Pushgateway"
    BUILT_IN = "Built-In"
    LOG = "Log"
    PROCESS = "Process"
    SNMP_TRAP = "SNMP_Trap"
    SNMP = "SNMP"
    K8S = "K8S"


class ConflictMap(object):
    """用于插件导入的冲突提示，此处国际化在调用方进行"""

    class VersionBelow(object):
        id = 1
        info = _("导入版本不大于当前版本")

    class PluginType(object):
        id = 2
        info = _("插件类型冲突")

    class RemoteCollectorConfig(object):
        id = 3
        info = _("远程采集配置项冲突")

    class RelatedCollectorConfig(object):
        id = 4
        info = _("插件已关联%s个采集配置")

    class DuplicatedPlugin(object):
        id = 5
        info = _("导入插件与当前插件内容完全一致")


SUPPORT_REMOTE_LIST = [PluginType.PUSHGATEWAY, PluginType.JMX, PluginType.SNMP]

# SNMP Trap插件默认运行参数
DEFAULT_TRAP_CONFIG = {
    "server_port": "162",
    "listen_ip": "0.0.0.0",
    "yaml": {"filename": "", "value": ""},
    "community": "",
    "aggregate": True,
}
DEFAULT_TRAP_V3_CONFIG = {
    "version": "v3",
    "auth_info": [
        {
            "security_level": "noAuthNoPriv",
            "security_name": "",
            "context_name": "",
            "authentication_protocol": "MD5",
            "authentication_passphrase": "",
            "privacy_protocol": "DES",
            "privacy_passphrase": "",
            "authoritative_engineID": "",
        }
    ],
}

SNMP_MAX_METRIC_NUM = 500
MAX_METRIC_NUM = 2000

PLUGIN_REVERSED_DIMENSION = [
    ("bk_target_ip", _("目标IP")),
    ("bk_target_cloud_id", _("云区域ID")),
    ("bk_target_topo_level", _("拓扑层级")),
    ("bk_target_topo_id", _("拓扑ID")),
    ("bk_target_service_category_id", _("服务类别ID")),
    ("bk_target_service_instance_id", _("服务实例")),
    ("bk_collect_config_id", _("采集配置ID")),
    ("bk_target_host_id", _("目标主机ID")),
    ("bk_host_id", _("采集主机ID")),
    ("time", _("数据上报时间")),
    ("bk_biz_id", _("业务ID")),
    ("bk_supplier_id", _("开发商ID")),
    ("bk_cloud_id", _("采集器云区域ID")),
    ("ip", _("采集器IP")),
    ("bk_cmdb_level", _("CMDB层级信息")),
    ("bk_agent_id", "Agent ID"),
]


ORIGIN_PLUGIN_EXCLUDE_DIMENSION = [
    "bk_host_id",
    "bk_target_host_id",
    "bk_biz_id",
    "ip",
    "time",
    "bk_supplier_id",
    "bk_cloud_id",
    "bk_cmdb_level",
    "bk_agent_id",
]
