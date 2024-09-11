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
import abc
import logging
from typing import List

from alarm_backends.core.alert import Alert, Event

logger = logging.getLogger("alert.enricher")


class BaseEventEnricher(metaclass=abc.ABCMeta):
    def __init__(self, events: List[Event]):
        self.events = events

    def enrich(self) -> List[Event]:
        events = []
        for event in self.events:
            try:
                if event.is_dropped():
                    events.append(event)

                event = self.enrich_event(event)
                if event.is_dropped():
                    logger.info(
                        "[drop event] %s event(%s) strategy(%s)",
                        self.__class__.__name__,
                        event.event_id,
                        event.strategy_id,
                    )
            except Exception as e:
                logger.exception("[event enricher ERROR] (%s), detail: %s", self.__class__.__name__, e)
            events.append(event)
        return events

    def enrich_event(self, event) -> Event:
        """
        单个事件丰富
        """
        return event


class BaseAlertEnricher(metaclass=abc.ABCMeta):
    def __init__(self, alerts: List[Alert]):
        self.alerts = alerts

    def enrich(self) -> List[Alert]:
        alerts = []
        for alert in self.alerts:
            try:
                if alert.is_new():
                    # 新产生的告警才需要丰富
                    alert = self.enrich_alert(alert)
            except Exception as e:
                logger.exception("[alert enricher ERROR] (%s), detail: %s", self.__class__.__name__, e)
            alerts.append(alert)
        return alerts

    def enrich_alert(self, alert: Alert) -> Alert:
        """
        单个告警丰富
        """
        return alert
