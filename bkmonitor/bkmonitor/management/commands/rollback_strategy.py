# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import datetime

from django.core.management.base import BaseCommand

from bkmonitor.models import StrategyHistoryModel
from core.drf_resource import resource

"""
--strategy_ids=46161 --timestamp=1721185500
"""


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--strategy_ids", type=str, required=True, help="策略列表半角逗号分隔")
        parser.add_argument("--timestamp", type=str, required=True, help="回滚时间线，将策略回滚至时间线之前的最新一次配置")

    def handle(self, *args, **kwargs):
        strategy_ids = [s.strip() for s in kwargs.pop("strategy_ids").split(",")]
        timestamp = int(kwargs.pop("timestamp"))
        strategy_ids = list(map(int, strategy_ids))
        print(strategy_ids, timestamp)
        for s_id in strategy_ids:
            rollback_strategy(s_id, timestamp)


def rollback_strategy(strategy_id, timestamp):
    old = (
        StrategyHistoryModel.objects.filter(
            strategy_id=strategy_id, create_time__lt=datetime.datetime.fromtimestamp(timestamp)
        )
        .order_by("-create_time")
        .first()
    )
    new = (
        StrategyHistoryModel.objects.filter(
            strategy_id=strategy_id, create_time__gt=datetime.datetime.fromtimestamp(timestamp)
        )
        .order_by("create_time")
        .first()
    )
    if not old or not new:
        print(f"strategy[{strategy_id}] history not found, do nothing.")
        return
    old_content = old.content
    if old.operate == "create":
        old_content["id"] = strategy_id
    try:
        resource.strategies.save_strategy_v2(old_content)
    except Exception as e:
        print(f"strategy[{strategy_id}] rollback error: {e}")
    else:
        print(f"strategy[{strategy_id}] rollback done")
