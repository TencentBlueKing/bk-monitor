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
from bkmonitor.models.strategy import QueryConfigModel, StrategyModel


class Command(BaseCommand):
    def add_arguments(self, parser):
        # 添加一个update参数
        parser.add_argument("--add_cloud_id", action="store_true", help="是否将bk_target_cloud_id维度添加到策略中")

    def handle(self, *args, **options):
        print(add_cloud_id_to_strategy.__doc__)
        add_cloud_id_to_strategy(add_cloud_id=options["add_cloud_id"])


def add_cloud_id_to_strategy(add_cloud_id: bool):
    """
    检索全业务下策略配置了bk_target_ip维度，但未配置bk_target_cloud_id维度的策略列表，并打印对应策略的信息：ID，名字，业务id
    add_cloud_id为True时，将bk_target_cloud_id维度添加到对应的策略配置中
    """
    query_configs = QueryConfigModel.objects.all().only("strategy_id", "config")

    strategy_ids = []
    query_config_instance = []
    for query_config in query_configs:
        agg_dimension = query_config.config.get("agg_dimension", [])
        if "bk_target_ip" in agg_dimension and "bk_target_cloud_id" not in agg_dimension:
            strategy_ids.append(query_config.strategy_id)
            if add_cloud_id:
                agg_dimension.append("bk_target_cloud_id")
                query_config_instance.append(query_config)

    strategies = StrategyModel.objects.filter(id__in=strategy_ids).only("id", "name", "bk_biz_id")

    print("策略ID，策略名字，业务id")
    for strategy in strategies:
        print(f"{strategy.id}, {strategy.name}, {strategy.bk_biz_id}")

    if add_cloud_id:
        QueryConfigModel.objects.bulk_update(query_config_instance, ["config"])
        print("bk_target_cloud_id维度添加完成")
