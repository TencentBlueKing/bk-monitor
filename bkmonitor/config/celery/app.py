"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from urllib.parse import quote, urlsplit, urlunsplit

from celery import Celery

from config import kms


def _authenticated_url(url, userinfo):
    if isinstance(url, list | tuple):
        return type(url)(_authenticated_url(item, userinfo) for item in url)
    if not isinstance(url, str) or not url:
        raise ValueError
    if ";" in url:
        return ";".join(_authenticated_url(item, userinfo) for item in url.split(";"))
    broker = urlsplit(url)
    if broker.scheme not in {"amqp", "amqps", "pyamqp"}:
        raise ValueError
    host = broker.netloc.rsplit("@", 1)[-1]
    return urlunsplit(broker._replace(netloc=f"{userinfo}@{host}"))


class MonitorCelery(Celery):
    broker_account = "saas"

    def _connection(self, url, *args, **kwargs):
        # Celery has already selected the environment, read/write or default URL.
        # Keep its failover topology and apply this app's credentials to each host.
        if kms.enabled():
            user = kms.value("rabbitmq", self.broker_account, "username")
            password = kms.value("rabbitmq", self.broker_account, "password")
            try:
                url = _authenticated_url(url, f"{quote(user, safe='')}:{quote(password, safe='')}")
            except (ValueError, TypeError):
                raise kms.KMSConfigurationError("KMS requires a valid RabbitMQ broker URL") from None
            if password == "":
                # pyamqp defaults an empty URL password to "guest". Its transport
                # options are applied afterwards, when building the AMQP client.
                kwargs["transport_options"] = {**(kwargs.get("transport_options") or {}), "password": ""}
        return super()._connection(url, *args, **kwargs)


class SchedulerCelery(MonitorCelery):
    broker_account = "backend"
