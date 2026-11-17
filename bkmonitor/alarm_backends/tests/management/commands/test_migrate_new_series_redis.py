"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from io import StringIO
from types import SimpleNamespace
from unittest import mock

import fakeredis
import pytest
from django.core.management import call_command


from alarm_backends.core.cache.key import KEY_PREFIX
from alarm_backends.management.commands.migrate_new_series_redis import Command


def _make_fake_redis():
    return fakeredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=False)


def test_migrate_new_series_redis_dry_run_and_apply_preserves_data_and_ttl(monkeypatch):
    source_a = _make_fake_redis()
    source_b = _make_fake_redis()
    target = _make_fake_redis()

    seen_key = f"{KEY_PREFIX}.detect.new_series.seen.101.201.sig1"
    done_key = f"{KEY_PREFIX}.detect.new_series.baseline_done.101.201.sig1"
    learn_key = f"{KEY_PREFIX}.detect.new_series.learn_start.102.202.sig2"
    other_key = f"{KEY_PREFIX}.detect.result.101.201.dim1.1"

    source_a.zadd(seen_key, {"fp-a": 1700000100, "fp-b": 1700000200})
    source_a.expire(seen_key, 3600)
    source_a.set(done_key, "1", ex=3600)
    source_a.zadd(other_key, {"1700000100|1": 1700000100})

    # 无 TTL 存量兼容键(PTTL == -1)也应按永久键原样恢复
    source_b.set(learn_key, "1700000000")

    nodes = [
        SimpleNamespace(
            id=1,
            node_alias="shard-a",
            host="192.0.2.1",
            port=6379,
            password="",
            cache_type="RedisCache",
            connection_kwargs={},
            is_enable=True,
        ),
        SimpleNamespace(
            id=2,
            node_alias="shard-b",
            host="192.0.2.2",
            port=6379,
            password="",
            cache_type="RedisCache",
            connection_kwargs={},
            is_enable=True,
        ),
    ]
    source_map = {1: source_a, 2: source_b}

    monkeypatch.setenv("REDIS_CACHE_NEW_SERIES_URL", "redis://192.0.2.99:6379")

    with (
        mock.patch(
            "alarm_backends.management.commands.migrate_new_series_redis.get_enabled_source_nodes",
            return_value=nodes,
        ),
        mock.patch(
            "alarm_backends.management.commands.migrate_new_series_redis.build_raw_source_client",
            side_effect=lambda node: source_map[node.id],
        ),
        mock.patch(
            "alarm_backends.management.commands.migrate_new_series_redis.build_raw_target_client",
            return_value=(target, ("192.0.2.99", 6379, 10)),
        ),
    ):
        # 1) 默认 dry-run 只统计不写目标库
        out = StringIO()
        call_command(Command(), stdout=out)
        assert target.dbsize() == 0
        assert "dry_run=True" in out.getvalue()

        # 2) --apply 拷贝所有 new_series 键并保留 TTL，不拷贝无关检测键，且不删源键
        out_apply = StringIO()
        call_command(Command(), "--apply", stdout=out_apply)

        assert target.zscore(seen_key, b"fp-a") == 1700000100.0
        assert target.zscore(seen_key, b"fp-b") == 1700000200.0
        assert 0 < target.ttl(seen_key) <= 3600
        assert target.get(done_key) == b"1"
        assert 0 < target.ttl(done_key) <= 3600
        assert target.get(learn_key) == b"1700000000"
        assert target.ttl(learn_key) == -1
        assert target.exists(other_key) == 0

        # 源端键保留，保证升级窗口和回滚安全
        assert source_a.exists(seen_key) == 1
        assert source_b.exists(learn_key) == 1

        # 3) 重复执行 --apply 幂等覆盖不报错
        call_command(Command(), "--apply", stdout=StringIO())
        assert target.zcard(seen_key) == 2


def test_migrate_new_series_redis_skips_same_endpoint_and_requires_target(monkeypatch):
    monkeypatch.delenv("REDIS_CACHE_NEW_SERIES_URL", raising=False)
    with pytest.raises(Exception, match="REDIS_CACHE_NEW_SERIES_URL"):
        call_command(Command())

    same_redis = _make_fake_redis()
    seen_key = "bk_monitorv3.ce.detect.new_series.seen.101.201.sig1"
    same_redis.zadd(seen_key, {"fp-a": 1700000100})

    node = SimpleNamespace(
        id=1,
        node_alias="same-node",
        host="192.0.2.99",
        port=6379,
        password="",
        cache_type="RedisCache",
        connection_kwargs={},
        is_enable=True,
    )
    with (
        mock.patch(
            "alarm_backends.management.commands.migrate_new_series_redis.get_enabled_source_nodes",
            return_value=[node],
        ),
        mock.patch(
            "alarm_backends.management.commands.migrate_new_series_redis.build_raw_source_client",
            return_value=same_redis,
        ) as mock_source_builder,
        mock.patch(
            "alarm_backends.management.commands.migrate_new_series_redis.build_raw_target_client",
            return_value=(same_redis, ("192.0.2.99", 6379, 10)),
        ),
    ):
        out = StringIO()
        call_command(Command(), "--target-url", "redis://192.0.2.99:6379", "--apply", stdout=out)
        mock_source_builder.assert_not_called()
        assert "skipped" in out.getvalue()
