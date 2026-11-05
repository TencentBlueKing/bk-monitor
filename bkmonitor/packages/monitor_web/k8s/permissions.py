from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.models import ApiAuthToken
from bkmonitor.utils.tenant import is_biz_in_tenant
from monitor_web.grafana.permissions import GrafanaReadPermission


class K8sGraphReadPermission(GrafanaReadPermission):
    def has_permission(self, request, view):
        # Every grant must apply to the business that the chart resource will query.
        biz_id = request.data.get("bk_biz_id") if hasattr(request.data, "get") else None
        if not request.biz_id or biz_id in (None, "") or str(biz_id) != str(request.biz_id):
            return False
        if not is_biz_in_tenant(request.biz_id, getattr(request.user, "tenant_id", None)):
            return False

        if getattr(request, "token", None):
            try:
                token = ApiAuthToken.objects.get(token=request.token, bk_tenant_id=request.user.tenant_id)
            except ApiAuthToken.DoesNotExist:
                return False
            if token.type == "kubernetes":
                # Keep the scene's existing action; ApiAuthResource still checks its query parameters.
                return BusinessActionPermission([ActionEnum.VIEW_BUSINESS]).has_permission(request, view)

        return super().has_permission(request, view)
