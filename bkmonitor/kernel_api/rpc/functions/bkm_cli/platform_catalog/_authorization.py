"""平台 catalog 嵌套业务参数的请求身份、租户和业务授权。"""

from __future__ import annotations

import copy

from bkmonitor.models import ApiAuthToken
from bkmonitor.utils.request import get_app_code_by_request, get_request
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from kernel_api.middlewares.authentication import is_match_api_token

from ._catalog import ParamsGuardRejected


def authorize_business(bk_biz_id: int, *, query_name: str) -> str:
    request = get_request(peaceful=True)
    user = getattr(request, "user", None)
    tenant = getattr(user, "tenant_id", None)
    if not request or not getattr(user, "is_authenticated", False) or not tenant:
        raise ParamsGuardRejected(f"{query_name} 查询需要已认证的应用和请求租户")
    try:
        if bk_biz_id_to_bk_tenant_id(bk_biz_id) != tenant:
            raise ParamsGuardRejected("目标业务不属于当前请求租户")
        request_biz = getattr(request, "biz_id", None)
        if request_biz and int(request_biz) != bk_biz_id:
            raise ParamsGuardRejected("目标业务与请求业务不一致")
        # 中间件未解析 catalog 的嵌套业务，两条认证路径都需重查实际目标。
        authorization = request.META.get("HTTP_AUTHORIZATION", "")
        if authorization.startswith("Bearer "):
            record = ApiAuthToken.objects.filter(token=authorization[7:], bk_tenant_id=tenant).first()
            if not record or record.is_expired() or not record.is_allowed_namespace(f"biz#{bk_biz_id}"):
                raise ParamsGuardRejected("API Token 未获目标业务授权或已失效")
        else:
            jwt_app = getattr(getattr(request, "jwt", None), "app", None)
            app_code = getattr(jwt_app, "app_code", None) or get_app_code_by_request(request)
            if not app_code:
                raise ParamsGuardRejected(f"{query_name} 查询缺少已认证的应用身份")
            scoped_request = copy.copy(request)
            scoped_request.biz_id = bk_biz_id
            if not is_match_api_token(scoped_request, tenant, app_code):
                raise ParamsGuardRejected("当前应用未获目标业务授权")
    except ParamsGuardRejected:
        raise
    except Exception as error:
        raise ParamsGuardRejected(f"无法验证 {query_name} 业务授权") from error
    return tenant
