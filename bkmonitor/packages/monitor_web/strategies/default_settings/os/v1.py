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

from django.utils.translation import gettext_lazy as _lazy

from common.context_processors import Platform

DEFAULT_OS_STRATEGIES = [
    {
        "name": _lazy("CPU总使用率"),
        "data_type_label": "time_series",
        "data_source_label": "bk_monitor",
        "result_table_label": "os",
        "metric_field": "usage",
        "result_table_id": "system.cpu_summary",
        "threshold": 95,
        "unit_prefix": "%",
        "method": "gte",
        "trigger_count": 3,
        "trigger_check_window": 5,
        "recovery_check_window": 5,
    },
    {
        "name": _lazy("磁盘I/O使用率"),
        "data_type_label": "time_series",
        "data_source_label": "bk_monitor",
        "result_table_label": "os",
        "metric_field": "util",
        "result_table_id": "system.io",
        "threshold": 80,
        "unit_prefix": "%",
        "method": "gte",
        "trigger_count": 3,
        "trigger_check_window": 5,
        "recovery_check_window": 5,
    },
    {
        "name": _lazy("磁盘使用率"),
        "data_type_label": "time_series",
        "data_source_label": "bk_monitor",
        "result_table_label": "os",
        "metric_field": "in_use",
        "result_table_id": "system.disk",
        "threshold": 95,
        "unit_prefix": "%",
        "method": "gte",
        "trigger_count": 1,
        "trigger_check_window": 5,
        "recovery_check_window": 5,
    },
    {
        "name": _lazy("应用内存使用率"),
        "data_type_label": "time_series",
        "data_source_label": "bk_monitor",
        "result_table_label": "os",
        "metric_field": "pct_used",
        "result_table_id": "system.mem",
        "threshold": 95,
        "unit_prefix": "%",
        "method": "gte",
        "trigger_count": 3,
        "trigger_check_window": 5,
        "recovery_check_window": 5,
    },
    {
        "name": _lazy("Agent心跳丢失"),
        "data_type_label": "event",
        "data_source_label": "bk_monitor",
        "result_table_label": "os",
        "metric_field": "agent-gse",
        # GSE 2.0版本默认触发次数为3，如果为1.0版本则需在saas部署时配置 GSE_VERSION_1 环境变量
        "trigger_count": 1 if "GSE_VERSION_1" in os.environ else 3,
        "trigger_check_window": 10,
        "recovery_check_window": 10,
        "recovery_status_setter": "close",
    },
    {
        "name": _lazy("磁盘只读"),
        "data_type_label": "event",
        "data_source_label": "bk_monitor",
        "result_table_label": "os",
        "metric_field": "disk-readonly-gse",
        "trigger_count": 1,
        "trigger_check_window": 20,
        "recovery_check_window": 20,
        "recovery_status_setter": "close",
    },
    {
        "name": _lazy("Corefile产生"),
        "data_type_label": "event",
        "data_source_label": "bk_monitor",
        "result_table_label": "os",
        "metric_field": "corefile-gse",
        "trigger_count": 1,
        "trigger_check_window": 5,
        "recovery_check_window": 5,
        "recovery_status_setter": "close",
    },
    {
        "name": _lazy("OOM异常告警"),
        "data_type_label": "event",
        "data_source_label": "bk_monitor",
        "result_table_label": "os",
        "metric_field": "oom-gse",
        "trigger_count": 1,
        "trigger_check_window": 5,
        "recovery_check_window": 5,
        "recovery_status_setter": "close",
    },
    {
        "name": _lazy("主机重启"),
        "data_type_label": "event",
        "data_source_label": "bk_monitor",
        "result_table_label": "os",
        "metric_field": "os_restart",
        "trigger_count": 1,
        "trigger_check_window": 5,
        "recovery_check_window": 5,
        "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
        "agg_method": "MAX",
        "recovery_status_setter": "close",
    },
    # deprecated
    # {
    #     "name": _lazy("自定义字符型告警"),
    #     "data_type_label": "event",
    #     "data_source_label": "bk_monitor",
    #     "result_table_label": "os",
    #     "metric_field": "gse_custom_event",
    #     "trigger_count": 1,
    #     "trigger_check_window": 5,
    #     "recovery_check_window": 5,
    #     "recovery_status_setter": "close",
    # },
    {
        "name": _lazy("进程端口"),
        "data_type_label": "event",
        "data_source_label": "bk_monitor",
        "result_table_label": "host_process",
        "metric_field": "proc_port",
        "trigger_count": 1,
        "trigger_check_window": 5,
        "recovery_check_window": 5,
        "agg_dimension": [
            "bk_target_ip",
            "bk_target_cloud_id",
            "display_name",
            "protocol",
            "listen",
            "nonlisten",
            "not_accurate_listen",
            "bind_ip",
        ],
    },
]

if not Platform.te:
    DEFAULT_OS_STRATEGIES.append(
        {
            "name": _lazy("PING不可达告警"),
            "data_type_label": "event",
            "data_source_label": "bk_monitor",
            "result_table_label": "os",
            "metric_field": "ping-gse",
            "trigger_count": 3,
            "trigger_check_window": 5,
            "recovery_check_window": 5,
        }
    )
