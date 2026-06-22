"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings
from django.utils.translation import gettext_lazy as _lazy

# v3 版本：多租户主机重启 / 进程端口内置策略。
#
# 这两类不是 gse 系统事件（不走 V4 base_{tenant}_{biz}_event），而是 V4 主机时序链路指标：
#   主机重启 = system.env.uptime（OsRestart 算法，与单租户等价）；
#   进程端口 = process.port.alive（"进程采集"模型，仅"端口存活"阈值降级版）。process.port 不携带
#   nonlisten/not_accurate_listen/bind_ip 维度，无法复现单租户 ProcPort 的"端口不监听/监听IP不符"判定。
#
# 为何独立成 v3 而非并入 v2：v2 的 5 类 custom event 走 V4 事件链路，与本文件两条策略所依赖的
# 主机时序缓存是【两条独立就绪的缓存】。若混在同一版本，custom event 先就绪、主机时序未同步时会
# 部分创建后即登记该版本接入记录，导致后续主机时序就绪也被幂等跳过、主机重启/进程端口永久漏建
# （base loader 仅在「零创建」时才不登记）。拆版本后每个版本内的策略共享同一就绪来源，
# 「零创建即不登记、就绪后整体补建」的语义才成立。system.env 与 process.port 由同一次
# get_metrics_multi_tenant 产出，故本版本内两条策略就绪时机一致。
#
# os_loader 用 default_config["event_detect"] 标记时序事件检测算法（见 os_loader.load_strategies）。
DEFAULT_OS_STRATEGIES = []

if settings.ENABLE_MULTI_TENANT_MODE:
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
