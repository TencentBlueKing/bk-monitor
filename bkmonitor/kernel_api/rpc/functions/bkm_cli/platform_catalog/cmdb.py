"""CMDB 原生单页主机查询；业务和租户授权在调用后台身份之前完成。"""

from __future__ import annotations

import copy
from typing import Any

from api.cmdb.client import list_biz_hosts
from bkmonitor.models import ApiAuthToken
from bkmonitor.utils.request import get_app_code_by_request, get_request
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from kernel_api.middlewares.authentication import is_match_api_token

from ._catalog import OperationSpec, ParamsGuardRejected, PlatformSourceCatalog, ProviderResponseRejected

HOST_FIELDS = ("bk_host_id", "bk_cloud_id", "bk_host_innerip", "bk_host_innerip_v6", "bk_host_name")
MAX_PAGE_SIZE = 500
ALLOWED_KEYS = frozenset({"bk_biz_id", "page", "page_size"})


def _positive_integer(value: Any, name: str, maximum: int | None = None) -> int:
    if type(value) is not int or value <= 0 or (maximum is not None and value > maximum):
        raise ParamsGuardRejected(f"{name} 必须是正整数" + (f"，且不超过 {maximum}" if maximum else ""))
    return value


def _authorize_business(bk_biz_id: int) -> str:
    request = get_request(peaceful=True)
    user = getattr(request, "user", None)
    tenant = getattr(user, "tenant_id", None)
    if not request or not getattr(user, "is_authenticated", False) or not tenant:
        raise ParamsGuardRejected("CMDB 查询需要已认证的应用和请求租户")
    try:
        if bk_biz_id_to_bk_tenant_id(bk_biz_id) != tenant:
            raise ParamsGuardRejected("目标业务不属于当前请求租户")
        request_biz = getattr(request, "biz_id", None)
        if request_biz and int(request_biz) != bk_biz_id:
            raise ParamsGuardRejected("目标业务与请求业务不一致")
        # catalog 的业务位于嵌套 params，中间件未解析该字段；两条认证路径
        # 都必须针对实际目标重做业务授权，租户归属校验不能替代该检查。
        authorization = request.META.get("HTTP_AUTHORIZATION", "")
        if authorization.startswith("Bearer "):
            record = ApiAuthToken.objects.filter(token=authorization[7:], bk_tenant_id=tenant).first()
            if not record or record.is_expired() or not record.is_allowed_namespace(f"biz#{bk_biz_id}"):
                raise ParamsGuardRejected("API Token 未获目标业务授权或已失效")
        else:
            jwt_app = getattr(getattr(request, "jwt", None), "app", None)
            app_code = getattr(jwt_app, "app_code", None) or get_app_code_by_request(request)
            if not app_code:
                raise ParamsGuardRejected("CMDB 查询缺少已认证的应用身份")
            scoped_request = copy.copy(request)
            scoped_request.biz_id = bk_biz_id
            if not is_match_api_token(scoped_request, tenant, app_code):
                raise ParamsGuardRejected("当前应用未获目标业务授权")
    except ParamsGuardRejected:
        raise
    except Exception as error:
        raise ParamsGuardRejected("无法验证 CMDB 业务授权") from error
    return tenant


def guard_list_biz_hosts(params: Any) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise ParamsGuardRejected("list_biz_hosts 参数必须是对象")
    unknown = sorted(str(key) for key in params if key not in ALLOWED_KEYS)
    if unknown:
        raise ParamsGuardRejected(f"list_biz_hosts 拒绝未声明参数: {unknown}")
    bk_biz_id = _positive_integer(params.get("bk_biz_id"), "bk_biz_id")
    page = _positive_integer(params.get("page", 1), "page")
    page_size = _positive_integer(params.get("page_size", 50), "page_size", MAX_PAGE_SIZE)
    tenant = _authorize_business(bk_biz_id)
    return {
        "bk_biz_id": bk_biz_id,
        "bk_tenant_id": tenant,
        "fields": list(HOST_FIELDS),
        "page": {"start": (page - 1) * page_size, "limit": page_size, "sort": "bk_host_id"},
    }


def project_list_biz_hosts(raw: Any, _fields: list[str] | None, params: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict) or type(raw.get("count")) is not int or raw["count"] < 0:
        raise ProviderResponseRejected("CMDB 分页响应缺少有效 count")
    hosts = raw.get("info")
    page = params["page"]
    expected_count = min(page["limit"], max(0, raw["count"] - page["start"]))
    if not isinstance(hosts, list) or len(hosts) != expected_count or raw.get("is_partial"):
        raise ProviderResponseRejected("CMDB 分页响应 info 无效")
    result = []
    for host in hosts:
        if (
            not isinstance(host, dict)
            or not set(HOST_FIELDS).issubset(host)
            or type(host["bk_host_id"]) is not int
            or host["bk_host_id"] <= 0
            or type(host["bk_cloud_id"]) is not int
            or host["bk_cloud_id"] < 0
            or any(host[field] is not None and not isinstance(host[field], str) for field in HOST_FIELDS[2:])
        ):
            raise ProviderResponseRejected("CMDB 分页响应包含无效主机身份")
        result.append({field: host[field] for field in HOST_FIELDS})
    if any(left["bk_host_id"] >= right["bk_host_id"] for left, right in zip(result, result[1:])):
        raise ProviderResponseRejected("CMDB 分页响应主机 ID 重复或未按要求排序")
    return {
        "count": raw["count"],
        "info": result,
        "page": page["start"] // page["limit"] + 1,
        "page_size": page["limit"],
        "has_more": page["start"] + len(result) < raw["count"],
        "is_snapshot": False,
    }


def register() -> None:
    PlatformSourceCatalog.register_domain(
        id="cmdb",
        summary="CMDB 业务主机身份单页只读查询",
        audit_tags=["readonly", "cmdb"],
        operations=[
            OperationSpec(
                id="list_biz_hosts",
                summary="分页读取已授权业务的 CMDB 主机身份",
                handler=list_biz_hosts,
                params_guard=guard_list_biz_hosts,
                response_postprocess=project_list_biz_hosts,
                response_postprocess_needs_params=True,
                default_fields=list(HOST_FIELDS),
                allowed_fields=list(HOST_FIELDS),
                required_params=["bk_biz_id"],
                params_schema_override={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["bk_biz_id"],
                    "properties": {
                        "bk_biz_id": {"type": "integer", "minimum": 1},
                        "page": {"type": "integer", "minimum": 1, "default": 1},
                        "page_size": {"type": "integer", "minimum": 1, "maximum": MAX_PAGE_SIZE, "default": 50},
                    },
                },
                example_params={"bk_biz_id": 2, "page": 1, "page_size": 50},
                audit_tags=["readonly", "cmdb", "business-scoped"],
                notes=(
                    "每次只调用一次 CMDB list_biz_hosts；固定按 bk_host_id 升序，字段固定，不接受任意过滤。"
                    "count 为 CMDB 返回的匹配总数，info 为本页；分页不是一致性快照，主机增删可能导致跨页漂移。"
                    "返回原始 CMDB 身份（IP 可能含逗号），不等同 SaaS 主机列表的有效 IP 过滤或指标统计。"
                    "需要已认证应用或 API Token、当前请求租户及目标业务授权；不支持负数关联空间。"
                ),
            )
        ],
    )


register()
