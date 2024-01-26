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

import json
import logging
import time

from django.conf import settings

from alarm_backends.core.cache import key
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.i18n import i18n
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.core.processor.base import BaseAbnormalPushProcessor
from alarm_backends.service.detect import DataPoint
from core.prometheus import metrics

logger = logging.getLogger("detect")


class DetectProcess(BaseAbnormalPushProcessor):
    def __init__(self, strategy_id: str):
        # note: 这里有个坑，进来的策略id是字符串
        self.strategy_id = strategy_id
        self.inputs = {}
        self.outputs = {}
        self.strategy = Strategy(strategy_id)
        i18n.set_biz(self.strategy.bk_biz_id)
        self.is_busy = False

    def pull_data(self, item, inputs=None):
        """
        :return: [datapoint, …]
        {
            "record_id":"f7659f5811a0e187c71d119c7d625f23",
            "value":1.38,
            "values":{
                "timestamp":1569246480,
                "load5":1.38
            },
            "dimensions":{
                "ip":"127.0.0.1"
            },
            "time":1569246480
        }
        """
        self.inputs[item.id] = []
        if inputs is not None:
            self.inputs[item.id].extend(inputs)
            return
        # pull data
        data_channel = key.DATA_LIST_KEY.get_key(strategy_id=self.strategy_id, item_id=item.id)
        client = key.DATA_LIST_KEY.client

        total_points = client.llen(data_channel)
        assert settings.SQL_MAX_LIMIT > 0, "SQL_MAX_LIMIT should bigger than zero"
        offset = min([total_points, settings.SQL_MAX_LIMIT])
        if offset == 0:
            logger.info("[detect] strategy({}) item({}) 暂无待检测数据".format(self.strategy_id, item.id))
            return
        if offset == settings.SQL_MAX_LIMIT:
            self.is_busy = True
            logger.error(
                "[detect] strategy({}) item({}) 待检测数据量达到配置值"
                "(SQL_MAX_LIMIT){}，部分数据可能存在处理延时".format(self.strategy_id, item.id, settings.SQL_MAX_LIMIT)
            )

        records = client.lrange(data_channel, -offset, -1)

        # 上报detect拉取数据量
        metrics.DETECT_PROCESS_DATA_COUNT.labels(strategy_id=metrics.TOTAL_TAG, type="pull").inc(len(records))

        unexpected_record_count = 0
        last_unexpected_record = None
        if records:
            client.ltrim(data_channel, 0, -offset - 1)
            # 队列左进右出，lrange 取出时需要做一次倒序才能保证先进先出
            for record in reversed(records):
                try:
                    data_point = DataPoint(json.loads(record), item)
                    # fill data point into inputs list
                    self.inputs[item.id].append(data_point)
                except ValueError:
                    unexpected_record_count += 1
                    last_unexpected_record = record
            if unexpected_record_count > 0:
                logger.error(
                    "[detect] strategy({}) item({}) 发现非期望格式的待检测数据{}条,"
                    " 其中之一: {}".format(self.strategy_id, item.id, unexpected_record_count, last_unexpected_record)
                )

            logger.info(
                "[detect] strategy({}) item({}) 拉取数据({})条".format(self.strategy_id, item.id, len(self.inputs[item.id]))
            )

    def handle_data(self, item):
        # detect data
        data_points = self.inputs[item.id]
        self.outputs[item.id] = item.detect(data_points)

    def push_data(self):
        current_time = time.time()
        for data_points in self.outputs.values():
            for data_point in data_points:
                if not data_point["data"].get("access_time"):
                    # 拿不到上一级记录的时间，忽略
                    continue
                latency = current_time - data_point["data"]["access_time"]
                data_point["data"]["detect_time"] = current_time
                if latency > 0:
                    metrics.DETECT_PROCESS_LATENCY.labels(strategy_id=metrics.TOTAL_TAG).observe(latency)
        anomaly_count = self.push_abnormal_data(self.outputs, self.strategy_id)
        if any(self.inputs.values()):
            logger.info("[detect] strategy({}) 异常检测完成: 异常记录数({})".format(self.strategy_id, anomaly_count))
            metrics.DETECT_PROCESS_DATA_COUNT.labels(strategy_id=metrics.TOTAL_TAG, type="push").inc(anomaly_count)

    def double_check(self, item):
        """二次确认"""
        # 当不存在异常时跳过二次确认
        if not self.outputs[item.id]:
            return
        # 灰度入口提前（不再放到二次确认代码逻辑中）
        # 基于性能考虑，先将逻辑设置为：没配置灰度，则不开启二次确认。
        # 后续优化性能后，考虑默认开启全量二次确认。
        if int(self.strategy_id) not in settings.DOUBLE_CHECK_SUM_STRATEGY_IDS:
            return
        logger.info("[detect] strategy({}) item({}) 开始异常二次确认流程".format(self.strategy_id, item.id))
        item.double_check(outputs=self.outputs[item.id])

    def process(self):
        with service_lock(key.SERVICE_LOCK_DETECT, strategy_id=self.strategy_id):
            start_at = time.time()
            logger.info(f"[detect][latency] strategy({self.strategy_id}) processing start")
            self.strategy.gen_strategy_snapshot()
            for item in self.strategy.items:
                self.pull_data(item)
                self.handle_data(item)
                try:
                    self.double_check(item)
                except Exception:
                    logger.exception("[detect] strategy(%s) 二次确认时发生异常，不影响告警主流程", self.strategy_id)

            self.push_data()
            end_at = time.time()
            logger.info(
                "[detect][latency] strategy({}) processing end in {}".format(self.strategy_id, end_at - start_at)
            )
            metrics.DETECT_PROCESS_TIME.labels(strategy_id=metrics.TOTAL_TAG).observe(end_at - start_at)
