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

from alarm_backends.core.cache.key import ANOMALY_SIGNAL_KEY, SERVICE_LOCK_TRIGGER
from alarm_backends.core.handlers import base
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.service.trigger.processor import TriggerProcessor
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

        logger.info("[start][latency] strategy({}), item({})".format(strategy_id, item_id))

        exc = None
        try:
            with service_lock(SERVICE_LOCK_TRIGGER, strategy_id=strategy_id, item_id=item_id):
                with metrics.TRIGGER_PROCESS_TIME.labels(strategy_id=metrics.TOTAL_TAG).time():
                    processor = TriggerProcessor(strategy_id, item_id)
                    processor.process()
        except LockError:
            logger.info(
                "[get service lock fail] strategy({}), item({}). will process later".format(strategy_id, item_id)
            )
            ANOMALY_SIGNAL_KEY.client.delay("rpush", ANOMALY_SIGNAL_KEY.get_key(), anomaly_key, delay=1)
            # 如果是获取锁失败，不需要上报指标，直接可以返回
            return
        except Exception as e:
            exc = e
            logger.exception(
                "[process error] strategy({strategy_id}), item({item_id}) reason：{msg}".format(
                    strategy_id=strategy_id, item_id=item_id, msg=e
                )
            )

        logger.info("[end][latency] strategy({}), item({})".format(strategy_id, item_id))

        metrics.TRIGGER_PROCESS_COUNT.labels(
            strategy_id=metrics.TOTAL_TAG, status=metrics.StatusEnum.from_exc(exc), exception=exc
        ).inc()
        metrics.report_all()
