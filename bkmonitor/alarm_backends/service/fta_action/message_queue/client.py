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
from typing import Any

import redis
from confluent_kafka import Producer
from django.conf import settings
from urllib.parse import urlparse, unquote

logger = logging.getLogger("action")


class BaseClient:
    def send(self, message):
        raise NotImplementedError


class KafKaClient:
    """
    KafKa客户端
    """

    def __init__(self, conf: Any):
        """
        支持两种输入：
        1) 字符串 DSN：kafka://host:port/topic （不包含用户名/密码）
        2) 结构化字典：必须包含 bootstrap.servers 与 topic，其它鉴权字段按示例配置
        conf = {
                'bootstrap.servers': 'host:port',
                'security.protocol': 'SASL_PLAINTEXT',  # 明文传输；若集群启用SSL则用 SASL_SSL
                'sasl.mechanism': 'SCRAM-SHA-512',
                'sasl.username': 'username',
                'sasl.password': 'password',
            }
        """
        if isinstance(conf, str):
            uri_obj = urlparse(conf)
            self.topic = uri_obj.path.strip("/")
            if not self.topic:
                raise ValueError(f"kafka uri({conf}) has no topic")
            bootstrap = f"{uri_obj.hostname}:{uri_obj.port}"
            producer_conf: dict[str, Any] = {"bootstrap.servers": bootstrap}
        elif isinstance(conf, dict):
            self.topic = conf.get("topic", "")
            if not self.topic:
                raise ValueError(f"kafka config (dict) requires 'topic' config: {conf}")
            _conf = {k: v for k, v in conf.items() if k != "topic"}
            producer_conf = dict(_conf)
        else:
            raise ValueError(f"unsupported kafka config type: {conf}")

        self.client = Producer(producer_conf)

    def send(self, message: str):
        """
        发送消息
        """
        try:
            self.client.produce(topic=self.topic, value=message.encode("utf-8"))
            # 等待发送完成（含重试）
            self.client.flush(timeout=3)
        finally:
            self.client.flush()  # 二次确保消息发送
            del self.client  # 释放生产者对象


class RedisClient:
    """
    Redis客户端
    """

    def __init__(self, uri):
        uri_obj = urlparse(uri)
        try:
            db, key = uri_obj.path.strip("/").split("/")
            db = int(db)
            assert len(key) > 0
        except Exception as e:
            logger.error(f"redis uri({uri}) parse error, {e}")
            raise e

        self.key = key
        self.client = redis.Redis(
            host=uri_obj.hostname,
            port=uri_obj.port,
            decode_responses=True,
            db=db,
            password=unquote(uri_obj.password) if uri_obj.password else None,
        )

        self.MAX_LENGTH = int(getattr(settings, "MESSAGE_QUEUE_MAX_LENGTH", 0) or 0)

    def send(self, message: str):
        """
        发送消息
        """
        self.client.lpush(self.key, message.encode())

        if self.MAX_LENGTH:
            self.client.ltrim(self.key, 0, int(self.MAX_LENGTH) - 1)


SchemaClientMapping = {
    "kafka": KafKaClient,
    "redis": RedisClient,
}


def get_client(uri):
    """
    获取Client
    :param uri: 消息队列的连接URI 或结构化Kafka配置字典
    :return: Client
    """
    # 结构化Kafka配置
    if isinstance(uri, dict):
        return KafKaClient(uri)

    uri_obj = urlparse(uri)
    client_class = SchemaClientMapping.get(uri_obj.scheme)
    if not client_class:
        raise Exception(f"message queue schema {uri_obj.scheme} is not support")
    return client_class(uri)
