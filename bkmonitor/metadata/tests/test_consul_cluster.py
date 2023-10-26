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


from collections import UserList

from metadata.models import DataSource
from metadata.models.constants import IGNORED_CONSUL_SYNC_DATA_IDS
from metadata.models.influxdb_cluster import InfluxDBClusterInfo


class MockHashConsul(object):
    result_list = []

    def put(self, key, value):
        self.result_list.append({"key": key, "value": value})


class MockClusterList(UserList):
    def count(self):
        return len(self.data)


class TestConsulCluster(object):
    def test_refresh_consul_cluster_config(self, mocker, patch_redis_tools):
        cluster_host_list = MockClusterList()
        cluster_host_list.append(InfluxDBClusterInfo(host_name="host1", cluster_name="cluster1", host_readable=True))
        cluster_host_list.append(InfluxDBClusterInfo(host_name="host2", cluster_name="cluster1", host_readable=False))
        mocker.patch("metadata.models.influxdb_cluster.InfluxDBClusterInfo.objects.all", return_value=cluster_host_list)
        mock_hash_consul = MockHashConsul()
        mocker.patch("metadata.utils.consul_tools.HashConsul", return_value=mock_hash_consul)
        InfluxDBClusterInfo.refresh_consul_cluster_config()
        assert mock_hash_consul.result_list[0]["key"] == "/".join([InfluxDBClusterInfo.CONSUL_PREFIX_PATH, "cluster1"])
        assert mock_hash_consul.result_list[0]["value"] == {
            "host_list": ["host1", "host2"],
            "unreadable_host_list": ["host2"],
        }

    def test_refresh_consul_data_source_config(self, mocker, patch_redis_tools):

        data_source_list = [DataSource(bk_data_id=data_id) for data_id in IGNORED_CONSUL_SYNC_DATA_IDS]
        data_source_list.append(DataSource(bk_data_id=12345))
        mocker.patch("metadata.models.DataSource.objects.all", return_value=data_source_list)
        mocker.patch("metadata.models.DataSource.to_json", return_value={})
        mock_hash_consul = MockHashConsul()
        mocker.patch("metadata.utils.consul_tools.HashConsul", return_value=mock_hash_consul)
        for ds in data_source_list:
            ds.refresh_consul_config()

        assert len(mock_hash_consul.result_list) == 1
        assert mock_hash_consul.result_list[0]["key"] == DataSource(bk_data_id=12345).consul_config_path
