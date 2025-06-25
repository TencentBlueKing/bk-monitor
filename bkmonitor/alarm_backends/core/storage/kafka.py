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
import socket
import uuid
from typing import Self

import kafka
import kafka.errors
from django.conf import settings

from alarm_backends.constants import CONST_ONE_DAY
from alarm_backends.core.storage.redis import Cache

logger = logging.getLogger("core.storage.kafka")


class KafkaQueue:
    reconnect_seconds = getattr(settings, "KAFKA_RECONNECT_SECONDS", 60)
    msg_push_batch_size = 1000

    def __init__(self, topic="", group_prefix="", redis_offset=True, kfk_conf=None, timeout=6):
        self.redis_offset = redis_offset
        if kfk_conf:
            self.bootstrap_servers = ["{}:{}".format(kfk_conf["domain"], kfk_conf["port"])]
        else:
            self.bootstrap_servers = [f"{settings.KAFKA_HOST[0]}:{settings.KAFKA_PORT}"]

        self.timeout_ms = timeout * 1000  # 转换为毫秒
        self._producer = None
        self.consumer_pool = {}
        self.offset_manager_pool: dict[str, KafkaOffsetManager] = {}
        self.set_topic(topic, group_prefix)
        self.pod_id = socket.gethostname().rsplit("-", 1)[-1] or str(uuid.uuid4())[:8]

    def __del__(self):
        self.close()

    @classmethod
    def get_alert_kafka_queue(cls) -> Self:
        kfk_conf = {"cluster_index": 0, "domain": settings.ALERT_KAFKA_HOST[0], "port": settings.ALERT_KAFKA_PORT}
        return cls(kfk_conf=kfk_conf)

    @classmethod
    def get_common_kafka_queue(cls) -> Self:
        kfk_conf = {"cluster_index": 0, "domain": settings.KAFKA_HOST[0], "port": settings.KAFKA_PORT}
        return cls(kfk_conf=kfk_conf)

    def close(self):
        """
        关闭 kafka 连接
        """
        if self._producer:
            self._producer.close()
        for consumer in self.consumer_pool.values():
            consumer.close()

    def set_topic(self, topic, group_prefix=""):
        """
        设置 topic
        """
        if topic:
            self.topic = topic
        if group_prefix:
            self.group_name = f"{group_prefix}{settings.KAFKA_CONSUMER_GROUP}"

    def get_producer(self) -> kafka.KafkaProducer:
        """
        获取 producer
        """
        if not self._producer:
            self._producer = kafka.KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                request_timeout_ms=self.timeout_ms,
                acks=1,
                retries=3,
                max_request_size=1048576,
            )
        return self._producer

    def get_consumer(self) -> kafka.KafkaConsumer:
        """
        获取 consumer
        """
        consumer_pool_key = f"{self.topic}-{self.group_name}"
        # 增加初始化判断机制 关键值未赋值 则初始化不成功
        consumer = self.consumer_pool.get(consumer_pool_key)
        if not consumer:
            consumer = self._create_consumer(self.topic, self.group_name)
            self.consumer_pool[consumer_pool_key] = consumer
        return consumer

    def get_offset_manager(self) -> "KafkaOffsetManager":
        """
        获取 offset 管理器
        """
        offset_manager_pool_key = f"{self.topic}-{self.group_name}"
        # 增加初始化判断机制 关键值未赋值 则初始化不成功
        if offset_manager_pool_key in self.offset_manager_pool:
            offset_manager = self.offset_manager_pool[offset_manager_pool_key]
        else:
            offset_manager = KafkaOffsetManager(self.get_consumer())
            self.offset_manager_pool[offset_manager_pool_key] = offset_manager
        return offset_manager

    # 重试3次 确认offsets赋值成功
    def _create_consumer(self, topic, group_name):
        for i in range(3):
            try:
                consumer = kafka.KafkaConsumer(
                    topic,
                    bootstrap_servers=self.bootstrap_servers,
                    group_id=group_name,
                    client_id=f"{group_name}-{self.pod_id}",
                    enable_auto_commit=settings.KAFKA_AUTO_COMMIT,
                    auto_offset_reset="latest",
                    consumer_timeout_ms=self.timeout_ms,
                    max_partition_fetch_bytes=1024 * 1024 * 5,
                    session_timeout_ms=30000,
                    request_timeout_ms=self.timeout_ms,
                )
            except Exception as e:
                logger.exception(
                    "topic(%s) create consumer failed %d times: %s",
                    topic,
                    i + 1,
                    e,
                )
                continue

            # 检查consumer是否正常创建
            try:
                # 尝试获取分区信息来验证连接
                partitions = consumer.partitions_for_topic(topic)
                if partitions:
                    return consumer
                else:
                    logger.warning("topic(%s) load metadata failed %d times", topic, i + 1)
                    continue
            except Exception as e:
                logger.warning("topic(%s) verify consumer failed %d times: %s", topic, i + 1, e)
                continue
        else:
            logger.error("topic %s load metadata failed", topic)
            raise Exception(f"topic {topic} load metadata failed")

    def _put(self, value, topic=""):
        """
        发送单条消息
        """
        producer = self.get_producer()
        try:
            if topic:
                for msg in value:
                    producer.send(topic, msg)
            else:
                for msg in value:
                    producer.send(self.topic, msg)
            producer.flush()  # 确保消息发送完成
        except kafka.errors.KafkaError:
            # 重试一次
            if topic:
                for msg in value:
                    producer.send(topic, msg)
            else:
                for msg in value:
                    producer.send(self.topic, msg)
            producer.flush()

    def put(self, value: list[bytes] | bytes, topic: str = ""):
        """
        发送消息
        """
        if not isinstance(value, list):
            value = [value]
        for i in range(0, len(value), self.msg_push_batch_size):
            batch = value[i : i + self.msg_push_batch_size]
            self._put(batch, topic)

    def reset_offset(self, force_offset: int = -1):
        """
        重置 offset
        """
        if force_offset >= 0:
            new_offset = force_offset
        else:
            offset = self.get_offset_manager().get_offset()
            tail = self.get_offset_manager().get_tail() - 5
            new_offset = max(offset, tail)
        self.get_offset_manager().set_offset(new_offset)

    def take_raw(self, count: int = 1, timeout: float = 5.0):
        """
        获取消息
        """
        consumer = self.get_consumer()
        if self.redis_offset:
            self.get_offset_manager().reset_consumer_offset(count)
        try:
            # 使用poll方法获取消息
            timeout_ms = int(timeout * 1000)
            records = consumer.poll(timeout_ms=timeout_ms, max_records=count)
            messages = []
            for topic_partition, msgs in records.items():
                messages.extend(msgs)
        except kafka.errors.OffsetOutOfRangeError:
            # 重置到最新位置
            consumer.seek_to_end()
            records = consumer.poll(timeout_ms=timeout_ms, max_records=count)
            messages = []
            for _, msgs in records.items():
                messages.extend(msgs)
        except kafka.errors.KafkaError:
            # retry
            records = consumer.poll(timeout_ms=timeout_ms, max_records=count)
            messages = []
            for _, msgs in records.items():
                messages.extend(msgs)
        finally:
            if settings.KAFKA_AUTO_COMMIT and messages:
                try:
                    consumer.commit()
                except Exception:
                    logger.warning("Kafka commit failure")
        if self.redis_offset:
            self.get_offset_manager().update_consumer_offset(messages)
        return messages

    def take(self, count=1, timeout=0.1):
        messages = self.take_raw(count, timeout)
        return [m.value for m in messages]


