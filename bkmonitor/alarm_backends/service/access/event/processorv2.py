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

from django.conf import settings

from alarm_backends.cluster import TargetType
from alarm_backends.core.cache import clear_mem_cache, key
from alarm_backends.core.cache.key import ACCESS_EVENT_LOCKS
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.cluster import get_cluster
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.detect_result import ANOMALY_LABEL, CheckResult
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.core.storage.kafka_v2 import KafkaQueueV2 as KafkaQueue
from alarm_backends.service.access.base import BaseAccessProcess
from alarm_backends.service.access.data.filters import HostStatusFilter, RangeFilter
from alarm_backends.service.access.event.filters import ConditionFilter, ExpireFilter
from alarm_backends.service.access.event.qos import QoSMixin
from alarm_backends.service.access.event.records import (
    AgentEvent,
    CorefileEvent,
    DiskFullEvent,
    DiskReadonlyEvent,
    GseProcessEventRecord,
    OOMEvent,
    PingEvent,
)
from alarm_backends.service.access.event.records.custom_event import (
    GseCustomStrEventRecord,
)
from alarm_backends.service.access.priority import PriorityChecker
from constants.common import DEFAULT_TENANT_ID
from constants.strategy import MAX_RETRIEVE_NUMBER
from core.drf_resource import api
from core.prometheus import metrics

logger = logging.getLogger("access.event")


class BaseAccessEventProcess(BaseAccessProcess, QoSMixin):
    def __init__(self):
        super().__init__()
        self.strategies = {}

        self.add_filter(ExpireFilter())
        self.add_filter(HostStatusFilter())
        self.add_filter(RangeFilter())
        self.add_filter(ConditionFilter())

    def post_handle(self):
        # 释放主机信息本地内存
        clear_mem_cache("host_cache")

    def pull(self):
        """
        Pull raw data and generate record.
        """
        raise NotImplementedError("pull must be implemented by BaseAccessEventProcess subclasses")

    def push_to_check_result(self):
        redis_pipeline = None
        last_checkpoints = {}
        for event_record in self.record_list:
            for item in event_record.items:
                strategy_id = item.strategy.id
                item_id = item.id
                if not event_record.is_retains[item_id] or event_record.inhibitions[item_id]:
                    continue

                timestamp = event_record.event_time
                md5_dimension = event_record.md5_dimension
                check_result = CheckResult(strategy_id, item_id, event_record.md5_dimension, event_record.level)

                if redis_pipeline is None:
                    redis_pipeline = check_result.CHECK_RESULT

                try:
                    # 1. 缓存数据（检测结果缓存）
                    name = f"{timestamp}|{ANOMALY_LABEL}"
                    kwargs = {name: event_record.event_time}
                    check_result.add_check_result_cache(**kwargs)

                    # 2. 缓存最后checkpoint
                    md5_dimension_last_point_key = (
                        md5_dimension,
                        strategy_id,
                        item_id,
                        event_record.level,
                    )
                    last_point = last_checkpoints.setdefault(md5_dimension_last_point_key, 0)
                    if last_point < timestamp:
                        last_checkpoints[md5_dimension_last_point_key] = timestamp

                    # 3. 缓存数据（维度缓存）  事件数据不设置维度缓存, 没有意义
                    # check_result.update_key_to_dimension(event_record.raw_data["dimensions"])
                except Exception as e:
                    logger.exception(f"set check result cache error: {e}")

        if redis_pipeline:
            # 不设置维度缓存，也没必要再设置过期
            # check_result.expire_key_to_dimension()
            redis_pipeline.execute()

        # 更新last_checkpoint
        for md5_dimension_last_point_key, point_timestamp in list(last_checkpoints.items()):
            try:
                md5_dimension, strategy_id, item_id, level = md5_dimension_last_point_key
                CheckResult.update_last_checkpoint_by_d_md5(strategy_id, item_id, md5_dimension, point_timestamp, level)
            except Exception as e:
                msg = f"set check result cache last_check_point error:{e}"
                logger.exception(msg)
            CheckResult.expire_last_checkpoint_cache(strategy_id=strategy_id, item_id=item_id)

    def push(self, output_client=None):
        """
        Push event_record to Queue.
        """
        self.check_qos()
        self.push_to_check_result()

        # 优先级检查
        PriorityChecker.check_records(self.record_list)

        # 1. split by strategy_id
        pending_to_push = {}
        for e in self.record_list:
            data_str = e.to_str()
            for item in e.items:
                strategy_id = item.strategy.id
                item_id = item.id
                if e.is_retains[item_id] and not e.inhibitions[item_id]:
                    pending_to_push.setdefault(strategy_id, {}).setdefault(item_id, []).append(data_str)

        # 2. push to the queue by strategy_id
        anomaly_signal_list = []
        client = output_client or key.ANOMALY_LIST_KEY.client
        pipeline = client.pipeline()
        for strategy_id, item_to_event_record in list(pending_to_push.items()):
            record_count = sum([len(records) for records in item_to_event_record.values()])
            metrics.ACCESS_PROCESS_PUSH_DATA_COUNT.labels(metrics.TOTAL_TAG, "event").inc(record_count)
            for item_id, event_list in list(item_to_event_record.items()):
                queue_key = key.ANOMALY_LIST_KEY.get_key(strategy_id=strategy_id, item_id=item_id)
                pipeline.lpush(queue_key, *event_list)
                anomaly_signal_list.append(f"{strategy_id}.{item_id}")
                pipeline.expire(queue_key, key.ANOMALY_LIST_KEY.ttl)
        pipeline.execute()

        if anomaly_signal_list:
            client = output_client or key.ANOMALY_SIGNAL_KEY.client
            client.lpush(key.ANOMALY_SIGNAL_KEY.get_key(), *anomaly_signal_list)
            client.expire(key.ANOMALY_SIGNAL_KEY.get_key(), key.ANOMALY_SIGNAL_KEY.ttl)

        logger.info("push %s event_record to match queue finished(%s)", self.__class__.__name__, len(self.record_list))


