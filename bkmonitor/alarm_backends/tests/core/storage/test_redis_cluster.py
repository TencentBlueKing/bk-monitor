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

from alarm_backends.core.storage import redis_cluster
from alarm_backends.core.storage.redis_cluster import (
    PipelineProxy,
    PipelineResultMismatch,
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
        mocker.patch.object(redis_cluster, "get_node_by_strategy_id", return_value=_node)
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
