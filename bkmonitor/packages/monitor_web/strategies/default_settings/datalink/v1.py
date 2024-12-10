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
import enum
from typing import Dict, List

from django.utils.translation import gettext_lazy as _

from monitor_web.plugin.constant import PluginType
from monitor_web.strategies.default_settings.common import (
    DEFAULT_NOTICE,
    NO_DATA_CONFIG,
    warning_algorithms_config,
    warning_detects_config,
)


class GatherType(enum.Enum):
    METRICBEAT = "metricbeat"
    SCRIPT = "script"
    PROCCUSTOM = "proccustom"


PLUGIN_TYPE_MAPPING = {
    PluginType.SCRIPT: GatherType.SCRIPT,
    PluginType.PROCESS: GatherType.PROCCUSTOM,
    PluginType.PUSHGATEWAY: GatherType.METRICBEAT,
    PluginType.EXPORTER: GatherType.METRICBEAT,
    PluginType.DATADOG: GatherType.METRICBEAT,
}


class DatalinkStrategy(enum.Enum):
    COLLECTING_SYS_ALARM = "datalink_collecting_sys_alarm"
    COLLECTING_USER_ALARM = "datalink_collecting_user_alarm"

    def render_label(self, **context):
        return self.value

    def render_escaped_label(self, **context):
        return "/{}/".format(self.render_label(**context))


COLLECTING_SYS_ALARM_DESC = _("数据采集遇到系统异常情况，导致无法上报数据，会发送告警。")
COLLECTING_USER_METRICBEAT_ALARM_DESC = _(
    "数据采集遇到插件异常情况，导致无法上报数据，会发送告警，目前能覆盖以下插件异常情况：" "\n- 端口服务无法正常监听" "\n- 服务输出的内容格式不符合Prom格式"
)
COLLECTING_USER_SCRIPT_ALARM_DESC = _(
    "当数据采集时遇到异常情况，导致无法上报数据，则会触发告警，目前能覆盖以下异常情况：" "\n- 脚本执行异常，返回非0状态码" "\n- 脚本打印内容格式不符合Prom格式"
)
COLLECTING_USER_PROCCUSTOM_ALARM_DESC = _(
    "当数据采集时遇到异常情况，导致无法上报数据，则会触发告警，目前能覆盖以下异常情况：" "\n- 用户配置中的PID文件不存在" "\n- 用户配置的匹配规则无命中任何进程"
)


DATALINK_GATHER_STATEGY_DESC = {
    (DatalinkStrategy.COLLECTING_SYS_ALARM, GatherType.METRICBEAT): COLLECTING_SYS_ALARM_DESC,
    (DatalinkStrategy.COLLECTING_SYS_ALARM, GatherType.SCRIPT): COLLECTING_SYS_ALARM_DESC,
    (DatalinkStrategy.COLLECTING_SYS_ALARM, GatherType.PROCCUSTOM): COLLECTING_SYS_ALARM_DESC,
    (DatalinkStrategy.COLLECTING_USER_ALARM, GatherType.METRICBEAT): COLLECTING_USER_METRICBEAT_ALARM_DESC,
    (DatalinkStrategy.COLLECTING_USER_ALARM, GatherType.SCRIPT): COLLECTING_USER_SCRIPT_ALARM_DESC,
    (DatalinkStrategy.COLLECTING_USER_ALARM, GatherType.PROCCUSTOM): COLLECTING_USER_PROCCUSTOM_ALARM_DESC,
}


class DataLinkStage(enum.Enum):
    COLLECTING = "collecting"
    TRANSFER = "transfer"
    STORAGE = "storage"


STAGE_STRATEGY_MAPPING: Dict[DataLinkStage, List[DatalinkStrategy]] = {
    DataLinkStage.COLLECTING: [DatalinkStrategy.COLLECTING_SYS_ALARM, DatalinkStrategy.COLLECTING_USER_ALARM],
    DataLinkStage.TRANSFER: [],
    DataLinkStage.STORAGE: [],
}


DEFAULT_DATALINK_COLLECTING_FLAG = "__datalink_collecting__"
DEFAULT_DATALINK_LABEL = _("集成内置")
DEFAULT_RULE_GROUP_NAME = _("集成内置-数据采集告警分派")


DEFAULT_DATALINK_STRATEGIES = [
    {
        "_name": DatalinkStrategy.COLLECTING_SYS_ALARM,
        "detects": warning_detects_config(5, 5, 4),
        "items": [
            {
                "algorithms": warning_algorithms_config("gt", 0),
                "expression": "a",
                "functions": [],
                "name": "count(bkm_gather_up)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"key": "bkm_up_code", "method": "nreg", "value": ["^2\\d{3}$"]},
                            {"key": "bkm_up_code", "method": "neq", "value": ["0", "2302", "2502"], "condition": "and"},
                            {"key": "bk_collect_config_id", "method": "neq", "value": [""], "condition": "and"},
                            {"key": "bk_biz_id", "method": "eq", "value": ["${{bk_biz_id}}"], "condition": "and"},
                        ],
                        "agg_dimension": [
                            "bkm_up_code",
                            "bkm_up_code_name",
                            "bk_collect_config_id",
                            "bk_target_ip",
                            "bk_target_cloud_id",
                        ],
                        "agg_interval": 60,
                        "agg_method": "COUNT",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "bkm_gather_up",
                        "name": "bkm_gather_up",
                        "result_table_id": "bkmonitorbeat_gather_up.__default__",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [DEFAULT_DATALINK_LABEL, "${{custom_label}}"],
        "name": _("集成内置-数据采集系统运行异常告警"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "_name": DatalinkStrategy.COLLECTING_USER_ALARM,
        "detects": warning_detects_config(5, 5, 4),
        "items": [
            {
                "algorithms": warning_algorithms_config("gt", 0),
                "expression": "a",
                "functions": [],
                "name": "count(bkm_gather_up)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"key": "bkm_up_code", "method": "reg", "value": ["^2\\d{3}$"]},
                            {"key": "bkm_up_code", "method": "neq", "value": ["0", "2302", "2502"], "condition": "and"},
                            {"key": "bk_collect_config_id", "method": "neq", "value": [""], "condition": "and"},
                            {"key": "bk_biz_id", "method": "eq", "value": ["${{bk_biz_id}}"], "condition": "and"},
                        ],
                        "agg_dimension": [
                            "bkm_up_code",
                            "bkm_up_code_name",
                            "bk_collect_config_id",
                            "bk_target_ip",
                            "bk_target_cloud_id",
                        ],
                        "agg_interval": 60,
                        "agg_method": "count",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "bkm_gather_up",
                        "name": "bkm_gather_up",
                        "result_table_id": "bkmonitorbeat_gather_up.__default__",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [DEFAULT_DATALINK_LABEL, "${{custom_label}}"],
        "name": _("集成内置-数据采集插件执行异常告警"),
        "notice": DEFAULT_NOTICE,
    },
]
