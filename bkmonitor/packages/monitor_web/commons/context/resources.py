"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from enum import Enum
from typing import Any

from django.middleware.csrf import get_token
from opentelemetry import trace

from bkm_space.api import SpaceApi
from bkm_space.define import Space
from bkm_space.utils import is_disabled_bkms_space
from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.utils.request import get_request, get_request_tenant_id
from bkmonitor.utils.user import get_request_username
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
from iam_engine.exceptions import ProviderUnavailable
from monitor.models.models import UserConfig
from monitor_web.commons.biz.resources import ListSpacesResource
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


def resolve_basic_space(request, space_uid, bk_biz_id, preferred_biz_id, default_biz_id):
    """Resolve one available space. Only an implicit target may fall back to another space."""
    try:
        tenant = get_request_tenant_id()
        if space_uid:
            if "__" not in space_uid:
                return -1, [], "not_found"
            detail = SpaceApi.get_space_detail(space_uid=space_uid)
            if detail is None or detail.bk_tenant_id != tenant:
                return -1, [], "not_found"
            bk_biz_id = detail.bk_biz_id
            if bk_biz_id in (-1, 0):
                return -1, [], "not_found"

        external_user = getattr(request, "external_user", None)
        if external_user:
            grants = ListSpacesResource.external_permissions(external_user)
        else:
            permission = Permission(username=request.user.username, bk_tenant_id=tenant)
            permission.skip_check = False

        def check_space(space):
            biz_id = space["bk_biz_id"]
            if external_user:
                return grants.filter(bk_biz_id=biz_id).exists()
            return permission.is_space_allowed(ActionEnum.VIEW_BUSINESS, biz_id)

        explicit = bk_biz_id not in (None, 0, -1)
        if explicit:
            targets = [bk_biz_id]
        else:
            targets = (
                preferred_biz_id,
                request.session.get("bk_biz_id"),
                request.COOKIES.get("bk_biz_id"),
                default_biz_id,
            )
        seen = set()
        probe_failed = False
        for target in targets:
            try:
                target = int(str(target).strip("/"))
            except ValueError:
                continue
            if target in (0, -1) or target in seen:
                continue
            seen.add(target)
            records = SpaceApi.read_space_records(tenant, [target])
            if not records or is_disabled_bkms_space(records[0]):
                if explicit:
                    return target, [], "not_found"
                continue
            try:
                if check_space(records[0]):
                    return target, records, "allowed"
            except ProviderUnavailable:
                if explicit:
                    raise
                probe_failed = True
                continue
            if explicit:
                return target, [], "denied"

        if external_user:
            ids = grants.values_list("bk_biz_id", flat=True).distinct()
            records = SpaceApi.read_space_records(tenant, ids, first_available=True)
        else:
            records = permission.list_authorized_space_records(ActionEnum.VIEW_BUSINESS, first_available=True)
        if records:
            return records[0]["bk_biz_id"], records, "allowed"
        return -1, [], "error" if probe_failed else "denied"
    except Exception:
        logger.exception("[get_basic_context] unable to resolve space access")
        return bk_biz_id or -1, [], "error"


class EnhancedGetContextResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID", default=0)
        space_uid = serializers.CharField(required=False, label="空间ID", default="")
        include_space_list = serializers.BooleanField(default=True)
        preferred_biz_id = serializers.IntegerField(required=False)
        context_type = serializers.ChoiceField(
            required=False,
            choices=[ContextType.BASIC.value, ContextType.FULL.value, ContextType.EXTRA.value],
            default=ContextType.FULL.value,
        )

    @classmethod
    def get_basic_context(cls, request, space_uid: str | None, bk_biz_id: int | None) -> dict[str, Any]:
        space_list: list[dict[str, Any]] = []
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
                    f"[get_basic_context] space_uid not found: uid -> {space_uid} not in space_list -> {space_list}"
                )
        elif not bk_biz_id:
            bk_biz_id = get_default_biz_id(request, space_list, "id")

        return cls.format_basic_context(request, space_list, bk_biz_id)

    @staticmethod
    def format_basic_context(request, spaces, biz_id, space_access=None):
        context = get_basic_context(request, spaces, biz_id, space_access=space_access)
        context["SPACE_LIST_STATE"] = "deferred" if space_access is not None else "full"
        context["CSRF_TOKEN"] = get_token(request)

        field_formatter(context)
        json_formatter(context)
        return context

    @classmethod
    def get_extra_context(cls, request, space_uid: str | None, bk_biz_id: int | None) -> dict[str, Any]:
        space: Space | None = None
        if space_uid:
            try:
                space = SpaceApi.get_space_detail(space_uid)
            except BKAPIError as e:
                logger.exception(f"[get_extra_context] get_space_detail({space_uid}) failed: error -> {e}")

        if space:
            bk_biz_id = space.bk_biz_id

        # 非核心路径，加上异常捕获避免因消息队列不可用导致页面也无法打开
        try:
            run_init_builtin.delay(bk_biz_id=bk_biz_id, username=get_request_username())
            logger.info(f"[get_extra_context] run_init_builtin has been added to the asynchronous queue；{bk_biz_id}")
        except Exception as e:
            logger.exception(f"[get_extra_context] run_init_builtin error but skipped: error -> {e}")

        return get_extra_context(request, space)

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        request = get_request()
        context_type: str = validated_request_data["context_type"]
        bk_biz_id: int | None = validated_request_data["bk_biz_id"]
        space_uid: str | None = validated_request_data["space_uid"]

        # 补充默认业务ID
        default_biz_config = UserConfig.objects.filter(
            username=request.user.username,
            key=UserConfig.Keys.DEFAULT_BIZ_ID,
        ).first()
        default_biz_id = default_biz_config.value if default_biz_config else None

        if (
            context_type == ContextType.BASIC.value
            and not validated_request_data["include_space_list"]
            and hasattr(SpaceApi, "read_space_records")
        ):
            with trace.get_tracer(__name__).start_as_current_span("context.resolve_basic_space") as span:
                biz_id, spaces, access = resolve_basic_space(
                    request, space_uid, bk_biz_id, validated_request_data.get("preferred_biz_id"), default_biz_id
                )
                span.set_attribute("space.access", access)
                span.set_attribute("space.row_count", len(spaces))
            context = self.format_basic_context(request, spaces, biz_id, access)
        elif context_type == ContextType.BASIC.value:
            context = self.get_basic_context(request, space_uid, bk_biz_id)
        elif context_type == ContextType.EXTRA.value:
            context = self.get_extra_context(request, space_uid, bk_biz_id)
        else:
            context = self.get_basic_context(request, space_uid, bk_biz_id)
            context.update(self.get_extra_context(request, space_uid, bk_biz_id))

        external_fields: list[str] = [
            "PLATFORM",
            "SPACE_LIST",
            "SPACE_LIST_STATE",
            "SPACE_ACCESS",
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
            "ENABLE_ISSUE_AI_ANALYSIS",
            "ENABLE_AIOPS_INCIDENT",
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

        context["DEFAULT_BIZ_ID"] = default_biz_id

        return {"context": context, "context_type": context_type}
