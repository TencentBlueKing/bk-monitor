"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import json
from copy import copy

from django.conf import settings
from django.http import JsonResponse

from apps.iam import ResourceEnum
from apps.iam.backends.v4.codec import BKLOG_ROOT_RESOURCE_TYPE_ID, BklogNameCodec
from apps.iam.views.resources import (
    BaseResourceProvider,
    CollectionResourceProvider,
    EsSourceResourceProvider,
    IndicesResourceProvider,
    ResourceApiDispatcher,
)
from apps.log_search.models import Space
from iam.contrib.django.dispatcher import InvalidPageException
from iam.resource.provider import ListResult


_RESOURCE_CODEC = BklogNameCodec()

_IAM_V4_ERROR_BY_LEGACY_CODE = {
    400: (400, "INVALID_ARGUMENT"),
    401: (401, "UNAUTHENTICATED"),
    404: (404, "NOT_FOUND"),
    406: (400, "INVALID_ARGUMENT"),
    422: (400, "INVALID_ARGUMENT"),
}


def _iam_v4_response(payload: dict, *, status: int, request_id: str = "") -> JsonResponse:
    response = JsonResponse(payload, status=status)
    if request_id:
        response["X-Request-Id"] = request_id
    return response


class V4ResourceApiDispatcher(ResourceApiDispatcher):
    """V4 资源回调 Dispatcher：多租户模式下禁止回退默认 Tenant。"""

    def _dispatch(self, request):
        """复用旧版 Dispatcher 执行请求，并将结果转换为 IAM V4 响应协议。"""
        legacy_response = super()._dispatch(request)
        request_id = legacy_response.get("X-Request-Id", "")

        try:
            payload = json.loads(legacy_response.content)
        except (TypeError, ValueError):
            return _iam_v4_response(
                {"error": {"code": "INTERNAL", "message": "internal server error"}},
                status=500,
                request_id=request_id,
            )

        if payload.get("result") is True and payload.get("code") == 0 and "data" in payload:
            return _iam_v4_response({"data": payload["data"]}, status=200, request_id=request_id)

        try:
            legacy_code = int(payload.get("code"))
        except (TypeError, ValueError):
            legacy_code = 500
        status, error_code = _IAM_V4_ERROR_BY_LEGACY_CODE.get(legacy_code, (500, "INTERNAL"))
        message = payload.get("message") or "internal server error"
        if status == 500:
            message = "internal server error"
        return _iam_v4_response(
            {"error": {"code": error_code, "message": message}},
            status=status,
            request_id=request_id,
        )

    @classmethod
    def _normalize_page(cls, data: dict) -> dict:
        """将文档中的 page/page_size 分页格式转换为 SDK 使用的 limit/offset 格式。"""
        page = data.get("page")
        if not isinstance(page, dict) or "limit" in page or "offset" in page:
            return data
        if "page" not in page and "page_size" not in page:
            return data

        page_number = cls._parse_page_integer(page.get("page"), field="page")
        page_size = cls._parse_page_integer(page.get("page_size"), field="page_size")
        if page_number <= 0:
            raise InvalidPageException("page.page must be an integer greater than 0")
        if page_size <= 0:
            raise InvalidPageException("page.page_size must be an integer greater than 0")

        normalized = dict(data)
        normalized["page"] = {
            "limit": page_size,
            "offset": (page_number - 1) * page_size,
        }
        return normalized

    @staticmethod
    def _parse_page_integer(value, *, field: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int | str):
            raise InvalidPageException(f"page.{field} must be an integer")
        try:
            return int(value)
        except ValueError as error:
            raise InvalidPageException(f"page.{field} must be an integer") from error

    @classmethod
    def _validate_page(cls, data: dict) -> None:
        page = data.get("page")
        if not isinstance(page, dict):
            raise InvalidPageException("page is required and must be an object")

        limit = cls._parse_page_integer(page.get("limit"), field="limit")
        if limit <= 0:
            raise InvalidPageException("page.limit must be an integer greater than 0")

        offset = cls._parse_page_integer(page.get("offset"), field="offset")
        if offset < 0:
            raise InvalidPageException("page.offset must be an integer greater than or equal to 0")

    def _dispatch_list_attr_value(self, request, data, request_id):
        data = self._normalize_page(data)
        self._validate_page(data)
        return super()._dispatch_list_attr_value(request, data, request_id)

    def _dispatch_list_instance(self, request, data, request_id):
        data = self._normalize_page(data)
        self._validate_page(data)
        return super()._dispatch_list_instance(request, data, request_id)

    def _dispatch_list_instance_by_policy(self, request, data, request_id):
        data = self._normalize_page(data)
        self._validate_page(data)
        return super()._dispatch_list_instance_by_policy(request, data, request_id)

    def _dispatch_search_instance(self, request, data, request_id):
        data = self._normalize_page(data)
        self._validate_page(data)
        return super()._dispatch_search_instance(request, data, request_id)

    def _dispatch_fetch_instance_list(self, request, data, request_id):
        data = self._normalize_page(data)
        self._validate_page(data)
        return super()._dispatch_fetch_instance_list(request, data, request_id)

    def _get_options(self, request):
        # 跳过 V3 Dispatcher 的默认租户回退，由 V4 回调强制校验请求头。
        options = super(ResourceApiDispatcher, self)._get_options(request)
        tenant_id = request.META.get("HTTP_X_BK_TENANT_ID", "").strip()
        if settings.ENABLE_MULTI_TENANT_MODE and not tenant_id:
            raise ValueError("X-Bk-Tenant-Id is required for IAM V4 resource callback")
        options["bk_tenant_id"] = tenant_id or settings.BK_APP_TENANT_ID
        return options


