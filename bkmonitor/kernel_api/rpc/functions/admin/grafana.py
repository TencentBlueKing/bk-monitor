"""按租户、业务只读查询 Grafana 仪表盘和已保存的版本。"""

import json

from django.db.models import BigIntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Cast

from bk_dataview.models import Dashboard, DashboardVersion, Org
from bk_dataview.redaction import redact_config
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    ResourceNotFound,
    build_response,
    normalize_pagination,
    paginate_queryset,
    require_bk_tenant_id,
)
from kernel_api.rpc.functions.admin.space import _apply_space_bk_biz_id_filter, tenant_business_ids
from metadata.models import Space

SCOPE = {"bk_tenant_id": "必填，具体租户", "bk_biz_id": "必填，业务或负空间 ID"}
PAGING = {"page": "页码，默认 1", "page_size": "每页条数，默认 20，最大 100"}
TARGET = {**SCOPE, "dashboard_id": "必填，列表返回的仪表盘 ID"}
EXAMPLE = {"bk_tenant_id": "system", "bk_biz_id": 2}
SUMMARY = ("id", "uid", "title", "updated", "version")


def _dashboards(params):
    tenant = require_bk_tenant_id(params)
    biz = params.get("bk_biz_id")
    if type(biz) is not int:
        raise CustomException(message="bk_biz_id 必须是整数")
    if not _apply_space_bk_biz_id_filter(Space.objects.filter(bk_tenant_id=tenant), biz).exists():
        raise CustomException(message="该租户下不存在指定业务空间")
    org_ids = Org.objects.filter(name=str(biz)).values("id")
    return Dashboard.objects.filter(org_id__in=org_ids, is_folder=0)


def _dashboard(params, *fields, dashboards=None):
    rows = _dashboards(params) if dashboards is None else dashboards
    row = rows.filter(id=params.get("dashboard_id")).values(*fields).first()
    if row is None:
        raise ResourceNotFound(message="该业务下不存在指定仪表盘")
    return row


def _response(operation, params, data):
    return build_response(
        operation=operation, func_name=f"admin.{operation}", bk_tenant_id=params["bk_tenant_id"], data=data
    )


def _page(queryset, params):
    page, page_size = normalize_pagination(params)
    items, total = paginate_queryset(queryset, page=page, page_size=page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@KernelRPCRegistry.register(
    "admin.grafana.list",
    summary="查询业务 Grafana 仪表盘",
    description="在指定租户业务下按标题或 UID 分页查询，不返回配置正文。",
    params_schema={
        **SCOPE,
        "bk_biz_id": "可选，省略时查询当前租户",
        **PAGING,
        "keyword": "可选，按标题或 UID 包含匹配",
    },
    example_params={**EXAMPLE, "keyword": "CPU", "page": 1, "page_size": 20},
)
def list_dashboards(params):
    tenant = require_bk_tenant_id(params)
    if tenant == "__all__":
        raise CustomException(message="请选择具体租户")
    if "bk_biz_id" in params:
        rows = _dashboards(params)
    else:
        # Space 和 Grafana 分库；在 Grafana 库中完成组织过滤、计数与分页。
        names = [str(biz) for biz in tenant_business_ids(tenant)]
        orgs = Org.objects.filter(name__in=names)
        rows = Dashboard.objects.filter(org_id__in=orgs.values("id"), is_folder=0)
    return _response("grafana.list", params, dashboard_page(rows, params))


def dashboard_page(dashboards, params):
    keyword = params.get("keyword")
    if keyword:
        dashboards = dashboards.filter(Q(title__icontains=keyword) | Q(uid__icontains=keyword))
    org_name = Org.objects.filter(id=OuterRef("org_id")).values("name")[:1]
    biz_id = Value(params["bk_biz_id"]) if "bk_biz_id" in params else Cast(Subquery(org_name), BigIntegerField())
    return _page(dashboards.order_by("-updated", "id").values(*SUMMARY, bk_biz_id=biz_id), params)


@KernelRPCRegistry.register(
    "admin.grafana.version_list",
    summary="查询仪表盘版本记录",
    description="按版本倒序分页查询变更时间、操作者 ID 和备注。",
    params_schema={**TARGET, **PAGING},
    example_params={**EXAMPLE, "dashboard_id": 10},
)
def list_versions(params, *, dashboards=None):
    dashboard = _dashboard(params, "id", dashboards=dashboards)
    versions = DashboardVersion.objects.filter(dashboard_id=dashboard["id"]).order_by("-version")
    return _response(
        "grafana.version_list", params, _page(versions.values("version", "created", "created_by", "message"), params)
    )


@KernelRPCRegistry.register(
    "admin.grafana.config",
    summary="读取当前或指定版本的仪表盘配置",
    description="省略 version 读取当前已保存配置；传入版本号读取该仪表盘的历史快照。凭据统一脱敏。",
    params_schema={**TARGET, "version": "可选，历史版本号；省略读取当前配置"},
    example_params={**EXAMPLE, "dashboard_id": 10, "version": 1},
)
def get_config(params, *, dashboards=None):
    version = params.get("version")
    if version is None:
        row = _dashboard(params, *SUMMARY, "data", dashboards=dashboards)
        raw = row.pop("data")
        version = row["version"]
    else:
        row = _dashboard(params, *SUMMARY, dashboards=dashboards)
        snapshot = DashboardVersion.objects.filter(dashboard_id=row["id"], version=version).values("data").first()
        if snapshot is None:
            raise ResourceNotFound(message="该仪表盘不存在指定历史版本")
        raw = snapshot["data"]
    paths = []
    config = redact_config(json.loads(raw), "", paths)
    return _response(
        "grafana.config", params, {"dashboard": row, "version": version, "config": config, "redacted_paths": paths}
    )
