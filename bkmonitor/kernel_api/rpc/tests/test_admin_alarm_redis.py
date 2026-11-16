from types import SimpleNamespace
from unittest.mock import Mock

import fakeredis
import pytest

from kernel_api.rpc.functions.admin import alarm_redis, alarm_redis_service as service, alarm_strategy
from kernel_api.rpc.registry import KernelRPCRegistry


def node(node_id=1, cluster="default", default=False):
    return SimpleNamespace(
        id=node_id,
        cluster_name=cluster,
        node_alias=f"node-{node_id}",
        cache_type="RedisCache",
        host="localhost",
        port=6379,
        connection_kwargs={},
        is_enable=True,
        is_default=default,
    )


def test_all_nodes_are_not_scoped_by_process_cluster(monkeypatch):
    nodes = [node(1), node(2, "other")]
    query = Mock()
    query.__getitem__ = Mock(return_value=nodes)
    query.count.return_value = 2
    monkeypatch.setattr(alarm_redis.CacheNode.objects, "order_by", Mock(return_value=query))
    result = alarm_redis.execute("node_list", {})
    assert [n["id"] for n in result["data"]["items"]] == [1, 2]
    assert "cluster_name" not in result["data"]["items"][0]
    assert result["meta"]["tenant_scope"] == "all"


def test_strategy_cross_tenant_does_not_filter_by_current_tenant(monkeypatch):
    all_rows = Mock()
    monkeypatch.setattr(alarm_strategy.StrategyModel.objects, "all", Mock(return_value=all_rows))
    monkeypatch.setattr(alarm_strategy.settings, "ENABLE_MULTI_TENANT_MODE", True)
    assert alarm_strategy.strategy_queryset({}) is all_rows
    all_rows.filter.assert_not_called()


def test_explicit_strategy_tenant_uses_business_scope(monkeypatch):
    query = Mock()
    monkeypatch.setattr(alarm_strategy.StrategyModel.objects, "all", Mock(return_value=query))
    monkeypatch.setattr(alarm_strategy.settings, "ENABLE_MULTI_TENANT_MODE", True)
    monkeypatch.setattr(alarm_strategy.SpaceApi, "list_spaces", Mock(return_value=[SimpleNamespace(bk_biz_id=7)]))
    alarm_strategy.strategy_queryset({"bk_tenant_id": "tenant-a"})
    query.filter.assert_called_once_with(bk_biz_id__in=[7])


@pytest.mark.parametrize("sid,expected", [(99, 1), (100, 2), (199, 2)])
def test_auto_route_uses_strict_upper_boundary(monkeypatch, sid, expected):
    a, b = node(1), node(2)
    rows = [
        SimpleNamespace(cluster_name="default", strategy_score=100, node=a),
        SimpleNamespace(cluster_name="default", strategy_score=200, node=b),
    ]
    monkeypatch.setattr(service, "routes", lambda: (rows, []))
    monkeypatch.setattr(
        service, "get_cluster", lambda: SimpleNamespace(get_targets_by_cluster=lambda *args: {"default": [7]})
    )
    monkeypatch.setattr(alarm_strategy, "scoped_strategy", lambda *args: SimpleNamespace(bk_biz_id=7))
    assert service.resolve_node({"strategy_id": sid}).id == expected


def test_ambiguous_route_requires_node_selection(monkeypatch):
    rows = [
        SimpleNamespace(cluster_name=name, strategy_score=1000, node=node(i, name)) for i, name in [(1, "a"), (2, "b")]
    ]
    monkeypatch.setattr(service, "routes", lambda: (rows, []))
    monkeypatch.setattr(service, "get_cluster", lambda: SimpleNamespace(get_targets_by_cluster=lambda *args: {}))
    monkeypatch.setattr(alarm_strategy, "scoped_strategy", lambda *args: SimpleNamespace(bk_biz_id=7))
    with pytest.raises(Exception, match="显式选择"):
        service.resolve_node({"strategy_id": 10})


def test_missing_default_never_initializes_configuration(monkeypatch):
    monkeypatch.setattr(service, "routes", lambda: ([], []))
    query = Mock()
    query.order_by.return_value = []
    monkeypatch.setattr(service.CacheNode.objects, "filter", Mock(return_value=query))
    initialize = Mock(side_effect=AssertionError("must not initialize"))
    monkeypatch.setattr(service.CacheNode, "default_node", initialize)
    with pytest.raises(Exception, match="显式选择"):
        service.resolve_node({})
    initialize.assert_not_called()


