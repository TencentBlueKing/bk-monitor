"""日志采集 MCP 使用的索引组资源。"""

from rest_framework import serializers

from bkm_space.utils import bk_biz_id_to_space_uid
from core.drf_resource import Resource, api


class ListLogIndexSetGroupsResource(Resource):
    """查询当前业务可用的索引组列表。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        space_uid = bk_biz_id_to_space_uid(validated_request_data["bk_biz_id"])
        return api.log_search.list_index_groups(space_uid=space_uid)
