# -*- coding: utf-8 -*-
from rest_framework import serializers

from constants.action import BKCHAT_TRIGGER_TYPE_MAPPING
from core.drf_resource import Resource, api


class GetBkchatGroupResource(Resource):
    """
    获取对应业务下的bkchat告警组列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        """
        返回示例：
        """
        groups = api.bkchat.get_notice_group_detail(biz_id=validated_request_data["bk_biz_id"])
        for group in groups:
            notice_way = BKCHAT_TRIGGER_TYPE_MAPPING.get(group['trigger_type'], group['trigger_type'])
            group["id"] = f"{notice_way}|{group['id']}"
            group["name"] = f"{group['name']}({group['trigger_name']})"
        return groups
