"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import threading
import time

from confluent_kafka import TIMESTAMP_NOT_AVAILABLE, Consumer, KafkaException
from confluent_kafka import TopicPartition as ConfluentTopicPartition
from django.db import DatabaseError, connections
from kafka import TopicPartition
from kafka.consumer.fetcher import ConsumerRecord
from kafka.errors import KafkaTimeoutError

from metadata import config as metadata_config
from metadata.models import ClusterInfo

logger = logging.getLogger("kafka")

SASL_CONFIG_CACHE_SECONDS = 60
# 没有 group_id 时只做元数据查询，不提交 offset；confluent-kafka 仍要求配置 group.id。
METADATA_GROUP_ID = "bkmonitor.kafka.metadata"
AUTO_COMMIT_INTERVAL_SECONDS = 5
ERROR_LOG_INTERVAL_SECONDS = 60

_sasl_config_cache: dict[str, tuple[float, dict | None]] = {}
_sasl_config_lock = threading.Lock()


def get_kafka_sasl_config(bootstrap_server) -> dict | None:
    """
    按 bootstrap 查 metadata 登记的鉴权 Kafka 集群，返回 confluent-kafka 的 SASL 配置；未开启鉴权返回 None。
    """
    if not isinstance(bootstrap_server, str):
        return None
    host, _, port = bootstrap_server.rpartition(":")
    if not host or not port.isdigit():
        return None

    now = time.monotonic()
    with _sasl_config_lock:
        cached = _sasl_config_cache.get(bootstrap_server)
    if cached and cached[0] > now:
        return cached[1]

    try:
        sasl_config = _query_kafka_sasl_config(host, int(port))
    except DatabaseError:
        if cached is None:
            raise
        logger.exception("[kafka sasl] query sasl config of %s failed, use cached config", bootstrap_server)
        return cached[1]
    with _sasl_config_lock:
        _sasl_config_cache[bootstrap_server] = (now + SASL_CONFIG_CACHE_SECONDS, sasl_config)
    return sasl_config


def _query_kafka_sasl_config(host, port) -> dict | None:
    # 调用方是长驻线程，不经过 Django 请求周期回收连接；事务内关闭连接会破坏事务
    connection = connections[ClusterInfo.objects.db]
    in_atomic_block = connection.in_atomic_block
    if not in_atomic_block:
        connection.close_if_unusable_or_obsolete()
    try:
        clusters = list(
            ClusterInfo.objects.filter(cluster_type=ClusterInfo.TYPE_KAFKA, domain_name=host, port=port, is_auth=True)
            .exclude(username="")
            .order_by("cluster_id")
        )
    finally:
        if not in_atomic_block:
            connection.close()

    sasl_configs = []
    for cluster in clusters:
        if not cluster.password:
            continue
        sasl_config = {
            "security.protocol": cluster.security_protocol or metadata_config.KAFKA_SASL_PROTOCOL,
            "sasl.mechanisms": cluster.sasl_mechanisms or metadata_config.KAFKA_SASL_MECHANISM,
            "sasl.username": cluster.username,
            "sasl.password": cluster.password,
        }
        if sasl_config not in sasl_configs:
            sasl_configs.append(sasl_config)
    if len(sasl_configs) > 1:
        cluster_ids = [cluster.cluster_id for cluster in clusters]
        raise ValueError(f"kafka {host}:{port} has conflicting sasl config in clusters {cluster_ids}")
    return sasl_configs[0] if sasl_configs else None