class AccessCustomEventGlobalProcessV2(BaseAccessEventProcess):
    TYPE_OS_RESTART = 0
    TYPE_CLOCK_UNSYNC = 1
    TYPE_AGENT = 2
    TYPE_DISK_READONLY = 3
    TYPE_PORT_MISSING = 4
    TYPE_PROCESS_MISSING = 5
    TYPE_DISK_FULL = 6
    TYPE_COREFILE = 7
    TYPE_PING = 8
    TYPE_OOM = 9
    TYPE_GSE_CUSTOM_STR_EVENT = 100
    TYPE_GSE_PROCESS_EVENT = 101

    OPENED_WHITE_LIST = [
        TYPE_AGENT,
        TYPE_DISK_READONLY,
        TYPE_DISK_FULL,
        TYPE_COREFILE,
        TYPE_PING,
        TYPE_OOM,
        TYPE_GSE_CUSTOM_STR_EVENT,
        TYPE_GSE_PROCESS_EVENT,
    ]

    # kafka 客户端缓存，单个进程共用一套缓存
    _kafka_queues = {}

    @classmethod
    def get_kafka_queue(cls, topic, group_prefix):
        """
        Kafka客户端缓存
        """
        queue_key = (topic, group_prefix)
        if queue_key not in cls._kafka_queues:
            kafka_queue = KafkaQueue.get_common_kafka_queue()
            kafka_queue.set_topic(topic, group_prefix=group_prefix)
            cls._kafka_queues[queue_key] = kafka_queue
        return cls._kafka_queues[queue_key]

    def __init__(self, data_id=None, topic=None):
        super().__init__()

        self.data_id = data_id
        if not topic:
            # 获取topic信息
            topic_info = api.metadata.get_data_id(
                bk_tenant_id=DEFAULT_TENANT_ID, bk_data_id=self.data_id, with_rt_info=False
            )
            self.topic = topic_info["mq_config"]["storage_config"]["topic"]
        else:
            self.topic = topic

        self.strategies = {}

        # gse基础事件、自定义字符型、进程托管事件策略ID列表缓存
        gse_base_event_strategy = StrategyCacheManager.get_gse_alarm_strategy_ids()
        self.process_strategies(gse_base_event_strategy)

    def process_strategies(self, strategies):
        """
        处理策略信息
        """
        for biz_id, strategy_id_list in list(strategies.items()):
            # 过滤出集群需要处理的业务ID
            if not get_cluster().match(TargetType.biz, biz_id):
                continue

            for strategy_id in strategy_id_list:
                self.strategies.setdefault(int(biz_id), {})[strategy_id] = Strategy(strategy_id)

    def fetch_custom_event_alarm_type(self, raw_data):
        """
        判断自定义事件上报的告警类型
        :param raw_data: 事件数据
        :return: alarm_type
        """
        if self.data_id == settings.GSE_CUSTOM_EVENT_DATAID:
            return self.TYPE_GSE_CUSTOM_STR_EVENT
        if settings.GSE_PROCESS_REPORT_DATAID == raw_data["data_id"]:
            return self.TYPE_GSE_PROCESS_EVENT

    def _instantiate_by_event_type(self, raw_data):
        """
        根据事件类型实例化数据
        :param raw_data: 原始数据
        :return: 实例化后的数据
        """

        # 获取告警类型
        alarms = raw_data.get("value")
        if alarms:
            alarm_type = alarms[0]["extra"]["type"]
        else:
            alarm_type = self.fetch_custom_event_alarm_type(raw_data)

        # 根据告警类型分配实例化方法
        if alarm_type in self.OPENED_WHITE_LIST:
            if alarm_type == self.TYPE_PING:
                if settings.ENABLE_PING_ALARM:
                    return PingEvent(raw_data, self.strategies)
            elif alarm_type == self.TYPE_AGENT:
                if settings.ENABLE_AGENT_ALARM:
                    return AgentEvent(raw_data, self.strategies)
            elif alarm_type == self.TYPE_COREFILE:
                return CorefileEvent(raw_data, self.strategies)
            elif alarm_type == self.TYPE_DISK_FULL:
                return DiskFullEvent(raw_data, self.strategies)
            elif alarm_type == self.TYPE_DISK_READONLY:
                return DiskReadonlyEvent(raw_data, self.strategies)
            elif alarm_type == self.TYPE_OOM:
                return OOMEvent(raw_data, self.strategies)
            elif alarm_type == self.TYPE_GSE_CUSTOM_STR_EVENT:
                return GseCustomStrEventRecord(raw_data, self.strategies)
            elif alarm_type == self.TYPE_GSE_PROCESS_EVENT:
                return GseProcessEventRecord(raw_data, self.strategies)

    def _pull_from_redis(self, max_records=MAX_RETRIEVE_NUMBER):
        data_channel = key.EVENT_LIST_KEY.get_key(data_id=self.data_id)
        client = key.DATA_LIST_KEY.client

        total_events = client.llen(data_channel)
        # 如果队列中事件数量超过1亿条，则记录日志，并进行清理
        # 有损，但需要保证整体服务依赖redis稳定
        if total_events > 10**7:
            logger.warning(
                f"[access event] data_id({self.data_id}) has {total_events} events, cleaning up! drop all events."
            )
            client.delete(data_channel)
            return []

        offset = min([total_events, max_records])
        if offset == 0:
            logger.info(f"[access event] data_id({self.data_id}) 暂无待检测事件")
            return []

        try:
            records = client.lrange(data_channel, -offset, -1)
        except UnicodeDecodeError as e:
            logger.error(
                "drop events: data_id(%s) topic(%s) poll alarm list(%s) from redis failed: %s",
                self.data_id,
                self.topic,
                offset,
                e,
            )
            client.ltrim(data_channel, 0, -offset - 1)
            return self._pull_from_redis(max_records=max_records)

        logger.info("data_id(%s) topic(%s) poll alarm list(%s) from redis", self.data_id, self.topic, len(records))
        if records:
            client.ltrim(data_channel, 0, -offset - 1)
        if offset == MAX_RETRIEVE_NUMBER:
            # 队列中时间量级超过单次处理上限。
            logger.info("data_id(%s) topic(%s) run_access_event_handler_v2 immediately", self.data_id, self.topic)
            from alarm_backends.service.access.tasks import run_access_event_handler_v2

            run_access_event_handler_v2.delay(self.data_id)
        return records

    def get_pull_type(self):
        # group_prefix
        cluster_name = get_cluster().name
        if cluster_name == "default":
            group_prefix = f"access.event.{self.data_id}"
        else:
            group_prefix = f"{cluster_name}.access.event.{self.data_id}"

        kafka_queue = self.get_kafka_queue(topic=self.topic, group_prefix=group_prefix)
        return "kafka" if kafka_queue.has_assigned_partitions() else "redis"

    def pull(self):
        """
        Pull raw data and generate event_record.
        """
        record_list = []

        if not self.topic:
            logger.warning(f"[access] dataid:({self.data_id}) no topic")
            return

        with service_lock(ACCESS_EVENT_LOCKS, data_id=f"{self.data_id}-[redis]"):
            result = self._pull_from_redis()
        for m in result:
            if not m:
                continue
            try:
                # GSE格式变动的临时兼容方案：判断一下结尾是否多了\n符号，多了先去掉
                data = json.loads(m[:-1] if m[-1] == "\x00" or m[-1] == "\n" else m)
                event_record = self._instantiate_by_event_type(data)
                if event_record and event_record.check():
                    record_list.extend(event_record.flat())
            except Exception as e:
                logger.exception("topic(%s) loads alarm(%s) failed, %s", self.topic, m, e)
        self.record_list.extend(record_list)
        metrics.ACCESS_EVENT_PROCESS_PULL_DATA_COUNT.labels(self.data_id).inc(len(record_list))

    def process(self):
        with metrics.ACCESS_EVENT_PROCESS_TIME.labels(data_id=self.data_id).time():
            if not self.strategies:
                logger.info("no strategy to process")
                exc = None
            else:
                exc = super().process()

        metrics.ACCESS_EVENT_PROCESS_COUNT.labels(
            data_id=self.data_id,
            status=metrics.StatusEnum.from_exc(exc),
            exception=exc,
        ).inc()
