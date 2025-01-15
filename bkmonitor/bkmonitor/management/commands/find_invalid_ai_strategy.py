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
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from bkmonitor.dataflow.constant import AccessStatus
from bkmonitor.models import AlgorithmModel, QueryConfigModel, StrategyModel


class Command(BaseCommand):
    def handle(self, **kwargs):
        # 1. 找出配置了aiops算法的策略ID
        strategy_ids = AlgorithmModel.objects.filter(
            type__in=AlgorithmModel.AIOPS_ALGORITHMS,
        ).values_list("strategy_id", flat=True)

        # 2. 没有配置aiops算法的策略，则直接返回
        if not strategy_ids:
            return

        # 3. 找出配置了aiops算法，但数据未接入计算平台的策略ID
        # 数据未接入计算平台的过滤条件
        # 一个是旧数据的过滤条件，一个是新数据的过滤条件
        not_access_condition = Q(
            config__intelligent_detect__status=AccessStatus.RUNNING,
            config__intelligent_detect__retries=0,
            config__intelligent_detect__message="",
        ) | Q(
            config__intelligent_detect__status=AccessStatus.FAILED,
            config__intelligent_detect__retries=0,
            config__intelligent_detect__message__regex=r'.*access\s*to\s*bkdata\s*failed.*',
        )
        strategy_ids = QueryConfigModel.objects.filter(
            not_access_condition,
            strategy_id__in=strategy_ids,
        ).values_list("strategy_id", flat=True)

        # 4. 配置了aiops算法，数据未接入计算平台的情况不存在，则直接返回
        if not strategy_ids:
            return

        # 5. 找出配置了aiops算法， 但未生效的策略
        strategies = (
            StrategyModel.objects.filter(id__in=strategy_ids, is_enabled=True)
            .values_list("id", "name", "bk_biz_id")
            .order_by("bk_biz_id")
        )
        url_tmp = f"{settings.BK_MONITOR_HOST}?bizId=%s/#/strategy-config/edit/%s"
        print("以下策略配置了aiops算法，但未生效:")
        for strategy in strategies:
            print(f"- 【{strategy[2]}】  [{strategy[1]}]({url_tmp % (strategy[2], strategy[0])})")
