# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import mock
import pytest
from influxdb.resultset import ResultSet

from core.drf_resource.exceptions import CustomException
from query_api.drivers import influxdb
from query_api.exceptions import StorageNotSupported
from query_api.resources import GetTSDataResource
from query_api.tests.test_influxdb_drivers import gen_mocked_cluster_info

get_ts_data = GetTSDataResource()
pytestmark = pytest.mark.django_db


def test_get_ts_data_resource():
    # 空sql
    with pytest.raises(CustomException):
        get_ts_data(sql="")

    # 参数格式错误
    with pytest.raises(CustomException):
        get_ts_data("select count(*) from 2_system_cpu_summary where time>'today'")

    table = "cpu_summary"
    database = "system"

    with pytest.raises(StorageNotSupported):
        with mock.patch(
            "metadata.models.ResultTable.get_result_table",
            return_value=influxdb.ResultTable(
                table_id="{}.{}".format(database, table), schema_type="fixed", default_storage="mysql"
            ),
        ):
            get_ts_data(sql="select count(*) from 2_system_cpu_summary where time>'today'")

    # mock requirements
    mocked_rt = influxdb.ResultTable(
        table_id="{}.{}".format(database, table), schema_type="fixed", default_storage="influxdb"
    )
    mocked_cluster_info = gen_mocked_cluster_info(database, table)

    with mock.patch("metadata.models.ResultTable.get_result_table", return_value=mocked_rt):
        with mock.patch("metadata.models.ResultTable.get_result_table_storage_info", return_value=mocked_cluster_info):
            mocked_resultset = ResultSet(
                {
                    "series": [
                        {
                            "columns": ["time", "mean", "node_id"],
                            "name": "heartbeat",
                            "values": [[1504225680000, 2, "1"], [1504225740000, 3, "2"]],
                        }
                    ],
                    "statement_id": 0,
                }
            )
            with mock.patch("influxdb.client.InfluxDBClient.query", return_value=mocked_resultset):
                get_ts_data(sql="select count(*) from 2_system_cpu_summary where time>'today'")
