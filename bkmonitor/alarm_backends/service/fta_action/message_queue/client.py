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

    # message.timeout.ms 与其 librdkafka 别名 delivery.timeout.ms 等价（同一投递时限）。
    # 仅当二者都未显式配置时才注入默认值，否则会额外注入冲突值、静默覆盖调用方的设置。
    DELIVERY_TIMEOUT_KEYS = ("message.timeout.ms", "delivery.timeout.ms")
    DEFAULT_DELIVERY_TIMEOUT_MS = 3000

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

        # 限定单条消息的投递时限，避免 broker 不可达时阻塞到 librdkafka
        # 默认的 message.timeout.ms(=5min)，从而拖垮 fta_action 执行队列。
        # 调用方通过 message.timeout.ms 或其别名 delivery.timeout.ms 显式指定时，尊重其取值，
        # 不再额外注入默认值（否则会与别名冲突、静默覆盖调用方的投递时限）。
        configured = [producer_conf[k] for k in self.DELIVERY_TIMEOUT_KEYS if k in producer_conf]
        if configured:
            raw_timeout = configured[-1]
        else:
            producer_conf["message.timeout.ms"] = self.DEFAULT_DELIVERY_TIMEOUT_MS
            raw_timeout = self.DEFAULT_DELIVERY_TIMEOUT_MS
        # flush 的等待窗口由生效的投递时限推导（再加 1s 余量等待投递回调），而不是写死常量：
        # 否则当调用方调大投递时限时，flush 会早于其返回，把本可在时限内成功的投递误判为失败。
        # 兼容 int/str/float 配置形式（librdkafka 统一转为字符串）；
        # 0 在 librdkafka 语义里是“无限”，与有界发送矛盾，退回默认值。
        try:
            timeout_ms = int(float(raw_timeout))
        except (TypeError, ValueError):
            timeout_ms = self.DEFAULT_DELIVERY_TIMEOUT_MS
        self.flush_timeout = (timeout_ms or self.DEFAULT_DELIVERY_TIMEOUT_MS) / 1000 + 1
        self.client = Producer(producer_conf)

    def send(self, message: str):
        """
        发送消息

        confluent_kafka 的 produce 仅为异步入队，broker 不可达/认证失败不会同步抛错，
        投递结果只能通过 delivery 回调获取。这里注册回调并检查 flush 的返回值（仍在
        队列中的消息数），任一表明未投递成功即抛异常，交由上层置为 FAILURE，
        从而保证推送失败能被如实统计，且不会无界阻塞。
        """
        delivery_error = {}

        def _on_delivery(err, _msg):
            if err is not None:
                delivery_error["err"] = err

        try:
            self.client.produce(
                topic=self.topic,
                value=message.encode("utf-8"),
                on_delivery=_on_delivery,
            )
            # 有界等待投递完成；返回值为仍未投递的消息数
            remaining = self.client.flush(timeout=self.flush_timeout)
            if remaining > 0:
                raise RuntimeError(f"kafka flush timeout, {remaining} message(s) not delivered to topic {self.topic}")
            if delivery_error:
                raise RuntimeError(f"kafka delivery failed for topic {self.topic}: {delivery_error['err']}")
        finally:
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
