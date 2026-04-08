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
import time

from alarm_backends.core.alert.adapter import MonitorEventAdapter
from alarm_backends.core.cache.key import ANOMALY_LIST_KEY, ANOMALY_SIGNAL_KEY
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.storage.redis_cluster import get_node_by_strategy_id
from alarm_backends.service.trigger.checker import AnomalyChecker
from core.errors.alarm_backends import StrategyNotFound
from core.prometheus import metrics

logger = logging.getLogger("trigger")


class TriggerProcessor:
    # 单次处理量(默认为全量处理)
    MAX_PROCESS_COUNT = 0

    def __init__(self, strategy_id, item_id):
        self.strategy_id = int(strategy_id)
        self.item_id = int(item_id)
        self.anomaly_list_key = ANOMALY_LIST_KEY.get_key(strategy_id=self.strategy_id, item_id=self.item_id)
        self.anomaly_points = []
        self.anomaly_records = []
        self.event_records = []
        # 策略快照数据
        self._strategy_snapshots = {}
        self.strategy = Strategy(self.strategy_id)

    def get_strategy_snapshot(self, key):
        """
        获取配置快照
        """
        try:
            # 查询对应的key快照是否存在
            return self._strategy_snapshots[key]
        except KeyError:
            # 如果查不到内存快照，则查询redis
            snapshot = Strategy.get_strategy_snapshot_by_key(key, self.strategy_id)
            if not snapshot:
                raise StrategyNotFound({"key": key})
            self._strategy_snapshots[key] = snapshot
            return snapshot

    def pull(self):
        self.anomaly_points = ANOMALY_LIST_KEY.client.lrange(self.anomaly_list_key, -self.MAX_PROCESS_COUNT, -1)
        # 对列表做翻转，按数据从旧到新的顺序处理
        self.anomaly_points.reverse()
        if self.anomaly_points:
            metrics.TRIGGER_PROCESS_PULL_DATA_COUNT.labels(strategy_id=metrics.TOTAL_TAG).inc(len(self.anomaly_points))
            ANOMALY_LIST_KEY.client.ltrim(self.anomaly_list_key, 0, -len(self.anomaly_points) - 1)
            if len(self.anomaly_points) == self.MAX_PROCESS_COUNT:
                # 拉取到的数量若等于最大数量，说明还没拉取完，下次需要再次拉取处理
                signal_key = f"{self.strategy_id}.{self.item_id}"
                ANOMALY_SIGNAL_KEY.client.delay("rpush", ANOMALY_SIGNAL_KEY.get_key(), signal_key, delay=1)
                logger.info(
                    f"[pull anomaly record] strategy({self.strategy_id}), item({self.item_id}) pull {len(self.anomaly_points)} record."
                    "queue has data, process next time"
                )
            else:
                logger.info(
                    f"[pull anomaly record] strategy({self.strategy_id}), item({self.item_id}) pull {len(self.anomaly_points)} record"
                )
        else:
            logger.warning(
                f"[pull anomaly record] strategy({self.strategy_id}), item({self.item_id}) pull {len(self.anomaly_points)} record"
            )

    def push_event_to_kafka(self, event_records):
        events = []
        current_time = time.time()
        max_latency = 0
        for record in event_records:
            event_record = record["event_record"]
            detect_time = event_record.get("data", {}).get("detect_time")
            if detect_time:
                latency = current_time - event_record["data"]["detect_time"]
                if latency > max_latency:
                    max_latency = latency

            adapter = MonitorEventAdapter(
                record=record["event_record"],
                strategy=self.get_strategy_snapshot(record["event_record"]["strategy_snapshot_key"]),
            )
            events.append(adapter.adapt())
        metrics.TRIGGER_PROCESS_LATENCY.labels(strategy_id=metrics.TOTAL_TAG).observe(max_latency)

        if max_latency > 60:
            # 如果当前的处理延迟大于1min, 打印一行日志出来(一批次打印一条即可)
            logger.warning(
                "[detect to trigger]big latency %s,  strategy(%s)",
                max_latency,
                self.strategy_id,
            )
            metrics.PROCESS_BIG_LATENCY.labels(
                strategy_id=self.strategy_id,
                module="detect_trigger",
                bk_biz_id=self.strategy.bk_biz_id,
                strategy_name=self.strategy.name,
            ).observe(max_latency)
        MonitorEventAdapter.push_to_kafka(events=events)

        if len(events) > 1000:
            # 获取 Redis 节点信息（带异常处理）
            try:
                cache_node = get_node_by_strategy_id(self.strategy_id)
                redis_node = cache_node.node_alias or f"{cache_node.host}:{cache_node.port}"
            except Exception:
                redis_node = "unknown"  # 异常情况下使用默认值

            metrics.PROCESS_OVER_FLOW.labels(
                module="trigger",
                strategy_id=self.strategy_id,
                bk_biz_id=self.strategy.bk_biz_id,
                strategy_name=self.strategy.name,
                redis_node=redis_node,
            ).inc(len(events))

    def push(self):
        # 推送事件记录到输出队列
        if self.event_records:
            self.push_event_to_kafka(self.event_records)
            logger.info(
                f"[process result collect] strategy({self.strategy_id}), item({self.item_id}) finish."
                f"push {len(self.anomaly_records)} AnomalyRecord, {len(self.event_records)} Event"
            )
            metrics.TRIGGER_PROCESS_PUSH_DATA_COUNT.labels(strategy_id=metrics.TOTAL_TAG).inc(len(self.event_records))

        self.anomaly_points = []
        self.anomaly_records = []
        self.event_records = []

    def process(self):
        self.pull()

        in_alarm_time, message = self.strategy.in_alarm_time()
        if not in_alarm_time:
            logger.info("[trigger] strategy(%s) not in alarm time: %s, skipped", self.strategy_id, message)
        else:
            for point in self.anomaly_points:
                try:
                    self.process_point(point)
                except Exception as e:
                    error_message = f"[process error] strategy({self.strategy_id}), item({self.item_id}) reason: {e} \norigin data: {point}"
                    logger.exception(error_message)

        self.push()

    def process_point(self, point):
        point = json.loads(point)
        strategy = self.get_strategy_snapshot(point["strategy_snapshot_key"])
        checker = AnomalyChecker(point, strategy, self.item_id)
        anomaly_records, event_record = checker.check()

        # 暂存结果，最后批量保存
        if event_record:
            self.event_records.append({"anomaly_records": anomaly_records, "event_record": event_record})
        else:
            self.anomaly_records.extend(anomaly_records)
