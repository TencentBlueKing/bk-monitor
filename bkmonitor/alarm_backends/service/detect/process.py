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
import uuid

from django.conf import settings

from alarm_backends.core.cache import key
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.i18n import i18n
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.core.processor.base import BaseAbnormalPushProcessor
from alarm_backends.core.storage.redis_cluster import get_node_by_strategy_id
from alarm_backends.service.detect import DataPoint
from core.prometheus import metrics

logger = logging.getLogger("detect")


def publish_alarmd_detect_shadow_batches(batches):
    return DetectProcess.publish_alarmd_detection_batches(batches)


class DetectProcess(BaseAbnormalPushProcessor):
    def __init__(self, strategy_id: str):
        # note: 这里有个坑，进来的策略id是字符串
        self.strategy_id = strategy_id
        self.inputs = {}
        self.outputs = {}
        self.inline_trigger_items = []
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
            logger.info(f"[detect] strategy({self.strategy_id}) item({item.id}) 暂无待检测数据")
            return
        if offset == settings.SQL_MAX_LIMIT:
            self.is_busy = True
            logger.error(
                f"[detect] strategy({self.strategy_id}) item({item.id}) 待检测数据量达到配置值"
                f"(SQL_MAX_LIMIT){settings.SQL_MAX_LIMIT}，部分数据可能存在处理延时"
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
                    f"[detect] strategy({self.strategy_id}) item({item.id}) 发现非期望格式的待检测数据{unexpected_record_count}条,"
                    f" 其中之一: {last_unexpected_record}"
                )

            logger.info(
                f"[detect] strategy({self.strategy_id}) item({item.id}) 拉取数据({len(self.inputs[item.id])})条"
            )

    def handle_data(self, item):
        # detect data
        data_points = self.inputs[item.id]
        if not data_points:
            self.bootstrap_new_series_empty_batch(item)
        self.outputs[item.id] = item.detect(data_points)

    @staticmethod
    def bootstrap_new_series_empty_batch(item):
        from alarm_backends.service.detect.strategy.new_series import NewSeries

        NewSeries.bootstrap_empty_batch(item)

    def prepare_alarmd_detection_batches(self):
        from alarm_backends.core.alarmd.config import shadow_flag

        if not shadow_flag(settings.ALARMD_SHADOW_ENABLED):
            return []

        finalized = int(self.strategy_id) not in settings.DOUBLE_CHECK_SUM_STRATEGY_IDS
        if not finalized:
            return []

        legacy_json = key.STRATEGY_SNAPSHOT_KEY.client.get(self.strategy.snapshot_key)
        if isinstance(legacy_json, str):
            legacy_json = legacy_json.encode()
        if not isinstance(legacy_json, bytes) or not legacy_json:
            logger.warning(f"[alarmd shadow] strategy({self.strategy_id}) snapshot is unavailable")
            return []
        try:
            snapshot_strategy = json.loads(legacy_json)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning(
                "[alarmd shadow] component=alarmd-python stage=detection result=skipped "
                "operation=load_snapshot records=0 strategy(%s) reason=invalid_json",
                self.strategy_id,
            )
            return []

        from alarm_backends.core.alarmd.contract import ContractValidationError, json_values_equal
        from alarm_backends.core.alarmd.async_publish import shadow_job_fits
        from alarm_backends.core.alarmd.publisher import DetectionPublishError, plan_detect_input_microbatches
        from alarm_backends.core.alarmd.runtime import prepare_detect_input_batch, prepare_finalized_threshold_batch

        batch_id = uuid.uuid4().hex
        batches = []
        for item in self.strategy.items:
            input_points = self.inputs.get(item.id, [])
            if not input_points:
                continue
            source_strategy = input_points[0].item.strategy
            if (
                any(data_point.item.strategy is not source_strategy for data_point in input_points)
                or int(source_strategy.id) != int(self.strategy_id)
                or not json_values_equal(source_strategy.config, self.strategy.config)
            ):
                logger.warning(f"[alarmd shadow] strategy({self.strategy_id}) item({item.id}) input snapshot is stale")
                continue
            data_points = [data_point.as_dict() for data_point in input_points]
            if not data_points:
                continue
            try:
                batch = prepare_finalized_threshold_batch(
                    tenant_id=self.strategy.bk_tenant_id,
                    strategy=snapshot_strategy,
                    item_id=item.id,
                    legacy_json=legacy_json,
                    batch_id=batch_id,
                    data_points=data_points,
                    anomaly_outputs=self.outputs.get(item.id, []),
                    finalized=finalized,
                )
            except ContractValidationError as error:
                logger.info(
                    "[alarmd shadow] component=alarmd-python stage=detection result=skipped "
                    "operation=prepare records=%s strategy(%s) item(%s) batch_id=%s reason=%s",
                    len(data_points),
                    self.strategy_id,
                    item.id,
                    batch_id,
                    error,
                )
                continue
            try:
                ranges = plan_detect_input_microbatches(batch["strategy_ir"], batch_id, data_points)
                if len(batch["outcomes"]) != len(data_points):
                    raise ContractValidationError("detection outcomes must align with accepted records")
                pending_ranges = list(reversed(ranges))
                while pending_ranges:
                    start, end = pending_ranges.pop()
                    chunk = {
                        "strategy_ir": batch["strategy_ir"],
                        "outcomes": batch["outcomes"][start:end],
                        "detect_input": prepare_detect_input_batch(
                            strategy_ir=batch["strategy_ir"],
                            batch_id=batch_id,
                            data_points=data_points[start:end],
                        ),
                    }
                    if not shadow_job_fits("detect_input", (chunk,)):
                        if end - start <= 1:
                            raise DetectionPublishError("single detect input Shadow job exceeds the byte limit")
                        middle = start + (end - start) // 2
                        pending_ranges.extend(((middle, end), (start, middle)))
                        continue
                    batches.append(chunk)
            except (ContractValidationError, DetectionPublishError):
                logger.exception(
                    "[alarmd shadow] component=alarmd-python stage=detect_input result=fail_open "
                    "operation=prepare records=%s strategy(%s) batch_id=%s",
                    len(data_points),
                    self.strategy_id,
                    batch_id,
                )
        return batches

    @staticmethod
    def publish_alarmd_detection_batches(batches):
        if not batches:
            return 0

        from alarm_backends.core.alarmd.config import shadow_kafka_config, shadow_topics
        from alarm_backends.core.alarmd.publisher import get_cached_kafka_detect_input_publisher
        from alarm_backends.core.alarmd.publish_session import publish_post_detection_shadow
        from alarm_backends.core.alarmd.reference import build_terminal_reference_decision_batches
        from alarm_backends.core.alarmd.reference_publisher import (
            get_cached_kafka_reference_decision_publisher,
        )
        from alarm_backends.core.alarmd.telemetry import (
            STAGE_DETECT_INPUT,
            STAGE_REFERENCE,
            record_shadow_publish_result,
            record_shadow_published_records,
        )

        allowed_topics = shadow_topics(settings.ALARMD_DETECT_INPUT_SHADOW_ALLOWED_TOPICS)
        detect_input_publisher = None
        detect_input_initialization_failed = False
        reference_publisher = None
        reference_initialization_failed = False

        published = 0
        job_failed = False
        for batch in batches:
            outcomes = batch.get("outcomes") or []
            strategy_ref = (batch.get("strategy_ir") or {}).get("strategy_ref") or {}
            strategy_id = strategy_ref.get("strategy_id", "unknown")
            batch_id = outcomes[0].get("batch_id", "unknown") if outcomes else "unknown"
            detect_input = batch.get("detect_input")
            detect_input_for_publish = None
            if detect_input and not detect_input_initialization_failed:
                try:
                    if detect_input_publisher is None:
                        detect_input_config_json = json.dumps(
                            shadow_kafka_config(settings.ALARMD_DETECT_INPUT_SHADOW_KAFKA_CONFIG),
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        detect_input_allowed_topics = shadow_topics(settings.ALARMD_DETECT_INPUT_SHADOW_ALLOWED_TOPICS)
                        detect_input_publisher = get_cached_kafka_detect_input_publisher(
                            detect_input_config_json,
                            detect_input_allowed_topics,
                        )
                    detect_input_for_publish = detect_input
                except Exception:
                    detect_input_initialization_failed = detect_input_publisher is None
                    job_failed = True
                    logger.exception(
                        "[alarmd shadow] component=alarmd-python stage=detect_input result=fail_open "
                        "operation=initialize records=0 strategy(%s) batch_id=%s",
                        strategy_id,
                        batch_id,
                    )
            reference_batches = []
            try:
                reference_batches = build_terminal_reference_decision_batches(
                    strategy_ir=batch["strategy_ir"],
                    detection_outcomes=batch["outcomes"],
                )
            except Exception:
                logger.exception("[alarmd shadow] failed to project terminal reference decision")
                reference_batches = []
                job_failed = True
            if reference_batches and not reference_initialization_failed and reference_publisher is None:
                try:
                    from alarm_backends.core.alert.adapter import MonitorEventAdapter

                    reference_config_json = json.dumps(
                        shadow_kafka_config(settings.ALARMD_TRIGGER_REFERENCE_SHADOW_KAFKA_CONFIG),
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    reference_allowed_topics = shadow_topics(settings.ALARMD_TRIGGER_REFERENCE_SHADOW_ALLOWED_TOPICS)
                    forbidden_topics = tuple(sorted(set(allowed_topics) | {MonitorEventAdapter.get_output_topic()}))
                    reference_publisher = get_cached_kafka_reference_decision_publisher(
                        reference_config_json,
                        reference_allowed_topics,
                        forbidden_topics,
                    )
                except Exception:
                    logger.exception("[alarmd shadow] failed to initialize terminal reference publisher")
                    reference_initialization_failed = True
                    job_failed = True
            detect_input_result, reference_result = publish_post_detection_shadow(
                detect_input_publisher=detect_input_publisher,
                detect_input=detect_input_for_publish,
                reference_publisher=reference_publisher,
                reference_batches=reference_batches if not reference_initialization_failed else (),
            )
            for stage, result in (
                (STAGE_DETECT_INPUT, detect_input_result),
                (STAGE_REFERENCE, reference_result),
            ):
                if result is None:
                    continue
                record_shadow_publish_result(stage, success=result.error is None, elapsed=result.elapsed)
                record_shadow_published_records(stage, result.acknowledged_records)
                published += result.acknowledged_records
                duration_ms = max(0, round(result.elapsed * 1000))
                if result.error is None:
                    logger.debug(
                        "[alarmd shadow] component=alarmd-python stage=%s result=broker_ack "
                        "records=%s duration_ms=%s shared_flush=%s strategy(%s) batch_id=%s",
                        stage,
                        result.acknowledged_records,
                        duration_ms,
                        str(result.shared_flush).lower(),
                        strategy_id,
                        batch_id,
                    )
                    continue
                job_failed = True
                logger.error(
                    "[alarmd shadow] component=alarmd-python stage=%s result=fail_open "
                    "operation=broker_publish records=%s duration_ms=%s shared_flush=%s "
                    "strategy(%s) batch_id=%s",
                    stage,
                    result.acknowledged_records,
                    duration_ms,
                    str(result.shared_flush).lower(),
                    strategy_id,
                    batch_id,
                    exc_info=(type(result.error), result.error, result.error.__traceback__),
                )
        if job_failed:
            raise RuntimeError("one or more alarmd Shadow stages failed")
        return published

    def push_data(self):
        current_time = time.time()
        max_latency = 0
        for data_points in self.outputs.values():
            for data_point in data_points:
                if not data_point["data"].get("access_time"):
                    # 拿不到上一级记录的时间，忽略
                    continue
                latency = current_time - data_point["data"]["access_time"]
                # SLI(detect) - 记录当前处理时间，用于 SLI 统计各模块间处理延迟场景
                data_point["data"]["detect_time"] = current_time
                if latency > max_latency:
                    max_latency = latency

        # 检测延迟指标，按处理频率进行上报， 不再以数据量频率进行上报
        metrics.DETECT_PROCESS_LATENCY.labels(strategy_id=metrics.TOTAL_TAG).observe(max_latency)
        if max_latency > 60:
            logger.warning(
                "[access to detect]big latency %s,  strategy(%s)",
                max_latency,
                self.strategy_id,
            )
            metrics.PROCESS_BIG_LATENCY.labels(
                strategy_id=self.strategy_id,
                module="access_detect",
                bk_biz_id=self.strategy.bk_biz_id,
                strategy_name=self.strategy.name,
            ).observe(max_latency)
        inline_trigger_enabled = settings.ENABLE_DETECT_INLINE_TRIGGER
        self.inline_trigger_items = (
            [item.id for item in self.strategy.items if self.outputs.get(item.id)] if inline_trigger_enabled else []
        )
        # 内联路径先只写异常详情；抢 Trigger 锁失败时再由 run_inline_trigger() 补写信号。
        anomaly_count = self.push_abnormal_data(
            self.outputs,
            self.strategy_id,
            publish_signal=not inline_trigger_enabled,
        )
        try:
            alarmd_batches = self.prepare_alarmd_detection_batches()
        except Exception:
            logger.exception(f"[alarmd shadow] strategy({self.strategy_id}) failed to prepare detection batch")
            alarmd_batches = []
        if alarmd_batches:
            from alarm_backends.core.alarmd.async_publish import submit_shadow_job

            for batch in alarmd_batches:
                submit_shadow_job(
                    "detect_input",
                    (batch,),
                    max_jobs=settings.ALARMD_SHADOW_ASYNC_QUEUE_SIZE,
                )
        if anomaly_count > 1000:
            # 获取 Redis 节点信息（带异常处理）
            try:
                cache_node = get_node_by_strategy_id(int(self.strategy_id))
                redis_node = cache_node.node_alias or f"{cache_node.host}:{cache_node.port}"
            except Exception:
                redis_node = "unknown"  # 异常情况下使用默认值

            # 记录异常数据量较大的策略信息
            metrics.PROCESS_OVER_FLOW.labels(
                module="detect",
                strategy_id=self.strategy_id,
                bk_biz_id=self.strategy.bk_biz_id,
                strategy_name=self.strategy.name,
                redis_node=redis_node,
            ).inc(anomaly_count)
        if any(self.inputs.values()):
            logger.info(f"[detect] strategy({self.strategy_id}) 异常检测完成: 异常记录数({anomaly_count})")
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
        logger.info(f"[detect] strategy({self.strategy_id}) item({item.id}) 开始异常二次确认流程")
        item.double_check(outputs=self.outputs[item.id])

    def run_inline_trigger(self):
        from alarm_backends.service.trigger.runner import run_trigger_item
        from core.errors.alarm_backends import LockError

        for item_id in self.inline_trigger_items:
            try:
                run_trigger_item(self.strategy_id, item_id, executor="detect_inline")
            except LockError:
                self.publish_anomaly_signals([f"{self.strategy_id}.{item_id}"])
                logger.info(
                    "[detect inline trigger] strategy(%s), item(%s) is locked; signal published for trigger worker",
                    self.strategy_id,
                    item_id,
                )

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
            logger.info(f"[detect][latency] strategy({self.strategy_id}) processing end in {end_at - start_at}")
            metrics.DETECT_PROCESS_TIME.labels(strategy_id=metrics.TOTAL_TAG).observe(end_at - start_at)
        self.run_inline_trigger()
