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


@KernelRPCRegistry.register(
    "info",
    summary="查询监控基础信息",
    description="返回当前环境的基础信息，包括是否启用多租户模式、监控访问地址和蓝鲸站点访问地址。",
)
def get_monitor_info(params):
    return {
        "is_multi_tenant_mode": settings.ENABLE_MULTI_TENANT_MODE,
        "monitor_access_url": settings.BK_MONITOR_HOST,
        "site_url": settings.SITE_URL,
    }
