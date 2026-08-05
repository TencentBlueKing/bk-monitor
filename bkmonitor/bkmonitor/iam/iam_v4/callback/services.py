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
# 资源回调 dispatch —— 通过 register 装饰器可插拔注册
#
# 装饰器统一做 codec 编解码，保证 handler 内部只处理"业务 ID"：
#   * 入站 decode：
#       - fetch_instance_info 的 ids     → 业务 ID
#       - list_instance 的 filter.parent.id → 业务 ID（parent 类型另用其 codec）
#   * 出站 encode：
#       - list_instance / fetch_instance_info 返回的每一项 id → 方言 ID
#
# handler 保持纯业务：拿业务对象、拼业务 ID，不感知 v4 方言。
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from ...iam_engine.provider.codec import IdentityCodec, NameCodec

logger = logging.getLogger(__name__)

ListInstanceFn = Callable[[dict, dict], dict]
FetchInstanceFn = Callable[[list[str], list[str]], list[dict]]


class CallbackService:
    """回调分发器 —— 持有 codec、维护 handler 注册表、装饰器包装编解码。"""

    def __init__(self, codec: NameCodec | None = None) -> None:
        self._codec: NameCodec = codec or IdentityCodec()
        self._list_handlers: dict[str, ListInstanceFn] = {}
        self._fetch_handlers: dict[str, FetchInstanceFn] = {}

    # ------------------------------------------------------------------
    # 装配（重置 codec 时使用；一般在 Django ready 阶段调用一次）
    # ------------------------------------------------------------------

    def set_codec(self, codec: NameCodec) -> None:
        self._codec = codec

    # ------------------------------------------------------------------
    # 注册装饰器
    # ------------------------------------------------------------------

    def list_instance(self, resource_type: str) -> Callable[[ListInstanceFn], ListInstanceFn]:
        """装饰器：注册一个 list_instance handler，自动做入参 decode + 出参 encode。

        handler 签名：(filter_data: dict, page: dict) -> {"count": int, "results": [...]}
        results 里的每一项要包含 "id"（业务 ID）；装饰器会把它 encode 成方言 ID。
        """

        def decorator(fn: ListInstanceFn) -> ListInstanceFn:
            def wrapper(filter_data: dict, page: dict) -> dict:
                decoded_filter = self._decode_filter(filter_data)
                result = fn(decoded_filter, page)
                self._encode_result_ids(result.get("results") or [], resource_type)
                return result

            self._list_handlers[resource_type] = wrapper
            return fn

        return decorator

    def fetch_instance_info(self, resource_type: str) -> Callable[[FetchInstanceFn], FetchInstanceFn]:
        """装饰器：注册一个 fetch_instance_info handler，自动做入参 decode + 出参 encode。

        handler 签名：(ids: list[str], requires: list[str]) -> list[dict]
        入参 ids：装饰器会把方言 ID → 业务 ID 后交给 handler。
        出参每一项的 "id"：业务 ID，装饰器会 encode 回方言 ID。
        """

        def decorator(fn: FetchInstanceFn) -> FetchInstanceFn:
            def wrapper(ids: list[str], requires: list[str]) -> list[dict]:
                decoded_ids = [self._codec.decode_resource_id(resource_type, i) for i in ids]
                result = fn(decoded_ids, requires)
                self._encode_result_ids(result, resource_type)
                return result

            self._fetch_handlers[resource_type] = wrapper
            return fn

        return decorator

    # ------------------------------------------------------------------
    # 分发（供 views 调用）
    # ------------------------------------------------------------------

    def dispatch_list_instance(self, resource_type: str, filter_data: dict, page: dict) -> dict:
        handler = self._list_handlers.get(resource_type)
        if handler is None:
            logger.warning("[iam_v4:callback] no list_instance handler for type=%s", resource_type)
            return {"count": 0, "results": []}
        return handler(filter_data, page)

    def dispatch_fetch_instance_info(
        self,
        resource_type: str,
        ids: list[str],
        requires: list[str],
    ) -> list[dict]:
        handler = self._fetch_handlers.get(resource_type)
        if handler is None:
            logger.warning("[iam_v4:callback] no fetch_instance_info handler for type=%s", resource_type)
            return []
        return handler(ids, requires)

    # ------------------------------------------------------------------
    # 内部：编解码工具
    # ------------------------------------------------------------------

    def _decode_filter(self, filter_data: dict) -> dict:
        """对 filter 里的 parent.id 做 decode（parent.type 按其自身 codec 规则）。

        为了不破坏 handler 视角，返回一个浅拷贝副本。
        """
        if not filter_data:
            return filter_data
        parent: Any = filter_data.get("parent")
        if not parent or not isinstance(parent, dict):
            return filter_data
        parent_type = parent.get("type", "")
        parent_id = parent.get("id", "")
        if not parent_type or not parent_id:
            return filter_data
        new_filter = dict(filter_data)
        new_parent = dict(parent)
        new_parent["id"] = self._codec.decode_resource_id(parent_type, parent_id)
        new_filter["parent"] = new_parent
        return new_filter

    def _encode_result_ids(self, items: list[dict], resource_type: str) -> None:
        """就地把 items 里每一项的 "id" 从业务 ID encode 为方言 ID。"""
        for item in items:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id")
            if not isinstance(raw_id, str):
                continue
            item["id"] = self._codec.encode_resource_id(resource_type, raw_id)


# ---------------------------------------------------------------------------
# 模块级默认单例 —— 便于 handlers.py 直接 `from .services import service` 使用
# 实际 codec 由 Provider 在 Django ready 阶段通过 service.set_codec(...) 注入。
# ---------------------------------------------------------------------------

service = CallbackService()
