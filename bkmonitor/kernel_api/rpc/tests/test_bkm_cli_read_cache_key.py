"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

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

    def scard(self, key):
        return len(self._data.get(key) or set())

    def smembers(self, key):
        return self._data.get(key) or set()

    def pttl(self, key):
        # 键存在返回固定剩余毫秒；不存在返回 -2（Redis PTTL 语义）
        return 123456 if (self._data.get(key) is not None) else -2


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


# ---------- set type ----------


def test_read_cache_key_set_access_duplicate(mocker):
    fake = FakeRedisClient()
    fake._data["test.access.data.duplicate.strategy_group_group_abc.1777000000"] = {b"item1", b"item2", b"item3"}

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(
            fake, "set", "test.access.data.duplicate.strategy_group_{strategy_group_key}.{dt_event_time}"
        ),
    )

    result = read_cache_key(
        {
            "key_name": "ACCESS_DUPLICATE_KEY",
            "params": {"strategy_group_key": "group_abc", "dt_event_time": "1777000000"},
            "limit": 10,
        }
    )

    assert result["key_type"] == "set"
    assert result["exists"] is True
    assert result["total_count"] == 3
    assert result["returned_count"] == 3
    assert result["truncated"] is False
    assert {"item1", "item2", "item3"} == set(result["members"])


def test_read_cache_key_set_empty(mocker):
    fake = FakeRedisClient()

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(
            fake, "set", "test.access.data.duplicate.strategy_group_{strategy_group_key}.{dt_event_time}"
        ),
    )

    result = read_cache_key(
        {
            "key_name": "ACCESS_DUPLICATE_KEY",
            "params": {"strategy_group_key": "group_abc", "dt_event_time": "1777000000"},
        }
    )

    assert result["exists"] is False
    assert result["total_count"] == 0
    assert result["members"] == []


def test_read_cache_key_set_truncated(mocker):
    fake = FakeRedisClient()
    fake._data["test.access.data.duplicate.strategy_group_group_abc.1777000000"] = {
        b"item1",
        b"item2",
        b"item3",
        b"item4",
        b"item5",
    }

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(
            fake, "set", "test.access.data.duplicate.strategy_group_{strategy_group_key}.{dt_event_time}"
        ),
    )

    result = read_cache_key(
        {
            "key_name": "ACCESS_DUPLICATE_KEY",
            "params": {"strategy_group_key": "group_abc", "dt_event_time": "1777000000"},
            "limit": 2,
        }
    )

    assert result["total_count"] == 5
    assert result["returned_count"] == 2
    assert result["truncated"] is True


# ---------- new string keys ----------


def test_read_cache_key_alert_data_poller_leader(mocker):
    fake = FakeRedisClient()
    fake._data["test.alert.poller.leader"] = b"host-1"

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "string", "test.alert.poller.leader"),
    )

    result = read_cache_key({"key_name": "ALERT_DATA_POLLER_LEADER_KEY", "params": {}})

    assert result["key_type"] == "string"
    assert result["exists"] is True
    assert result["value"] == "host-1"


def test_read_cache_key_alert_detect_result(mocker):
    fake = FakeRedisClient()
    fake._data["test.alert.detect.1774970114271323713"] = b'{"status": "ok"}'

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "string", "test.alert.detect.{alert_id}"),
    )

    result = read_cache_key({"key_name": "ALERT_DETECT_RESULT", "params": {"alert_id": 1774970114271323713}})

    assert result["key_type"] == "string"
    assert result["value"] == {"status": "ok"}


def test_read_cache_key_alert_snapshot(mocker):
    fake = FakeRedisClient()
    fake._data["test.alert.builder.snapshot.121950.1774970114271323713"] = b'{"data": "snapshot_content"}'

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "string", "test.alert.builder.snapshot.{strategy_id}.{alert_id}"),
    )

    result = read_cache_key(
        {
            "key_name": "ALERT_SNAPSHOT_KEY",
            "params": {"strategy_id": 121950, "alert_id": 1774970114271323713},
        }
    )

    assert result["exists"] is True
    assert result["value"] == {"data": "snapshot_content"}


