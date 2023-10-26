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
from query_api.drivers.influxdb import pool as influxdb_pool


class TestInfluxDBClientPool(object):
    def test_poll_size(self):

        connect_args_list = [{"host": "127.0.0.1", "port": i} for i in range(8086, 8100)]
        for connect_args in connect_args_list:
            influxdb_pool.get_client(**connect_args)

        influxdb_pool.get_client(**{"host": "127.0.0.1", "port": 8096, "other": "test"})
        influxdb_pool.get_client(**{"host": "127.0.0.1", "port": 8100, "other": "test"})

        assert influxdb_pool.is_full and influxdb_pool.size == influxdb_pool.max_poll_size