class KafkaOffsetManager:
    TIMEOUT = CONST_ONE_DAY
    KEY_PREFIX = f"{settings.APP_CODE}_kafka_offset"

    def __init__(self, consumer: kafka.KafkaConsumer):
        self.consumer = consumer
        self.cache = Cache("service")
        self.instance_offset = self.get_offset()

    @property
    def key(self):
        # 新版consumer的group_id和主题信息获取方式
        group_id = getattr(self.consumer, "_group_id", "unknown")
        topics = list(self.consumer.subscription() or ["unknown"])
        topic = topics[0] if topics else "unknown"
        return "_".join(map(str, [self.KEY_PREFIX, group_id, topic]))

    def get_offset(self) -> int:
        """
        获取 offset
        """
        return int(self.cache.get(self.key) or 0)

    def set_offset(self, offset: int) -> int:
        """
        设置消费者的 offset。

        Args:
            offset (int): 要设置的 offset 值
            force (bool, optional): 是否强制设置 offset，忽略重置检查。默认为 False

        Returns:
            int: 实际设置后的 offset 值

        Note:
            设置成功后会在缓存中存储新的 offset 值。
        """
        logger.debug("Kafka_offset local %s: %s", self.key, offset)
        self.cache.set(self.key, str(offset), self.TIMEOUT)
        return self.get_offset()

    def set_seek(self, *args, **kwargs):
        """
        设置 seek
        """
        # 新版API的seek方法需要TopicPartition对象
        topics = list(self.consumer.subscription() or [])
        if topics:
            partitions = self.consumer.assignment()
            if partitions:
                for tp in partitions:
                    self.consumer.seek(tp, args[0] if args else 0)

        # 获取当前offset
        try:
            committed = self.consumer.committed(list(self.consumer.assignment())[0])
            remote_offset = committed.offset if committed else 0
        except (IndexError, AttributeError):
            remote_offset = 0

        self.cache.set(self.key, remote_offset, self.TIMEOUT)
        return self.get_offset()

    def _set_consumer_offset(self, new_remote_offset):
        """
        设置所有分区的 offset 到 new_remote_offset。
        """
        assignment = self.consumer.assignment()
        if not assignment:
            logger.warning("No partitions assigned to consumer when setting offset.")
            return
        for tp in assignment:
            try:
                current_position = self.consumer.position(tp)
                logger.debug(
                    "Kafka_offset remote %s: %s to %s (partition %s)", self.key, current_position, new_remote_offset, tp
                )
                self.consumer.seek(tp, new_remote_offset)
            except Exception as e:
                logger.warning("Failed to set consumer offset for %s: %s", tp, e)

    def reset_consumer_offset(self, count: int = 1) -> None:
        """
        优先从缓存读取 offset，若有则 seek 到该 offset，否则 seek 到最新 offset 前 3 条。
        支持多分区。
        """
        if self.instance_offset is None:
            cached_offset = self.get_offset()
            if cached_offset is not None:
                self.instance_offset = cached_offset
            else:
                self.instance_offset = max(self.get_tail() - 3, 0)
        self._set_consumer_offset(self.instance_offset)

    def get_tail(self) -> int:
        """
        获取所有分区的最大 offset（取最大值）。
        """
        assignment = self.consumer.assignment()
        max_offset = 0
        if assignment:
            try:
                end_offsets = self.consumer.end_offsets(list(assignment))
                if end_offsets:
                    max_offset = max(end_offsets.values())
            except Exception:
                return 0
        return max_offset

    def update_consumer_offset(self, messages: list):
        if not messages:
            return
        # 更新到最后一条消息的offset + 1
        last_offset = messages[-1].offset + 1
        self.instance_offset = last_offset
        self.set_offset(last_offset)