def test_read_cache_key_alert_dedupe_content(mocker):
    fake = FakeRedisClient()
    fake._data["test.alert.builder.121950.abc123.content"] = b'{"alert": "content"}'

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "string", "test.alert.builder.{strategy_id}.{dedupe_md5}.content"),
    )

    result = read_cache_key(
        {
            "key_name": "ALERT_DEDUPE_CONTENT_KEY",
            "params": {"strategy_id": 121950, "dedupe_md5": "abc123"},
        }
    )

    assert result["exists"] is True
    assert result["value"] == {"alert": "content"}


def test_read_cache_key_service_lock_nodata(mocker):
    fake = FakeRedisClient()
    fake._data["test.detect.lock.100367"] = b"locked"

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "string", "test.detect.lock.{strategy_id}"),
    )

    result = read_cache_key({"key_name": "SERVICE_LOCK_NODATA", "params": {"strategy_id": 100367}})

    assert result["key_type"] == "string"
    assert result["value"] == "locked"


# ---------- new hash key ----------


def test_read_cache_key_alert_host_data_id_hgetall(mocker):
    fake = FakeRedisClient()
    fake._data["test.alert.poller.host_data_id"] = {b"host-1": b"data_id_1", b"host-2": b"data_id_2"}

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "hash", "test.alert.poller.host_data_id"),
    )

    result = read_cache_key({"key_name": "ALERT_HOST_DATA_ID_KEY", "params": {}})

    assert result["key_type"] == "hash"
    assert result["exists"] is True
    assert result["total_fields"] == 2
    assert "host-1" in result["items"]


def test_read_cache_key_alert_host_data_id_single_field(mocker):
    fake = FakeRedisClient()
    fake._data["test.alert.poller.host_data_id"] = {b"host-1": b"data_id_1"}

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "hash", "test.alert.poller.host_data_id"),
    )

    result = read_cache_key({"key_name": "ALERT_HOST_DATA_ID_KEY", "params": {}, "field": "host-1"})

    assert result["field"] == "host-1"
    assert result["value"] == "data_id_1"


def test_read_cache_key_set_missing_param_raises():
    with pytest.raises(CustomException, match="缺少必填参数"):
        read_cache_key(
            {
                "key_name": "ACCESS_DUPLICATE_KEY",
                "params": {"strategy_group_key": "abc"},
            }
        )


# ---------- issue fingerprint keys (B10) ----------


def test_read_cache_key_issue_active_content_hit(mocker):
    fake = FakeRedisClient()
    fake._data["test.issue.active.content.fp-abc"] = b'{"issue_id":"i-1","status":"ABNORMAL"}'

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "string", "test.issue.active.content.{fingerprint}"),
    )

    result = read_cache_key({"key_name": "ISSUE_ACTIVE_CONTENT_KEY", "params": {"fingerprint": "fp-abc"}})

    assert result["key_type"] == "string"
    assert result["exists"] is True
    assert result["value"] == {"issue_id": "i-1", "status": "ABNORMAL"}


def test_read_cache_key_issue_active_content_requires_fingerprint():
    with pytest.raises(CustomException, match="缺少必填参数"):
        read_cache_key({"key_name": "ISSUE_ACTIVE_CONTENT_KEY", "params": {}})


def test_read_cache_key_issue_fingerprint_lock_held(mocker):
    fake = FakeRedisClient()
    fake._data["test.issue.fingerprint.lock.fp-xyz"] = b"locked"

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "string", "test.issue.fingerprint.lock.{fingerprint}"),
    )

    result = read_cache_key({"key_name": "ISSUE_FINGERPRINT_LOCK", "params": {"fingerprint": "fp-xyz"}})

    assert result["exists"] is True
    assert result["value"] == "locked"


