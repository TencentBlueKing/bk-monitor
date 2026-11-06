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

from utils.redis_client import RedisClient


@pytest.mark.parametrize("mode", ["sentinel", "standalone"])
@pytest.mark.parametrize("db_value", [None, "0", "7"], ids=["default-db", "db-zero", "nonzero-db"])
def test_from_envs_uses_db_from_selected_prefix(monkeypatch, mocker, mode, db_value):
    prefix = "TEST_METADATA"
    env = {
        f"{prefix}_REDIS_MODE": mode,
        f"{prefix}_REDIS_HOST": "redis-standalone.example.com",
        f"{prefix}_REDIS_PORT": "6379",
        f"{prefix}_REDIS_PASSWORD": "test-password",
        f"{prefix}_REDIS_SENTINEL_HOST": "sentinel.example.com",
        f"{prefix}_REDIS_SENTINEL_PORT": "26379",
        f"{prefix}_REDIS_SENTINEL_PASSWORD": "test-sentinel-password",
        f"{prefix}_REDIS_SENTINEL_MASTER_NAME": "test-master",
        "BK_MONITOR_REDIS_DB": "9",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    if db_value is None:
        monkeypatch.delenv(f"{prefix}_REDIS_DB", raising=False)
    else:
        monkeypatch.setenv(f"{prefix}_REDIS_DB", db_value)

    sentinel = mocker.patch("utils.redis_client.Sentinel")
    sentinel.return_value.discover_master.return_value = ("redis-master.example.com", 6380)

    client = RedisClient.from_envs(prefix=prefix)
    try:
        connection = client.connection_pool.connection_kwargs
        assert int(connection["db"]) == int(db_value or 0)
        assert connection["password"] == "test-password"
        if mode == "sentinel":
            assert connection["host"] == "redis-master.example.com"
            assert connection["port"] == 6380
            sentinel.return_value.discover_master.assert_called_once_with("test-master")
        else:
            assert connection["host"] == "redis-standalone.example.com"
            assert int(connection["port"]) == 6379
            sentinel.assert_not_called()
    finally:
        client.close()
