"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest
from datetime import datetime

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.bkm_cli.cache import read_config_cache


class TestReadConfigCacheDispatch:
    def test_missing_cache_type_raises(self):
        with pytest.raises(CustomException, match="cache_type is required"):
            read_config_cache({"params": {}})

    def test_params_not_dict_raises(self):
        with pytest.raises(CustomException, match="params must be an object"):
            read_config_cache({"cache_type": "strategy", "params": "not_a_dict"})

    def test_unknown_cache_type_raises(self):
        with pytest.raises(CustomException, match="不支持的 cache_type"):
            read_config_cache({"cache_type": "unknown", "params": {}})


class TestStrategyCacheType:
    def test_strategy_found(self, mocker):
        mocker.patch(
            "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
            return_value={"id": 1, "name": "test_strategy", "is_enabled": True},
        )
        result = read_config_cache(
            {
                "cache_type": "strategy",
                "params": {"strategy_id": 1},
            }
        )
        assert result["cache_type"] == "strategy"
        assert result["exists"] is True
        assert result["data"]["id"] == 1
        assert result["data"]["name"] == "test_strategy"

    def test_strategy_not_found(self, mocker):
        mocker.patch(
            "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
            return_value=None,
        )
        result = read_config_cache(
            {
                "cache_type": "strategy",
                "params": {"strategy_id": 99999},
            }
        )
        assert result["exists"] is False
        assert result["data"] is None

    def test_strategy_missing_id_raises(self):
        with pytest.raises(CustomException, match="strategy_id is required"):
            read_config_cache({"cache_type": "strategy", "params": {}})

    def test_strategy_id_not_integer_raises(self):
        with pytest.raises(CustomException, match="must be an integer"):
            read_config_cache({"cache_type": "strategy", "params": {"strategy_id": "abc"}})


class TestHostCacheType:
    def test_host_found(self, mocker):
        from api.cmdb.define import Host

        fake_host = Host(
            {
                "bk_host_innerip": "127.0.0.1",
                "bk_cloud_id": 0,
                "bk_host_id": 100,
                "bk_biz_id": 2,
                "bk_host_name": "test-host",
                "bk_os_name": "linux",
            }
        )
        mocker.patch(
            "alarm_backends.core.cache.cmdb.host.HostManager.get",
            return_value=fake_host,
        )
        result = read_config_cache(
            {
                "cache_type": "host",
                "params": {"ip": "127.0.0.1", "bk_cloud_id": 0},
            }
        )
        assert result["exists"] is True
        assert result["data"]["bk_host_innerip"] == "127.0.0.1"
        assert result["data"]["bk_cloud_id"] == 0
        assert result["data"]["bk_host_id"] == 100

    def test_host_not_found(self, mocker):
        mocker.patch(
            "alarm_backends.core.cache.cmdb.host.HostManager.get",
            return_value=None,
        )
        result = read_config_cache(
            {
                "cache_type": "host",
                "params": {"ip": "127.0.0.2", "bk_cloud_id": 0},
            }
        )
        assert result["exists"] is False
        assert result["data"] is None

    def test_host_missing_ip_raises(self):
        with pytest.raises(CustomException, match="ip is required"):
            read_config_cache({"cache_type": "host", "params": {"bk_cloud_id": 0}})

    def test_host_default_bk_tenant_id(self, mocker):
        from api.cmdb.define import Host

        fake_host = Host({"bk_host_innerip": "127.0.0.1", "bk_cloud_id": 0})
        mock_get = mocker.patch(
            "alarm_backends.core.cache.cmdb.host.HostManager.get",
            return_value=fake_host,
        )
        read_config_cache(
            {
                "cache_type": "host",
                "params": {"ip": "127.0.0.1", "bk_cloud_id": 0},
            }
        )
        assert mock_get.call_args.kwargs["bk_tenant_id"] == "system"


class TestAssignBizCacheType:
    def test_assign_biz_found(self, mocker):
        mocker.patch(
            "alarm_backends.core.cache.assign.AssignCacheManager.get_assign_priority_by_biz_id",
            return_value=[10, 20],
        )
        mocker.patch(
            "alarm_backends.core.cache.assign.AssignCacheManager.get_assign_groups_by_priority",
            side_effect=lambda biz_id, priority: {1, 2} if priority == 10 else {3},
        )
        mocker.patch(
            "alarm_backends.core.cache.assign.AssignCacheManager.get_assign_rules_by_group",
            side_effect=lambda biz_id, group_id: [{"id": group_id, "name": f"rule_{group_id}"}],
        )
        result = read_config_cache(
            {
                "cache_type": "assign.biz",
                "params": {"bk_biz_id": 2},
            }
        )
        assert result["exists"] is True
        assert result["data"]["bk_biz_id"] == 2
        assert "10" in result["data"]["groups"]
        assert "20" in result["data"]["groups"]
        assert result["data"]["groups"]["10"] == [1, 2]
        assert result["data"]["groups"]["20"] == [3]

    def test_assign_biz_empty(self, mocker):
        mocker.patch(
            "alarm_backends.core.cache.assign.AssignCacheManager.get_assign_priority_by_biz_id",
            return_value=[],
        )
        result = read_config_cache(
            {
                "cache_type": "assign.biz",
                "params": {"bk_biz_id": 2},
            }
        )
        assert result["exists"] is False
        assert result["data"]["priorities"] == []

    def test_assign_missing_biz_id_raises(self):
        with pytest.raises(CustomException, match="bk_biz_id is required"):
            read_config_cache({"cache_type": "assign.biz", "params": {}})


class TestShieldBizCacheType:
    def test_shield_biz_found(self, mocker):
        fake_shields = [
            {
                "id": 1,
                "bk_biz_id": 2,
                "begin_time": datetime(2019, 10, 3, 16, 0),
                "end_time": datetime(2019, 10, 10, 16, 0),
                "failure_time": datetime(2019, 10, 10, 16, 0),
                "create_time": datetime(2019, 10, 4, 8, 26, 34),
                "update_time": datetime(2019, 10, 4, 8, 26, 34),
                "is_enabled": True,
            }
        ]
        mocker.patch(
            "alarm_backends.core.cache.shield.ShieldCacheManager.get_shields_by_biz_id",
            return_value=fake_shields,
        )
        result = read_config_cache(
            {
                "cache_type": "shield.biz",
                "params": {"bk_biz_id": 2},
            }
        )
        assert result["exists"] is True
        assert len(result["data"]) == 1
        # datetime fields should be ISO strings
        assert isinstance(result["data"][0]["begin_time"], str)
        assert "2019-10-03" in result["data"][0]["begin_time"]
        assert isinstance(result["data"][0]["end_time"], str)
        assert isinstance(result["data"][0]["create_time"], str)

    def test_shield_biz_empty(self, mocker):
        mocker.patch(
            "alarm_backends.core.cache.shield.ShieldCacheManager.get_shields_by_biz_id",
            return_value=[],
        )
        result = read_config_cache(
            {
                "cache_type": "shield.biz",
                "params": {"bk_biz_id": 9999},
            }
        )
        assert result["exists"] is False
        assert result["data"] == []

    def test_shield_missing_biz_id_raises(self):
        with pytest.raises(CustomException, match="bk_biz_id is required"):
            read_config_cache({"cache_type": "shield.biz", "params": {}})
