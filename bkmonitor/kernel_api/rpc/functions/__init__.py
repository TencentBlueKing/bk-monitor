"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from importlib import import_module
from pkgutil import iter_modules

from kernel_api.rpc.registry import KernelRPCRegistry


def load_builtin_functions() -> None:
    for module in iter_modules(__path__):
        if module.name.startswith("_"):
            continue
        imported_module = import_module(f"{__name__}.{module.name}")
        resource_rpcs = getattr(imported_module, "RESOURCE_RPCS", None)
        if resource_rpcs:
            KernelRPCRegistry.register_resource_list(resource_rpcs)
