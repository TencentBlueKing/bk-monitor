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

from django.utils.translation import ugettext_lazy as _lazy

DEFAULT_GSE_PROCESS_EVENT_STRATEGIES = [
    {
        "type": "business",
        "name": _lazy("Gse进程托管事件告警(业务侧)"),
        "data_type_label": "event",
        "data_source_label": "bk_monitor",
        "result_table_label": "host_process",
        "metric_id": "bk_monitor.gse_process_event",
        "metric_field": "gse_process_event",
        "result_table_id": "system.event",
        "trigger_count": 1,
        "trigger_check_window": 5,
        "recovery_check_window": 5,
        "agg_condition": [
            {
                "key": "process_name",
                "method": "neq",
                "value": [
                    "basereport",
                    "processbeat",
                    "exceptionbeat",
                    "bkmonitorbeat",
                    "bkmonitorproxy",
                    "bkunifylogbeat",
                    "unifyTlogc",
                    "unifytlogc",
                    "gseAgent",
                    "bk-collector",
                ],
            },
        ],
    },
    {
        "type": "blueking",
        "name": _lazy("Gse进程托管事件告警(平台侧)"),
        "data_type_label": "event",
        "data_source_label": "bk_monitor",
        "result_table_label": "host_process",
        "metric_id": "bk_monitor.gse_process_event",
        "metric_field": "gse_process_event",
        "result_table_id": "system.event",
        "trigger_count": 1,
        "trigger_check_window": 5,
        "recovery_check_window": 5,
        "agg_condition": [
            {
                "key": "process_name",
                "method": "eq",
                "value": [
                    "basereport",
                    "processbeat",
                    "exceptionbeat",
                    "bkmonitorbeat",
                    "bkmonitorproxy",
                    "bkunifylogbeat",
                    "unifyTlogc",
                    "unifytlogc",
                    "gseAgent",
                ],
            },
        ],
    },
]
