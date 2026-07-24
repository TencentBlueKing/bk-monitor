# -*- coding: utf-8 -*-  # noqa: UP009
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.management.commands.clean_strategy_history import Command as CleanStrategyHistoryCommand
from bkmonitor.strategy.history import MIN_CLEAN_STRATEGY_HISTORY_DAYS
from bkmonitor.strategy.history import CleanStrategyHistoryParams
from bkmonitor.strategy.history import clean_strategy_history_compat


class Command(CleanStrategyHistoryCommand):
    """兼容旧批量操作历史状态的临时清理命令。"""

    help = (
        "临时兼容清理命令：为窗口外旧版批量 update 历史额外保留最近快照，"
        "并为已删除策略保留最新 delete 记录；其余规则与 clean_strategy_history 一致。"
        f"默认 dry-run；真正删除需加 --execute。--days 不得小于 {MIN_CLEAN_STRATEGY_HISTORY_DAYS}。"
    )
    command_name = "clean strategy history compatibility"
    deprecation_warning = (
        "deprecated compatibility command: only use while legacy bulk update/delete status records need cleanup"
    )

    @staticmethod
    def cleanup(params: CleanStrategyHistoryParams) -> int:
        return clean_strategy_history_compat(params)
