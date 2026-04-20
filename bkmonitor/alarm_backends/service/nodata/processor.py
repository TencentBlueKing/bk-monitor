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


import json
import logging

import arrow

from alarm_backends.constants import LATEST_NO_DATA_CHECK_POINT
from alarm_backends.core.cache import key
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.i18n import i18n
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.core.processor.base import BaseAbnormalPushProcessor
from alarm_backends.service.access.data.token import TokenBucket
from alarm_backends.service.detect import DataPoint
from core.prometheus import metrics

logger = logging.getLogger("nodata")


class CheckProcessor(BaseAbnormalPushProcessor):
    def __init__(self, strategy_id):
        self.strategy_id = strategy_id
        self.inputs = {}
        self.outputs = {}
        self.strategy = Strategy(strategy_id)
        i18n.set_biz(self.strategy.bk_biz_id)

    def pull_data(self, item, check_timestamp, inputs=None):
        """
        :
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
            # for debug
            self.inputs[item.id].extend(inputs)
            return
        # pull data
        data_channel = key.NO_DATA_LIST_KEY.get_key(strategy_id=self.strategy_id, item_id=item.id)
        client = key.NO_DATA_LIST_KEY.client

        total_points = client.llen(data_channel)
        if total_points == 0:
            logger.info(
                "[nodata] strategy({}) item({}) check_timestamp({}) 无待检测数据，可能触发无数据告警".format(
                    self.strategy_id, item.id, check_timestamp
                )
            )
            return

        records = client.lrange(data_channel, -total_points, -1)
        metrics.NODATA_PROCESS_PULL_DATA_COUNT.labels(strategy_id=metrics.TOTAL_TAG).inc(len(records))

        unexpected_record_count = 0
        last_unexpected_record = None
        if records:
            client.ltrim(data_channel, 0, -total_points - 1)
            logger.info(
                "[nodata] strategy({}) item({}) check_timestamp({}) pull records({})".format(
                    self.strategy_id, item.id, check_timestamp, total_points
                )
            )
            future_records = []
            for record in records:
                try:
                    data_point = DataPoint(json.loads(record), item)
                    if data_point.timestamp <= check_timestamp:
                        self.inputs[item.id].append(data_point)
                    else:
                        future_records.append(record)
                except ValueError:
                    unexpected_record_count += 1
                    last_unexpected_record = record

            # 如果当前监测点之前无数据，但是未来有数据，那么取未来一个周期的数据
            if not self.inputs[item.id] and future_records:
                record = future_records[0]
                data_point = DataPoint(json.loads(record), item)
                earliest_future_timestamp = data_point.timestamp
                earliest_future_points = [data_point]
                earliest_future_records_idx = [0]
                for index, record in enumerate(future_records[1:]):
                    data_point = DataPoint(json.loads(record), item)
                    # 遇到更早时间数据，重置 earliest_future_points 和 earliest_future_records_idx
                    if data_point.timestamp < earliest_future_timestamp:
                        earliest_future_timestamp = data_point.timestamp
                        earliest_future_points = [data_point]
                        earliest_future_records_idx = [index + 1]
                    # 遇到和当前最早时间一致的数据，加入 earliest_future_points 和 earliest_future_records_idx
                    elif data_point.timestamp == earliest_future_timestamp:
                        earliest_future_points.append(data_point)
                        earliest_future_records_idx.append(index + 1)

                self.inputs[item.id] = earliest_future_points
                future_records = [
                    record for index, record in enumerate(future_records) if index not in earliest_future_records_idx
                ]
                logger.info(
                    "[nodata] strategy({}) item({}) check_timestamp({}) get future_timestamp({}) {} records,"
                    "其中之一: {}".format(
                        self.strategy_id,
                        item.id,
                        check_timestamp,
                        earliest_future_timestamp,
                        len(earliest_future_records_idx),
                        data_point._raw_input,
                    )
                )

            # 当前检测周期之后的数据或者未来周期非最早时间的数据，重新放入队列等待后续检测
            if future_records:
                client.rpush(data_channel, *future_records)
            if unexpected_record_count > 0:
                logger.error(
                    "[nodata] strategy({}) item({}) check_timestamp({}) 发现非期望格式的待检测数据{}条,"
                    "其中之一: {}".format(
                        self.strategy_id, item.id, check_timestamp, unexpected_record_count, last_unexpected_record
                    )
                )

            logger.info(
                "[nodata] strategy({}) item({}) check_timestamp({}) 拉取数据({})条".format(
                    self.strategy_id, item.id, check_timestamp, len(self.inputs[item.id])
                )
            )

    def handle_data(self, item, check_timestamp):
        # check no data
        data_points = self.inputs[item.id]
        self.outputs[item.id] = item.check(data_points, check_timestamp)

    def push_data(self):
        """
        推送无数据异常点至缓存队列
        :return:
        """
        anomaly_signal_list = []
        anomaly_count = self.push_abnormal_data(self.outputs, self.strategy_id, anomaly_signal_list)
        metrics.NODATA_PROCESS_PUSH_DATA_COUNT.labels(strategy_id=metrics.TOTAL_TAG).inc(len(anomaly_signal_list))
        if any(self.inputs.values()):
            logger.info("[nodata] strategy({}) 无数据检测完成: 无数据异常记录数({})".format(self.strategy_id, anomaly_count))

    def process(self, now_timestamp):
        with service_lock(key.SERVICE_LOCK_NODATA, strategy_id=self.strategy_id):
            self.strategy.gen_strategy_snapshot()

            for item in self.strategy.items:
                last_checkpoint_cache_key = key.LAST_CHECKPOINTS_CACHE_KEY.get_key(
                    strategy_id=self.strategy_id,
                    item_id=item.id,
                )
                group_key = item.item_config.get("query_md5")
                # 处于流控的策略不进行无数据告警检测。
                if group_key and not TokenBucket(group_key).acquire():
                    logger.info(
                        "[nodata] strategy({}) item({}) skipped, because {} token is not available".format(
                            self.strategy_id, item.id, group_key
                        )
                    )
                    continue

                if item.no_data_config.get("is_enabled"):
                    # 由于存在access_data入库延时问题，所以后台检测往前推一个周期
                    # TODO：多指标下周期的计算
                    agg_interval = int(item.query_configs[0]["agg_interval"])
                    check_timestamp = (now_timestamp // agg_interval) * agg_interval - agg_interval
                    logger.info(
                        "[nodata] strategy({}) item({}) checkpoint({}) processing start".format(
                            self.strategy_id, item.id, check_timestamp
                        )
                    )

                    # 检测时间点已经检测过，直接跳过
                    last_checkpoint_cache_field = key.LAST_CHECKPOINTS_CACHE_KEY.get_field(
                        dimensions_md5=LATEST_NO_DATA_CHECK_POINT,
                        level=item.no_data_level,
                    )
                    last_point = key.LAST_CHECKPOINTS_CACHE_KEY.client.hget(
                        last_checkpoint_cache_key, last_checkpoint_cache_field
                    )

                    if (not last_point) or (int(last_point) < check_timestamp):
                        self.pull_data(item, check_timestamp)
                        # 队列已清空,立即写入去重标记,防止锁超时后secondary worker以空队列重复检测
                        key.LAST_CHECKPOINTS_CACHE_KEY.client.hset(
                            last_checkpoint_cache_key, last_checkpoint_cache_field, check_timestamp
                        )
                        self.handle_data(item, check_timestamp)
                        logger.info(
                            "[nodata] strategy({}) item({}) checkpoint({}) processing end at time({})".format(
                                self.strategy_id, item.id, check_timestamp, arrow.utcnow()
                            )
                        )
                    else:
                        logger.info(
                            "[nodata] strategy({}) item({}) checkpoint({}) processing skip at time({})".format(
                                self.strategy_id, item.id, check_timestamp, arrow.utcnow()
                            )
                        )
            self.push_data()
