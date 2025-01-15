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

from alarm_backends.core.cache import key
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.service.preparation.aiops.processor import (
    TsDependPreparationProcess,
)
from alarm_backends.service.scheduler.app import app
from constants.aiops import SDKDetectStatus
from core.errors.alarm_backends import LockError

logger = logging.getLogger("preparation")


@app.task(ignore_result=True, queue="celery_cron")
def refresh_aiops_sdk_depend_data(strategy_id, update_time: int = None, force: bool = False):
    """刷新用于AIOPS SDK异常检测的历史依赖数据.

    :param strategy_id: 策略ID
    :return:
    """
    try:
        TsDependPreparationProcess().process(strategy_id, update_time, force)
    except LockError:
        logger.info("Failed to acquire lock. on strategy({}) with update time: {}".format(strategy_id, update_time))
    except Exception as e:
        logger.exception("Process strategy({strategy_id}) exception, " "{msg}".format(strategy_id=strategy_id, msg=e))


@app.task(ignore_result=True, queue="celery_cron")
def maintain_all_aiops_sdk_depend_data():
    """通过轮训的方式管理AIOPS SDK的历史依赖.

    :return:
    """
    # 进程总锁， 基于celery任务分发，分布式场景，master不需要多个
    service_key = key.SERVICE_LOCK_PREPARATION.get_key(strategy_id=0)
    client = key.SERVICE_LOCK_PREPARATION.client
    ret = client.set(service_key, time.time(), ex=key.SERVICE_LOCK_PREPARATION.ttl, nx=True)
    if not ret:
        logger.info("[preparation] skip for not leader")
        time.sleep(1)
        return

    logger.info("[preparation] get leader now")
    strategy_ids = StrategyCacheManager.get_aiops_sdk_strategy_ids()
    for strategy_id in strategy_ids:
        strategy = Strategy(strategy_id)
        query_config = strategy.config["items"][0]["query_configs"][0]

        # 只有使用SDK进行检测的智能监控策略才进行历史依赖数据的初始化
        if query_config.get("intelligent_detect") and query_config["intelligent_detect"].get("use_sdk", False):
            # 历史依赖准备就绪才开始检测
            if query_config["intelligent_detect"]["status"] == SDKDetectStatus.PREPARING:
                refresh_aiops_sdk_depend_data(strategy_id)
