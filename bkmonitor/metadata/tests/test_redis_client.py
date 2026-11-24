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
from redis.sentinel import Sentinel, SentinelConnectionPool

from utils.redis_client import RedisClient


PREFIX = "TEST_METADATA"


def set_redis_envs(monkeypatch, mode, db_value=None):
    env = {
        f"{PREFIX}_REDIS_MODE": mode,
        f"{PREFIX}_REDIS_HOST": "redis-standalone.example.com",
        f"{PREFIX}_REDIS_PORT": "6379",
        f"{PREFIX}_REDIS_PASSWORD": "test-password",
        f"{PREFIX}_REDIS_SENTINEL_HOST": "sentinel-a.example.com;sentinel-b.example.com;",
        f"{PREFIX}_REDIS_SENTINEL_PORT": "26379",
        f"{PREFIX}_REDIS_SENTINEL_PASSWORD": "test-sentinel-password",
        f"{PREFIX}_REDIS_SENTINEL_MASTER_NAME": "test-master",
        "BK_MONITOR_REDIS_DB": "9",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    if db_value is None:
        monkeypatch.delenv(f"{PREFIX}_REDIS_DB", raising=False)
    else:
        monkeypatch.setenv(f"{PREFIX}_REDIS_DB", db_value)


@pytest.mark.parametrize("mode", ["sentinel", "standalone"])
@pytest.mark.parametrize("db_value", [None, "0", "7"], ids=["default-db", "db-zero", "nonzero-db"])
def test_from_envs_uses_db_from_selected_prefix(monkeypatch, mocker, mode, db_value):
    set_redis_envs(monkeypatch, mode, db_value)
    discover_master = mocker.patch.object(Sentinel, "discover_master")

    client = RedisClient.from_envs(prefix=PREFIX)
    try:
        pool = client.connection_pool
        connection = pool.connection_kwargs
        assert int(connection["db"]) == int(db_value or 0)
        assert connection["password"] == "test-password"
        if mode == "sentinel":
            assert isinstance(pool, SentinelConnectionPool)
            assert pool.service_name == "test-master"
            assert connection["db"] == int(db_value or 0)
            sentinels = pool.sentinel_manager.sentinels
            assert sorted(s.connection_pool.connection_kwargs["host"] for s in sentinels) == [
                "sentinel-a.example.com",
                "sentinel-b.example.com",
            ]
            assert all(s.connection_pool.connection_kwargs["port"] == 26379 for s in sentinels)
            assert all(s.connection_pool.connection_kwargs["password"] == "test-sentinel-password" for s in sentinels)
        else:
            assert not isinstance(pool, SentinelConnectionPool)
            assert connection["host"] == "redis-standalone.example.com"
            assert int(connection["port"]) == 6379
        discover_master.assert_not_called()
    finally:
        client.close()


def test_sentinel_client_follows_master_after_failover(monkeypatch, mocker):
    set_redis_envs(monkeypatch, "sentinel")
    discover_master = mocker.patch.object(
        Sentinel,
        "discover_master",
        side_effect=[("redis-old-master.example.com", 6379), ("redis-new-master.example.com", 6380)],
    )

    client = RedisClient.from_envs(prefix=PREFIX)
    try:
        assert client.connection_pool.get_master_address() == ("redis-old-master.example.com", 6379)
        assert client.connection_pool.get_master_address() == ("redis-new-master.example.com", 6380)
        assert discover_master.call_args_list == [mocker.call("test-master"), mocker.call("test-master")]
    finally:
        client.close()
