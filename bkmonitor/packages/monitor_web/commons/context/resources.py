# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from django.middleware.csrf import get_token

from bkm_space.api import SpaceApi
from bkmonitor.utils.request import get_request
from bkmonitor.views import serializers
from common.context_processors import get_full_context
from core.drf_resource.base import Resource


class GetContextResource(Resource):
    """
    获取业务下的结果表列表（包含全业务）
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID", default=0)
        space_uid = serializers.CharField(required=False, default="")
        context_name = serializers.CharField(required=False)
        with_biz_id = serializers.BooleanField(required=False, default=False)

        def validate(self, attrs):
            if not attrs.get("space_uid", "") and attrs["bk_biz_id"]:
                attrs["with_biz_id"] = True
                return attrs
            if attrs.get("space_uid"):
                space = SpaceApi.get_space_detail(attrs["space_uid"])
                attrs["bk_biz_id"] = space.bk_biz_id
                attrs["with_biz_id"] = True
            return attrs

    def perform_request(self, validated_request_data):
        request = get_request()
        context_name = validated_request_data.get("context_name", None)
        # 获取csrf_token值无需获取context，提前返回
        if context_name and context_name == "csrf_token":
            return {context_name: get_token(request)}

        if validated_request_data["with_biz_id"]:
            request.biz_id = validated_request_data["bk_biz_id"]

        context = get_full_context(request)

        result = {key: context[key] for key in context if key not in ["gettext", "_"]}

        result["PLATFORM"] = {key: getattr(context["PLATFORM"], key) for key in ["ce", "ee", "te"]}
        result["LANGUAGES"] = dict(result["LANGUAGES"])

        result["csrf_token"] = get_token(request)

        if context_name and context_name in result:
            return {context_name: result[context_name]}
        return result
