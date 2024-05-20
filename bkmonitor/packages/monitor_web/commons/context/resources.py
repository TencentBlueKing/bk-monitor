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
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from django.conf import settings
from django.middleware.csrf import get_token
from django.utils import timezone

from bkm_space.api import SpaceApi
from bkm_space.define import Space
from bkmonitor.models.external_iam import ExternalPermission
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
from monitor_web.tasks import run_init_builtin


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


class ContextType(Enum):
    BASIC = "basic"
    EXTRA = "extra"
    FULL = "full"


class EnhancedGetContextResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID", default=0)
        space_uid = serializers.CharField(required=False, label="空间ID", default="")
        context_type = serializers.ChoiceField(
            required=False,
            choices=[ContextType.BASIC.value, ContextType.FULL.value, ContextType.EXTRA.value],
            default=ContextType.FULL.value,
        )

    @classmethod
    def get_basic_context(cls, request, space_uid: Optional[str], bk_biz_id: Optional[int]) -> Dict[str, Any]:
        space_list: List[Dict[str, Any]] = []
        try:
            space_list = resource.commons.list_spaces()
        except Exception:  # noqa
            logger.exception("[get_basic_context] list_spaces failed")

        # 新增space_uid的支持
        if space_uid:
            try:
                space = {s["space_uid"]: s for s in space_list}[space_uid]
                bk_biz_id = space["bk_biz_id"]
            except KeyError:
                logger.warning(
                    f"[get_basic_context] space_uid not found: " f"uid -> {space_uid} not in space_list -> {space_list}"
                )
                if settings.DEMO_BIZ_ID:
                    bk_biz_id = int(settings.DEMO_BIZ_ID or 0)
        elif not bk_biz_id:
            bk_biz_id = get_default_biz_id(request, space_list, "bk_biz_id")

        context = get_basic_context(request, space_list, bk_biz_id)
        context["CSRF_TOKEN"] = get_token(request)

        field_formatter(context)
        json_formatter(context)
        return context

    @classmethod
    def get_extra_context(cls, request, space_uid: Optional[str], bk_biz_id: Optional[int]) -> Dict[str, Any]:
        space: Optional[Space] = None
        if space_uid:
            try:
                space = SpaceApi.get_space_detail(space_uid)
            except BKAPIError as e:
                logger.exception(f"[get_extra_context] get_space_detail({space_uid}) failed: error -> {e}")

        if space:
            bk_biz_id = space.bk_biz_id

        # 非核心路径，加上异常捕获避免因消息队列不可用导致页面也无法打开
        try:
            run_init_builtin.delay(bk_biz_id=bk_biz_id)
            logger.info(f"[get_extra_context] run_init_builtin has been added to the asynchronous queue；{bk_biz_id}")
        except Exception as e:
            logger.exception(f"[get_extra_context] run_init_builtin error but skipped: error -> {e}")

        return get_extra_context(request, space)

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        request = get_request()
        context_type: str = validated_request_data["context_type"]
        bk_biz_id: Optional[int] = validated_request_data["bk_biz_id"]
        space_uid: Optional[str] = validated_request_data["space_uid"]

        if context_type == ContextType.BASIC.value:
            context = self.get_basic_context(request, space_uid, bk_biz_id)
        elif context_type == ContextType.EXTRA.value:
            context = self.get_extra_context(request, space_uid, bk_biz_id)
        else:
            context = self.get_basic_context(request, space_uid, bk_biz_id)
            context.update(self.get_extra_context(request, space_uid, bk_biz_id))

        external_fields: List[str] = [
            "PLATFORM",
            "SPACE_LIST",
            "SITE_URL",
            "STATIC_URL",
            "BK_BIZ_ID",
            "CSRF_COOKIE_NAME",
            "CSRF_TOKEN",
            "UIN",
            "IS_SUPERUSER",
            "MAX_AVAILABLE_DURATION_LIMIT",
            "GRAPH_WATERMARK",
            "ENABLE_AIOPS",
            "ENABLE_APM",
            "ENABLE_CMDB_LEVEL",
            "HOST_DATA_FIELDS",
            "WXWORK_BOT_SEND_IMAGE",
            # extra
            "COLLECTING_CONFIG_FILE_MAXSIZE",
            "IS_CONTAINER_MODE",
            "MONITOR_MANAGERS",
        ]
        if getattr(request, "external_user", None):
            context = {k: v for k, v in context.items() if k in external_fields}
            context["UIN"] = request.external_user

            if context_type not in [ContextType.EXTRA.value]:
                biz_id_list: Set[int] = set(
                    ExternalPermission.objects.filter(
                        authorized_user=request.external_user, expire_time__gt=timezone.now()
                    )
                    .values_list("bk_biz_id", flat=True)
                    .distinct()
                )
                context["SPACE_LIST"] = [space for space in context["SPACE_LIST"] if space["bk_biz_id"] in biz_id_list]
                if context["BK_BIZ_ID"] not in biz_id_list:
                    if context["SPACE_LIST"]:
                        context["BK_BIZ_ID"] = context["SPACE_LIST"][0]["bk_biz_id"]
                    else:
                        context["BK_BIZ_ID"] = -1

        return {"context": context, "context_type": context_type}
