"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from unittest.mock import PropertyMock

import fakeredis
import pytest
from django.conf import settings

from metadata import config
from metadata.feature_flag import FeatureFlagRedisSync
from metadata.tests.conftest import MockHashConsul
from metadata.utils.redis_tools import RedisTools


class TestFeatureFlagRedisSync:
    def test_uses_unify_query_shared_paths(self):
        assert FeatureFlagRedisSync.CONSUL_SOURCE_PATH == f"{config.MIGRATION_CONSUL_PATH}/unify-query/data/feature_flag"
        assert FeatureFlagRedisSync.REDIS_TARGET_KEY == f"{settings.BACKEND_APP_CODE}:unify-query:data:feature_flag"
        assert FeatureFlagRedisSync.REDIS_CHANNEL == f"{FeatureFlagRedisSync.REDIS_TARGET_KEY}:feature_flag_channel"

    @pytest.fixture
    def redis_client(self, mocker):
        client = fakeredis.FakeRedis()
        mocker.patch.object(RedisTools, "client", new_callable=PropertyMock, return_value=client)
        return client

    @pytest.fixture
    def consul_client(self, mocker):
        client = MockHashConsul()
        client._kv_store.clear()
        client._call_history.clear()
        mocker.patch("metadata.feature_flag.consul_tools.HashConsul", return_value=client)
        return client

    def test_syncs_consul_snapshot_to_redis(self, redis_client, consul_client, mocker):
        snapshot = {
            "must-vm-query": {
                "variations": {"Default": False, "enabled": True},
                "targeting": [],
                "defaultRule": {"variation": "Default"},
            }
        }
        consul_client.put(FeatureFlagRedisSync.CONSUL_SOURCE_PATH, snapshot)
        publish_spy = mocker.spy(redis_client, "publish")

        FeatureFlagRedisSync.sync_from_consul()

        assert json.loads(redis_client.get(FeatureFlagRedisSync.REDIS_TARGET_KEY)) == snapshot
        publish_spy.assert_called_once_with(FeatureFlagRedisSync.REDIS_CHANNEL, json.dumps(snapshot))

    def test_missing_consul_snapshot_clears_redis(self, redis_client, consul_client, mocker):
        redis_client.set(FeatureFlagRedisSync.REDIS_TARGET_KEY, json.dumps({"stale-flag": {}}))
        publish_spy = mocker.spy(redis_client, "publish")

        FeatureFlagRedisSync.sync_from_consul()

        assert redis_client.get(FeatureFlagRedisSync.REDIS_TARGET_KEY) is None
        publish_spy.assert_called_once_with(FeatureFlagRedisSync.REDIS_CHANNEL, "{}")

    @pytest.mark.parametrize("snapshot", ["not-json", "[]", "null"])
    def test_rejects_invalid_consul_snapshot(self, redis_client, consul_client, snapshot):
        consul_client._kv_store[FeatureFlagRedisSync.CONSUL_SOURCE_PATH] = {
            "Key": FeatureFlagRedisSync.CONSUL_SOURCE_PATH,
            "Value": snapshot,
        }

        with pytest.raises(ValueError):
            FeatureFlagRedisSync.sync_from_consul()

        assert redis_client.get(FeatureFlagRedisSync.REDIS_TARGET_KEY) is None

    def test_raises_when_redis_write_fails(self, redis_client, consul_client, mocker):
        consul_client.put(FeatureFlagRedisSync.CONSUL_SOURCE_PATH, {"flag": {}})
        mocker.patch.object(redis_client, "set", return_value=False)

        with pytest.raises(RuntimeError, match="set feature flag config to redis failed"):
            FeatureFlagRedisSync.sync_from_consul()

    def test_raises_when_redis_publish_fails(self, redis_client, consul_client, mocker):
        consul_client.put(FeatureFlagRedisSync.CONSUL_SOURCE_PATH, {"flag": {}})
        mocker.patch.object(redis_client, "publish", side_effect=RuntimeError("redis unavailable"))

        with pytest.raises(RuntimeError, match="redis unavailable"):
            FeatureFlagRedisSync.sync_from_consul()
