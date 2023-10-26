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

from django.core.management.base import BaseCommand

from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.strategy import Strategy


class Command(BaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument("--group_key", help="strategy group key")
        parser.add_argument("--strategy_id", help="strategy id")

    def handle(self, *args, **options):
        group_key = options.get("group_key")
        strategy_id = options.get("strategy_id")
        if not group_key and not strategy_id:
            raise Exception("group_key and strategy_id must have one.")

        if strategy_id:
            print("---------strategy to group_key----------")
            strategy = StrategyCacheManager.get_strategy_by_id(strategy_id)
            if not strategy:
                print("strategy({}) no config, please confirm that the strategy_id is correct.".format(strategy_id))
            else:
                for item in strategy["items"]:
                    if item.get("query_md5"):
                        print(
                            "strategy({}), item({}) strage_group_key({})".format(
                                strategy_id, item["id"], item["query_md5"]
                            )
                        )

        if group_key:
            print("---------group_key to strategy----------")
            records = StrategyCacheManager.get_strategy_group_detail(group_key)
            if not records:
                print(
                    "strategy_group_key({}) no config, please confirm that the group_key is correct.".format(group_key)
                )
            else:
                for strategy_id, item_ids in list(records.items()):
                    try:
                        strategy_id = int(strategy_id)
                    except ValueError:
                        continue
                    strategy = Strategy(strategy_id)
                    for item in strategy.items:
                        print("strategy({}), item({}) strage_group_key({})".format(strategy_id, item.id, group_key))
