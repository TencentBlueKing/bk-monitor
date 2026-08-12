"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

import pytest

from alarm_backends.core.cache import key
from alarm_backends.core.detect_result import CheckResult
from alarm_backends.core.storage import redis_cluster
from alarm_backends.core.storage.redis import REDIS_SOCKET_TIMEOUT_FLOOR
from alarm_backends.core.storage.redis_cluster import (
    PipelineProxy,
    PipelineResultMismatch,
    RedisNode,
    RedisProxy,
)


def _make_proxy():
    # node_proxy 仅在 pipeline_instance() 中用到；本组用例直接注入 _pipeline_pool，Mock 即可
    return PipelineProxy(mock.Mock())


class TestPipelineProxyExecute:
    def test_success_returns_in_command_order_and_clears_stack(self):
        proxy = _make_proxy()
        pipe = mock.Mock()
        pipe.execute.return_value = ["v1", "v2"]
        proxy._pipeline_pool = {"node-a": pipe}
        proxy.command_stack = ["node-a", "node-a"]

        result = proxy.execute()

        assert result == ["v1", "v2"]
        assert proxy.command_stack == []

    def test_clears_stack_and_resets_pipelines_on_exception(self):
        # 回归：节点 execute 抛错（如连接被关）时，必须清空 command_stack 并 reset 原生 pipeline，
        # 否则被缓存复用的代理会带着脏命令进入下一批，导致结果与请求错位。
        proxy = _make_proxy()
        pipe = mock.Mock()
        pipe.execute.side_effect = RuntimeError("server closed connection")
        proxy._pipeline_pool = {"node-a": pipe}
        proxy.command_stack = ["node-a", "node-a"]

        with pytest.raises(RuntimeError):
            proxy.execute()

        assert proxy.command_stack == []
        pipe.reset.assert_called_once()

    def test_raises_mismatch_when_node_response_count_differs(self):
        # 某节点返回数与入队命令数不一致时抛 PipelineResultMismatch（RedisError 派生），不静默错位回填
        proxy = _make_proxy()
        pipe = mock.Mock()
        pipe.execute.return_value = ["only-one"]  # 1 个响应
        proxy._pipeline_pool = {"node-a": pipe}
        proxy.command_stack = ["node-a", "node-a"]  # 2 条命令

        with pytest.raises(PipelineResultMismatch):
            proxy.execute()

        assert proxy.command_stack == []

    def test_no_dirty_carryover_between_reused_executes(self):
        # 复现并验证修复：上一批失败后，复用同一 proxy 的下一批不应残留命令、不应错位
        proxy = _make_proxy()
        bad = mock.Mock()
        bad.execute.side_effect = RuntimeError("boom")
        proxy._pipeline_pool = {"node-a": bad}
        proxy.command_stack = ["node-a"]
        with pytest.raises(RuntimeError):
            proxy.execute()
        assert proxy.command_stack == []

        good = mock.Mock()
        good.execute.return_value = ["x", "y"]
        proxy._pipeline_pool = {"node-b": good}
        proxy.command_stack = ["node-b", "node-b"]

        result = proxy.execute()

        assert result == ["x", "y"]
        assert proxy.command_stack == []


class _Node:
    """最小 CacheNode 替身；execute 行为由 fail/partial 控制。"""

    def __init__(self, nid):
        self.id = nid
        self.fail = False
        self.partial = False


class _FakeNativePipeline:
    """模拟 redis-py 原生 pipeline：execute() 后自重置 buffer（成功或失败均重置）。"""

    def __init__(self, node):
        self.node = node
        self.buffer = []

    def get(self, key):
        self.buffer.append(key)
        return self

    def execute(self):
        buf = self.buffer
        self.buffer = []
        if self.node.fail:
            raise ConnectionError("server closed connection")
        out = [f"val:{k}" for k in buf]
        if self.node.partial and out:
            out = out[:-1]  # 少返回一个，模拟部分响应
        return out

    def reset(self):
        self.buffer = []


