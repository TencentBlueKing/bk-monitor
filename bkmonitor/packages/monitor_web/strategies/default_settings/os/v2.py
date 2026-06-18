"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import os

from django.conf import settings
from django.utils.translation import gettext_lazy as _lazy

from common.context_processors import Platform

# v2 版本：多租户系统事件内置策略。
#
# 多租户模式下系统事件走 V4 分业务链路（custom 源，每个 cmdb 业务独立结果表 base_{tenant}_{biz}_event），
# 与单租户的全局 system.event（bk_monitor 源）不同，v1 中的 bk_monitor 事件策略在多租户下匹配不到指标。
# 此处只声明事件名（即 custom_event_name，取自 V4 系统事件表的 event_name），
# result_table_id 由 os_loader 运行时按业务实地注入。
#
# 单独作为新版本而非并入 v1：使已接入 v1 的存量业务也能增量补齐这些事件策略；单租户下本版本为空。
DEFAULT_OS_STRATEGIES = []

if settings.ENABLE_MULTI_TENANT_MODE:
    DEFAULT_OS_STRATEGIES.extend(
        [
            {
                "name": _lazy("Agent心跳丢失"),
                "data_type_label": "event",
                "data_source_label": "custom",
                "result_table_label": "os",
                "metric_field": "AgentLost",
                # GSE 2.0版本默认触发次数为3，如果为1.0版本则需在saas部署时配置 GSE_VERSION_1 环境变量
                "trigger_count": 1 if "GSE_VERSION_1" in os.environ else 3,
                "trigger_check_window": 10,
                "recovery_check_window": 10,
                "recovery_status_setter": "close",
            },
            {
                "name": _lazy("磁盘只读"),
                "data_type_label": "event",
                "data_source_label": "custom",
                "result_table_label": "os",
                "metric_field": "DiskReadonly",
                "trigger_count": 1,
                "trigger_check_window": 20,
                "recovery_check_window": 20,
                "recovery_status_setter": "close",
            },
            {
                "name": _lazy("Corefile产生"),
                "data_type_label": "event",
                "data_source_label": "custom",
                "result_table_label": "os",
                "metric_field": "CoreFile",
                "trigger_count": 1,
                "trigger_check_window": 5,
                "recovery_check_window": 5,
                "recovery_status_setter": "close",
            },
            {
                "name": _lazy("OOM异常告警"),
                "data_type_label": "event",
                "data_source_label": "custom",
                "result_table_label": "os",
                "metric_field": "OOM",
                "trigger_count": 1,
                "trigger_check_window": 5,
                "recovery_check_window": 5,
                "recovery_status_setter": "close",
            },
        ]
    )
    if not Platform.te:
        DEFAULT_OS_STRATEGIES.append(
            {
                "name": _lazy("PING不可达告警"),
                "data_type_label": "event",
                "data_source_label": "custom",
                "result_table_label": "os",
                "metric_field": "PingUnreachable",
                "trigger_count": 3,
                "trigger_check_window": 5,
                "recovery_check_window": 5,
            }
        )
