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
from bkmonitor.models import StrategyModel, DetectModel, QueryConfigModel


class Command(BaseCommand):
    """
    更新gse2.0升级后内置心跳策略
    """

    def handle(self, **kwargs):
        # 针对已内置策略的业务
        strategy_ids = QueryConfigModel.objects.filter(metric_id="bk_monitor.agent-gse").values_list(
            "strategy_id", flat=True
        )
        for detect in DetectModel.objects.filter(strategy_id__in=strategy_ids):
            origin_count = detect.trigger_config["count"]
            origin_check_window = detect.trigger_config["check_window"]
            if origin_count >= 3 and origin_check_window >= 5:
                continue
            if origin_count < 3:
                detect.trigger_config["count"] = 3
            if origin_check_window < 5:
                detect.trigger_config["check_window"] = 5
            detect.save()
            print(
                f"Agent心跳丢失策略({detect.strategy_id})触发次数/周期更新完成：{origin_count}/{origin_check_window} ->"
                f" {detect.trigger_config['count']}/{detect.trigger_config['check_window']}"
            )
