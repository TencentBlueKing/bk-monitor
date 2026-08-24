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
from itertools import chain

from django.conf import settings

from alarm_backends.core.alert.adapter import MonitorEventAdapter
from alarm_backends.core.cache import key as cache_key
from alarm_backends.core.cache.key import ANOMALY_LIST_KEY, ANOMALY_SIGNAL_KEY, TRIGGER_EVENT_RATE_LIMIT_KEY
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.storage.redis_cluster import get_node_by_strategy_id, routing_snapshot
from alarm_backends.service.trigger.checker import AnomalyChecker
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from core.errors.alarm_backends import StrategyNotFound
from core.prometheus import metrics

# 每个（策略, 数据时间戳）计数器的最大 event 数，超过则丢弃
TRIGGER_EVENT_RATE_LIMIT_THRESHOLD = 5000
ALARMD_REFERENCE_BATCHES_PER_FLUSH = 500

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
        self.reference_candidates = []
        # 策略快照数据
        self._strategy_snapshots = {}
        self._strategy_snapshot_legacy_json = {}
        self._alarmd_reference_eligibility = {}
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

    def get_strategy_snapshot_legacy_json(self, snapshot_key):
        """Read and cache the exact legacy strategy document used by this Trigger point."""

        try:
            return self._strategy_snapshot_legacy_json[snapshot_key]
        except KeyError:
            routed_snapshot_key = cache_key.SimilarStr(snapshot_key)
            routed_snapshot_key.strategy_id = self.strategy_id
            legacy_json = cache_key.STRATEGY_SNAPSHOT_KEY.client.get(routed_snapshot_key)
            if isinstance(legacy_json, str):
                legacy_json = legacy_json.encode("utf-8")
            if not isinstance(legacy_json, bytes) or not legacy_json:
                raise StrategyNotFound({"key": snapshot_key})
            self._strategy_snapshot_legacy_json[snapshot_key] = legacy_json
            return legacy_json

    def is_alarmd_reference_selected(self, *, strategy, strategy_snapshot_key):
        from alarm_backends.core.alarmd.config import shadow_flag

        if not shadow_flag(settings.ALARMD_DETECTION_SHADOW_ENABLED):
            return False
        if not shadow_flag(settings.ALARMD_TRIGGER_REFERENCE_SHADOW_ENABLED):
            return False
        try:
            if self.strategy_id in settings.DOUBLE_CHECK_SUM_STRATEGY_IDS:
                return False
        except TypeError:
            return False

        if strategy_snapshot_key in self._alarmd_reference_eligibility:
            return self._alarmd_reference_eligibility[strategy_snapshot_key]

        from alarm_backends.core.alarmd.contract import (
            ContractValidationError,
            build_trigger_strategy_ir_from_legacy_config,
        )

        try:
            build_trigger_strategy_ir_from_legacy_config(
                tenant_id=bk_biz_id_to_bk_tenant_id(strategy["bk_biz_id"]),
                purpose="DETECT",
                strategy=strategy,
                item_id=self.item_id,
                legacy_json=self.get_strategy_snapshot_legacy_json(strategy_snapshot_key),
            )
        except ContractValidationError as error:
            logger.info(
                "[alarmd shadow] component=alarmd-python stage=reference result=skipped "
                "operation=eligibility records=0 strategy(%s) item(%s) reason=%s",
                self.strategy_id,
                self.item_id,
                error,
            )
            selected = False
        except Exception:
            logger.exception(
                "[alarmd shadow] component=alarmd-python stage=reference result=fail_open "
                "operation=eligibility records=0 strategy(%s) item(%s)",
                self.strategy_id,
                self.item_id,
            )
            selected = False
        else:
            selected = True

        self._alarmd_reference_eligibility[strategy_snapshot_key] = selected
        return selected

    def capture_alarmd_reference_candidate(self, *, point, event_record):
        try:
            self.reference_candidates.append(
                {
                    "strategy_snapshot_key": point["strategy_snapshot_key"],
                    "point": point,
                    "event_record": event_record,
                }
            )
        except Exception:
            logger.exception(
                "[alarmd shadow] failed to capture Trigger reference candidate for strategy(%s) item(%s)",
                self.strategy_id,
                self.item_id,
            )

    def publish_alarmd_reference_candidates(self):
        if not self.reference_candidates:
            return 0

        from alarm_backends.core.alarmd.config import shadow_kafka_config, shadow_topics
        from alarm_backends.core.alarmd.reference import build_reference_trigger_decision_candidate
        from alarm_backends.core.alarmd.reference_publisher import (
            ReferenceDecisionPublishError,
            get_cached_kafka_reference_decision_publisher,
        )
        from alarm_backends.core.alarmd.telemetry import (
            STAGE_REFERENCE,
            observe_shadow_publish,
            record_shadow_published_records,
        )

        publisher = None
        published = 0
        for start in range(0, len(self.reference_candidates), ALARMD_REFERENCE_BATCHES_PER_FLUSH):
            started_at = time.monotonic()
            projected_batches = 0

            def iter_batches():
                nonlocal projected_batches
                for candidate in self.reference_candidates[start : start + ALARMD_REFERENCE_BATCHES_PER_FLUSH]:
                    try:
                        strategy_snapshot_key = candidate["strategy_snapshot_key"]
                        batch = build_reference_trigger_decision_candidate(
                            strategy=self.get_strategy_snapshot(strategy_snapshot_key),
                            legacy_json=self.get_strategy_snapshot_legacy_json(strategy_snapshot_key),
                            strategy_snapshot_key=strategy_snapshot_key,
                            tenant_id_resolver=bk_biz_id_to_bk_tenant_id,
                            item_id=self.item_id,
                            point=candidate["point"],
                            event_record=candidate["event_record"],
                        )
                        projected_batches += 1
                        yield batch
                    except Exception:
                        logger.exception(
                            "[alarmd shadow] failed to project Trigger reference for strategy(%s) item(%s)",
                            self.strategy_id,
                            self.item_id,
                        )

            batches = iter_batches()
            try:
                first_batch = next(batches)
            except StopIteration:
                continue
            if publisher is None:
                try:
                    config_json = json.dumps(
                        shadow_kafka_config(settings.ALARMD_TRIGGER_REFERENCE_SHADOW_KAFKA_CONFIG),
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    allowed_topics = shadow_topics(settings.ALARMD_TRIGGER_REFERENCE_SHADOW_ALLOWED_TOPICS)
                    forbidden_topics = tuple(
                        sorted(
                            set(shadow_topics(settings.ALARMD_DETECTION_SHADOW_ALLOWED_TOPICS))
                            | {MonitorEventAdapter.get_output_topic()}
                        )
                    )
                    publisher = get_cached_kafka_reference_decision_publisher(
                        config_json,
                        allowed_topics,
                        forbidden_topics,
                    )
                except Exception:
                    logger.exception("[alarmd shadow] failed to initialize Trigger reference publisher")
                    break
            try:
                with observe_shadow_publish(STAGE_REFERENCE):
                    acknowledged = publisher.publish_batches(chain((first_batch,), batches))
                record_shadow_published_records(STAGE_REFERENCE, acknowledged)
                duration_ms = max(0, round((time.monotonic() - started_at) * 1000))
                batch_id = first_batch.get("batch_id", "unknown") if projected_batches == 1 else "mixed"
                logger.info(
                    "[alarmd shadow] component=alarmd-python stage=reference result=broker_ack "
                    "records=%s duration_ms=%s strategy(%s) batch_id=%s",
                    acknowledged,
                    duration_ms,
                    self.strategy_id,
                    batch_id,
                )
                published += acknowledged
            except Exception as error:
                duration_ms = max(0, round((time.monotonic() - started_at) * 1000))
                acknowledged = error.acknowledged_records if isinstance(error, ReferenceDecisionPublishError) else 0
                batch_id = first_batch.get("batch_id", "unknown") if projected_batches == 1 else "mixed"
                logger.exception(
                    "[alarmd shadow] component=alarmd-python stage=reference result=fail_open "
                    "operation=broker_publish records=%s duration_ms=%s strategy(%s) item(%s) batch_id=%s",
                    acknowledged,
                    duration_ms,
                    self.strategy_id,
                    self.item_id,
                    batch_id,
                )
                break
        return published

    def pull(self):
        # lrange + ltrim 必须落在同一路由快照：列表长度依赖首读结果，无法无脑打进一个 pipeline，
        # 用 routing_snapshot 避免 TTL 边界把读/裁切拆到不同 Redis 节点。
        with routing_snapshot():
            self.anomaly_points = ANOMALY_LIST_KEY.client.lrange(self.anomaly_list_key, -self.MAX_PROCESS_COUNT, -1)
            # 对列表做翻转，按数据从旧到新的顺序处理
            self.anomaly_points.reverse()
            if self.anomaly_points:
                metrics.TRIGGER_PROCESS_PULL_DATA_COUNT.labels(strategy_id=metrics.TOTAL_TAG).inc(
                    len(self.anomaly_points)
                )
                ANOMALY_LIST_KEY.client.ltrim(self.anomaly_list_key, 0, -len(self.anomaly_points) - 1)
        if self.anomaly_points:
            if len(self.anomaly_points) == self.MAX_PROCESS_COUNT:
                # 拉取到的数量若等于最大数量，说明还没拉取完，下次需要再次拉取处理
                signal_key = f"{self.strategy_id}.{self.item_id}"
                ANOMALY_SIGNAL_KEY.client.delay("rpush", ANOMALY_SIGNAL_KEY.get_key(), signal_key, delay=1)
                logger.info(
                    f"[pull anomaly record] strategy({self.strategy_id}), item({self.item_id}) "
                    f"pull {len(self.anomaly_points)} record."
                    "queue has data, process next time"
                )
            else:
                logger.info(
                    f"[pull anomaly record] strategy({self.strategy_id}), item({self.item_id}) "
                    f"pull {len(self.anomaly_points)} record"
                )
        else:
            logger.warning(
                f"[pull anomaly record] strategy({self.strategy_id}), item({self.item_id}) "
                f"pull {len(self.anomaly_points)} record"
            )
        return len(self.anomaly_points)

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

        try:
            self.publish_alarmd_reference_candidates()
        except Exception:
            logger.exception(
                "[alarmd shadow] unexpected Trigger reference failure for strategy(%s) item(%s)",
                self.strategy_id,
                self.item_id,
            )

        self.anomaly_points = []
        self.anomaly_records = []
        self.event_records = []
        self.reference_candidates = []

    def process(self):
        pulled_count = self.pull()

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
        return pulled_count

    def process_point(self, point):
        point = json.loads(point)
        strategy = self.get_strategy_snapshot(point["strategy_snapshot_key"])
        checker = AnomalyChecker(point, strategy, self.item_id)
        anomaly_records, event_record = checker.check()

        if not checker.is_no_data_point(point) and self.is_alarmd_reference_selected(
            strategy=strategy,
            strategy_snapshot_key=point["strategy_snapshot_key"],
        ):
            self.capture_alarmd_reference_candidate(
                point=point,
                event_record=event_record,
            )

        # 暂存结果，最后批量保存
        if event_record:
            self.event_records.append({"anomaly_records": anomaly_records, "event_record": event_record})
        else:
            self.anomaly_records.extend(anomaly_records)
