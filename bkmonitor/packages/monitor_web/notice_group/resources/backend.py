"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext as _

from bkmonitor.models.base import NoticeGroup
from bk_monitor_base.strategy import NoticeGroupSerializer
from bkmonitor.views import serializers
from core.drf_resource.base import Resource
from core.errors.notice_group import (
    NoticeGroupHasStrategy,
    NoticeGroupNameExist,
    NoticeGroupNotExist,
)


class BackendSearchNoticeGroup(Resource):
    """
    查询通知组
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_ids = serializers.ListField(
            child=serializers.IntegerField(required=True, label="业务ID"), required=False
        )
        ids = serializers.ListField(child=serializers.IntegerField(required=True, label="告警组ID"), required=False)

    def perform_request(self, params):
        notice_groups = NoticeGroup.objects.all().order_by("-update_time")

        if params.get("bk_biz_ids"):
            notice_groups = notice_groups.filter(bk_biz_id__in=params.get("bk_biz_ids"))

        if params.get("ids"):
            notice_groups = notice_groups.filter(id__in=params.get("ids"))

        result = []
        for notice_group in notice_groups:
            result.append(
                {
                    "id": notice_group.id,
                    "name": notice_group.name,
                    "notice_way": notice_group.notice_way,
                    "notice_receiver": [],
                    "webhook_url": notice_group.webhook_url,
                    "wxwork_group": notice_group.wxwork_group,
                    "message": notice_group.message,
                    "create_time": notice_group.create_time,
                    "update_time": notice_group.update_time,
                    "update_user": notice_group.update_user,
                    "bk_biz_id": notice_group.bk_biz_id,
                    "create_user": notice_group.create_user,
                }
            )
            for receiver in notice_group.notice_receiver:
                receiver_list = receiver.split("#")
                result[-1]["notice_receiver"].append(
                    {"id": receiver_list[1] if len(receiver_list) > 1 else "", "type": receiver_list[0]}
                )
        return result


class BackendSaveNoticeGroupResource(Resource):
    """
    保存通知组
    """

    RequestSerializer = NoticeGroupSerializer

    def validate_request_data(self, request_data):
        # 对象不存在
        if request_data.get("id"):
            instance = NoticeGroup.objects.filter(bk_biz_id=request_data["bk_biz_id"], id=request_data["id"]).first()
            if not instance:
                raise NoticeGroupNotExist({"msg": _("修改通知组失败")})
            serializer = self.RequestSerializer(instance, data=request_data, partial=True)
            serializer.is_valid(raise_exception=True)
            return serializer.validated_data

        # 重名检测
        instance = (
            NoticeGroup.objects.filter(name=request_data["name"], bk_biz_id=request_data["bk_biz_id"])
            .exclude(id=request_data.get("id"))
            .first()
        )
        if instance:
            raise NoticeGroupNameExist()

        return super().validate_request_data(request_data)

    def perform_request(self, validated_request_data):
        if validated_request_data.get("notice_receiver"):
            validated_request_data["notice_receiver"] = [
                "{}#{}".format(data["type"], data["id"]) for data in validated_request_data["notice_receiver"]
            ]

        if validated_request_data.get("id"):
            notice_group_id = validated_request_data["id"]
            instance = NoticeGroup.objects.get(id=notice_group_id, bk_biz_id=validated_request_data["bk_biz_id"])
            for attr, value in list(validated_request_data.items()):
                setattr(instance, attr, value)
            instance.save()
        else:
            instance = NoticeGroup.objects.create(**validated_request_data)
        return {"id": instance.id}


class BackendDeleteNoticeGroupResource(Resource):
    """
    删除通知组
    """

    class RequestSerializer(serializers.Serializer):
        ids = serializers.ListField(required=True, label="通知组ID")

    def perform_request(self, validated_request_data):
        ids = validated_request_data["ids"]
        groups = NoticeGroup.objects.filter(id__in=ids)
        for group in groups:
            if group.related_strategy:
                raise NoticeGroupHasStrategy
        groups.update(is_deleted=True)
