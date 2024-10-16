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
import logging
from typing import List, Type

from alarm_backends.core.alert import Alert, Event
from alarm_backends.service.alert.enricher.base import (
    BaseAlertEnricher,
    BaseEventEnricher,
)
from alarm_backends.service.alert.enricher.cmdb import CMDBEnricher
from alarm_backends.service.alert.enricher.dimension import (
    DimensionOrderEnricher,
    MonitorTranslateEnricher,
    PreEventEnricher,
    StandardTranslateEnricher,
)
from alarm_backends.service.alert.enricher.kubernetes_cmdb import KubernetesCMDBEnricher
from alarm_backends.service.alert.enricher.rule_assign import AssignInfoEnricher
from alarm_backends.service.alert.enricher.strategy import StrategySnapshotEnricher
from alarm_backends.service.alert.enricher.whitelist import BizWhiteListFor3rdEvent

logger = logging.getLogger("alert.enricher")

INSTALLED_EVENT_ENRICHER: List[Type[BaseEventEnricher]] = [
    PreEventEnricher,
    CMDBEnricher,
    BizWhiteListFor3rdEvent,
]

INSTALLED_AlERT_ENRICHER: List[Type[BaseAlertEnricher]] = [
    StrategySnapshotEnricher,
    StandardTranslateEnricher,
    MonitorTranslateEnricher,
    DimensionOrderEnricher,
    AssignInfoEnricher,
    KubernetesCMDBEnricher,
]


class EventEnrichFactory:
    def __init__(self, events: List[Event]):
        self.events = events

    def enrich(self):
        events = self.events
        for enricher_cls in INSTALLED_EVENT_ENRICHER:
            enricher = enricher_cls(events)
            events = enricher.enrich()
        return events


class AlertEnrichFactory:
    def __init__(self, alerts: List[Alert]):
        self.alerts = alerts

    def enrich(self):
        alerts = self.alerts
        for enricher_cls in INSTALLED_AlERT_ENRICHER:
            enricher = enricher_cls(alerts)
            alerts = enricher.enrich()
        return alerts
