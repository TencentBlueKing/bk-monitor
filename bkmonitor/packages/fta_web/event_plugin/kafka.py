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
import json

from kafka import KafkaConsumer, TopicPartition

from core.errors.event_plugin import KafkaConnectError, KafkaPartitionError


class KafkaManager(object):
    def __init__(self, server, port, topic, username=None, password=None):
        self.server = server
        self.port = int(port)
        self.topic = topic
        self.kafka_server = f"{server}:{port}"
        try:
            if username:
                self.consumer = KafkaConsumer(
                    self.topic,
                    bootstrap_servers=self.kafka_server,
                    security_protocol="SASL_PLAINTEXT",
                    sasl_mechanism="PLAIN",
                    sasl_plain_username=username,
                    sasl_plain_password=password,
                    request_timeout_ms=1000,
                    consumer_timeout_ms=1000,
                )
            else:
                self.consumer = KafkaConsumer(
                    self.topic, bootstrap_servers=self.kafka_server, request_timeout_ms=1000, consumer_timeout_ms=1000
                )
        except Exception as e:
            raise KafkaConnectError({"msg": e})

    def fetch_latest_messages(self, count=10):
        """
        读取kafka的数据
        :return:
        """
        self.consumer.poll(10)

        # 获取topic分区信息
        topic_partitions = self.consumer.partitions_for_topic(self.topic)
        if not topic_partitions:
            raise KafkaPartitionError()

        messages = []
        for partition in topic_partitions:

            # 获取该分区最大偏移量
            tp = TopicPartition(topic=self.topic, partition=partition)
            end_offset = self.consumer.end_offsets([tp])[tp]
            beginning_offset = self.consumer.beginning_offsets([tp])[tp]
            if not end_offset:
                continue

            self.consumer.seek(tp, max(end_offset - count, beginning_offset))

            # 消费消息
            for msg in self.consumer:
                try:
                    messages.insert(0, json.loads(msg.value.decode()))
                except Exception:
                    pass
                if len(messages) == count:
                    self.consumer.close()
                    return messages
                if msg.offset == end_offset - 1:
                    break

        self.consumer.close()
        return messages
