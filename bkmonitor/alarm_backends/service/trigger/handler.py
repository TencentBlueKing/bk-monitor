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

from alarm_backends.core.cache.key import ANOMALY_SIGNAL_KEY
from alarm_backends.core.handlers import base
from alarm_backends.service.trigger.runner import run_trigger_item
from core.errors.alarm_backends import LockError
from core.prometheus import metrics

logger = logging.getLogger("trigger")


class TriggerHandler(base.BaseHandler):
    DATA_FETCH_TIMEOUT = 5

    def handle(self):
        logger.info("[trigger][latency] start to fetch anomaly_key")
        if self.DATA_FETCH_TIMEOUT:
            anomaly_key = ANOMALY_SIGNAL_KEY.client.brpop(ANOMALY_SIGNAL_KEY.get_key(), self.DATA_FETCH_TIMEOUT)
        else:
            anomaly_key = ANOMALY_SIGNAL_KEY.client.rpop(ANOMALY_SIGNAL_KEY.get_key())

        if not anomaly_key:
            return
        if self.DATA_FETCH_TIMEOUT:
            anomaly_key = anomaly_key[1]

        try:
            strategy_id, item_id = anomaly_key.split(".")
        except Exception as e:
            logger.error("ANOMALY_SIGNAL_KEY({}) parse error：{}".format(anomaly_key, e))
            return

        try:
            run_trigger_item(strategy_id, item_id, executor="trigger_worker")
        except LockError:
            logger.info(
                "[get service lock fail] strategy({}), item({}). will process later".format(strategy_id, item_id)
            )
            ANOMALY_SIGNAL_KEY.client.delay("rpush", ANOMALY_SIGNAL_KEY.get_key(), anomaly_key, delay=1)
            # 如果是获取锁失败，不需要上报指标，直接可以返回
            return
        metrics.report_all()
