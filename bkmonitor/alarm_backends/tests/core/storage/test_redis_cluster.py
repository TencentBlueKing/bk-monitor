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

from alarm_backends.core.storage.redis_cluster import (
    PipelineProxy,
    PipelineResultMismatch,
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
