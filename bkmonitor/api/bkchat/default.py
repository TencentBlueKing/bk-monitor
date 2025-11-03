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

import six
from django.conf import settings
from django.utils.translation import gettext as _
from rest_framework import serializers

from core.drf_resource import APIResource
from core.drf_resource.exceptions import CustomException
from core.errors.api import BKAPIError


class BkchatAPIGWResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    base_url = settings.BKCHAT_API_BASE_URL

    # 模块名
    module_name = "bkchat"

    @property
    def label(self):
        return self.__doc__


class GetNoticeGroup(BkchatAPIGWResource):
    """
    获取用户信息
    """

    action = "/api/v1/notice_group/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        biz_id = serializers.CharField(required=False, label="业务ID")


class GetNoticeGroupDetail(BkchatAPIGWResource):
    """
    获取用户信息
    """

    action = "/api/v1/notice_group/detail_list/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        biz_id = serializers.CharField(required=False, label="业务ID")


class SendNoticeGroupMsg(BkchatAPIGWResource):
    action = "/api/v1/notice_group_send_msg/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        notice_group_id_list = serializers.ListField(
            required=True, label="通知组列表", child=serializers.IntegerField()
        )
        msg_type = serializers.CharField(required=False, label="内容格式", default="text")
        msg_content = serializers.CharField(required=False, label="发送内容")
        msg_param = serializers.DictField(required=False, label="发送内容结构体")

    def validate_request_data(self, request_data):
        validated_data = super().validate_request_data(request_data)
        if not any([validated_data.get("msg_content"), validated_data.get("msg_param")]):
            raise CustomException(
                _("Resource[{}] 请求参数格式错误：{}").format(
                    self.get_resource_name(), _("msg_content和msg_param至少需要一项")
                )
            )
        return validated_data

    def perform_request(self, validated_request_data):
        try:
            super().perform_request(validated_request_data)
            return {"username_check": {"invalid": []}, "message": _("发送成功")}
        except BKAPIError as e:
            invalid = validated_request_data["notice_group_id_list"]
            if isinstance(e.data, dict):
                try:
                    invalid = e.data["data"]["fail_notice_group_id_list"]
                except (KeyError, TypeError):
                    pass
            return {"username_check": {"invalid": invalid}, "message": str(e)}
        except Exception as e:
            self.report_api_failure_metric(error_code=getattr(e, "code", 0), exception_type=type(e).__name__)
            return {"username_check": {"invalid": validated_request_data["notice_group_id_list"]}, "message": str(e)}
