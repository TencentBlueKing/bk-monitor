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

import redis
from django.conf import settings
from kafka import KafkaProducer
from six.moves.urllib.parse import unquote, urlparse

logger = logging.getLogger("action")


class BaseClient(object):
    def send(self, message):
        raise NotImplementedError


class KafKaClient(object):
    """
    KafKa客户端
    """

    def __init__(self, uri):
        uri_obj = urlparse(uri)
        params = {
            "bootstrap_servers": "{}:{}".format(uri_obj.hostname, uri_obj.port),
        }

        if uri_obj.username:
            params.update(
                {"sasl_plain_username": unquote(uri_obj.username), "sasl_plain_password": unquote(uri_obj.password)}
            )

        self.topic = uri_obj.path.strip("/")
        if not self.topic:
            raise ValueError("KafKa URI({}) has not topic".format(uri))

        self.client = KafkaProducer(**params)

    def send(self, message: str):
        """
        发送消息
        """
        try:
            self.client.send(
                self.topic,
                message.encode(),
            )
            self.client.flush(timeout=3)
        finally:
            self.client.close()


class RedisClient(object):
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
            logger.error("Redis URI({}) parse error, {}".format(uri, e))
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
    :param uri: 消息队列的连接URI
    :return: Client
    """
    uri_obj = urlparse(uri)

    client_class = SchemaClientMapping.get(uri_obj.scheme)
    if not client_class:
        raise Exception("message queue schema {} is not support".format(uri_obj.scheme))

    return client_class(uri)