class SaslKafkaConsumer:
    """
    kafka-python 1.4.6 不支持 SCRAM，鉴权集群改用 confluent-kafka，并按 kafka-python 接口暴露告警拉取与自监控用到的方法。
    """

    def __init__(
        self,
        bootstrap_server,
        sasl_config,
        group_id=None,
        request_timeout_ms=30000,
        session_timeout_ms=None,
        max_partition_fetch_bytes=None,
        **kwargs,
    ):
        conf = {
            "bootstrap.servers": bootstrap_server,
            "group.id": group_id or METADATA_GROUP_ID,
            "auto.offset.reset": "latest",
            # 手动提交，对齐 kafka-python：poll 时按间隔异步提交，close(autocommit=False) 不做最终提交
            "enable.auto.commit": False,
            **sasl_config,
        }
        if session_timeout_ms:
            conf["session.timeout.ms"] = session_timeout_ms
        if max_partition_fetch_bytes:
            conf["max.partition.fetch.bytes"] = max_partition_fetch_bytes
        self.config = {"bootstrap_servers": bootstrap_server, "group_id": group_id}
        self._timeout = request_timeout_ms / 1000
        self._consumer = Consumer(conf)
        self._metadata = None
        self._partitions: set[TopicPartition] = set()
        self._start_offsets: dict[TopicPartition, int] = {}
        self._fetching = False
        self._commit_enabled = bool(group_id)
        self._next_commit_at = time.monotonic() + AUTO_COMMIT_INTERVAL_SECONDS
        self._error_logged_at: dict[str, float] = {}

    def topics(self):
        self._metadata = self._consumer.list_topics(timeout=self._timeout)
        return set(self._metadata.topics)

    def partitions_for_topic(self, topic):
        # 不按 topic 查询：broker 开启自动建 topic 时，查询未知 topic 会将其创建
        if self._metadata is None:
            self.topics()
        topic_metadata = self._metadata.topics.get(topic)
        if topic_metadata is None or topic_metadata.error is not None:
            return None
        return set(topic_metadata.partitions) or None

    def assignment(self):
        return set(self._partitions)

    def assign(self, partitions):
        self._partitions = {TopicPartition(tp.topic, tp.partition) for tp in partitions}
        self._start_offsets = {}
        self._fetching = False
        self._apply_assignment()

    def seek(self, partition, offset):
        if partition not in self._partitions:
            raise ValueError(f"partition {partition} is not assigned")
        if self._fetching:
            self._consumer.seek(ConfluentTopicPartition(partition.topic, partition.partition, offset))
            return
        # confluent-kafka 不允许对尚未开始拉取的分区 seek，改为带起始 offset 重新 assign
        self._start_offsets[partition] = offset
        self._apply_assignment()

    def _apply_assignment(self):
        assignment = []
        for tp in self._partitions:
            if tp in self._start_offsets:
                assignment.append(ConfluentTopicPartition(tp.topic, tp.partition, self._start_offsets[tp]))
            else:
                assignment.append(ConfluentTopicPartition(tp.topic, tp.partition))
        self._consumer.assign(assignment)

    def poll(self, timeout_ms=0, max_records=None):
        self._commit_if_due()
        messages = self._consumer.consume(num_messages=max_records or 500, timeout=timeout_ms / 1000)
        self._fetching = bool(self._partitions)
        records = {}
        for message in messages:
            if message.error():
                self._log_consume_error(message.error())
                continue
            tp = TopicPartition(message.topic(), message.partition())
            records.setdefault(tp, []).append(self._to_record(message))
        return records

    def _log_consume_error(self, error):
        # topic 未创建等持续性错误每次 consume 都会返回，按错误内容限频
        error_key = str(error)
        now = time.monotonic()
        if now < self._error_logged_at.get(error_key, float("-inf")) + ERROR_LOG_INTERVAL_SECONDS:
            return
        self._error_logged_at[error_key] = now
        logger.warning("[kafka sasl] %s consume error: %s", self.config["bootstrap_servers"], error)

    def _commit_if_due(self):
        if not self._commit_enabled or not self._partitions or time.monotonic() < self._next_commit_at:
            return
        self._next_commit_at = time.monotonic() + AUTO_COMMIT_INTERVAL_SECONDS
        try:
            self._consumer.commit(asynchronous=True)
        except KafkaException as error:
            # 尚未消费到消息时没有可提交的 offset
            logger.debug("[kafka sasl] %s skip commit: %s", self.config["bootstrap_servers"], error)

    @staticmethod
    def _to_record(message):
        timestamp_type, timestamp = message.timestamp()
        key, value = message.key(), message.value()
        if timestamp_type == TIMESTAMP_NOT_AVAILABLE:
            timestamp, timestamp_type = -1, None
        else:
            # confluent-kafka: CREATE_TIME=1、LOG_APPEND_TIME=2；kafka-python: 0、1
            timestamp_type -= 1
        return ConsumerRecord(
            topic=message.topic(),
            partition=message.partition(),
            offset=message.offset(),
            timestamp=timestamp,
            timestamp_type=timestamp_type,
            key=key,
            value=value,
            headers=message.headers() or [],
            checksum=None,
            serialized_key_size=len(key) if key is not None else -1,
            serialized_value_size=len(value) if value is not None else -1,
            serialized_header_size=-1,
        )

    def end_offsets(self, partitions):
        # 与 kafka-python 一致，所有分区共享一个超时
        deadline = time.monotonic() + self._timeout
        offsets = {}
        for tp in partitions:
            remaining = deadline - time.monotonic()
            watermarks = None
            if remaining > 0:
                watermarks = self._consumer.get_watermark_offsets(
                    ConfluentTopicPartition(tp.topic, tp.partition), timeout=remaining
                )
            # 超时时 confluent-kafka 返回 None
            if watermarks is None:
                raise KafkaTimeoutError(f"Failed to get end offsets in {self._timeout * 1000:.0f} ms")
            offsets[tp] = watermarks[1]
        return offsets

    def committed(self, partition):
        committed = self._consumer.committed(
            [ConfluentTopicPartition(partition.topic, partition.partition)], timeout=self._timeout
        )[0]
        if committed.error:
            raise KafkaException(committed.error)
        return committed.offset if committed.offset >= 0 else None

    def close(self, autocommit=True):
        try:
            if autocommit and self._commit_enabled and self._partitions:
                try:
                    self._consumer.commit(asynchronous=False)
                except KafkaException as error:
                    logger.debug("[kafka sasl] %s skip commit: %s", self.config["bootstrap_servers"], error)
        finally:
            self._consumer.close()
