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
from metadata.feature_flag import FeatureFlagRedisSync, FeatureFlagSourceMissingError
from metadata.tests.conftest import MockHashConsul
from metadata.utils.redis_tools import RedisTools


class TestFeatureFlagRedisSync:
    def test_uses_unify_query_shared_paths(self):
        """验证 Consul 源路径和 Redis 目标路径与统一查询服务的约定一致。"""
        assert (
            FeatureFlagRedisSync.CONSUL_SOURCE_PATH == f"{config.MIGRATION_CONSUL_PATH}/unify-query/data/feature_flag"
        )
        assert FeatureFlagRedisSync.REDIS_TARGET_KEY == f"{settings.BACKEND_APP_CODE}:unify-query:data:feature_flag"
        assert FeatureFlagRedisSync.REDIS_CHANNEL == f"{FeatureFlagRedisSync.REDIS_TARGET_KEY}:feature_flag_channel"

    @pytest.fixture
    def redis_client(self, mocker):
        """使用内存 Redis 隔离测试，避免访问真实 Redis。"""
        client = fakeredis.FakeRedis()
        mocker.patch.object(RedisTools, "client", new_callable=PropertyMock, return_value=client)
        return client

    @pytest.fixture
    def consul_client(self, mocker):
        """清理单例 Consul Mock，避免不同测试之间互相污染配置和调用记录。"""
        client = MockHashConsul()
        client._kv_store.clear()
        client._call_history.clear()
        mocker.patch("metadata.feature_flag.consul_tools.HashConsul", return_value=client)
        return client

    @pytest.fixture
    def subscriber(self, redis_client):
        """订阅 Feature Flag 通知，用于验证首次迁移才会发布消息。"""
        subscriber = redis_client.pubsub()
        subscriber.subscribe(FeatureFlagRedisSync.REDIS_CHANNEL)
        assert subscriber.get_message(timeout=0.1)["type"] == "subscribe"
        return subscriber

    @pytest.mark.parametrize(
        "snapshot",
        [
            pytest.param(
                {
                    "must-vm-query": {
                        "variations": {"Default": False, "enabled": True},
                        "targeting": [],
                        "defaultRule": {"variation": "Default"},
                    }
                },
                id="正常快照",
            ),
            pytest.param({}, id="空快照"),
        ],
    )
    def test_writes_consul_snapshot_to_redis_without_delete(
        self, redis_client, consul_client, subscriber, mocker, snapshot
    ):
        """验证 Consul 快照写入 Redis，并且无论快照是否为空都不会调用 delete。"""
        consul_client.put(FeatureFlagRedisSync.CONSUL_SOURCE_PATH, snapshot)
        delete_spy = mocker.spy(redis_client, "delete")

        FeatureFlagRedisSync.sync_from_consul()

        assert json.loads(redis_client.get(FeatureFlagRedisSync.REDIS_TARGET_KEY)) == snapshot
        assert delete_spy.call_count == 0
        message = subscriber.get_message(timeout=0.1)
        assert message["channel"] == FeatureFlagRedisSync.REDIS_CHANNEL.encode()
        assert json.loads(message["data"]) == snapshot
        assert redis_client.get(FeatureFlagRedisSync.REDIS_MIGRATION_MARKER_KEY)

    def test_missing_consul_snapshot_preserves_redis(self, redis_client, consul_client, subscriber):
        """验证 Consul 源配置缺失时任务失败，但不删除已有 Redis 快照或发布通知。"""
        redis_client.set(FeatureFlagRedisSync.REDIS_TARGET_KEY, json.dumps({"stale-flag": {}}))

        with pytest.raises(FeatureFlagSourceMissingError):
            FeatureFlagRedisSync.sync_from_consul()

        assert json.loads(redis_client.get(FeatureFlagRedisSync.REDIS_TARGET_KEY)) == {"stale-flag": {}}
        assert subscriber.get_message(timeout=0.1) is None

    def test_repeated_sync_is_skipped(self, redis_client, consul_client, subscriber):
        """验证首次迁移完成后，即使 Consul 不可用，重复执行也只读取 Redis 并跳过。"""
        snapshot = {"flag": {"enabled": True}}
        consul_client.put(FeatureFlagRedisSync.CONSUL_SOURCE_PATH, snapshot)

        FeatureFlagRedisSync.sync_from_consul()
        consul_client.clear_call_history()
        consul_client._kv_store.clear()
        FeatureFlagRedisSync.sync_from_consul()

        first_message = subscriber.get_message(timeout=0.1)
        assert json.loads(first_message["data"]) == snapshot
        assert subscriber.get_message(timeout=0.1) is None
        assert consul_client.get_call_history() == []

    def test_existing_snapshot_is_marked_without_second_dispatch(self, redis_client, consul_client, subscriber):
        """验证 Redis 已有相同快照时只补完成标记，不重复写入或发布通知。"""
        snapshot = {"z-flag": {"enabled": True}, "a-flag": {"enabled": False}}
        payload = json.dumps(snapshot)
        consul_client.put(FeatureFlagRedisSync.CONSUL_SOURCE_PATH, snapshot)
        redis_client.set(FeatureFlagRedisSync.REDIS_TARGET_KEY, payload)

        FeatureFlagRedisSync.sync_from_consul()

        assert json.loads(redis_client.get(FeatureFlagRedisSync.REDIS_TARGET_KEY)) == snapshot
        assert redis_client.get(FeatureFlagRedisSync.REDIS_MIGRATION_MARKER_KEY)
        assert subscriber.get_message(timeout=0.1) is None

    @pytest.mark.parametrize("snapshot", ["not-json", "[]", "null"])
    def test_rejects_invalid_consul_snapshot(self, redis_client, consul_client, snapshot):
        """验证 Consul 中的非法 JSON 或非对象配置不会写入 Redis。"""
        consul_client._kv_store[FeatureFlagRedisSync.CONSUL_SOURCE_PATH] = {
            "Key": FeatureFlagRedisSync.CONSUL_SOURCE_PATH,
            "Value": snapshot,
        }

        with pytest.raises(ValueError):
            FeatureFlagRedisSync.sync_from_consul()

        assert redis_client.get(FeatureFlagRedisSync.REDIS_TARGET_KEY) is None

    @pytest.mark.parametrize(
        ("execute_result", "execute_error", "expected_message"),
        [
            pytest.param([False, 0, True], None, "set feature flag config to redis failed", id="写入返回失败"),
            pytest.param(None, RuntimeError("redis unavailable"), "redis unavailable", id="事务执行异常"),
        ],
    )
    def test_propagates_redis_failures(
        self, redis_client, consul_client, mocker, execute_result, execute_error, expected_message
    ):
        """验证 Redis 写入返回失败或事务异常时，迁移任务都会向上抛错并触发重试。"""
        consul_client.put(FeatureFlagRedisSync.CONSUL_SOURCE_PATH, {"flag": {}})
        pipeline = mocker.MagicMock()
        pipeline.__enter__.return_value = pipeline
        pipeline.__exit__.return_value = False
        pipeline.get.side_effect = [None, None]
        if execute_error is None:
            pipeline.execute.return_value = execute_result
        else:
            pipeline.execute.side_effect = execute_error
        mocker.patch.object(redis_client, "pipeline", return_value=pipeline)

        with pytest.raises(RuntimeError, match=expected_message):
            FeatureFlagRedisSync.sync_from_consul()

    def test_rejects_marker_for_different_snapshot(self, redis_client, consul_client, subscriber):
        """验证完成标记与 Redis 快照不一致时失败，避免覆盖既有配置。"""
        consul_client.put(FeatureFlagRedisSync.CONSUL_SOURCE_PATH, {"flag": {"enabled": True}})
        redis_client.set(FeatureFlagRedisSync.REDIS_MIGRATION_MARKER_KEY, "different-snapshot")
        redis_client.set(FeatureFlagRedisSync.REDIS_TARGET_KEY, json.dumps({"flag": {"enabled": True}}))

        with pytest.raises(RuntimeError, match="different snapshot"):
            FeatureFlagRedisSync.sync_from_consul()

        assert subscriber.get_message(timeout=0.1) is None
