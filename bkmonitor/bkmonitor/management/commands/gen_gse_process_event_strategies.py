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
from django.db.models import Count

from bkmonitor.models import StrategyModel
from monitor_web.strategies.built_in import run_gse_process_build_in


class Command(BaseCommand):
    """
    执行进程托管的内置策略逻辑
    使用示例
    ./bin/api_manage.sh gen_gse_process_event_strategies
    """

    def handle(self, *usernames, **kwargs):
        # 针对已内置策略的业务
        biz_strategy_count = StrategyModel.objects.values("bk_biz_id").annotate(count=Count("bk_biz_id"))
        for item in list(biz_strategy_count):
            if not StrategyModel.objects.filter(bk_biz_id=item["bk_biz_id"]).exists():
                continue
            if StrategyModel.objects.filter(
                name__in=["Gse进程托管事件告警(平台侧)", "Gse进程托管事件告警(业务侧)"], bk_biz_id=item["bk_biz_id"]
            ).exists():
                print(f"已存在进程托管事件默认策略，跳过业务:{item['bk_biz_id']}。")
                continue
            run_gse_process_build_in(item["bk_biz_id"])
            print(f"创建完成：{item['bk_biz_id']} 业务的进程托管事件!")
