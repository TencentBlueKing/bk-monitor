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
from alarm_backends.core.cache.key import ANOMALY_LIST_KEY, ANOMALY_SIGNAL_KEY, TRIGGER_EVENT_RATE_LIMIT_KEY
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.storage.redis_cluster import get_node_by_strategy_id
from alarm_backends.service.trigger.checker import AnomalyChecker
from core.errors.alarm_backends import StrategyNotFound
from core.prometheus import metrics

# 每个（策略, 数据时间戳）计数器的最大 event 数，超过则丢弃
TRIGGER_EVENT_RATE_LIMIT_THRESHOLD = 5000

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

    def _filter_by_rate_limit(self, event_records):
        """
        按（strategy_id, item_id, 数据时间戳）对本批 event_records 进行限流判定。

        key 含 item_id，与 trigger 执行锁粒度一致，保证同一 key 不存在并发写入。

        算法：
        1. 内存中按 source_time 分组，统计各时间戳的请求数。
        2. pipeline MGET 一次取各计数器的 Redis 已有值。
        3. 逐条判定：redis_count + 本批已通过数 >= 阈值时拒绝本条（fail-open 无时间戳）。

        注意：INCRBY 不在本方法内执行，由调用方在 Kafka 发送成功后统一提交，
              避免「先记账后投递」导致 Kafka 失败时额度被静默消耗。

        返回：(allowed_records, batch_counts, ts_keys, drop_counts)
          - allowed_records : 允许下发的记录列表
          - batch_counts    : {source_time: 本批通过数}，供发送后 INCRBY 使用
          - ts_keys         : {source_time: redis_key}
          - drop_counts     : {source_time: 丢弃数}，用于上报指标
        """
        client = TRIGGER_EVENT_RATE_LIMIT_KEY.client
        threshold = TRIGGER_EVENT_RATE_LIMIT_THRESHOLD

        # step1: 收集本批各时间戳的 Redis key
        ts_keys = {}  # source_time -> redis key
        for record in event_records:
            source_time = record["event_record"].get("data", {}).get("time")
            if source_time is None:
                continue
            source_time = int(source_time)
            if source_time not in ts_keys:
                ts_keys[source_time] = TRIGGER_EVENT_RATE_LIMIT_KEY.get_key(
                    strategy_id=self.strategy_id, item_id=self.item_id, source_time=source_time
                )

        if not ts_keys:
            return event_records, {}, {}, {}

        # step2: pipeline MGET 取 Redis 已有计数
        ordered_ts = list(ts_keys.keys())
        pipe = client.pipeline(transaction=False)
        for ts in ordered_ts:
            pipe.get(ts_keys[ts])
        try:
            redis_results = pipe.execute()
        except Exception as e:
            logger.warning("[trigger rate limit] redis MGET failed, fail-open. reason: %s", e)
            return event_records, {}, {}, {}

        redis_counts = {ts: int(val) if val is not None else 0 for ts, val in zip(ordered_ts, redis_results)}

        # step3: 内存逐条判定（不写 Redis）
        allowed_records = []
        batch_counts = {ts: 0 for ts in ordered_ts}
        drop_counts = {}

        for record in event_records:
            event_record = record["event_record"]
            event_data = event_record.get("data", {})
            source_time = event_data.get("time")
            if source_time is None:
                allowed_records.append(record)
                continue
            source_time = int(source_time)
            already = redis_counts[source_time] + batch_counts[source_time]
            if already >= threshold:
                drop_counts[source_time] = drop_counts.get(source_time, 0) + 1
                logger.warning(
                    "[trigger rate limit] drop event: strategy(%s) item(%s) source_time(%s) "
                    "record_id(%s) dimensions(%s) count(%s) threshold(%s)",
                    self.strategy_id,
                    self.item_id,
                    source_time,
                    event_data.get("record_id"),
                    event_data.get("dimensions"),
                    already + 1,
                    threshold,
                )
            else:
                batch_counts[source_time] += 1
                allowed_records.append(record)

        return allowed_records, batch_counts, ts_keys, drop_counts

    def _commit_rate_limit_counts(self, batch_counts, ts_keys):
        """Kafka 发送成功后，将本批通过数写入 Redis 计数器（每个 ts 至多一次 INCRBY）。"""
        if not any(cnt > 0 for cnt in batch_counts.values()):
            return
        client = TRIGGER_EVENT_RATE_LIMIT_KEY.client
        pipe = client.pipeline(transaction=False)
        for ts, cnt in batch_counts.items():
            if cnt > 0:
                pipe.incrby(ts_keys[ts], cnt)
                pipe.expire(ts_keys[ts], TRIGGER_EVENT_RATE_LIMIT_KEY.ttl)
        try:
            pipe.execute()
        except Exception as e:
            logger.warning("[trigger rate limit] redis INCRBY failed. reason: %s", e)

    def push_event_to_kafka(self, event_records):
        try:
            cache_node = get_node_by_strategy_id(self.strategy_id)
            redis_node = cache_node.node_alias or f"{cache_node.host}:{cache_node.port}"
        except Exception:
            redis_node = "unknown"

        # step1: 限流判定（只读 Redis，不写）
        allowed_records, batch_counts, ts_keys, drop_counts = self._filter_by_rate_limit(event_records)
        total_drop = sum(drop_counts.values())
        if total_drop > 0:
            metrics.TRIGGER_EVENT_RATE_LIMIT_DROP.labels(
                module="trigger",
                strategy_id=self.strategy_id,
                bk_biz_id=self.strategy.bk_biz_id,
                strategy_name=self.strategy.name,
                redis_node=redis_node,
            ).inc(total_drop)

        # step2: 构建 Kafka 消息
        events = []
        current_time = time.time()
        max_latency = 0
        for record in allowed_records:
            event_record = record["event_record"]
            detect_time = event_record.get("data", {}).get("detect_time")
            if detect_time:
                latency = current_time - detect_time
                if latency > max_latency:
                    max_latency = latency
            adapter = MonitorEventAdapter(
                record=event_record,
                strategy=self.get_strategy_snapshot(event_record["strategy_snapshot_key"]),
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

        # step3: 发送到 Kafka；成功后再提交计数，避免失败时额度被静默消耗
        MonitorEventAdapter.push_to_kafka(events=events)
        self._commit_rate_limit_counts(batch_counts, ts_keys)

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