def _fix_nested_path_to_string(results: list[dict]) -> None:
    """把 V3 Provider 返回的嵌套数组 _bk_iam_path_ 原地改写成字符串格式。"""
    for item in results:
        path = item.get("_bk_iam_path_")
        if isinstance(path, list) and path and path[0]:
            biz_id = path[0][0]["id"]
            encoded_biz_id = _RESOURCE_CODEC.encode_resource_id(BKLOG_ROOT_RESOURCE_TYPE_ID, biz_id)
            item["_bk_iam_path_"] = f"/{ResourceEnum.BUSINESS.id},{encoded_biz_id}/"


def _with_decoded_parent_space(filter_obj):
    parent = getattr(filter_obj, "parent", None)
    if not isinstance(parent, dict) or parent.get("id") in (None, ""):
        return filter_obj
    decoded_filter = copy(filter_obj)
    decoded_parent = dict(parent)
    decoded_parent["id"] = _RESOURCE_CODEC.decode_resource_id(BKLOG_ROOT_RESOURCE_TYPE_ID, parent["id"])
    decoded_filter["parent"] = decoded_parent
    return decoded_filter


def _decode_policy_expression(value):
    if isinstance(value, list):
        return [_decode_policy_expression(item) for item in value]
    if not isinstance(value, dict):
        return value
    decoded = {key: _decode_policy_expression(item) for key, item in value.items()}
    field = str(decoded.get("field") or "")
    expression_value = decoded.get("value")
    if field.endswith("._bk_iam_path_") and isinstance(expression_value, str):
        decoded["value"] = _RESOURCE_CODEC.decode_iam_path(expression_value)
    elif field == "space.id" and expression_value is not None:
        decoded["value"] = _RESOURCE_CODEC.decode_resource_id(BKLOG_ROOT_RESOURCE_TYPE_ID, expression_value)
    return decoded


def _with_decoded_policy_expression(filter_obj):
    expression = getattr(filter_obj, "expression", None)
    if expression is None:
        return filter_obj
    decoded_filter = copy(filter_obj)
    decoded_filter["expression"] = _decode_policy_expression(expression)
    return decoded_filter


def _fix_approver_field(results: list[dict]) -> None:
    """把 V3 Provider 返回的单数 _bk_iam_approver_ 改写成 V4 要求的复数数组。"""
    for item in results:
        approver = item.pop("_bk_iam_approver_", None)
        if approver is not None:
            item["_bk_iam_approvers_"] = [approver] if approver else []