@pytest.fixture
def redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.mark.parametrize("kind", ["string", "list", "hash", "set", "zset"])
def test_key_read_types_and_paging(redis, kind):
    if kind == "string":
        redis.set("key", "hello")
    elif kind == "list":
        redis.rpush("key", "a", "b", "c")
    elif kind == "hash":
        redis.hset("key", mapping={"a": "b"})
    elif kind == "set":
        redis.sadd("key", "a", "b")
    else:
        redis.zadd("key", {"a": 1, "b": 2})
    data = service.key_read(redis, "key", {}, {"page_size": 1})
    assert data["type"] == kind
    assert data["ttl"] == -1
    assert data["exists"] is True
    assert data["content_omitted"] is False
    if kind in ("list", "zset"):
        assert data["next_cursor"] == "1"


def test_missing_and_expiring_key(redis):
    data = service.key_read(redis, "missing", {}, {})
    assert data["ttl"] == -2 and data["exists"] is False and data["value"] is None
    redis.set("key", "ok", ex=120)
    assert 0 < service.key_status(redis, "key", {})["ttl"] <= 120


def test_large_value_is_explicitly_omitted(redis):
    redis.set("key", "x" * (service.MAX_CONTENT_BYTES + 1))
    data = service.key_read(redis, "key", {}, {})
    assert data["content_omitted"] is True and data["value"] is None


def test_scan_preserves_empty_batch_cursor(monkeypatch):
    client = Mock()
    client.scan.return_value = (71, [])
    monkeypatch.setattr(service, "target", lambda params: (client, {}, "*.detect.*"))
    result = alarm_redis.execute("key_scan", {"node_id": 1, "cursor": "5"})
    assert result["data"]["next_cursor"] == "71"
    assert result["data"]["items"] == []
    client.scan.assert_called_once_with(cursor=5, match="*.detect.*", count=100)


def test_slowlog_does_not_return_arguments(monkeypatch):
    client = Mock()
    client.execute_command.return_value = [[1, 100, 200, [b"SET", b"secret-key", b"super secret value"]]]
    monkeypatch.setattr(service, "target", lambda params: (client, {}, ""))
    result = alarm_redis.execute("node_slowlog", {"node_id": 1})
    assert result["data"]["items"][0]["command"] == "SET"
    assert "super-secret" not in str(result)


def test_info_partial_sections_keep_successful_snapshot(monkeypatch):
    client = Mock()

    def info(section=None):
        if section == "commandstats":
            return {"cmdstat_get": {"calls": 5, "usec": 10, "usec_per_call": 2}}
        if section:
            raise RuntimeError("unknown section")
        return {"run_id": "instance", "role": "master", "connected_clients": 3}

    client.info.side_effect = info
    monkeypatch.setattr(service, "target", lambda params: (client, {}, ""))
    monkeypatch.setattr(service, "actual_address", lambda c: {"host": "master", "port": 6379})
    result = alarm_redis.execute("node_info", {"node_id": 1})
    assert result["data"]["commands"][0]["command"] == "get"
    assert result["data"]["info"]["connected_clients"] == 3
    assert result["data"]["errorstats"] is None
    assert len(result["warnings"]) == 2


def test_non_default_template_prefix_and_independent_strategy_cache(monkeypatch):
    chosen = node(2, "other")
    client = Mock()
    monkeypatch.setattr(service, "resolve_node", lambda params: chosen)
    monkeypatch.setattr(service, "setup_client", lambda *args: client)
    _, source, redis_key = service.target(
        {"template_id": "DATA_LIST_KEY", "node_id": 2, "strategy_id": 7, "key_params": {"item_id": 8}}
    )
    assert redis_key == f"{service.keys.PUBLIC_KEY_PREFIX}.other.access.data.7.8"
    assert source["node"]["id"] == 2
    cache = Mock(return_value=client)
    monkeypatch.setattr(service, "Cache", cache)
    monkeypatch.setattr(alarm_strategy, "scoped_strategy", lambda *args: SimpleNamespace(bk_biz_id=7))
    _, source, redis_key = service.target({"template_id": "STRATEGY_CONFIG_CACHE", "strategy_id": 7})
    cache.assert_called_once_with("cache-strategy")
    assert source["node"] is None and redis_key.endswith(".strategy_7")


