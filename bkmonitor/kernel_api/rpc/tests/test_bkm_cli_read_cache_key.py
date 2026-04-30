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

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.bkm_cli.cache import read_cache_key


class FakeRedisClient:
    """可配置返回值的 Redis fake 客户端。"""

    def __init__(self):
        self._data: dict = {}

    def get(self, key):
        return self._data.get(key)

    def hgetall(self, key):
        return self._data.get(key, {})

    def hget(self, key, field):
        bucket = self._data.get(key) or {}
        field_b = field.encode() if isinstance(field, str) else field
        return bucket.get(field_b) or bucket.get(field)

    def zcard(self, key):
        return len(self._data.get(key) or [])

    def zrange(self, key, start, stop, withscores=False):
        items = list(self._data.get(key) or [])
        sliced = items[start : None if stop == -1 else stop + 1]
        return sliced

    def zrangebyscore(self, key, min_score, max_score, withscores=False, start=0, num=50):
        items = [pair for pair in (self._data.get(key) or []) if min_score <= pair[1] <= max_score]
        return items[start : start + num]

    def llen(self, key):
        return len(self._data.get(key) or [])

    def lrange(self, key, start, stop):
        items = list(self._data.get(key) or [])
        return items[start : None if stop == -1 else stop + 1]


def _make_key_obj(fake_client, key_type: str, key_tpl: str):
    """创建最小化的假 key 对象。"""

    class FakeKey:
        def get_key(self, **kwargs):
            return key_tpl.format(**kwargs)

        @property
        def client(self):
            return fake_client

    obj = FakeKey()
    obj.key_type = key_type
    return obj


def test_read_cache_key_unknown_key_name_raises():
    with pytest.raises(CustomException, match="不在 bkm-cli read-cache-key 白名单"):
        read_cache_key({"key_name": "NONEXISTENT_KEY", "params": {}})


def test_read_cache_key_missing_key_name_raises():
    with pytest.raises(CustomException, match="key_name is required"):
        read_cache_key({"params": {}})


def test_read_cache_key_missing_required_params_raises():
    with pytest.raises(CustomException, match="缺少必填参数"):
        read_cache_key({"key_name": "CHECK_RESULT_CACHE_KEY", "params": {"strategy_id": 1}})


def test_read_cache_key_limit_over_max_raises():
    with pytest.raises(CustomException, match="limit 超过硬上限"):
        read_cache_key(
            {
                "key_name": "CHECK_RESULT_CACHE_KEY",
                "params": {"strategy_id": 1, "item_id": 2, "dimensions_md5": "abc", "level": 1},
                "limit": 9999,
            }
        )


def test_read_cache_key_zset_check_result(mocker):
    fake = FakeRedisClient()
    fake._data["test.detect.result.1.2.abc.1"] = [
        (b"1776376740|0.5", 1776376740.0),
        (b"1776376800|ANOMALY_LABEL", 1776376800.0),
    ]

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "zset", "test.detect.result.{strategy_id}.{item_id}.{dimensions_md5}.{level}"),
    )

    result = read_cache_key(
        {
            "key_name": "CHECK_RESULT_CACHE_KEY",
            "params": {"strategy_id": 1, "item_id": 2, "dimensions_md5": "abc", "level": 1},
            "limit": 10,
        }
    )

    assert result["key_name"] == "CHECK_RESULT_CACHE_KEY"
    assert result["key_type"] == "zset"
    assert result["exists"] is True
    assert result["total_count"] == 2
    assert len(result["members"]) == 2
    assert result["members"][0]["score"] == 1776376740.0


def test_read_cache_key_zset_empty(mocker):
    fake = FakeRedisClient()
    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "zset", "test.{strategy_id}.{item_id}.{dimensions_md5}.{level}"),
    )

    result = read_cache_key(
        {
            "key_name": "CHECK_RESULT_CACHE_KEY",
            "params": {"strategy_id": 1, "item_id": 2, "dimensions_md5": "abc", "level": 1},
        }
    )

    assert result["exists"] is False
    assert result["total_count"] == 0
    assert result["members"] == []


def test_read_cache_key_hash_hgetall(mocker):
    fake = FakeRedisClient()
    fake._data["test.priority.PGK:abc"] = {
        b"dim1": b"100:1776376740.0",
        b"dim2": b"50:1776376700.0",
    }

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "hash", "test.priority.{priority_group_key}"),
    )

    result = read_cache_key(
        {
            "key_name": "ACCESS_PRIORITY_KEY",
            "params": {"priority_group_key": "PGK:abc"},
        }
    )

    assert result["key_type"] == "hash"
    assert result["exists"] is True
    assert result["total_fields"] == 2
    assert "dim1" in result["items"]


def test_read_cache_key_hash_specific_field(mocker):
    fake = FakeRedisClient()
    fake._data["test.priority.PGK:abc"] = {b"dim1": b"100:1776376740.0"}

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "hash", "test.priority.{priority_group_key}"),
    )

    result = read_cache_key(
        {
            "key_name": "ACCESS_PRIORITY_KEY",
            "params": {"priority_group_key": "PGK:abc"},
            "field": "dim1",
        }
    )

    assert result["field"] == "dim1"
    assert result["value"] == "100:1776376740.0"


def test_read_cache_key_string(mocker):
    fake = FakeRedisClient()
    fake._data["test.checkpoint.group_key_abc"] = b'{"ts": 1776376740}'

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "string", "test.checkpoint.{strategy_group_key}"),
    )

    result = read_cache_key(
        {
            "key_name": "STRATEGY_CHECKPOINT_KEY",
            "params": {"strategy_group_key": "group_key_abc"},
        }
    )

    assert result["key_type"] == "string"
    assert result["exists"] is True
    assert result["value"] == {"ts": 1776376740}


def test_read_cache_key_resolved_key_in_output(mocker):
    fake = FakeRedisClient()
    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "string", "test.snapshot.{strategy_id}.{update_time}"),
    )

    result = read_cache_key(
        {
            "key_name": "STRATEGY_SNAPSHOT_KEY",
            "params": {"strategy_id": 99, "update_time": 1776376740},
        }
    )

    assert "resolved_key" in result
    assert "99" in result["resolved_key"]
    assert "label" in result