class V4SpaceResourceProvider(BaseResourceProvider):
    """IAM V4 space 资源回调。实例 ID 使用 bk_biz_id，与 ResourceEnum.BUSINESS 保持一致。

    只读取本地 Space 快照，禁止运行时回源监控平台 / Metadata。
    """

    @staticmethod
    def _require_tenant_id(options: dict) -> str:
        tenant_id = str(options.get("bk_tenant_id") or "").strip()
        if settings.ENABLE_MULTI_TENANT_MODE and not tenant_id:
            raise ValueError("bk_tenant_id is required for V4 space resource provider")
        return tenant_id or settings.BK_APP_TENANT_ID

    @staticmethod
    def _to_result_item(space: dict) -> dict:
        return {
            "id": _RESOURCE_CODEC.encode_resource_id(BKLOG_ROOT_RESOURCE_TYPE_ID, space["bk_biz_id"]),
            "display_name": f"[{space['space_type_name']}] {space['space_name']}",
        }

    def list_instance(self, filter, page, **options):
        keywords = (filter.search.get("space", []) or []) if filter.search else []
        spaces, count = Space.get_spaces_page(
            self._require_tenant_id(options),
            offset=page.slice_from,
            limit=page.slice_to - page.slice_from,
            keywords=keywords,
        )
        return ListResult(results=[self._to_result_item(space) for space in spaces], count=count)

    def fetch_instance_info(self, filter, **options):
        tenant_id = self._require_tenant_id(options)
        if not filter.ids:
            return ListResult(results=[], count=0)

        decoded_ids = [
            _RESOURCE_CODEC.decode_resource_id(BKLOG_ROOT_RESOURCE_TYPE_ID, resource_id) for resource_id in filter.ids
        ]
        spaces = Space.get_spaces_by_bk_biz_ids(tenant_id, decoded_ids)

        results = []
        for space in spaces:
            item = self._to_result_item(space)
            # Space 模型当前没有稳定的管理员字段，不编造审批人
            item["_bk_iam_approvers_"] = []
            results.append(item)
        return ListResult(results=results, count=len(results))

    def search_instance(self, filter, page, **options):
        spaces, count = Space.get_spaces_page(
            self._require_tenant_id(options),
            offset=page.slice_from,
            limit=page.slice_to - page.slice_from,
            keywords=[filter.keyword] if filter.keyword else [],
        )
        return ListResult(results=[self._to_result_item(space) for space in spaces], count=count)

    def list_instance_by_policy(self, filter, page, **options):
        # V4 space 的按策略反查契约尚未确认，先返回空结果
        return ListResult(results=[], count=0)


class V4CollectionResourceProvider(CollectionResourceProvider):
    def list_instance(self, filter, page, **options):
        result = super().list_instance(_with_decoded_parent_space(filter), page, **options)
        _fix_nested_path_to_string(result.results)
        return result

    def fetch_instance_info(self, filter, **options):
        result = super().fetch_instance_info(filter, **options)
        _fix_approver_field(result.results)
        return result

    def search_instance(self, filter, page, **options):
        return super().search_instance(_with_decoded_parent_space(filter), page, **options)

    def list_instance_by_policy(self, filter, page, **options):
        return super().list_instance_by_policy(_with_decoded_policy_expression(filter), page, **options)


class V4IndicesResourceProvider(IndicesResourceProvider):
    def list_instance(self, filter, page, **options):
        result = super().list_instance(_with_decoded_parent_space(filter), page, **options)
        _fix_nested_path_to_string(result.results)
        return result

    def fetch_instance_info(self, filter, **options):
        result = super().fetch_instance_info(filter, **options)
        _fix_approver_field(result.results)
        return result

    def search_instance(self, filter, page, **options):
        return super().search_instance(_with_decoded_parent_space(filter), page, **options)

    def list_instance_by_policy(self, filter, page, **options):
        return super().list_instance_by_policy(_with_decoded_policy_expression(filter), page, **options)


class V4EsSourceResourceProvider(EsSourceResourceProvider):
    def list_instance(self, filter, page, **options):
        result = super().list_instance(_with_decoded_parent_space(filter), page, **options)
        _fix_nested_path_to_string(result.results)
        return result

    def fetch_instance_info(self, filter, **options):
        result = super().fetch_instance_info(filter, **options)
        _fix_approver_field(result.results)
        return result

    def search_instance(self, filter, page, **options):
        return super().search_instance(_with_decoded_parent_space(filter), page, **options)

    def list_instance_by_policy(self, filter, page, **options):
        return super().list_instance_by_policy(_with_decoded_policy_expression(filter), page, **options)
