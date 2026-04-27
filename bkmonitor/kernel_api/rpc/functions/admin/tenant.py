"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from django.db.models import Count, Q

from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response, normalize_pagination
from metadata import models

FUNC_TENANT_LIST = "admin.tenant.list"


def _normalize_tenant_id(value: Any) -> str:
    return str(value or "").strip()


def _extract_api_tenant(raw_tenant: dict[str, Any]) -> dict[str, Any] | None:
    tenant_id = _normalize_tenant_id(raw_tenant.get("id") or raw_tenant.get("bk_tenant_id"))
    if not tenant_id:
        return None

    return {
        "id": tenant_id,
        "name": raw_tenant.get("name") or raw_tenant.get("display_name") or raw_tenant.get("tenant_name") or tenant_id,
        "display_name": raw_tenant.get("display_name") or raw_tenant.get("name") or raw_tenant.get("tenant_name"),
        "source": "bk_login",
    }


def _get_api_tenants() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        raw_tenants = api.bk_login.list_tenant()
    except Exception as error:
        return [], [{"code": "BK_LOGIN_TENANT_LIST_FAILED", "message": f"获取登录租户列表失败: {error}"}]

    tenants = []
    for raw_tenant in raw_tenants or []:
        if not isinstance(raw_tenant, dict):
            continue
        tenant = _extract_api_tenant(raw_tenant)
        if tenant:
            tenants.append(tenant)
    return tenants, []


def _count_by_tenant(model_cls: Any) -> dict[str, int]:
    queryset = model_cls.objects.exclude(Q(bk_tenant_id__isnull=True) | Q(bk_tenant_id=""))
    pk_field = model_cls._meta.pk.name
    return {
        item["bk_tenant_id"]: item["total"]
        for item in queryset.values("bk_tenant_id").annotate(total=Count(pk_field)).order_by()
    }


def _get_metadata_tenant_ids(*count_maps: dict[str, int]) -> set[str]:
    tenant_ids: set[str] = set()
    for count_map in count_maps:
        tenant_ids.update(count_map)
    tenant_ids.add(DEFAULT_TENANT_ID)
    return tenant_ids


def _match_keyword(tenant: dict[str, Any], keyword: str) -> bool:
    if not keyword:
        return True

    normalized_keyword = keyword.lower()
    return any(
        normalized_keyword in str(tenant.get(field) or "").lower() for field in ["id", "name", "display_name", "source"]
    )


@KernelRPCRegistry.register(
    FUNC_TENANT_LIST,
    summary="Admin 查询租户列表",
    description="只读查询当前环境可见租户。优先使用 bk_login 租户列表，并补充 metadata 中已有数据的租户。",
    params_schema={
        "keyword": "可选，按租户 ID / 名称包含匹配",
        "page": "可选，默认 1",
        "page_size": "可选，默认 100，最大 200",
    },
    example_params={"keyword": "system", "page": 1, "page_size": 100},
)
def list_tenants(params: dict[str, Any]) -> dict[str, Any]:
    page, page_size = normalize_pagination(params, default_page_size=100, max_page_size=200)
    keyword = str(params.get("keyword") or "").strip()
    datasource_count_map = _count_by_tenant(models.DataSource)
    result_table_count_map = _count_by_tenant(models.ResultTable)
    tenants: dict[str, dict[str, Any]] = {}
    api_tenants, warnings = _get_api_tenants()

    for tenant in api_tenants:
        tenants[tenant["id"]] = tenant

    for tenant_id in _get_metadata_tenant_ids(datasource_count_map, result_table_count_map):
        tenants.setdefault(
            tenant_id,
            {
                "id": tenant_id,
                "name": tenant_id,
                "display_name": tenant_id,
                "source": "metadata",
            },
        )

    items = []
    for tenant in tenants.values():
        tenant_id = tenant["id"]
        items.append(
            {
                **tenant,
                "datasource_count": datasource_count_map.get(tenant_id, 0),
                "result_table_count": result_table_count_map.get(tenant_id, 0),
            }
        )

    filtered_items = [item for item in items if _match_keyword(item, keyword)]
    filtered_items.sort(key=lambda item: (item["id"] != DEFAULT_TENANT_ID, item["id"]))
    total = len(filtered_items)
    offset = (page - 1) * page_size

    return build_response(
        operation="tenant.list",
        func_name=FUNC_TENANT_LIST,
        bk_tenant_id=DEFAULT_TENANT_ID,
        data={
            "items": filtered_items[offset : offset + page_size],
            "page": page,
            "page_size": page_size,
            "total": total,
        },
        warnings=warnings,
    )
