"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ---------------------------------------------------------------------------
# 全局 handler 注册表
#
# handler 通过 register_* 装饰器在 import 时注册到模块级 dict。
# 不绑定任何 CallbackService 实例，由各 Provider 版本的 dispatch 层
# 自行读取 + 包装（codec、协议适配等）。
#
# 装饰器名 register_list_instance / register_fetch_instance_info 来自
# IAM 平台的标准回调协议方法名，与 IAM 版本无关。
# ---------------------------------------------------------------------------

from __future__ import annotations

from collections.abc import Callable

ListInstanceFn = Callable[[dict, dict], dict]
FetchInstanceFn = Callable[[list[str], list[str]], list[dict]]

_list_handlers: dict[str, ListInstanceFn] = {}
_fetch_handlers: dict[str, FetchInstanceFn] = {}


def register_list_instance(resource_type: str) -> Callable[[ListInstanceFn], ListInstanceFn]:
    """装饰器：注册 list_instance handler。

    handler 签名：
        (filter_data: dict, page: dict) -> {"count": int, "results": list[dict]}

    handler 内部只处理业务 ID；编解码由各 Provider 的 dispatch 层完成。

    Args:
        resource_type: 资源类型 ID（如 "space"、"apm_application"）。

    Returns:
        装饰器函数，原样返回被装饰的 handler。
    """

    def decorator(fn: ListInstanceFn) -> ListInstanceFn:
        _list_handlers[resource_type] = fn
        return fn

    return decorator


def register_fetch_instance_info(resource_type: str) -> Callable[[FetchInstanceFn], FetchInstanceFn]:
    """装饰器：注册 fetch_instance_info handler。

    handler 签名：
        (ids: list[str], requires: list[str]) -> list[dict]

    handler 内部只处理业务 ID；编解码由各 Provider 的 dispatch 层完成。

    Args:
        resource_type: 资源类型 ID（如 "space"、"apm_application"）。

    Returns:
        装饰器函数，原样返回被装饰的 handler。
    """

    def decorator(fn: FetchInstanceFn) -> FetchInstanceFn:
        _fetch_handlers[resource_type] = fn
        return fn

    return decorator
