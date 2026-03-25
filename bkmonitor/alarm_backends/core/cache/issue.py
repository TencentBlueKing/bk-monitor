"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from alarm_backends.core.cache.key import ISSUE_ACTIVE_CONTENT_KEY, ISSUE_STRATEGY_LOCK  # noqa: F401

logger = logging.getLogger("fta_action.issue")

# StrategyIssueConfigCache 已废弃（v2 改造后 issue_config 合并进策略缓存 JSON）。
# ISSUE_ACTIVE_CONTENT_KEY / ISSUE_STRATEGY_LOCK 是 Issue 运营数据缓存，与本次改造无关，保持不动。
#
# 如需访问 issue_config，请通过策略缓存读取：
#   from alarm_backends.core.cache.strategy import StrategyCacheManager
#   strategy = StrategyCacheManager.get_strategy_by_id(strategy_id)
#   issue_config = strategy.get("issue_config")