def test_node_info_requires_configured_node_and_backend():
    with pytest.raises(Exception, match="node_id"):
        alarm_redis.execute("node_info", {})
    with pytest.raises(Exception):
        alarm_redis.execute("key_read", {"backend": "arbitrary-url", "key": "x"})


def test_operations_are_registered():
    for name in alarm_redis.OPERATIONS:
        assert KernelRPCRegistry.get_function_detail("admin.alarm_redis." + name) is not None


@pytest.fixture
def native_redis():
    """仅用于验证 Redis 协议解析的隔离实例；不连接部署环境。"""
    import shutil
    import subprocess
    import tempfile
    import time
    from redis import Redis

    binary = shutil.which("redis-server")
    if not binary:
        pytest.skip("redis-server not installed")
    with tempfile.TemporaryDirectory(prefix="alarm-redis-", dir="/tmp") as directory:
        socket = directory + "/redis.sock"
        process = subprocess.Popen(
            [binary, "--port", "0", "--save", "", "--appendonly", "no", "--unixsocket", socket],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        client = Redis(unix_socket_path=socket, decode_responses=True)
        try:
            for _ in range(50):
                try:
                    if client.ping():
                        break
                except Exception:
                    time.sleep(0.02)
            else:
                pytest.fail("isolated Redis did not start")
            yield client
        finally:
            client.close()
            process.terminate()
            process.wait(timeout=5)


def test_native_info_clients_and_raw_slowlog(monkeypatch, native_redis):
    client = native_redis
    client.config_set("slowlog-log-slower-than", 0)
    client.set("sample", "a value containing spaces")
    monkeypatch.setattr(service, "target", lambda params: (client, {}, ""))
    monkeypatch.setattr(service, "actual_address", lambda c: {"host": "isolated-test", "port": 0})
    info = alarm_redis.execute("node_info", {"node_id": 1})["data"]
    assert info["info"]["redis_version"]
    assert any(row["command"] == "set" for row in info["commands"])
    clients = alarm_redis.execute("node_clients", {"node_id": 1})["data"]
    assert isinstance(clients["items"][0]["age"], int)
    slowlog = alarm_redis.execute("node_slowlog", {"node_id": 1})["data"]
    write = next(row for row in slowlog["items"] if row["command"].lower() == "set")
    assert write["argument_count"] == 2
    assert "containing spaces" not in str(slowlog)


def test_strategy_detail_only_serializes_without_refresh_or_priority_generation(monkeypatch):
    record = SimpleNamespace(**{field: "" for field in alarm_strategy.FIELDS})
    record.id = 7
    projection = Mock()
    projection.to_dict.return_value = {"items": [], "detects": []}
    monkeypatch.setattr(alarm_strategy, "scoped_strategy", lambda *args: record)
    monkeypatch.setattr(alarm_strategy.Strategy, "from_models", Mock(return_value=[projection]))
    result = alarm_strategy.detail({"strategy_id": 7})
    assert result["data"]["strategy"]["id"] == 7
    assert result["meta"]["tenant_scope"] == "all"
    projection.to_dict.assert_called_once_with(convert_dashboard=False, generate_priority_group_key=False)


def test_query_rejects_unknown_command_switch():
    with pytest.raises(Exception, match="不支持的请求参数"):
        alarm_redis.execute("node_info", {"node_id": 1, "command": "FLUSHALL"})


def test_key_expiring_between_type_and_ttl_is_missing():
    client = Mock()
    client.type.return_value = "list"
    client.ttl.return_value = -2
    status = service.key_status(client, "key", {})
    assert status["exists"] is False and status["type"] == "none"
    client.llen.assert_not_called()


def test_disabled_node_is_not_connected(monkeypatch):
    disabled = node()
    disabled.is_enable = False
    monkeypatch.setattr(service, "resolve_node", lambda params: disabled)
    connect = Mock(side_effect=AssertionError("disabled node must not be connected"))
    monkeypatch.setattr(service, "setup_client", connect)
    with pytest.raises(Exception, match="已禁用"):
        service.target({"node_id": 1, "key": "key"})
    connect.assert_not_called()


def test_route_metadata_includes_machine_readable_parameters():
    details = KernelRPCRegistry.get_function_detail("admin.alarm_redis.node_info")
    assert details["params_schema"]["required"] == ["node_id"]
    assert details["params_schema"]["additionalProperties"] is False
    assert "command" not in details["params_schema"]["properties"]


@pytest.mark.parametrize(
    "filters",
    [
        {"strategy_id": [1, 2], "bk_biz_id": [2, -7], "scenario": ["os", "host_process"], "is_enabled": [False]},
        {"strategy_id": 1, "bk_biz_id": 2, "scenario": "os", "is_enabled": False},
    ],
)
def test_strategy_list_combines_multi_value_filters(monkeypatch, filters):
    query = Mock()
    query.filter.return_value = query
    query.order_by.return_value = query
    monkeypatch.setattr(alarm_strategy, "strategy_queryset", lambda params: query)
    monkeypatch.setattr(alarm_strategy, "paginate_queryset", lambda *args, **kwargs: ([], 0))
    result = alarm_strategy.list_strategies(filters)
    for key, value in filters.items():
        field = "id" if key == "strategy_id" else key
        query.filter.assert_any_call(**{field + "__in": value if isinstance(value, list) else [value]})
    assert result["data"]["items"] == []


def test_strategy_empty_lists_do_not_filter_and_detail_still_requires_scalar(monkeypatch):
    query = Mock()
    query.order_by.return_value = query
    monkeypatch.setattr(alarm_strategy, "strategy_queryset", lambda params: query)
    monkeypatch.setattr(alarm_strategy, "paginate_queryset", lambda *args, **kwargs: ([], 0))
    alarm_strategy.list_strategies({"strategy_id": [], "bk_biz_id": [], "scenario": []})
    query.filter.assert_not_called()
    with pytest.raises(Exception):
        alarm_strategy.validate({"strategy_id": [1, 2]}, "detail")


def test_strategy_multiple_names_are_or_conditions(monkeypatch):
    query = Mock()
    query.filter.return_value = query
    query.order_by.return_value = query
    monkeypatch.setattr(alarm_strategy, "strategy_queryset", lambda params: query)
    monkeypatch.setattr(alarm_strategy, "paginate_queryset", lambda *args, **kwargs: ([], 0))
    alarm_strategy.list_strategies({"name": ["CPU", "内存"]})
    condition = query.filter.call_args.args[0]
    assert condition.connector == "OR"
    assert condition.children == [("name__icontains", "CPU"), ("name__icontains", "内存")]


def test_native_slowlog_with_binary_arguments_never_decodes_payload(monkeypatch, native_redis):
    native_redis.config_set("slowlog-log-slower-than", 0)
    native_redis.set("binary-key", b"\xff\xd7\x00compressed-data")
    monkeypatch.setattr(service, "target", lambda params: (native_redis, {}, ""))
    result = alarm_redis.execute("node_slowlog", {"node_id": 1})["data"]
    assert any(row["command"].lower() == "set" and row["argument_count"] == 2 for row in result["items"])
    assert "compressed-data" not in str(result)


@pytest.mark.parametrize("operation", ["key_status", "key_read"])
def test_batch_keys_reuse_original_operations_and_keep_partial_failures(monkeypatch, redis, operation):
    redis.set("first", "hello")
    redis.rpush("second", "a", "b", "c")
    target = Mock(return_value=(redis, {}, ""))
    monkeypatch.setattr(service, "target", target)
    original = service.key_status

    def status(client, key, source):
        if key == "broken":
            raise RuntimeError("read denied")
        return original(client, key, source)

    monkeypatch.setattr(service, "key_status", status)
    data = alarm_redis.execute(
        operation,
        {"node_id": 1, "keys": ["first", "broken", "second", "missing"], "page_size": 2}
        if operation == "key_read"
        else {"node_id": 1, "keys": ["first", "broken", "second", "missing"]},
    )["data"]
    target.assert_called_once()
    assert [item["key"] for item in data["items"]] == ["first", "broken", "second", "missing"]
    assert data["items"][1]["error"] == "read denied"
    assert data["items"][3]["exists"] is False
    if operation == "key_read":
        assert data["items"][0]["value"] == "hello"
        assert data["items"][2]["value"] == ["a", "b"]
        assert data["items"][2]["next_cursor"] == "2"


@pytest.mark.parametrize("keys", [[], ["a"] * 21])
def test_batch_key_http_limits(keys):
    with pytest.raises(Exception):
        alarm_redis.execute("key_read", {"node_id": 1, "keys": keys})
