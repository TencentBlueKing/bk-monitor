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
import logging
import time
from typing import List

from alarm_backends.core.alert import Alert

logger = logging.getLogger("alert.manager")


class BaseChecker:
    def __init__(self, alerts: List[Alert]):
        self.alerts = alerts

    def is_enabled(self, alert: Alert):
        return alert.is_abnormal()

    def check(self, alert: Alert):
        raise NotImplementedError

    def check_all(self):
        success = 0
        failed = 0
        start = time.time()
        for alert in self.alerts:
            if self.is_enabled(alert):
                try:
                    self.check(alert)
                    success += 1
                except Exception as e:
                    logger.exception(
                        "[%s failed] alert(%s) strategy(%s) %s", self.__class__.__name__, alert.id, alert.strategy_id, e
                    )
                    failed += 1
        logger.info(
            "[%s] success(%s), failed(%s), cost: %s", self.__class__.__name__, success, failed, time.time() - start
        )
