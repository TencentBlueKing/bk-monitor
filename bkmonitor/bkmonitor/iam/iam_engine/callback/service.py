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
# CallbackService —— codec 感知的 handler 分发器
#
# 持有 NameCodec，从全局注册表读取 handler，dispatch 时统一做编解码包装：
#   - 入站 decode：将平台方言 ID 转为业务 ID 后调用 handler
#   - 出站 encode：将 handler 返回的业务 ID 转回平台方言 ID
#
# 各 Provider 版本各自创建自己的 CallbackService，注入各自版本的 codec。
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging
from typing import Any

from ..provider.codec import IdentityCodec, NameCodec
from .registry import _fetch_handlers, _list_handlers

logger = logging.getLogger(__name__)


class CallbackService:
    """IAM 资源回调分发器。

    codec 在构造时注入，不可变。dispatch 时统一做：
      - 入站 decode：将平台方言 ID 转为业务 ID 后调用 handler
      - 出站 encode：将 handler 返回的业务 ID 转回平台方言 ID

    每个 Provider 实例持有自己的 CallbackService，codec 由 Provider 注入。
    """

    def __init__(self, codec: NameCodec | None = None) -> None:
        """初始化回调分发器。

        Args:
            codec: NameCodec 实例，用于 handler 入参/出参的编解码。
                   未传入时使用 IdentityCodec（恒等）。
        """
        self._codec: NameCodec = codec or IdentityCodec()

    # ------------------------------------------------------------------
    # 分发
    # ------------------------------------------------------------------

    def dispatch_list_instance(self, resource_type: str, filter_data: dict, page: dict) -> dict:
        """分发 list_instance 请求。

        流程：
        1. 从全局注册表查找 handler
        2. decode filter.parent.id（平台方言 → 业务 ID）
        3. 调用 handler
        4. encode results[*]["id"]（业务 ID → 平台方言）

        Args:
            resource_type: 资源类型 ID。
            filter_data: IAM 平台传入的过滤条件。
            page: 分页参数 {"page": int, "page_size": int}。

        Returns:
            {"count": int, "results": list[dict]}，results 中 id 已编码为方言。
        """
        handler = _list_handlers.get(resource_type)
        if handler is None:
            logger.warning("[callback] no list_instance handler for type=%s", resource_type)
            return {"count": 0, "results": []}
        decoded_filter = self._decode_filter(filter_data)
        result = handler(decoded_filter, page)
        self._encode_result_ids(result.get("results") or [], resource_type)
        return result

    def dispatch_fetch_instance_info(
        self,
        resource_type: str,
        ids: list[str],
        requires: list[str],
    ) -> list[dict]:
        """分发 fetch_instance_info 请求。

        流程：
        1. 从全局注册表查找 handler
        2. decode 入参 ids（平台方言 → 业务 ID）
        3. 调用 handler
        4. encode 出参各项 "id"（业务 ID → 平台方言）

        Args:
            resource_type: 资源类型 ID。
            ids: 平台方言格式的资源实例 ID 列表。
            requires: 需要返回的字段列表（如 "_bk_iam_path_"）。

        Returns:
            list[dict]: 每项 "id" 已编码为平台方言。
        """
        handler = _fetch_handlers.get(resource_type)
        if handler is None:
            logger.warning("[callback] no fetch_instance_info handler for type=%s", resource_type)
            return []
        decoded_ids = [self._codec.decode_resource_id(resource_type, i) for i in ids]
        result = handler(decoded_ids, requires)
        self._encode_result_ids(result, resource_type)
        return result

    # ------------------------------------------------------------------
    # 内部：编解码
    # ------------------------------------------------------------------

    def _decode_filter(self, filter_data: dict) -> dict:
        """对 filter 里的 parent.id 做 decode（平台方言 → 业务 ID）。

        Args:
            filter_data: IAM 平台传入的 filter 字典。

        Returns:
            parent.id 已 decode 为业务 ID 的 filter 浅拷贝。
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
        """就地把 items 里每项的 "id" 和 "_bk_iam_path_" 从业务 ID encode 为平台方言 ID。

        _bk_iam_path_ 格式为 IAM 标准资源路径：``"/space,3/apm_application,42/"``。
        每段是 ``<resource_type>,<resource_id>``，对每段的 resource_id 做 encode。

        Args:
            items: handler 返回的结果列表（原地修改）。
            resource_type: 资源类型 ID，用于分派 encode 规则。
        """
        for item in items:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id")
            if isinstance(raw_id, str):
                item["id"] = self._codec.encode_resource_id(resource_type, raw_id)
            raw_path = item.get("_bk_iam_path_")
            if isinstance(raw_path, str):
                item["_bk_iam_path_"] = self._encode_iam_path(raw_path)

    def _encode_iam_path(self, path: str) -> str:
        """对 _bk_iam_path_ 字符串中的每段 resource_id 做 encode。

        IAM 路径格式：``"/space,3/apm_application,42/"``
        每段 ``<type>,<id>`` 中的 id 是业务 ID，需 encode 为平台方言 ID。

        Args:
            path: handler 产出的业务 ID 路径。

        Returns:
            每段 resource_id 已 encode 为平台方言的路径。
        """
        segments: list[str] = []
        for seg in path.split("/"):
            if not seg:
                continue
            # 按首个逗号分割 <type>,<id>；假设 resource_id 本身不含逗号
            parts = seg.split(",", 1)
            if len(parts) == 2:
                rt, rid = parts[0], parts[1]
                segments.append(f"{rt},{self._codec.encode_resource_id(rt, rid)}")
            else:
                segments.append(seg)
        return "/" + "/".join(segments) + ("/" if path.endswith("/") else "")
