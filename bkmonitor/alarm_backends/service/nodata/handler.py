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
import time

import arrow

from alarm_backends import constants
from alarm_backends.cluster import TargetType
from alarm_backends.core.cache import key
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.cluster import get_cluster
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.handlers import base
from alarm_backends.service.nodata.tasks import no_data_check

logger = logging.getLogger("nodata")
# 每分钟运行一次，检测两个周期前的 access 数据，运行间隔需要保持一致，建议设置为每分钟的后半分钟时间段
EXECUTE_TIME_SECOND = 55


class NodataHandler(base.BaseHandler):
    def handle(self):
        # 特定时间点执行
        if arrow.now().second != EXECUTE_TIME_SECOND:
            time.sleep(1)
            return

        # 进程总锁， 基于celery任务分发，分布式场景，master不需要多个
        service_key = key.SERVICE_LOCK_NODATA.get_key(strategy_id=0)
        client = key.SERVICE_LOCK_NODATA.client
        ret = client.set(service_key, time.time(), ex=key.SERVICE_LOCK_NODATA.ttl, nx=True)
        if not ret:
            logger.info("[nodata] skip for not leader")
            time.sleep(1)
            return

        logger.info("[nodata] get leader now")
        now_timestamp = arrow.utcnow().timestamp - constants.CONST_MINUTES
        strategy_ids = StrategyCacheManager.get_nodata_strategy_ids()
        published = []
        for strategy_id in strategy_ids:
            strategy = Strategy(strategy_id)

            # 只处理当前集群的策略
            if not get_cluster().match(TargetType.biz, strategy.bk_biz_id):
                continue

            interval = strategy.get_interval()

            # 如果发现access的运行时间距离当前时间超过了2倍的检测周期，则不再进行检测，防止access不执行导致的误报
            last_access_run_timestamp_key = key.ACCESS_RUN_TIMESTAMP_KEY.get_key(
                strategy_group_key=strategy.strategy_group_key
            )
            last_access_run_time = int(key.ACCESS_RUN_TIMESTAMP_KEY.client.get(last_access_run_timestamp_key) or 0)

            if last_access_run_time and (
                time.time() - last_access_run_time > max(2 * interval, 2 * EXECUTE_TIME_SECOND)
            ):
                logger.info(f"[nodata] skip strategy({strategy_id}) for access not run since {last_access_run_time}")
                continue

            self.no_data_check(strategy_id, now_timestamp)
            published.append(strategy_id)

        logger.info(
            "[nodata] no_data_check published {}/{} strategy_ids: {}".format(
                len(published), len(strategy_ids), published
            )
        )

        # 先缓1s，过了EXECUTE_TIME_SECOND时间窗口先
        if arrow.now().second == EXECUTE_TIME_SECOND:
            time.sleep(1)

        client.delete(service_key)
        # 等下一波（EXECUTE_TIME_SECOND）
        wait_for = (EXECUTE_TIME_SECOND + 60 - arrow.now().second) % 60
        logger.info("[nodata] wait {}s for next leader competition".format(wait_for))
        if wait_for > 1:
            time.sleep(wait_for)

    @classmethod
    def no_data_check(cls, strategy_id, now_timestamp):
        no_data_check(strategy_id, now_timestamp)


class NodataCeleryHandler(NodataHandler):
    @classmethod
    def no_data_check(cls, strategy_id, now_timestamp):
        no_data_check.delay(strategy_id, now_timestamp)
