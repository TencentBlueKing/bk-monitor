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
# 覆盖范围：仅 V4 gse_system_event 表实际产出的 5 类事件
# （AgentLost / DiskReadonly / CoreFile / OOM / PingUnreachable），custom 源。
# 主机重启 os_restart、进程端口 proc_port 不在此列——它们不是 gse 系统事件，而是底层 system.env /
# system.proc_port 时序指标（CMDB 内置进程采集），由 BaseAlarmMetricCacheManager 在多租户内置为
# bk_monitor 源伪事件、经 os/v3 命中创建（见 metric_list_cache.BaseAlarmMetricCacheManager、
# os_loader 与 os/v3.py 注释），不走 custom 链路。
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
    # PING 不可达：是否内置由全局 ping 开关 ENABLE_PING_ALARM 决定（而非部署平台）。该开关是动态设置、
    # 需运行时读，故不在此模块级门控，改由 os_loader 加载时按 settings.ENABLE_PING_ALARM 跳过（access 层
    # 同样按此开关门控 ping 事件处理，见 alarm_backends access processor）。检测语义差异（有意为之）：
    # 单租户 PING 走 pingserver.base.loss_percent 时序 + PingUnreachable 算法（按丢包率）；多租户作为 V4
    # 系统事件，与上面 4 个事件一致走 custom 计数阈值（事件计数 >= 1 即异常，见 os_loader is_custom_event 分支）。
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
