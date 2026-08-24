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

import logging
from typing import Any

from ....iam_engine.provider.codec import IdentityCodec, NameCodec
from .registry import V4CallbackRegistry

logger = logging.getLogger(__name__)


class V4CallbackService:
    """项目侧 V4 资源 callback 协议分发器。

    dispatch 方法接收业务资源类型，View 负责先把平台传入的 type 解码。本类仅处理
    V4 的 filter、path 和结果编码协议，再将业务 ID 交给项目 handler。
    """

    def __init__(self, codec: NameCodec | None = None, registry: V4CallbackRegistry | None = None) -> None:
        self._codec: NameCodec = codec or IdentityCodec()
        self.registry = registry or V4CallbackRegistry()

    def decode_resource_type(self, dialect_resource_type: str) -> str:
        """将 V4 请求中的资源类型转换为业务资源类型。"""
        return self._codec.decode_resource_type(dialect_resource_type)

    def dispatch_list_instance(self, resource_type: str, filter_data: dict, page: dict) -> dict:
        """分发 V4 list_instance 请求。"""
        handler = self.registry.get_list_instance(resource_type)
        if handler is None:
            logger.warning("[iam_v4:callback] no list_instance handler for type=%s", resource_type)
            return {"count": 0, "results": []}
        result = handler(self._decode_filter(filter_data), page)
        self._encode_result_ids(result.get("results") or [], resource_type)
        return result

    def dispatch_fetch_instance_info(
        self,
        resource_type: str,
        ids: list[str],
        requires: list[str],
    ) -> list[dict]:
        """分发 V4 fetch_instance_info 请求。"""
        handler = self.registry.get_fetch_instance_info(resource_type)
        if handler is None:
            logger.warning("[iam_v4:callback] no fetch_instance_info handler for type=%s", resource_type)
            return []
        decoded_ids = [self._codec.decode_resource_id(resource_type, resource_id) for resource_id in ids]
        result = handler(decoded_ids, requires)
        self._encode_result_ids(result, resource_type)
        return result

    def _decode_filter(self, filter_data: dict) -> dict:
        """解码 V4 filter.parent 的资源类型和实例 ID。"""
        if not filter_data:
            return filter_data
        parent: Any = filter_data.get("parent")
        if not parent or not isinstance(parent, dict):
            return filter_data
        dialect_parent_type = parent.get("type", "")
        parent_id = parent.get("id", "")
        if not dialect_parent_type or not parent_id:
            return filter_data

        parent_type = self.decode_resource_type(dialect_parent_type)
        decoded_filter = dict(filter_data)
        decoded_parent = dict(parent)
        decoded_parent["type"] = parent_type
        decoded_parent["id"] = self._codec.decode_resource_id(parent_type, parent_id)
        decoded_filter["parent"] = decoded_parent
        return decoded_filter

    def _encode_result_ids(self, items: list[dict], resource_type: str) -> None:
        """就地编码回调结果中的 id 和 V4 IAM 路径。"""
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
        """编码 V4 IAM 路径中每段的资源类型和资源实例 ID。"""
        if not path:
            return path

        segments: list[str] = []
        for segment in path.split("/"):
            if not segment:
                continue
            resource_type, separator, resource_id = segment.partition(",")
            if separator and resource_type and resource_id:
                dialect_type = self._codec.encode_resource_type(resource_type)
                dialect_id = self._codec.encode_resource_id(resource_type, resource_id)
                segments.append(f"{dialect_type},{dialect_id}")
            else:
                segments.append(segment)

        if not segments:
            return path
        prefix = "/" if path.startswith("/") else ""
        suffix = "/" if path.endswith("/") else ""
        return f"{prefix}{'/'.join(segments)}{suffix}"
