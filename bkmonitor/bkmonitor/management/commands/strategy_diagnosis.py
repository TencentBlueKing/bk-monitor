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
        parser.add_argument("--add_cloud_id", action="store_true", help="补充bk_target_cloud_id维度到策略中")
        parser.add_argument("--bk_biz_id", type=int, default=0)

    def handle(self, *args, **options):
        print(add_cloud_id_to_strategy.__doc__)
        add_cloud_id_to_strategy(add_cloud_id=options["add_cloud_id"], bk_biz_id=options["bk_biz_id"])


def add_cloud_id_to_strategy(add_cloud_id: bool, bk_biz_id: int):
    """
    检索全业务下策略配置了bk_target_ip维度，但未配置bk_target_cloud_id维度的策略列表，并打印对应策略的信息：ID，名字，业务id

    python manage.py strategy_diagnosis  # 只展示信息
    python manage.py strategy_diagnosis --add_cloud_id  # 补充bk_target_cloud_id维度到策略中
    """
    query_set = QueryConfigModel.objects.all()
    if bk_biz_id != 0:
        s_ids = list(StrategyModel.objects.filter(bk_biz_id=bk_biz_id, is_enabled=1).values_list("id", flat=1))
        query_set = query_set.filter(strategy_id__in=s_ids)
    query_configs = query_set.only("strategy_id", "config")

    strategy_ids = []
    query_config_instances = []
    for query_config in query_configs:
        if (query_config.data_source_label, query_config.data_type_label) not in [
            ("bk_monitor", "time_series"),
            ("custom", "time_series"),
        ]:
            # 仅处理监控采集相关指标（明确已内置标准字段： bk_target_cloud_id）
            continue
        agg_dimension = query_config.config.get("agg_dimension", [])
        if "bk_target_ip" in agg_dimension and "bk_target_cloud_id" not in agg_dimension:
            strategy_ids.append(query_config.strategy_id)
            if add_cloud_id:
                agg_dimension.append("bk_target_cloud_id")
                query_config_instances.append(query_config)

    strategies = StrategyModel.objects.filter(id__in=strategy_ids).only("id", "name", "bk_biz_id")

    print("策略ID，策略名字，业务id")
    for strategy in strategies:
        print(f"{strategy.id}, {strategy.name}, {strategy.bk_biz_id}")

    if add_cloud_id:
        QueryConfigModel.objects.bulk_update(query_config_instances, ["config"])
        print("bk_target_cloud_id维度添加完成")
