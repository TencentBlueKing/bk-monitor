"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


def test_env_info_op_resolves_to_info_func():
    # 导入 info 模块即触发其模块级 BkmCliOpRegistry.register（无需 ensure_loaded）
    from kernel_api.rpc.functions import info  # noqa: F401
    from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry

    op = BkmCliOpRegistry._ops.get("env-info")
    assert op is not None, "env-info op 未注册"
    assert op.func_name == "info"
    assert op.capability_level == "readonly"
    assert op.risk_level == "low"
    assert op.requires_confirmation is False


def test_get_monitor_info_returns_regime_flags():
    from kernel_api.rpc.functions.info import get_monitor_info

    result = get_monitor_info({})
    assert {
        "is_multi_tenant_mode",
        "enable_space_builtin_data_link",
        "space_builtin_data_link_mode",
        "monitor_access_url",
        "site_url",
    } <= set(result)
