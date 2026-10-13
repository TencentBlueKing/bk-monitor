"""日志采集 MCP 路由共享的业务权限校验。"""

from bkmonitor.iam.drf import BusinessActionPermission


class CanonicalBusinessActionPermission(BusinessActionPermission):
    """用请求中的 ``bk_biz_id`` 作为 IAM 校验的唯一业务上下文。"""

    request_data_source = "body"
    check_query_biz_id = False

    def get_request_data(self, request):
        if self.request_data_source == "query":
            return getattr(request, "query_params", {})
        return getattr(request, "data", {})

    def has_permission(self, request, view):
        request_data = self.get_request_data(request)
        request_data = request_data if hasattr(request_data, "get") else {}
        canonical_biz_id = request_data.get("bk_biz_id")
        if canonical_biz_id is not None:
            for alias in ("biz_id", "business_id"):
                alias_biz_id = request_data.get(alias)
                if alias_biz_id is not None and str(alias_biz_id) != str(canonical_biz_id):
                    return False
            if self.check_query_biz_id:
                query_biz_id = getattr(request, "query_params", {}).get("bk_biz_id")
                if query_biz_id is not None and str(query_biz_id) != str(canonical_biz_id):
                    return False
            request_biz_id = getattr(request, "biz_id", None)
            if request_biz_id is not None and str(request_biz_id) != str(canonical_biz_id):
                return False
            request.biz_id = canonical_biz_id
        return super().has_permission(request, view)
