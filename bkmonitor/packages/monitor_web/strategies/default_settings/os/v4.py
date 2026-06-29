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

# v4 版本：多租户 PING 不可达内置策略（bk_monitor 源伪事件，走指标逻辑，与单租户 v1 同形）。
#
# 修正：v2（PR #11148）曾把多租户 PING 当 V4 custom 系统事件（PingUnreachable）内置，形态错误——
# PING 不可达本质是时序指标（底层 pingserver.base/loss_percent 按丢包率），不是 gse 系统事件，custom
# 计数语义不符。单租户一直走 bk_monitor 源伪事件 ping-gse + EVENT_QUERY_CONFIG_MAP 重定向到
# pingserver.base/loss_percent + PingUnreachable 算法（见 os/v1.py 的 ping-gse、
# constants.strategy.EVENT_QUERY_CONFIG_MAP/EVENT_DETECT_LIST）。本版本把多租户 PING 改回同一指标逻辑：
# 声明 bk_monitor/event/ping-gse，由 os_loader 命中 BaseAlarmMetricCacheManager 在多租户内置的
# bk_monitor.ping-gse 目录项后，按上述重定向建出时序阈值策略。
#
# 为何单列 v4、而非并入 v2/v3 或放回 v1：
#   - v2 是 custom 源系统事件，形态不符；
#   - v3 已随 #11148 上线、部分业务可能已登记接入，并入会因幂等跳过、永不补建（同 v3 不并入 v1 的理由）；
#   - v1 的 ping-gse 声明在多租户仍执行，但已登记 v1 的存量业务会因幂等跳过、永不补建。
#   故单列新版本 v4 才能对存量业务增量补建 PING。
#
# 是否真正建出由全局开关 ENABLE_PING_ALARM 运行时单点治理（os_loader 加载时按 settings.ENABLE_PING_ALARM
# 跳过、access 层同门控；BaseAlarmMetricCacheManager 内置 ping-gse 目录项时亦按此开关门控），而非部署
# 平台——多租户 PING 不沿用单租户 Platform.te 排除口径，统一由 ENABLE_PING_ALARM 单点治理。
# 配置与 v1 的 ping-gse 完全一致，不降级。
DEFAULT_OS_STRATEGIES = []

if settings.ENABLE_MULTI_TENANT_MODE:
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