class _FakeClient:
    def __init__(self, node):
        self.node = node

    def pipeline(self, *args, **kwargs):
        return _FakeNativePipeline(self.node)


class _Key(str):
    """携带 strategy_id 的 str 子类，供 PipelineProxy 路由提取（复刻 key.py 的 SimilarStr）。"""

    strategy_id = 0


def _key(alert_id, strategy_id=101):
    k = _Key(f"snap:{strategy_id}:{alert_id}")
    k.strategy_id = strategy_id
    return k


class TestPipelineProxyCascade:
    """端到端：经真实 RedisProxy（缓存单例代理）+ PipelineProxy，验证一次失败不串扰下一批。"""

    @pytest.fixture
    def node(self, mocker):
        _node = _Node("node-A")
        mocker.patch.object(redis_cluster, "_refresh_strategy_router_cache")
        mocker.patch.object(redis_cluster, "_resolve_node", return_value=_node)
        mocker.patch.object(RedisProxy, "get_client", side_effect=lambda n: _FakeClient(n))
        return _node

    def test_node_failure_does_not_poison_next_batch(self, node):
        proxy = RedisProxy("service")

        # 批1：节点宕，execute 抛错；RedisProxy 缓存该 PipelineProxy 供后续复用
        node.fail = True
        pipe = proxy.pipeline()
        pipe.get(_key(1))
        pipe.get(_key(2))
        with pytest.raises(ConnectionError):
            pipe.execute()
        assert pipe.command_stack == []  # 异常后已清栈

        # 批2：节点恢复，复用同一缓存代理。修复前此处会因脏命令栈返回 4 条 → 消费端 keys[index] 越界
        node.fail = False
        pipe2 = proxy.pipeline()
        assert pipe2 is pipe  # 确为缓存复用的同一单例
        pipe2.get(_key(3))
        pipe2.get(_key(4))
        result = pipe2.execute()

        assert len(result) == 2
        assert result == ["val:snap:101:3", "val:snap:101:4"]

    def test_partial_node_response_raises_mismatch(self, node):
        node.partial = True  # 某节点少返回一个响应
        proxy = RedisProxy("service")
        pipe = proxy.pipeline()
        pipe.get(_key(1))
        pipe.get(_key(2))

        with pytest.raises(PipelineResultMismatch):
            pipe.execute()
        assert pipe.command_stack == []


class TestRedisNodeConnectionConf:
    """分片节点连接构造: 历史上 gen_connection_conf 只取 db, 无任何 socket 超时(主切换时读无限挂起)。"""

    def test_gen_connection_conf_injects_resilient_params(self):
        node = RedisNode("127.0.0.1", 6379, password="x")
        conf = node.gen_connection_conf("queue")

        # 修复后: 分片节点必须带有界 connect/read 超时 + keepalive
        assert conf["socket_timeout"] >= REDIS_SOCKET_TIMEOUT_FLOOR
        assert conf["socket_connect_timeout"] < conf["socket_timeout"]
        assert conf["socket_keepalive"] is True
        # 原有连接字段保持不变
        assert conf["host"] == "127.0.0.1"
        assert conf["port"] == 6379
        assert "db" in conf


