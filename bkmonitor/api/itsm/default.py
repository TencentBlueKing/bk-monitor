# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import abc
import os

import six
from django.conf import settings
from rest_framework import serializers

from bkmonitor.utils.request import get_request
from core.drf_resource.contrib.api import APIResource


class ITSMBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    base_url = os.path.join(settings.BK_COMPONENT_API_URL, "api/c/compapi/v2/itsm/")
    module_name = "itsm"

    def full_request_data(self, validated_request_data):
        try:
            validated_request_data["_origin_user"] = get_request().user.username
        except Exception:  # pylint: disable=broad-except
            pass
        self.bk_username = settings.COMMON_USERNAME
        return super(ITSMBaseResource, self).full_request_data(validated_request_data)


class MetaSerializer(serializers.Serializer):
    callback_url = serializers.URLField(label="回调URL", required=True)


class CreateFastApprovalTicketResource(ITSMBaseResource):
    """
    作业列表
    """

    action = "create_ticket"
    method = "post"

    class RequestSerializer(serializers.Serializer):
        creator = serializers.CharField(label="提单人", required=True)
        service_id = serializers.IntegerField(label="服务ID", required=False)
        fast_approval = serializers.BooleanField(label="是否为快速审批", required=False, default=True)
        fields = serializers.JSONField(label="提单内容", required=True)
        meta = MetaSerializer(required=False)


class TicketApproveResultResource(ITSMBaseResource):
    action = "ticket_approval_result"
    method = "post"

    class RequestSerializer(serializers.Serializer):
        sn = serializers.ListField(label="单号", child=serializers.CharField(), required=True)


class TicketRevokeResource(ITSMBaseResource):
    action = "operate_ticket"
    method = "post"

    class RequestSerializer(serializers.Serializer):
        sn = serializers.CharField(label="单号", required=True)
        operator = serializers.CharField(label="撤单人", required=True)
        action_message = serializers.CharField(label="撤单消息", required=False, default="撤销单据")

    def full_request_data(self, validated_request_data):
        validated_request_data = super(TicketRevokeResource, self).full_request_data(validated_request_data)
        validated_request_data.update(
            {
                "action_type": "WITHDRAW",
            }
        )
        return validated_request_data


class TokenVerifyResource(ITSMBaseResource):
    action = "token/verify"
    method = "post"

    class RequestSerializer(serializers.Serializer):
        token = serializers.CharField(label="校验码", required=True)


class GetTicketStatusResource(ITSMBaseResource):
    action = "get_ticket_status"
    method = "get"

    class RequestSerializer(serializers.Serializer):
        sn = serializers.CharField(label="单号", required=True)
