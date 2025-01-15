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
import time
from typing import Callable, Dict

import pika
from django.utils.translation import gettext_lazy as _
from kombu.utils.url import url_to_parts
from pika.exceptions import ChannelClosedByBroker

logger = logging.getLogger()


class RabbitMQClient(object):
    _instance = None

    def __init__(self, broker_url: str) -> None:
        try:
            schema, host, port, user, password, path, query = url_to_parts(broker_url)
            self.schema = schema
            self.host = host
            self.port = port
            self.user = user
            self.password = password
            self.path = path
            self.query = query

        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Failed to get rabbitmq infomation, err: {e}")

    def ping(self) -> Dict:
        result = {"status": False, "data": None, "message": "", "suggestion": ""}
        start_time = time.time()
        try:
            auth = pika.PlainCredentials(self.user, self.password)
            connection = pika.BlockingConnection(pika.ConnectionParameters(self.host, self.port, self.path, auth))
            if connection:
                result["status"] = True
                self.connection = connection
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"failed to ping rabbitmq, msg: {e}")
            result["message"] = str(e)
            result["suggestion"] = _("确认RabbitMQ是否可用")
        spend_time = time.time() - start_time
        result["data"] = "{}ms".format(int(spend_time * 1000))
        return result

    def get_queue_len(self, queue_name: str) -> Dict:
        result = {"status": False, "data": None, "message": ""}
        try:
            channel = self.connection.channel()
            declear_queue_result = channel.queue_declare(queue=queue_name, durable=True)
            result["data"] = declear_queue_result.method.message_count
            result["status"] = True
            channel.close()
        except ChannelClosedByBroker as e:
            logger.error(f"failed to get llen[{queue_name}], err: {e}")
            result["message"] = str(e)
        return result

    def start_consuming(self, queue_name: str, callback: Callable = None) -> None:
        try:
            channel = self.connection.channel()
            channel.queue_declare(queue=queue_name, durable=True)
            if callback:
                channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=False)
            channel.start_consuming()
        except ChannelClosedByBroker as e:
            logger.exception(f"failed to get llen[{queue_name}], err: {e}")
