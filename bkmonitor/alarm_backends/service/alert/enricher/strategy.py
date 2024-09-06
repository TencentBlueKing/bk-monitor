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
from alarm_backends.core.alert import Alert
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.service.alert.enricher import BaseAlertEnricher
from core.errors.strategy import StrategyNotExist


class StrategySnapshotEnricher(BaseAlertEnricher):
    """
    增加告警的快照
    """

    def enrich_alert(self, alert: Alert) -> Alert:
        strategy = alert.get_extra_info(key="strategy")

        if not strategy:
            origin_alarm = alert.get_extra_info(key="origin_alarm")
            if not origin_alarm:
                return alert

            # 尝试从快照获取
            strategy = Strategy.get_strategy_snapshot_by_key(origin_alarm["strategy_snapshot_key"])

        if not strategy:
            # 如果没有，则从缓存中获取
            strategy = StrategyCacheManager.get_strategy_by_id(int(alert.strategy_id))

        if not strategy and alert.strategy_id:
            raise StrategyNotExist("strategy(%s) not exist", alert.strategy_id)

        alert.update_extra_info(key="strategy", value=strategy)
        alert.update_labels(strategy.get("labels", []))
        return alert
