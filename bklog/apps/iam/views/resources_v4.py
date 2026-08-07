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

from django.conf import settings

from apps.iam import ResourceEnum
from apps.iam.views.resources import (
    BaseResourceProvider,
    CollectionResourceProvider,
    EsSourceResourceProvider,
    IndicesResourceProvider,
    ResourceApiDispatcher,
)
from apps.log_search.models import Space
from iam.resource.provider import ListResult


class V4ResourceApiDispatcher(ResourceApiDispatcher):
    """V4 资源回调 Dispatcher：多租户模式下禁止回退默认 Tenant。"""

    def _get_options(self, request):
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
            item["_bk_iam_path_"] = f"/{ResourceEnum.BUSINESS.id},{biz_id}/"


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
            "id": str(space["bk_biz_id"]),
            "display_name": f"[{space['space_type_name']}] {space['space_name']}",
        }

    def list_instance(self, filter, page, **options):
        spaces = Space.get_all_spaces(self._require_tenant_id(options))
        if filter.search:
            keywords = filter.search.get("space", []) or []
            if keywords:
                spaces = [
                    space
                    for space in spaces
                    if any(
                        keyword in space.get("space_name", "")
                        or keyword in space.get("space_type_name", "")
                        or keyword in str(space.get("bk_biz_id", ""))
                        for keyword in keywords
                    )
                ]

        results = [self._to_result_item(space) for space in spaces[page.slice_from : page.slice_to]]
        return ListResult(results=results, count=len(spaces))

    def fetch_instance_info(self, filter, **options):
        spaces = Space.get_all_spaces(self._require_tenant_id(options))
        if filter.ids:
            ids = {str(i) for i in filter.ids}
            spaces = [space for space in spaces if str(space["bk_biz_id"]) in ids]

        results = []
        for space in spaces:
            item = self._to_result_item(space)
            # Space 模型当前没有稳定的管理员字段，不编造审批人
            item["_bk_iam_approvers_"] = []
            results.append(item)
        return ListResult(results=results, count=len(results))

    def search_instance(self, filter, page, **options):
        spaces = Space.get_all_spaces(self._require_tenant_id(options))
        keyword = (filter.keyword or "").lower()
        if keyword:
            spaces = [
                space
                for space in spaces
                if keyword in str(space.get("space_name", "")).lower()
                or keyword in str(space.get("space_type_name", "")).lower()
                or keyword in str(space.get("bk_biz_id", "")).lower()
            ]

        results = [self._to_result_item(space) for space in spaces[page.slice_from : page.slice_to]]
        return ListResult(results=results, count=len(spaces))

    def list_instance_by_policy(self, filter, page, **options):
        # V4 space 的按策略反查契约尚未确认，先返回空结果
        return ListResult(results=[], count=0)


class V4CollectionResourceProvider(CollectionResourceProvider):
    def list_instance(self, filter, page, **options):
        result = super().list_instance(filter, page, **options)
        _fix_nested_path_to_string(result.results)
        return result

    def fetch_instance_info(self, filter, **options):
        result = super().fetch_instance_info(filter, **options)
        _fix_approver_field(result.results)
        return result


class V4IndicesResourceProvider(IndicesResourceProvider):
    def list_instance(self, filter, page, **options):
        result = super().list_instance(filter, page, **options)
        _fix_nested_path_to_string(result.results)
        return result

    def fetch_instance_info(self, filter, **options):
        result = super().fetch_instance_info(filter, **options)
        _fix_approver_field(result.results)
        return result


class V4EsSourceResourceProvider(EsSourceResourceProvider):
    def list_instance(self, filter, page, **options):
        result = super().list_instance(filter, page, **options)
        _fix_nested_path_to_string(result.results)
        return result

    def fetch_instance_info(self, filter, **options):
        result = super().fetch_instance_info(filter, **options)
        _fix_approver_field(result.results)
        return result