def test_read_cache_key_issue_active_count_hit(mocker):
    fake = FakeRedisClient()
    fake._data["test.issue.active_count.10313"] = b"42"

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "string", "test.issue.active_count.{strategy_id}"),
    )

    result = read_cache_key({"key_name": "ISSUE_ACTIVE_COUNT_KEY", "params": {"strategy_id": 10313}})

    assert result["exists"] is True
    assert result["value"] == 42


def test_read_cache_key_issue_active_count_requires_strategy_id():
    with pytest.raises(CustomException, match="缺少必填参数"):
        read_cache_key({"key_name": "ISSUE_ACTIVE_COUNT_KEY", "params": {}})


def test_read_cache_key_issue_legacy_migration_done_sentinel(mocker):
    fake = FakeRedisClient()
    fake._data["test.issue.legacy_migration.done"] = b"1"

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "string", "test.issue.legacy_migration.done"),
    )

    # 无必填参数；params 可为空
    result = read_cache_key({"key_name": "ISSUE_LEGACY_MIGRATION_DONE_KEY", "params": {}})

    assert result["exists"] is True
    assert result["value"] == 1


def test_read_cache_key_issue_legacy_migration_done_missing(mocker):
    """legacy 迁移哨兵不存在时返回 exists=False，agent 判定为"未完成或被清理"。"""
    fake = FakeRedisClient()

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "string", "test.issue.legacy_migration.done"),
    )

    result = read_cache_key({"key_name": "ISSUE_LEGACY_MIGRATION_DONE_KEY", "params": {}})

    assert result["exists"] is False
    assert result["value"] is None


# ---------- routing echo ----------


class FakeSimilarKey(str):
    """模拟 SimilarStr：携带 strategy_id 路由属性的字符串。"""

    strategy_id = 0


def _make_routed_key_obj(fake_client, key_type: str, key_tpl: str, backend: str = "service", strategy_id: int = 0):
    """创建带 backend 属性、get_key 返回 SimilarStr 形态对象的假 key。"""

    class FakeKey:
        def get_key(self, **kwargs):
            key = FakeSimilarKey(key_tpl.format(**kwargs))
            key.strategy_id = strategy_id
            return key

        @property
        def client(self):
            return fake_client

    obj = FakeKey()
    obj.key_type = key_type
    obj.backend = backend
    return obj


def _fake_cache_node():
    return SimpleNamespace(
        id=7,
        node_alias="demo-node",
        cluster_name="default",
        cache_type="RedisCache",
        host="127.0.0.1",
        port=6379,
        is_default=True,
        is_enable=True,
    )


def test_read_cache_key_routing_echo(mocker):
    fake = FakeRedisClient()
    fake._data["test.detect.lock.42"] = b"locked"

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_routed_key_obj(fake, "string", "test.detect.lock.{strategy_id}", strategy_id=42),
    )
    mocker.patch(
        "alarm_backends.core.storage.redis_cluster.get_node_by_strategy_id",
        return_value=_fake_cache_node(),
    )
    mocker.patch(
        "alarm_backends.core.cluster.get_cluster",
        return_value=SimpleNamespace(name="default"),
    )
    mocker.patch.dict(
        "alarm_backends.core.storage.redis.CACHE_BACKEND_CONF_MAP",
        {"service": {"db": 10}},
    )

    result = read_cache_key({"key_name": "SERVICE_LOCK_NODATA", "params": {"strategy_id": 42}})

    assert result["value"] == "locked"
    routing = result["routing"]
    assert routing["strategy_id"] == 42
    assert routing["backend"] == "service"
    assert routing["db"] == 10
    assert routing["process_cluster"] == "default"
    assert routing["node"]["cluster_name"] == "default"
    assert routing["node"]["is_default"] is True
    # 红线：host/port（内网拓扑）与 password 绝不回显
    assert "host" not in routing["node"]
    assert "port" not in routing["node"]
    assert "password" not in routing["node"]
    # 回归：node 不含任何 IP 形态值
    import re as _re

    assert not any(isinstance(v, str) and _re.search(r"\d+\.\d+\.\d+\.\d+", v) for v in routing["node"].values())


