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
from kernel_api.resource.bkm_cli import BkmCliOpCallResource
from kernel_api.rpc.bkm_cli_registry import BkmCliOpNotFound, BkmCliOpRegistry
from kernel_api.rpc.registry import KernelRPCRegistry


@pytest.fixture(autouse=True)
def _cleanup_registries():
    """每个测试结束后清理测试注册的函数和 op，避免污染全局注册表。"""
    KernelRPCRegistry.ensure_loaded()
    _original_functions = dict(KernelRPCRegistry._functions)
    _original_ops = dict(BkmCliOpRegistry._ops)
    _original_loaded = KernelRPCRegistry._loaded
    yield
    KernelRPCRegistry._functions = _original_functions
    BkmCliOpRegistry._ops = _original_ops
    KernelRPCRegistry._loaded = _original_loaded


def test_bkm_cli_op_call_resolves_op_id_to_whitelisted_registered_function():
    KernelRPCRegistry.register_function(
        func_name="bkm_cli.phase1_echo",
        summary="phase1 echo",
        description="phase1 echo",
        handler=lambda params: {"echo": params["value"]},
    )
    BkmCliOpRegistry.register(
        op_id="phase1-echo",
        func_name="bkm_cli.phase1_echo",
        capability_level="readonly",
        risk_level="low",
        requires_confirmation=False,
        audit_tags=["phase1"],
        params_schema={"type": "object", "required": ["value"]},
        example_params={"value": "ok"},
    )

    result = BkmCliOpCallResource().perform_request({"op_id": "phase1-echo", "params": {"value": "ok"}})

    assert result["op_id"] == "phase1-echo"
    assert result["func_name"] == "bkm_cli.phase1_echo"
    assert result["protocol"] == "bkm_cli_op_call"
    assert result["result"] == {"echo": "ok"}
    assert result["audit"]["capability_level"] == "readonly"
    assert result["audit"]["risk_level"] == "low"
    assert result["audit"]["audit_tags"] == ["phase1"]


def test_bkm_cli_op_call_rejects_unknown_op_id():
    with pytest.raises(CustomException) as exc:
        BkmCliOpCallResource().perform_request({"op_id": "missing-op", "params": {}})

    assert "未找到 bkm-cli op" in str(exc.value)


def test_resolve_unknown_op_raises_op_not_found_with_code_404():
    """未注册 op 抛 BkmCliOpNotFound，且 .code == 404（让 CLI 映射为 target_not_found，
    而非误落 invalid_argument 兜底导致 agent 徒劳改 schema）。"""
    KernelRPCRegistry.ensure_loaded()
    with pytest.raises(BkmCliOpNotFound) as exc:
        BkmCliOpRegistry.resolve("不存在的op")

    assert exc.value.code == 404
    assert exc.value.status_code == 404
    # 子类仍是 CustomException，沿用既有异常处理链
    assert isinstance(exc.value, CustomException)
    assert "未找到 bkm-cli op" in str(exc.value)


def test_op_not_found_code_survives_into_envelope():
    """custom_exception_handler 末尾 result.update(exc.extra) 不会把 envelope 的 code 冲掉，
    最终 envelope 里 code 仍为 404（子类 __init__ 已把 code=404 注入 extra）。"""
    from core.drf_resource.exceptions import custom_exception_handler

    exc = BkmCliOpNotFound(message="未找到 bkm-cli op: x")
    response = custom_exception_handler(exc, context={})
    assert response.status_code == 404
    assert response.data["code"] == 404


def test_bkm_cli_op_call_does_not_accept_raw_func_name():
    KernelRPCRegistry.register_function(
        func_name="bkm_cli.raw_func_should_not_be_called",
        summary="raw function",
        description="raw function",
        handler=lambda params: {"called": True},
    )

    with pytest.raises(CustomException) as exc:
        BkmCliOpCallResource().perform_request(
            {
                "op_id": "bkm_cli.raw_func_should_not_be_called",
                "params": {"func_name": "bkm_cli.raw_func_should_not_be_called"},
            }
        )

    assert "未找到 bkm-cli op" in str(exc.value)
