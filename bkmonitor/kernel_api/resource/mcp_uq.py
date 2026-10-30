"""MCP-only bounded UQ reads; shared UQ APIs and ordinary calls stay unchanged."""

from urllib.parse import urljoin

import requests
from django.conf import settings

from api.unify_query.default import (
    QueryDataByPromqlResource,
    QueryMultiResource,
    QueryMultiResourceRange,
    QueryRawResource,
    QueryReferenceResource,
    get_unify_query_url,
)
from api.unify_query.relation_routing import resolve_relation_query_path
from bkm_space.api import SpaceApi
from bkm_space.utils import bk_biz_id_to_space_uid
from bkmonitor.utils.graph_relation import RELATION_SCHEMA_VERSION_HEADER, get_relation_schema_version
from bkmonitor.utils.local import local
from bkmonitor.utils.request import get_request, get_request_tenant_id
from bkmonitor.utils.tenant import space_uid_to_bk_tenant_id
from core.errors.api import BKAPIError
from kernel_api.resource.mcp_response import get_max_response_bytes, read_bounded_json

UQ_OPERATIONS = {
    "query_data_by_promql": QueryDataByPromqlResource,
    "query_raw": QueryRawResource,
    "query_reference": QueryReferenceResource,
    "query_multi": QueryMultiResource,
    "query_multi_resource_range": QueryMultiResourceRange,
}


def query_uq(operation, params, *, max_bytes=None):
    """Reuse original serializers and request contracts with a bounded reader.

    This explicit opt-in is called only by MCP Resource branches. UQ's shared
    client has no overridable I/O hook, so request construction is mirrored here
    and covered by parity tests against UnifyQueryAPIResource.perform_request.
    """
    try:
        client_class = UQ_OPERATIONS[operation]
    except KeyError as error:
        raise ValueError(f"Unsupported MCP UQ operation: {operation}") from error
    client = client_class()
    params = client.validate_request_data(dict(params))
    if operation == "query_raw":
        # Preserve QueryRawResource.perform_request's transformation.
        params["from"] = params.pop("_from", 0)
    if max_bytes is None:
        max_bytes = get_max_response_bytes()
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("MCP UQ response limit must be a positive integer")

    request = get_request(peaceful=True)
    username = request.user.username if request and hasattr(request, "user") else ""
    bk_biz_id = None
    space_uid = ""
    if "space_uid" in params:
        space_uid = params["space_uid"]
    elif params.get("bk_biz_ids"):
        bk_biz_id = params.pop("bk_biz_ids")[0]
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)
    elif request and request.biz_id:
        bk_biz_id = request.biz_id
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)

    space = SpaceApi.get_space_detail(space_uid=space_uid) if space_uid else None
    is_global = space.is_global if space else False
    if bk_biz_id is None and space:
        bk_biz_id = space.bk_biz_id
    bk_tenant_id = params.get("bk_tenant_id")
    if not bk_tenant_id and space_uid:
        try:
            bk_tenant_id = space_uid_to_bk_tenant_id(space_uid)
        except ValueError:
            pass
    if not bk_tenant_id:
        bk_tenant_id = get_request_tenant_id(peaceful=True)

    source = "backend"
    if username:
        source = f"username:{username}"
    elif getattr(local, "strategy_id", None):
        source = f"strategy:{local.strategy_id}"
    headers = {"Bk-Query-Source": source, "Accept-Encoding": "gzip, identity"}
    if space_uid is None or is_global:
        headers["X-Bk-Scope-Skip-Space"] = settings.APP_CODE
    elif space_uid:
        headers["X-Bk-Scope-Space-Uid"] = space_uid
    if bk_tenant_id:
        headers["X-Bk-Tenant-Id"] = bk_tenant_id
    schema_version = get_relation_schema_version(bk_biz_id) if client.v1beta3_path else ""
    if schema_version:
        headers[RELATION_SCHEMA_VERSION_HEADER] = schema_version
    path = resolve_relation_query_path(client.path, client.v1beta3_path, schema_version=schema_version)
    url = urljoin(get_unify_query_url(space_uid), path.format(**params))
    with requests.request(
        method=client.method,
        url=url,
        headers=headers,
        json=params,
        timeout=60,
        stream=True,
        allow_redirects=False,
    ) as response:
        data, error = read_bounded_json(response, max_bytes)
        if error is not None:
            # Never re-expand a large upstream error through logs / API wrappers.
            summary = error[:512] + ("... [truncated]" if len(error) > 512 else "")
            raise BKAPIError(system_name="unify-query", url=url, result=summary)
        return data