def test_read_cache_key_routing_echo_failure_does_not_break_read(mocker):
    fake = FakeRedisClient()
    fake._data["test.detect.lock.42"] = b"locked"

    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "string", "test.detect.lock.{strategy_id}"),
    )
    mocker.patch(
        "alarm_backends.core.storage.redis_cluster.get_node_by_strategy_id",
        side_effect=Exception("router table unavailable"),
    )

    result = read_cache_key({"key_name": "SERVICE_LOCK_NODATA", "params": {"strategy_id": 42}})

    # 主读取不受回显失败影响
    assert result["exists"] is True
    assert result["value"] == "locked"
    assert "error" in result["routing"]


# ---------- ttl_ms (F6) ----------


def test_read_cache_key_ttl_ms_present(mocker):
    fake = FakeRedisClient()
    fake._data["test.detect.lock.42"] = b"locked"
    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "string", "test.detect.lock.{strategy_id}"),
    )
    result = read_cache_key({"key_name": "SERVICE_LOCK_NODATA", "params": {"strategy_id": 42}})
    assert result["ttl_ms"] == 123456


def test_read_cache_key_ttl_ms_missing_key_is_minus_two(mocker):
    fake = FakeRedisClient()  # 空，键不存在
    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "string", "test.detect.lock.{strategy_id}"),
    )
    result = read_cache_key({"key_name": "SERVICE_LOCK_NODATA", "params": {"strategy_id": 42}})
    assert result["exists"] is False
    assert result["ttl_ms"] == -2


def test_read_cache_key_ttl_ms_failure_is_none(mocker):
    class NoPttlClient(FakeRedisClient):
        def pttl(self, key):
            raise Exception("PTTL unsupported")

    fake = NoPttlClient()
    fake._data["test.detect.lock.42"] = b"locked"
    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache._get_key_obj",
        return_value=_make_key_obj(fake, "string", "test.detect.lock.{strategy_id}"),
    )
    result = read_cache_key({"key_name": "SERVICE_LOCK_NODATA", "params": {"strategy_id": 42}})
    # ttl 回显失败不影响主读取
    assert result["value"] == "locked"
    assert result["ttl_ms"] is None


# ---------- list-cache-routing (F2) ----------


def test_list_cache_routing(mocker):
    from kernel_api.rpc.functions.bkm_cli.cache import list_cache_routing

    # node 故意不带 host/port：_node_identity 不读取它们，输出契约就是"不含 host/port"
    node_default = SimpleNamespace(
        id=2,
        node_alias="monitor-01",
        cluster_name="default",
        cache_type="SentinelRedisCache",
        is_default=True,
        is_enable=True,
    )
    node_b = SimpleNamespace(
        id=5,
        node_alias="monitor-02",
        cluster_name="default",
        cache_type="RedisCache",
        is_default=False,
        is_enable=True,
    )
    router_b = SimpleNamespace(strategy_score=100000, node=node_b)

    class FakeRouterQS:
        def filter(self, **kwargs):
            return self

        def select_related(self, *args):
            return self

        def order_by(self, *args):
            return [router_b]

    class FakeNodeQS:
        def filter(self, **kwargs):
            return self

        def first(self):
            return node_default

    mocker.patch("bkmonitor.models.CacheRouter", SimpleNamespace(objects=FakeRouterQS()))
    mocker.patch("bkmonitor.models.CacheNode", SimpleNamespace(objects=FakeNodeQS()))
    mocker.patch("alarm_backends.core.cluster.get_cluster", return_value=SimpleNamespace(name="default"))

    result = list_cache_routing({})

    assert result["cluster_name"] == "default"
    assert result["router_count"] == 1
    r0 = result["routers"][0]
    assert r0["strategy_score"] == 100000
    assert r0["score_range"] == {"floor": 0, "ceil": 99999}
    assert r0["node"]["node_alias"] == "monitor-02"
    assert result["default_node"]["node_alias"] == "monitor-01"
    # 红线：路由表也不回显 host/port
    for n in (r0["node"], result["default_node"]):
        assert "host" not in n
        assert "port" not in n
        assert "password" not in n
