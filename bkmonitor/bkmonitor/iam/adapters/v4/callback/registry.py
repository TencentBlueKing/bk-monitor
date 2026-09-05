"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

from collections.abc import Callable

ListInstanceHandler = Callable[[dict, dict], dict]
FetchInstanceInfoHandler = Callable[[list[str], list[str]], list[dict]]


class V4CallbackRegistry:
    """监控项目 V4 callback 的 handler 注册入口。

    Registry 由 callback 项目创建并持有，不使用进程全局 handler 状态，也不依赖
    PermissionProvider。独立部署 callback 时，只需在目标项目创建同等的 registry。
    """

    def __init__(self) -> None:
        self._list_handlers: dict[str, ListInstanceHandler] = {}
        self._fetch_handlers: dict[str, FetchInstanceInfoHandler] = {}

    def register_list_instance(
        self,
        resource_type: str,
        *,
        replace: bool = False,
    ) -> Callable[[ListInstanceHandler], ListInstanceHandler]:
        """返回注册 list_instance handler 的装饰器。"""

        def decorator(handler: ListInstanceHandler) -> ListInstanceHandler:
            if resource_type in self._list_handlers and not replace:
                raise ValueError(f"list_instance handler already registered for resource_type={resource_type!r}")
            self._list_handlers[resource_type] = handler
            return handler

        return decorator

    def register_fetch_instance_info(
        self,
        resource_type: str,
        *,
        replace: bool = False,
    ) -> Callable[[FetchInstanceInfoHandler], FetchInstanceInfoHandler]:
        """返回注册 fetch_instance_info handler 的装饰器。"""

        def decorator(handler: FetchInstanceInfoHandler) -> FetchInstanceInfoHandler:
            if resource_type in self._fetch_handlers and not replace:
                raise ValueError(f"fetch_instance_info handler already registered for resource_type={resource_type!r}")
            self._fetch_handlers[resource_type] = handler
            return handler

        return decorator

    def get_list_instance(self, resource_type: str) -> ListInstanceHandler | None:
        return self._list_handlers.get(resource_type)

    def get_fetch_instance_info(self, resource_type: str) -> FetchInstanceInfoHandler | None:
        return self._fetch_handlers.get(resource_type)