class TestStrategyRouterCacheTTL:
    """CacheRouter 进程快照 TTL / stale-while-error / pipeline pin / routing_snapshot。"""

    def setup_method(self):
        redis_cluster.STRATEGY_ROUTER_CACHE = None
        redis_cluster.STRATEGY_ROUTER_CACHE_AT = 0.0
        redis_cluster.STRATEGY_ROUTER_CACHE_NEXT_RETRY_AT = 0.0
        redis_cluster.STRATEGY_NODE_MAP = {}
        redis_cluster.DEFAULT_NODE = None
        redis_cluster._reset_routing_pin_for_tests()

    def teardown_method(self):
        self.setup_method()

    def _router(self, score, node):
        return mock.Mock(strategy_score=score, node=node)

    def test_loads_once_within_ttl_and_reuses_node_map(self):
        node_a = mock.Mock(id="a", node_alias="alarm-a")
        routers = [self._router(1000, node_a)]
        qs = mock.MagicMock()
        qs.filter.return_value.select_related.return_value.order_by.return_value = routers

        with mock.patch.object(redis_cluster, "get_cluster", return_value=mock.Mock(name="default")):
            with mock.patch.object(redis_cluster, "CacheRouter") as cache_router:
                with mock.patch.object(redis_cluster, "monotonic", side_effect=[100.0, 110.0, 120.0]):
                    with mock.patch.object(redis_cluster, "_router_cache_ttl", return_value=30.0):
                        cache_router.objects = qs
                        assert redis_cluster.get_node_by_strategy_id(1) is node_a
                        assert redis_cluster.get_node_by_strategy_id(1) is node_a
                        assert redis_cluster.get_node_by_strategy_id(2) is node_a

        assert qs.filter.call_count == 1
        assert redis_cluster.STRATEGY_NODE_MAP[1] is node_a
        assert redis_cluster.STRATEGY_NODE_MAP[2] is node_a

    def test_expires_reloads_and_rebases_node_map(self):
        node_old = mock.Mock(id="old", node_alias="alarm-old")
        node_new = mock.Mock(id="new", node_alias="alarm-new")
        qs = mock.MagicMock()
        qs.filter.return_value.select_related.return_value.order_by.side_effect = [
            [self._router(1000, node_old)],
            [self._router(1000, node_new)],
        ]

        with mock.patch.object(redis_cluster, "get_cluster", return_value=mock.Mock(name="default")):
            with mock.patch.object(redis_cluster, "CacheRouter") as cache_router:
                with mock.patch.object(redis_cluster, "monotonic", side_effect=[100.0, 140.0]):
                    with mock.patch.object(redis_cluster, "_router_cache_ttl", return_value=30.0):
                        cache_router.objects = qs
                        assert redis_cluster.get_node_by_strategy_id(1) is node_old
                        assert redis_cluster.get_node_by_strategy_id(1) is node_new

        assert qs.filter.call_count == 2
        assert redis_cluster.STRATEGY_NODE_MAP[1] is node_new

    def test_empty_router_table_still_respects_ttl(self):
        qs = mock.MagicMock()
        qs.filter.return_value.select_related.return_value.order_by.return_value = []

        with mock.patch.object(redis_cluster, "get_cluster", return_value=mock.Mock(name="default")):
            with mock.patch.object(redis_cluster, "CacheRouter") as cache_router:
                with mock.patch.object(redis_cluster, "monotonic", side_effect=[100.0, 110.0]):
                    with mock.patch.object(redis_cluster, "_router_cache_ttl", return_value=30.0):
                        cache_router.objects = qs
                        with pytest.raises(Exception, match="策略ID超过设置的默认上限"):
                            redis_cluster.get_node_by_strategy_id(1)
                        with pytest.raises(Exception, match="策略ID超过设置的默认上限"):
                            redis_cluster.get_node_by_strategy_id(1)

        assert qs.filter.call_count == 1

    def test_stale_while_error_keeps_old_cache_and_backs_off(self):
        node_old = mock.Mock(id="old", node_alias="alarm-old")
        qs = mock.MagicMock()
        # 首次成功，之后持续失败
        qs.filter.return_value.select_related.return_value.order_by.side_effect = [
            [self._router(1000, node_old)],
            RuntimeError("db down"),
            RuntimeError("db down"),
        ]

        with mock.patch.object(redis_cluster, "get_cluster", return_value=mock.Mock(name="default")):
            with mock.patch.object(redis_cluster, "CacheRouter") as cache_router:
                with mock.patch.object(
                    redis_cluster, "monotonic", side_effect=[100.0, 140.0, 141.0, 142.0]
                ):
                    with mock.patch.object(redis_cluster, "_router_cache_ttl", return_value=30.0):
                        with mock.patch.object(redis_cluster, "_router_cache_retry_backoff", return_value=5.0):
                            with mock.patch.object(redis_cluster, "_report_router_refresh_fail"):
                                cache_router.objects = qs
                                assert redis_cluster.get_node_by_strategy_id(1) is node_old
                                # TTL 过期后刷新失败：仍返回旧节点
                                assert redis_cluster.get_node_by_strategy_id(1) is node_old
                                # 退避窗口内不再打库
                                assert redis_cluster.get_node_by_strategy_id(1) is node_old
                                assert redis_cluster.get_node_by_strategy_id(2) is node_old

        # 1 次成功加载 + 1 次失败刷新；退避内无第三次查询
        assert qs.filter.call_count == 2
        assert redis_cluster.STRATEGY_NODE_MAP[1] is node_old

    def test_refresh_fail_without_cache_still_raises(self):
        qs = mock.MagicMock()
        qs.filter.return_value.select_related.return_value.order_by.side_effect = RuntimeError("db down")

        with mock.patch.object(redis_cluster, "get_cluster", return_value=mock.Mock(name="default")):
            with mock.patch.object(redis_cluster, "CacheRouter") as cache_router:
                with mock.patch.object(redis_cluster, "monotonic", return_value=100.0):
                    cache_router.objects = qs
                    with pytest.raises(RuntimeError, match="db down"):
                        redis_cluster.get_node_by_strategy_id(1)

    def test_pipeline_pin_keeps_same_node_when_global_cache_switches(self):
        node_old = mock.Mock(id="old")
        node_new = mock.Mock(id="new")
        redis_cluster.STRATEGY_ROUTER_CACHE = [self._router(10**12, node_old)]
        redis_cluster.STRATEGY_ROUTER_CACHE_AT = 100.0
        redis_cluster.STRATEGY_NODE_MAP = {}

        node_proxy = mock.Mock()
        pipe_inst = mock.Mock()
        node_proxy.get_client.return_value.pipeline.return_value = pipe_inst
        key = mock.Mock(strategy_id=1)

        with mock.patch.object(redis_cluster, "monotonic", return_value=100.0):
            with mock.patch.object(redis_cluster, "_router_cache_ttl", return_value=30.0):
                pp = PipelineProxy(node_proxy)
                pp.lpush(key, "x")
                # 模拟其它协程/后续刷新已切到新节点
                redis_cluster.STRATEGY_ROUTER_CACHE = [self._router(10**12, node_new)]
                redis_cluster.STRATEGY_NODE_MAP.clear()
                pp.expire(key, 60)
                assert pp.command_stack == ["old", "old"]
                # pipeline 只用实例快照，不得留下 thread-local pin
                assert redis_cluster._get_routing_pin() is None
                pipe_inst.execute.return_value = ["ok", True]
                pp.execute()

        assert pp.command_stack == []
        assert pp._routing_snapshot is None
        assert redis_cluster._get_routing_pin() is None
        assert all(call.args[0] is node_old for call in node_proxy.get_client.call_args_list)

    def test_pipeline_setup_fail_does_not_leak_thread_pin(self):
        """入队期 get_client/setup_client 失败不得泄漏 thread pin，否则路由永久钉死旧节点。"""
        node_old = mock.Mock(id="old")
        node_new = mock.Mock(id="new")
        redis_cluster.STRATEGY_ROUTER_CACHE = [self._router(10**12, node_old)]
        redis_cluster.STRATEGY_ROUTER_CACHE_AT = 100.0
        redis_cluster.STRATEGY_NODE_MAP = {}

        node_proxy = mock.Mock()
        node_proxy.get_client.side_effect = Exception("client setup failed")
        key = mock.Mock(strategy_id=1)

        with mock.patch.object(redis_cluster, "monotonic", return_value=100.0):
            with mock.patch.object(redis_cluster, "_router_cache_ttl", return_value=30.0):
                pp = PipelineProxy(node_proxy)
                with pytest.raises(Exception, match="client setup failed"):
                    pp.lpush(key, "x")

        assert pp.command_stack == []
        assert pp._routing_snapshot is None
        assert redis_cluster._get_routing_pin() is None

        # 全局已切新节点：单命令路径应跟上，而不是永久解析 old
        redis_cluster.STRATEGY_ROUTER_CACHE = [self._router(10**12, node_new)]
        redis_cluster.STRATEGY_ROUTER_CACHE_AT = 100.0
        redis_cluster.STRATEGY_NODE_MAP.clear()
        with mock.patch.object(redis_cluster, "monotonic", return_value=100.0):
            with mock.patch.object(redis_cluster, "_router_cache_ttl", return_value=30.0):
                assert redis_cluster.get_node_by_strategy_id(1) is node_new

    def test_pipeline_abandon_without_execute_does_not_leak_thread_pin(self):
        node_old = mock.Mock(id="old")
        node_new = mock.Mock(id="new")
        redis_cluster.STRATEGY_ROUTER_CACHE = [self._router(10**12, node_old)]
        redis_cluster.STRATEGY_ROUTER_CACHE_AT = 100.0
        redis_cluster.STRATEGY_NODE_MAP = {}

        node_proxy = mock.Mock()
        pipe_inst = mock.Mock()
        node_proxy.get_client.return_value.pipeline.return_value = pipe_inst

        with mock.patch.object(redis_cluster, "monotonic", return_value=100.0):
            with mock.patch.object(redis_cluster, "_router_cache_ttl", return_value=30.0):
                pp = PipelineProxy(node_proxy)
                pp.lpush(mock.Mock(strategy_id=1), "x")
                # 遗弃：不调用 execute；实例 snapshot 可残留在本 proxy，但不得污染线程

        assert redis_cluster._get_routing_pin() is None
        redis_cluster.STRATEGY_ROUTER_CACHE = [self._router(10**12, node_new)]
        redis_cluster.STRATEGY_ROUTER_CACHE_AT = 100.0
        redis_cluster.STRATEGY_NODE_MAP.clear()
        with mock.patch.object(redis_cluster, "monotonic", return_value=100.0):
            with mock.patch.object(redis_cluster, "_router_cache_ttl", return_value=30.0):
                assert redis_cluster.get_node_by_strategy_id(1) is node_new

    def test_next_pipeline_call_resets_abandoned_batch(self):
        """上一任务入队后未 execute：下一次 pipeline() 必须清残留，并按新路由开新批次。"""
        node_old = mock.Mock(id="old")
        node_new = mock.Mock(id="new")
        redis_cluster.STRATEGY_ROUTER_CACHE = [self._router(10**12, node_old)]
        redis_cluster.STRATEGY_ROUTER_CACHE_AT = 100.0
        redis_cluster.STRATEGY_NODE_MAP = {}

        pipes = {}

        class FakePipe:
            def __init__(self, node_id):
                self.node_id = node_id
                self.cmds = []

            def lpush(self, *args, **kwargs):
                self.cmds.append(f"{self.node_id}:lpush")
                return True

            def expire(self, *args, **kwargs):
                self.cmds.append(f"{self.node_id}:expire")
                return True

            def execute(self):
                out = list(self.cmds)
                self.cmds.clear()
                return out

            def reset(self):
                self.cmds.clear()

        def get_client(node):
            client = mock.Mock()

            def _pipeline(*args, **kwargs):
                if node.id not in pipes:
                    pipes[node.id] = FakePipe(node.id)
                return pipes[node.id]

            client.pipeline = _pipeline
            return client

        proxy = redis_cluster.RedisProxy("service")
        proxy.get_client = get_client

        with mock.patch.object(redis_cluster, "monotonic", return_value=100.0):
            with mock.patch.object(redis_cluster, "_router_cache_ttl", return_value=30.0):
                p1 = proxy.pipeline(transaction=False)
                p1.lpush(mock.Mock(strategy_id=1), "abandoned")
                assert p1.command_stack == ["old"]

                redis_cluster.STRATEGY_ROUTER_CACHE = [self._router(10**12, node_new)]
                redis_cluster.STRATEGY_NODE_MAP.clear()

                p2 = proxy.pipeline(transaction=False)
                assert p1 is p2
                assert p2.command_stack == []
                assert p2._routing_snapshot is None
                p2.lpush(mock.Mock(strategy_id=1), "y")
                p2.expire(mock.Mock(strategy_id=1), 60)
                assert p2.command_stack == ["new", "new"]
                result = p2.execute()

        assert result == ["new:lpush", "new:expire"]
        assert all(c.startswith("new:") for c in result)
        assert "old" not in "".join(result)

    def test_check_result_new_batch_resets_abandoned_pipeline(self, mocker):
        """CheckResult 类缓存不能绕过 RedisProxy 的新批次入口。"""
        node_old = _Node("old")
        node_new = _Node("new")
        redis_cluster.STRATEGY_ROUTER_CACHE = [self._router(10**12, node_old)]
        redis_cluster.STRATEGY_ROUTER_CACHE_AT = 100.0
        redis_cluster.STRATEGY_NODE_MAP = {}

        proxy = RedisProxy("service")
        get_client = mocker.patch.object(proxy, "get_client", side_effect=lambda node: _FakeClient(node))
        mocker.patch.object(key.CHECK_RESULT_CACHE_KEY, "_cache", proxy)
        mocker.patch.object(CheckResult, "_pipeline", None)

        with mock.patch.object(redis_cluster, "monotonic", return_value=100.0):
            with mock.patch.object(redis_cluster, "_router_cache_ttl", return_value=30.0):
                first_batch = CheckResult.begin_pipeline_batch()
                first_batch.get(_key(1))

                redis_cluster.STRATEGY_ROUTER_CACHE = [self._router(10**12, node_new)]
                redis_cluster.STRATEGY_NODE_MAP.clear()

                next_batch = CheckResult.begin_pipeline_batch()
                check_result = CheckResult(strategy_id=101, item_id=1, dimensions_md5="md5", level=1)
                assert check_result.CHECK_RESULT is next_batch
                next_batch.get(_key(2))
                result = next_batch.execute()

        assert result == ["val:snap:101:2"]
        assert get_client.call_args_list[-1].args[0] is node_new

    def test_routing_snapshot_keeps_same_node_across_ttl_boundary(self):
        node_old = mock.Mock(id="old")
        node_new = mock.Mock(id="new")
        redis_cluster.STRATEGY_ROUTER_CACHE = [self._router(10**12, node_old)]
        redis_cluster.STRATEGY_ROUTER_CACHE_AT = 100.0
        redis_cluster.STRATEGY_NODE_MAP = {}

        with mock.patch.object(redis_cluster, "monotonic", side_effect=[100.0, 200.0, 200.0]):
            with mock.patch.object(redis_cluster, "_router_cache_ttl", return_value=30.0):
                with redis_cluster.routing_snapshot():
                    assert redis_cluster.get_node_by_strategy_id(1) is node_old
                    redis_cluster.STRATEGY_ROUTER_CACHE = [self._router(10**12, node_new)]
                    redis_cluster.STRATEGY_NODE_MAP.clear()
                    # 块内仍钉在旧快照
                    assert redis_cluster.get_node_by_strategy_id(1) is node_old

        # 离开 pin 后按全局新表解析
        with mock.patch.object(redis_cluster, "monotonic", return_value=200.0):
            with mock.patch.object(redis_cluster, "_router_cache_ttl", return_value=30.0):
                redis_cluster.STRATEGY_ROUTER_CACHE = [self._router(10**12, node_new)]
                redis_cluster.STRATEGY_ROUTER_CACHE_AT = 200.0
                assert redis_cluster.get_node_by_strategy_id(1) is node_new
