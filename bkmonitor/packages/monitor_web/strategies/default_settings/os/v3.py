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

# v3 版本：多租户主机重启 / 进程端口内置策略（bk_monitor 源伪事件，与单租户 v1 完全同形）。
#
# 这两条不是 gse 系统事件（不走 v2 的 custom/base_{tenant}_{biz}_event 链路），而是 bk_monitor 源
# 伪事件：底层时序表 system.env（uptime）/ system.proc_port（proc_exists，CMDB 内置进程采集，
# 富维度 nonlisten/not_accurate_listen/bind_ip）在多租户同样产出，由 BaseAlarmMetricCacheManager
# 在多租户内置为 bk_monitor.os_restart / bk_monitor.proc_port 目录项；os_loader 经
# EVENT_QUERY_CONFIG_MAP 把查询重定向到底层时序表并套 OsRestart/ProcPort 算法，与单租户语义一致。
#
# 为何单列 v3、而非直接放开 v1 的对应声明：
#   1) v1 把 os_restart/proc_port 连同 gse 事件圈在 `if not ENABLE_MULTI_TENANT_MODE` 块内，
#      多租户不声明，故需要一个多租户专用版本来声明这两条；
#   2) v1 在多租户已因 CPU/内存/磁盘/IO 等时序策略被登记接入（DefaultStrategyBizAccessModel），
#      若把这两条移进 v1，已登记 v1 的存量业务会因幂等跳过、永不补建——单列新版本 v3 才能对
#      存量业务增量补建。
# 配置与 v1 的 os_restart/proc_port 完全一致（bk_monitor + event + metric_field），不降级。
DEFAULT_OS_STRATEGIES = []

if settings.ENABLE_MULTI_TENANT_MODE:
    DEFAULT_OS_STRATEGIES.extend(
        [
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
    )
