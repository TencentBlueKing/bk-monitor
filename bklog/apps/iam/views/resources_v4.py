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

import binascii
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
from apps.log_databus.models import CollectorConfig
from apps.log_search.models import LogIndexSet, Space
from apps.utils.log import logger
from bkm_space.utils import space_uid_to_bk_biz_id
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
        request_id = request.META.get("HTTP_X_REQUEST_ID", "")
        try:
            legacy_response = super()._dispatch(request)
        except (binascii.Error, UnicodeDecodeError, ValueError):
            # SDK 在鉴权阶段解析 Basic 头时抛出，不在其 try 覆盖范围内
            logger.warning("iam v4 callback(%s) invalid authorization header", request_id)
            return _iam_v4_response(
                {"error": {"code": "UNAUTHENTICATED", "message": "basic auth failed"}},
                status=401,
                request_id=request_id,
            )
        except Exception:
            logger.exception("iam v4 callback(%s) unexpected error", request_id)
            return _iam_v4_response(
                {"error": {"code": "INTERNAL", "message": "internal server error"}},
                status=500,
                request_id=request_id,
            )
        request_id = legacy_response.get("X-Request-Id", request_id)

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

    @classmethod
    def _normalize_list_instance_keyword(cls, data: dict) -> dict:
        """把 V4 list_instance 的 filter.keyword 转成 SDK 认识的 search / resource_type_chain。"""
        filter_data = data.get("filter")
        if not isinstance(filter_data, dict):
            return data
        keyword = filter_data.get("keyword")
        if not isinstance(keyword, str) or not keyword.strip() or filter_data.get("search"):
            return data
        resource_type = data.get("type")
        if not isinstance(resource_type, str) or not resource_type:
            return data

        normalized = dict(data)
        normalized_filter = dict(filter_data)
        normalized_filter["search"] = {resource_type: [keyword.strip()]}
        if not normalized_filter.get("resource_type_chain"):
            if resource_type == ResourceEnum.BUSINESS.id:
                normalized_filter["resource_type_chain"] = [{"id": ResourceEnum.BUSINESS.id}]
            else:
                normalized_filter["resource_type_chain"] = [
                    {"id": ResourceEnum.BUSINESS.id},
                    {"id": resource_type},
                ]
        normalized["filter"] = normalized_filter
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
        data = self._normalize_list_instance_keyword(data)
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


def _search_keywords(filter_obj, resource_type: str) -> list[str]:
    search = getattr(filter_obj, "search", None) or {}
    if not isinstance(search, dict):
        return []
    keywords = search.get(resource_type) or []
    return [keyword for keyword in keywords if isinstance(keyword, str) and keyword]


def _with_keyword(filter_obj, keyword: str):
    keyword_filter = copy(filter_obj)
    keyword_filter["keyword"] = keyword
    return keyword_filter


def _attach_space_paths(results: list[dict], biz_id_by_id: dict[str, str]) -> None:
    """为缺少路径的实例补上空间路径，再统一转成 V4 字符串形态。"""
    for item in results:
        path = item.get("_bk_iam_path_")
        if isinstance(path, str) and path:
            continue
        if isinstance(path, list) and path:
            continue
        biz_id = biz_id_by_id.get(str(item.get("id")))
        if biz_id in (None, ""):
            continue
        item["_bk_iam_path_"] = [[{"type": ResourceEnum.BUSINESS.id, "id": str(biz_id), "display_name": str(biz_id)}]]
    _fix_nested_path_to_string(results)


def _int_ids(results: list[dict]) -> list[int]:
    ids = []
    for item in results:
        try:
            ids.append(int(item["id"]))
        except (TypeError, ValueError, KeyError):
            continue
    return ids


class _V4ChildResourceProvider:
    """collection / indices / es_source 共用的 V4 格式转换与 keyword 兼容。"""

    _search_resource_type = ""

    def list_instance(self, filter, page, **options):
        decoded = _with_decoded_parent_space(filter)
        keywords = _search_keywords(decoded, self._search_resource_type)
        parent = getattr(decoded, "parent", None)
        if isinstance(parent, dict) and parent.get("id") not in (None, "") and keywords:
            # V3 list_instance 在有 parent 时会丢掉 search；改走已支持「上级 + keyword」的 search_instance
            return super().search_instance(_with_keyword(decoded, keywords[0]), page, **options)
        result = super().list_instance(decoded, page, **options)
        _fix_nested_path_to_string(result.results)
        return result

    def fetch_instance_info(self, filter, **options):
        result = super().fetch_instance_info(filter, **options)
        _fix_approver_field(result.results)
        missing_path = [item for item in result.results if not item.get("_bk_iam_path_")]
        biz_id_by_id = self._instance_space_ids(missing_path, **options) if missing_path else {}
        _attach_space_paths(result.results, biz_id_by_id)
        return result

    def search_instance(self, filter, page, **options):
        return super().search_instance(_with_decoded_parent_space(filter), page, **options)

    def list_instance_by_policy(self, filter, page, **options):
        return super().list_instance_by_policy(_with_decoded_policy_expression(filter), page, **options)

    def _instance_space_ids(self, results: list[dict], **options) -> dict[str, str]:
        raise NotImplementedError


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


class V4CollectionResourceProvider(_V4ChildResourceProvider, CollectionResourceProvider):
    _search_resource_type = "collection"

    def _instance_space_ids(self, results: list[dict], **options) -> dict[str, str]:
        ids = _int_ids(results)
        if not ids:
            return {}
        return {
            str(pk): str(bk_biz_id)
            for pk, bk_biz_id in CollectorConfig.objects.filter(pk__in=ids).values_list("pk", "bk_biz_id")
        }


class V4IndicesResourceProvider(_V4ChildResourceProvider, IndicesResourceProvider):
    _search_resource_type = "indices"

    def _instance_space_ids(self, results: list[dict], **options) -> dict[str, str]:
        ids = _int_ids(results)
        if not ids:
            return {}
        return {
            str(pk): str(space_uid_to_bk_biz_id(space_uid))
            for pk, space_uid in LogIndexSet.objects.filter(pk__in=ids).values_list("pk", "space_uid")
        }


class V4EsSourceResourceProvider(_V4ChildResourceProvider, EsSourceResourceProvider):
    _search_resource_type = "es_source"

    def _instance_space_ids(self, results: list[dict], **options) -> dict[str, str]:
        ids = {str(item.get("id")) for item in results}
        clusters = self.list_clusters(bk_tenant_id=options["bk_tenant_id"])
        return {
            str(cluster["id"]): str(cluster["bk_biz_id"])
            for cluster in clusters
            if str(cluster["id"]) in ids and cluster.get("bk_biz_id") not in (None, "")
        }
