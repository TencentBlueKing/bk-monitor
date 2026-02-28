"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import itertools
import logging
import socket
import uuid

import kafka
import kafka.errors
from django.conf import settings


logger = logging.getLogger("core.storage.kafka")


class KafkaQueueV2:
    def __init__(self, topic="", group_prefix="", kfk_conf=None):
        if kfk_conf:
            kafka_hosts = ["{}:{}".format(kfk_conf["domain"], kfk_conf["port"])]
        else:
            kafka_hosts = [f"{host}:{settings.KAFKA_PORT}" for host in settings.KAFKA_HOST]
        self.consumer_pool = {}
        self.topic = ""
        self.group_name = ""
        self.bootstrap_servers = kafka_hosts
        self.set_topic(topic, group_prefix)
        self.pod_id = socket.gethostname().rsplit("-", 1)[-1] or str(uuid.uuid4())[:8]

    def __del__(self):
        for consumer in self.consumer_pool.values():
            consumer.close()

    @classmethod
    def get_alert_kafka_queue(cls):
        kfk_conf = {"cluster_index": 0, "domain": settings.ALERT_KAFKA_HOST[0], "port": settings.ALERT_KAFKA_PORT}
        return cls(kfk_conf=kfk_conf)

    @classmethod
    def get_common_kafka_queue(cls):
        kfk_conf = {"cluster_index": 0, "domain": settings.KAFKA_HOST[0], "port": settings.KAFKA_PORT}
        return cls(kfk_conf=kfk_conf)

    def set_topic(self, topic, group_prefix=""):
        self.topic = topic
        self.group_name = f"{group_prefix}{settings.KAFKA_CONSUMER_GROUP}"

    def get_consumer(self):
        if not self.topic:
            raise ValueError("topic is empty, set_topic first")
        consumer_pool_key = f"{self.topic}-{self.group_name}-{self.pod_id}"
        # 增加初始化判断机制 关键值未赋值 则初始化不成功
        consumer = self.consumer_pool.get(consumer_pool_key)
        if not consumer:
            consumer = self._create_consumer(self.topic, self.group_name)
            self.consumer_pool[consumer_pool_key] = consumer
        return consumer

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
                    max_poll_interval_ms=300000,
                    session_timeout_ms=30000,
                    max_partition_fetch_bytes=1024 * 1024 * 5,  # 增大分区拉取量
                    partition_assignment_strategy=[kafka.coordinator.assignors.roundrobin.RoundRobinPartitionAssignor],
                    auto_offset_reset="latest",
                )
                consumer.subscribe([topic])
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
            raise Exception(f"topic {topic} load metadata failed")

    def reset_offset(self, latest=True):
        consumer = self.get_consumer()
        if latest:
            consumer.seek_to_end(*consumer._subscription.assigned_partitions())
        else:
            consumer.seek_to_beginning(*consumer._subscription.assigned_partitions())

    def _ensure_connected(self, consumer):
        """主动检查并重建消费者连接"""
        # 通过检查客户端连接字典判断是否存活
        if not consumer._client._conns:  # 没有活跃连接时触发重连
            # logger.warning("检测到Kafka连接断开，尝试主动重连...")
            consumer.close()
            del self.consumer_pool[f"{self.topic}-{self.group_name}-{self.pod_id}"]
            return self.get_consumer()
        return consumer

    def has_assigned_partitions(self):
        """检查当前消费组是否已分配分区"""
        try:
            consumer = self.get_consumer()
            consumer._coordinator.poll()
            # 检查消费者是否已分配分区且不为空集合
            return bool(consumer.assignment())
        except Exception as e:
            logger.warning(f"检查分区分配异常: {str(e)}")
            return False

    def has_reassigned_partitions(self):
        """检查分区是否发生重新分配"""
        try:
            consumer = self.get_consumer()
            current_assignment = frozenset(consumer.assignment())

            # 首次检查时初始化记录
            if not hasattr(self, "last_assignment"):
                self.last_assignment = current_assignment
                return False

            # 比较当前分配与上次记录是否一致
            is_reassigned = self.last_assignment != current_assignment
            self.last_assignment = current_assignment  # 更新分配记录
            return is_reassigned
        except Exception as e:
            logger.warning(f"检查分区重分配异常: {str(e)}")
            return False

    def take_raw(self, count=1, timeout=0.1):
        consumer = self._ensure_connected(self.get_consumer())
        records = consumer.poll(timeout_ms=timeout * 1000, max_records=count).values()
        messages = list(itertools.chain.from_iterable(records))
        consumer.commit()  # 手动提交保证可靠性
        logger.info(f"{consumer.assignment()} poll messages: {len(messages)}")
        return messages

    def take(self, count=1, timeout=0.1):
        return [m.value for m in self.take_raw(count, timeout)]
