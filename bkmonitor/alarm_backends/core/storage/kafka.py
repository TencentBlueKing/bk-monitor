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

import arrow
import kafka
import kafka.errors
from django.conf import settings
from six.moves import map, range

from alarm_backends.constants import CONST_ONE_DAY
from alarm_backends.core.storage.redis import Cache

logger = logging.getLogger("core.storage.kafka")


class KafkaQueue(object):
    reconnect_seconds = getattr(settings, "KAFKA_RECONNECT_SECONDS", 60)

    def __init__(self, topic="", group_prefix="", redis_offset=True, kfk_conf=None, timeout=6):
        self.redis_offset = redis_offset
        if kfk_conf:
            kafka_hosts = "{}:{}".format(kfk_conf["domain"], kfk_conf["port"])
        else:
            kafka_hosts = f"{settings.KAFKA_HOST[0]}:{settings.KAFKA_PORT}"
        self._client = kafka.SimpleClient(hosts=kafka_hosts, timeout=timeout)
        self._client_init_time = arrow.utcnow()
        self.producer = kafka.producer.SimpleProducer(self.client)
        self.consumer_pool = {}
        self.offset_manager_pool = {}
        self.set_topic(topic, group_prefix)

    def __del__(self):
        self.close()

    @classmethod
    def get_alert_kafka_queue(cls):
        kfk_conf = {"cluster_index": 0, "domain": settings.ALERT_KAFKA_HOST[0], "port": settings.ALERT_KAFKA_PORT}
        return cls(kfk_conf=kfk_conf)

    @classmethod
    def get_common_kafka_queue(cls):
        kfk_conf = {"cluster_index": 0, "domain": settings.KAFKA_HOST[0], "port": settings.KAFKA_PORT}
        return cls(kfk_conf=kfk_conf)

    def close(self):
        self.client.close()

    @property
    def client(self):
        now = arrow.utcnow()
        delta = (now - self._client_init_time).total_seconds()
        if delta > self.reconnect_seconds:
            self._client_init_time = now
            self._client.reinit()
        return self._client

    def set_topic(self, topic, group_prefix=""):
        if topic:
            self.topic = topic
        if group_prefix:
            self.group_name = "{}{}".format(group_prefix, settings.KAFKA_CONSUMER_GROUP)

    def get_producer(self):
        if hasattr(self, "producer"):
            return self.producer
        self.producer = kafka.producer.SimpleProducer(self.client)
        return self.producer

    def get_consumer(self):
        consumer_pool_key = "{}-{}".format(self.topic, self.group_name)
        # 增加初始化判断机制 关键值未赋值 则初始化不成功
        consumer = self.consumer_pool.get(consumer_pool_key)
        if not consumer:
            consumer = self._create_consumer(self.topic, self.group_name)
            self.consumer_pool[consumer_pool_key] = consumer
        return consumer

    def get_offset_manager(self):
        offset_manager_pool_key = "{}-{}".format(self.topic, self.group_name)
        # 增加初始化判断机制 关键值未赋值 则初始化不成功
        if self.offset_manager_pool.get(offset_manager_pool_key):
            offset_manager = self.offset_manager_pool.get(offset_manager_pool_key)
        else:
            offset_manager = KafkaOffsetManager(self.get_consumer())
            self.offset_manager_pool[offset_manager_pool_key] = offset_manager
        return offset_manager

    # 重试3次 确认offsets赋值成功
    def _create_consumer(self, topic, group_name):
        for i in range(3):
            try:
                consumer = kafka.consumer.SimpleConsumer(
                    self.client, group_name, topic, auto_commit=settings.KAFKA_AUTO_COMMIT, max_buffer_size=None
                )
            except Exception as e:
                logger.exception(
                    "topic(%s) create consumer failed %d times: %s",
                    topic,
                    i + 1,
                    e,
                )
                continue
            if consumer.offsets:
                return consumer
            else:
                logger.warning("topic(%s) load metadata failed %d times", topic, i + 1)
                continue
        else:
            logger.error("topic %s load metadata failed", topic)
            raise Exception("topic {} load metadata failed".format(topic))

    def put(self, value, topic=""):
        if not isinstance(value, list):
            value = [value]
        try:
            if topic:
                return self.get_producer().send_messages(topic, *value)
            else:
                return self.get_producer().send_messages(self.topic, *value)
        except kafka.errors.FailedPayloadsError:
            if topic:
                return self.get_producer().send_messages(topic, *value)
            else:
                return self.get_producer().send_messages(self.topic, *value)

    def reset_offset(self, force_offset=-1):
        if force_offset >= 0:
            new_offset = force_offset
        else:
            offset = self.get_offset_manager().get_offset()
            tail = self.get_offset_manager().get_tail() - 5
            new_offset = max(offset, tail)
        self.get_offset_manager().set_offset(new_offset, True)

    def take_raw(self, count=1, timeout=5):
        if self.redis_offset:
            self.get_offset_manager().reset_consumer_offset(count)
        try:
            messages = self.get_consumer().get_messages(count=count, timeout=timeout)
        except kafka.errors.OffsetOutOfRangeError:
            self.get_consumer().seek(-1, 2)
            messages = self.get_consumer().get_messages(count=count, timeout=timeout)
        except kafka.errors.FailedPayloadsError:
            # retry
            messages = self.get_consumer().get_messages(count=count, timeout=timeout)
        finally:
            if settings.KAFKA_AUTO_COMMIT:
                if self.get_consumer().commit() is False:
                    logger.warning("Kafka commit failure")
        if self.redis_offset:
            self.get_offset_manager().update_consumer_offset(count, messages)
        return messages

    def take(self, count=1, timeout=0.1):
        return [m.message.value for m in self.take_raw(count, timeout)]


