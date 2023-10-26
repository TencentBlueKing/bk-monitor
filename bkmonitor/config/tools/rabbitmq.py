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

import os

from config.tools.environment import PAAS_VERSION


def get_rabbitmq_settings(app_code: str, backend=False):
    """
    获取RabbitMQ配置及Broker URL
    """

    if backend:
        host = os.environ.get("BK_MONITOR_RABBITMQ_HOST", "rabbitmq.service.consul")
        port = int(os.environ.get("BK_MONITOR_RABBITMQ_PORT", 5672))
        vhost = os.environ.get("BK_MONITOR_RABBITMQ_VHOST", app_code)
        user = os.environ.get("BK_MONITOR_RABBITMQ_USERNAME", app_code)
        password = os.environ.get("BK_MONITOR_RABBITMQ_PASSWORD", "")
    elif PAAS_VERSION == "V2":
        broker_url = os.environ.get("BK_BROKER_URL", "amqp://guest:guest@127.0.0.1:5672/")[7:]
        broker_url, vhost = broker_url.split("/")
        user, broker_url = broker_url.split(":", 1)
        password, broker_url = broker_url.split("@", 1)
        host, port = broker_url.split(":", 1)
        port = int(port)
    else:
        vhost = os.getenv("RABBITMQ_VHOST", "")
        port = int(os.getenv("RABBITMQ_PORT", 5672))
        host = os.getenv("RABBITMQ_HOST", "")
        user = os.getenv("RABBITMQ_USER", "guest")
        password = os.getenv("RABBITMQ_PASSWORD", "guest")

    broker_url = "amqp://{user}:{password}@{host}:{port}/{vhost}".format(
        user=user, password=password, host=host, port=port, vhost=vhost
    )
    return host, port, vhost, user, password, broker_url
