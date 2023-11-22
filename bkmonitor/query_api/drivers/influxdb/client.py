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
"""
usage:
>>>from query_api.drivers.influxdb import pool
>>>client = pool.get_client()
>>>client = pool.get_client(host="127.0.0.1", port=8086)
"""
__all__ = ["pool"]


from influxdb import InfluxDBClient

from query_api.drivers.client_pool import BaseClientFactory, ClientPoolManage


class InfluxDBClientFactory(BaseClientFactory):
    def client_key(self, host="127.0.0.1", port=8086, **context):
        return "{}:{}".format(host, port)

    def new_client(self, host="127.0.0.1", port=8086, retries=-1, **context):
        key_words = [
            "host",
            "port",
            "username",
            "password",
            "database",
            "ssl",
            "verify_ssl",
            "timeout",
            "retries",
            "use_udp",
            "udp_port",
            "proxies",
            "pool_size",
            "path",
        ]
        for k in list(context.keys()):
            if k not in key_words:
                context.pop(k)

        return InfluxDBClient(host=host, port=port, retries=retries, **context)

    @staticmethod
    def client_close_fn(client):
        client.close()


pool = ClientPoolManage(InfluxDBClientFactory(), max_poll_size=10)
