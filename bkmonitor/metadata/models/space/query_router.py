"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import TYPE_CHECKING, Any

from metadata.models.space.constants import SpaceTypes

if TYPE_CHECKING:
    from metadata.models.space import Space


def normalize_query_router_config(config: dict[str, Any] | None, default_space_type: str) -> dict[str, Any]:
    """仅持久化显式指定的 exempt_owner，兼容存量路由配置。"""
    config = config or {}
    space_type = config.get("space_type") or default_space_type
    if space_type not in {item.value for item in SpaceTypes}:
        raise ValueError(f"query_router_config.space_type: {space_type} is invalid")

    filter_value = config.get("filter_value") or "bk_biz_id"
    if filter_value not in {"space_id", "bk_biz_id"}:
        raise ValueError(f"query_router_config.filter_value: {filter_value} is invalid")

    filter_key = config.get("filter_key")
    if filter_key is not None and not isinstance(filter_key, str):
        raise ValueError("query_router_config.filter_key must be a string")

    normalized = {
        "space_type": space_type,
        "filter_value": filter_value,
        "filter_key": filter_key or "bk_biz_id",
    }
    if "exempt_owner" in config:
        if not isinstance(config["exempt_owner"], bool):
            raise ValueError("query_router_config.exempt_owner must be a boolean")
        normalized["exempt_owner"] = config["exempt_owner"]
    return normalized


def compose_query_route(
    config: dict[str, Any], space: "Space", *, is_owner: bool, short_link: bool = False
) -> dict | None:
    """返回当前空间的路由；None 表示保留已有路由。短链路始终包含归属空间。"""
    if not (short_link and is_owner) and config["space_type"] not in (SpaceTypes.ALL.value, space.space_type_id):
        return None
    if is_owner:
        exempt_owner = config.get("exempt_owner", True if short_link else None)
        if exempt_owner is None:
            return None
        if exempt_owner:
            return {"filters": []}

    value = space.space_id if config["filter_value"] == "space_id" else space.get_bk_biz_id()
    # UQ 的 SpaceResultTable.Filters 按字符串维度值解码。
    return {"filters": [{config["filter_key"]: str(value)}]}
