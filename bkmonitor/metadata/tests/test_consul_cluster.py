"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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


class MockHashConsul:
    result_list = []

    def put(self, key, value):
        self.result_list.append({"key": key, "value": value})


class MockClusterList(UserList):
    def count(self):
        return len(self.data)


class TestConsulCluster:
    def test_refresh_consul_cluster_config(self, mocker):
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

    def test_refresh_consul_data_source_config(self, mocker):
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

    def test_fta_worker_takeover(self, mocker, settings):
        settings.FTA_CLEAN_ENABLED = True
        settings.FTA_CLEAN_ALL = False
        settings.FTA_CLEAN_DATA_IDS = {42}
        consul = mocker.patch("metadata.utils.consul_tools.HashConsul").return_value
        mocker.patch.object(DataSource, "to_json", return_value={})
        source = DataSource(bk_data_id=42, etl_config="bk_fta_event", is_enable=True, created_from="bkgse")
        source.refresh_consul_config()
        consul.put.assert_not_called()
        source.bk_data_id = 43
        source.refresh_consul_config()
        assert consul.put.call_count == 1
        settings.FTA_CLEAN_ALL = True
        source.refresh_consul_config()
        assert consul.put.call_count == 1
        source.etl_config = "anti_ddos_origin_data"
        source.refresh_consul_config()
        assert consul.put.call_count == 2
        source.etl_config = "bk_fta_event"
        settings.FTA_CLEAN_ENABLED = False
        source.refresh_consul_config()
        assert consul.put.call_count == 3
