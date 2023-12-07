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
from django.conf import settings
from django.middleware.csrf import get_token

from bkm_space.api import SpaceApi
from bkmonitor.utils.request import get_request
from bkmonitor.views import serializers
from common.context_processors import (
    field_formatter,
    get_basic_context,
    get_default_biz_id,
    get_extra_context,
    get_full_context,
    json_formatter,
)
from common.log import logger
from core.drf_resource import resource
from core.drf_resource.base import Resource
from core.errors.api import BKAPIError
from fta_web.tasks import run_init_builtin


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
                bk_biz_id = None
                try:
                    space = SpaceApi.get_space_detail(attrs["space_uid"])
                    bk_biz_id = space.bk_biz_id
                except BKAPIError as e:
                    logger.exception(f"获取空间信息({attrs['space_uid']})失败：{e}")
                    if settings.DEMO_BIZ_ID:
                        bk_biz_id = settings.DEMO_BIZ_ID

                if bk_biz_id:
                    attrs["bk_biz_id"] = bk_biz_id
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

        json_formatter(context)

        context["csrf_token"] = get_token(request)

        if context_name and context_name in context:
            return {context_name: context[context_name]}

        return context


class EnhancedGetContextResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID", default=0)
        space_uid = serializers.CharField(required=False, label="空间ID", default="")
        context_type = serializers.ChoiceField(required=False, choices=["basic", "extra", "full"], default="full")

    @classmethod
    def get_basic_context(cls, request, space_uid, bk_biz_id):

        try:
            space_list = resource.commons.list_spaces()
        except Exception:  # noqa
            space_list = []
            logger.exception("[get_basic_context] list_spaces failed")

        # 新增space_uid的支持
        if space_uid:
            try:
                space = {}
                for space in space_list:
                    if space["space_uid"] == space_uid:
                        break
                bk_biz_id = space["bk_biz_id"]
            except KeyError:
                logger.warning(
                    f"[get_basic_context] space_uid not found: " f"uid -> {space_uid} not in space_list -> {space_list}"
                )
                if settings.DEMO_BIZ_ID:
                    bk_biz_id = settings.DEMO_BIZ_ID
        else:
            if not bk_biz_id:
                bk_biz_id = get_default_biz_id(request, space_list, "bk_biz_id")

        context = get_basic_context(request, space_list, bk_biz_id)
        context["SPACE_LIST"] = space_list
        context["CSRF_TOKEN"] = get_token(request)

        field_formatter(context)
        json_formatter(context)
        return context

    @classmethod
    def get_extra_context(cls, request, space_uid, bk_biz_id):
        space = None
        if space_uid:
            try:
                space = SpaceApi.get_space_detail(space_uid)
            except BKAPIError as e:
                logger.exception(f"[get_extra_context] get_space_detail({space_uid}) failed: error -> {e}")

        if space:
            bk_biz_id = space.bk_biz_id

        logger.info(f"[get_extra_context] run_init_builtin has been added to the asynchronous queue；{bk_biz_id}")
        run_init_builtin.delay(bk_biz_id=bk_biz_id)

        return get_extra_context(request, space)

    def perform_request(self, validated_request_data):

        request = get_request()
        context_type = validated_request_data["context_type"]

        if validated_request_data["context_type"] == "basic":
            context = self.get_basic_context(
                request, validated_request_data["space_uid"], validated_request_data["bk_biz_id"]
            )
        elif validated_request_data["context_type"] == "extra":
            context = self.get_extra_context(
                request, validated_request_data["space_uid"], validated_request_data["bk_biz_id"]
            )
        else:
            context = self.get_basic_context(
                request, validated_request_data["space_uid"], validated_request_data["bk_biz_id"]
            )
            context.update(
                self.get_extra_context(
                    request, validated_request_data["space_uid"], validated_request_data["bk_biz_id"]
                )
            )

        return {"context": context, "context_type": context_type}
