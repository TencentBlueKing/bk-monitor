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

from django.core.cache import caches

from alarm_backends.core.cache import key
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.handlers import base
from alarm_backends.service.detect.tasks import run_detect, run_detect_with_sdk

logger = logging.getLogger("detect")
mem_cache = caches["locmem"]


class DetectHandler(base.BaseHandler):
    def __init__(self):
        super(DetectHandler, self).__init__()
        self.client = key.DATA_SIGNAL_KEY.client
        self.data_signal_key = key.DATA_SIGNAL_KEY.get_key()

    def handle(self):
        ret = self.client.brpop(self.data_signal_key, 5)
        if ret is None:
            logger.debug("未拉取到待处理的策略项")
            return

        run_detect(ret[1])


class DetectCeleryHandler(DetectHandler):
    max_input_count = 100

    def handle(self):
        strategy_ids = set()
        while len(strategy_ids) <= self.max_input_count:
            strategy_id = self.client.rpop(self.data_signal_key)
            if strategy_id is None:
                # 当前队列无待处理数据
                if len(strategy_ids) > 0:
                    # 已经拉到部分, 直接开始处理
                    break
                else:
                    # 阻塞等待新数据
                    ret = self.client.brpop(self.data_signal_key, 5)
                    if ret:
                        strategy_id = ret[1]

            if strategy_id:
                strategy_ids.add(strategy_id)
                continue

            break

        aiops_strategy_ids = set()
        # 根据策略检测算法及是否启用sdk检测，决定推送不同的处理队列
        for strategy_id in strategy_ids:
            if self.use_aiops_sdk(strategy_id):
                run_detect_with_sdk.apply_async(args=(strategy_id,))
                aiops_strategy_ids.add(strategy_id)
                continue
            run_detect.apply_async(args=(strategy_id,))

        logger.info("[detect] total published {} strategy_ids: {}".format(len(strategy_ids), strategy_ids))
        if aiops_strategy_ids:
            logger.info("[detect] published aiops_strategy_ids: {}".format(aiops_strategy_ids))

    @classmethod
    def use_aiops_sdk(cls, strategy_id):
        # 内存
        use_api_sdk = mem_cache.get(str(strategy_id))
        if use_api_sdk is None:
            # 内存过期或没命中，从redis获取
            strategy = Strategy(strategy_id)
            use_api_sdk = strategy.use_api_sdk
            # 10分钟缓存
            mem_cache.set(str(strategy_id), use_api_sdk, 10 * 60)
        return use_api_sdk
