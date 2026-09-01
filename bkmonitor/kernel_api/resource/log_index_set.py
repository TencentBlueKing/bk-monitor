"""日志采集 MCP 使用的索引组资源。"""

from typing import Any

from rest_framework import serializers

from core.drf_resource import Resource, api


def normalize_index_group(index_group: dict[str, Any]) -> dict[str, Any]:
    """只返回创建/更新采集归属关系所需的索引组字段。"""
    return {
        "index_set_id": index_group.get("index_set_id"),
        "index_set_name": index_group.get("index_set_name") or "",
        "space_uid": index_group.get("space_uid") or "",
        "is_group": True,
    }


def extract_index_set_list(result: Any) -> list[dict[str, Any]]:
    """兼容 APIResource 已解包和保留 data 包装的两种返回结构。"""
    if isinstance(result, dict):
        result = result.get("list") or result.get("data") or []
    if isinstance(result, dict):
        result = result.get("list") or result.get("data") or []
    return [item for item in result if isinstance(item, dict)] if isinstance(result, list) else []


class ListLogIndexSetGroupsResource(Resource):
    """查询当前业务可用的索引组列表。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, min_value=1, label="业务ID")

    def perform_request(self, validated_request_data):
        result = api.log_search.search_index_set(
            bk_biz_id=validated_request_data["bk_biz_id"],
            is_group=True,
        )
        groups = [item for item in extract_index_set_list(result) if item.get("is_group")]
        return {"groups": [normalize_index_group(group) for group in groups]}
