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
# 资源回调 dispatch —— 通过 register_handler 可插拔注册
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

ListInstanceFn = Callable[[dict, dict], dict]
FetchInstanceFn = Callable[[list[str], list[str]], list[dict]]

_LIST_HANDLERS: dict[str, ListInstanceFn] = {}
_FETCH_HANDLERS: dict[str, FetchInstanceFn] = {}


def register_handler(resource_type: str, list_fn: ListInstanceFn, fetch_fn: FetchInstanceFn) -> None:
    """注册一个资源类型的回调处理器。"""
    _LIST_HANDLERS[resource_type] = list_fn
    _FETCH_HANDLERS[resource_type] = fetch_fn


def list_instance(resource_type: str, filter_data: dict, page: dict) -> dict:
    """IAM 回调 — 列出资源实例。"""
    handler = _LIST_HANDLERS.get(resource_type)
    if handler is None:
        logger.warning("[iam_v4:callback] no list_instance handler for type=%s", resource_type)
        return {"count": 0, "results": []}
    return handler(filter_data, page)


def fetch_instance_info(resource_type: str, ids: list[str], requires: list[str]) -> list[dict]:
    """IAM 回调 — 批量获取资源实例详情。"""
    handler = _FETCH_HANDLERS.get(resource_type)
    if handler is None:
        logger.warning("[iam_v4:callback] no fetch_instance_info handler for type=%s", resource_type)
        return []
    return handler(ids, requires)
