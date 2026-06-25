"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings

from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry


@KernelRPCRegistry.register(
    "info",
    summary="查询监控基础信息与环境 regime 标志",
    description=(
        "返回当前环境的基础信息：是否多租户(is_multi_tenant_mode)、空间内置链路开关与模式"
        "(enable_space_builtin_data_link/space_builtin_data_link_mode)、监控与蓝鲸站点访问地址。"
        "多租户与否决定结果表命名是否带租户前缀、基础采集 dataid 是否按业务申请等行为。"
    ),
)
def get_monitor_info(params):
    return {
        "is_multi_tenant_mode": settings.ENABLE_MULTI_TENANT_MODE,
        "enable_space_builtin_data_link": settings.ENABLE_SPACE_BUILTIN_DATA_LINK,
        "space_builtin_data_link_mode": settings.SPACE_BUILTIN_DATA_LINK_MODE,
        "monitor_access_url": settings.BK_MONITOR_HOST,
        "site_url": settings.SITE_URL,
    }


BkmCliOpRegistry.register(
    op_id="env-info",
    func_name="info",
    summary="查询环境 regime(多租户/空间内置链路)与访问地址",
    description=(
        "返回 is_multi_tenant_mode / enable_space_builtin_data_link / space_builtin_data_link_mode "
        "等环境 regime 标志及监控访问地址。排障 metadata/datalink 类问题建议前置调用,据此判断结果表"
        "命名是否带租户前缀、基础采集 dataid 是否按业务申请,避免按错误的 regime 假设解读证据。"
    ),
    capability_level="readonly",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["env", "readonly", "discovery"],
    params_schema={},
    example_params={},
)
