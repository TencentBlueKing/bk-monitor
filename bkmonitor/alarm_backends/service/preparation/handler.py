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
from django.conf import settings

from alarm_backends.core.cache import key
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.handlers import base
from alarm_backends.service.preparation.aiops.processor import (
    TsDependEventPreparationProcess,
    TsDependPreparationProcess,
)
from bkmonitor.models.strategy import QueryConfigModel
from bkmonitor.strategy.new_strategy import QueryConfig
from constants.aiops import SDKDetectStatus
from constants.data_source import DataTypeLabel

logger = logging.getLogger("preparation")
# 每分钟运行一次
EXECUTE_TIME_SECOND = 35


class PreparationHandler(base.BaseHandler):
    """
    PreparationHandler
    """

    def __init__(self, targets=None, *args, **option):
        self.service = option.get("service")

        self.targets = targets or []
        self.option = option
        super(PreparationHandler, self).__init__(*args, **option)

    def handle(self):
        self.handle_with_polling()

    def handle_with_event(self):
        processor = TsDependEventPreparationProcess(
            broker_url=settings.BK_DATA_AIOPS_INCIDENT_BROKER_URL, queue_name=settings.BK_DATA_AIOPS_INCIDENT_SYNC_QUEUE
        )
        processor.process()

    def handle_with_polling(self):
        # 特定时间点执行
        if arrow.now().second != EXECUTE_TIME_SECOND:
            time.sleep(1)
            return

        # 进程总锁， 基于celery任务分发，分布式场景，master不需要多个
        service_key = key.SERVICE_LOCK_PREPARATION.get_key(strategy_id=0)
        client = key.SERVICE_LOCK_PREPARATION.client
        ret = client.set(service_key, time.time(), ex=key.SERVICE_LOCK_PREPARATION.ttl, nx=True)
        if not ret:
            logger.info("[preparation] skip for not leader")
            time.sleep(1)
            return

        logger.info("[preparation] get leader now")
        strategy_ids = StrategyCacheManager.get_strategy_ids()
        processor = TsDependPreparationProcess()
        for strategy_id in strategy_ids:
            strategy = Strategy(strategy_id)

            # 跳过非时序的监控策略
            if strategy.config["metric_type"] != DataTypeLabel.TIME_SERIES:
                continue

            query_config = strategy.config["items"][0]["query_configs"][0]

            # 只有使用SDK进行检测的智能监控策略才进行历史依赖数据的初始化
            if query_config.get("intelligent_detect") and query_config["intelligent_detect"].get("use_sdk", False):
                # 历史依赖准备就绪才开始检测
                if query_config["intelligent_detect"]["status"] == SDKDetectStatus.PREPARING:
                    processor.init_strategy_depend_data(strategy)
                    query_config = QueryConfig.from_models(QueryConfigModel.objects.filter(id=query_config["id"]))[0]
                    query_config.intelligent_detect["status"] = SDKDetectStatus.READY
                    query_config.save()
                    StrategyCacheManager.refresh_strategy_ids([{"id": strategy_id}])
