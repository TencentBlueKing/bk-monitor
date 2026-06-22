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
#
# agg_dimension（聚合维度）必须显式声明：custom event 走 access/data 聚合检测（COUNT），
# 检测按 agg_dimension 做 group by。若留空会把整个业务的同类事件合并成一条，丢失主机归属、
# 拓扑目标定位与按维度的恢复判定。维度取自系统事件表的 dimension_list：所有事件按主机
# （bk_target_ip/bk_target_cloud_id）聚合，磁盘只读/Corefile 再叠加各自的实例维度以区分
# 同主机的不同只读盘 / 不同 corefile 信号。
#
# 覆盖范围：
# 1) V4 gse_system_event 表的 5 类事件（AgentLost / DiskReadonly / CoreFile / OOM / PingUnreachable），custom 源；
# 2) 主机重启 os_restart、进程端口 proc_port——它们不是 gse 系统事件，而是时序指标，多租户走 V4 主机时序链路：
#    主机重启 = system.env.uptime（OsRestart 算法，与单租户等价）；
#    进程端口 = process.port.alive（"进程采集"模型，仅"端口存活"阈值降级版）。process.port 不携带
#    nonlisten/not_accurate_listen/bind_ip 维度，无法复现单租户 ProcPort 的"端口不监听/监听IP不符"判定。
# os_loader 用 default_config["event_detect"] 标记时序事件检测算法（见 os_loader.load_strategies）。
# DiskFull 在 v1/v2 均未内置，为历史一致行为，非本次引入的缺口。
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
                "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
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
                "agg_dimension": ["bk_target_ip", "bk_target_cloud_id", "position", "type", "fs"],
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
                "agg_dimension": ["bk_target_ip", "bk_target_cloud_id", "executable_path", "executable", "signal"],
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
                # OOM 在旧链路 process 属补充字段、不参与去重；这里按主机聚合，process 不参与聚合、不保证出现在告警维度
                "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
                "trigger_count": 1,
                "trigger_check_window": 5,
                "recovery_check_window": 5,
                "recovery_status_setter": "close",
            },
        ]
    )
    # 主机重启 / 进程端口：多租户走 V4 主机时序链路（非 gse 系统事件、非 custom event）。
    DEFAULT_OS_STRATEGIES.extend(
        [
            {
                "name": _lazy("主机重启"),
                "data_type_label": "time_series",
                "data_source_label": "bk_monitor",
                "result_table_label": "os",
                "result_table_id": "system.env",
                "metric_field": "uptime",
                # 时序事件检测：套用 OsRestart 算法（基于 uptime 回落判定重启），与单租户 os_restart 等价。
                "event_detect": "os_restart",
                "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
                "agg_method": "MAX",
                "agg_interval": 60,
                "trigger_count": 1,
                "trigger_check_window": 5,
                "recovery_check_window": 5,
                "recovery_status_setter": "close",
            },
            {
                "name": _lazy("进程端口"),
                "data_type_label": "time_series",
                "data_source_label": "bk_monitor",
                "result_table_label": "host_process",
                "result_table_id": "process.port",
                "metric_field": "alive",
                # 降级版：process.port（进程采集模型）不携带 nonlisten/not_accurate_listen/bind_ip 维度，
                # 无法复现单租户 ProcPort 的"端口不监听/监听IP不符"判定，仅做"端口存活"阈值（alive < 1 即异常）。
                "threshold": 1,
                "method": "lt",
                "agg_dimension": [
                    "bk_target_ip",
                    "bk_target_cloud_id",
                    "process_name",
                    "listen_address",
                    "listen_port",
                ],
                "agg_method": "MAX",
                "agg_interval": 60,
                "trigger_count": 1,
                "trigger_check_window": 5,
                "recovery_check_window": 5,
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
                "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
                "trigger_count": 3,
                "trigger_check_window": 5,
                "recovery_check_window": 5,
                "recovery_status_setter": "close",
            }
        )