class KafkaOffsetManager(object):
    TIMEOUT = CONST_ONE_DAY
    KEY_PREFIX = "{}_kafka_offset".format(settings.APP_CODE)

    def __init__(self, consumer):
        self.consumer = consumer
        self.cache = Cache("service")
        self.instance_offset = self.get_offset()
        self.reset_offset = 0  # 当前的重置点

    @property
    def key(self):
        return "_".join(map(str, [self.KEY_PREFIX, self.consumer.group, self.consumer.topic]))

    @property
    def reset_key(self):
        return "RESET_%s" % self.key

    def _get_offset(self):
        return self.cache.get(self.key)

    def get_offset(self):
        return int(self._get_offset() or 0)

    def get_reset_offset(self):
        return int(self.cache.get(self.reset_key) or 0)

    def set_offset(self, offset, force=False):
        if not force and self.get_reset_offset() != self.reset_offset:
            return logger.info("Kafka_offset pass set")
        logger.debug("Kafka_offset local %s: %s", self.key, offset)
        self.cache.set(self.key, offset, self.TIMEOUT)
        return self.get_offset()

    def set_seek(self, *args, **kwargs):
        self.consumer.seek(*args, **kwargs)
        remote_offset = max(self.consumer.offsets.values())
        self.cache.set(self.key, remote_offset, self.TIMEOUT)
        return self.get_offset()

    def set_reset_offset(self, offset):
        logger.debug("Kafka_offset set_reset %s: %s", self.key, offset)
        self.cache.set(self.reset_key, offset, self.TIMEOUT)
        return self.set_offset(offset, force=True)

    def _set_consumer_offset(self, new_remote_offset):
        remote_offset = max(self.consumer.offsets.values())
        logger.debug("Kafka_offset remote %s: %s to %s", self.key, remote_offset, new_remote_offset)
        self.consumer.seek(new_remote_offset - remote_offset, 1)

    def reset_consumer_offset(self, count):
        reset_offset = self.get_reset_offset()
        # 如果有新的重置点，那么当前游标设置为重置点
        if reset_offset and reset_offset != self.reset_offset:
            self.instance_offset = self.reset_offset = reset_offset
        # 如果第一次读这个 topic，那么当前游标设置为最新前 3 条
        if self._get_offset() is None:
            self.consumer.seek(0, 2)
            self.instance_offset = max(self.consumer.offsets.values()) - 3
        # 否则从 redis 读取游标
        else:
            self.instance_offset = self.get_offset()

        # 更新 client 的游标
        self._set_consumer_offset(self.instance_offset)

        new_local_offset = self.instance_offset + count
        if self.get_offset() < new_local_offset:
            self.instance_offset = self.set_offset(new_local_offset)

    def get_tail(self):
        self.consumer.seek(0, 2)
        if len(list(self.consumer.offsets.values())) > 0:
            return max(self.consumer.offsets.values())
        else:
            return 0

    def update_consumer_offset(self, count, messages):
        if not messages:
            self.instance_offset = self.set_offset(self.consumer.fetch_offsets[0])
        elif len(messages) < count:
            offset = messages[-1].offset + 1
            logger.debug("Kafka_offset local_desc %s: %s to %s", self.key, self.instance_offset, offset)
            self.instance_offset = self.set_offset(offset)
