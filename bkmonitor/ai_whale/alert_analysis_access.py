"""Server-side identity and alert authorization for deterministic conversations."""

from rest_framework.exceptions import NotAuthenticated, PermissionDenied


def current_identity():
    from bkmonitor.utils.request import get_request, get_request_tenant_id

    request = get_request()
    if not request.user.is_authenticated or not request.user.username:
        raise NotAuthenticated()
    if getattr(request, "token", None):
        raise PermissionDenied("分享凭据不能访问个人告警分析会话")
    return request.user.username, get_request_tenant_id()


def authorized_alert(alert_id, bk_biz_id=None):
    from bkmonitor.documents import AlertDocument
    from core.errors.alert import AlertNotFoundError

    username, tenant_id = current_identity()
    alert = AlertDocument.get(str(alert_id))
    if not alert:
        raise AlertNotFoundError()
    biz_id = int(alert.bk_biz_id)
    if bk_biz_id is not None and biz_id != int(bk_biz_id):
        raise PermissionDenied("告警不属于当前业务")
    authorize_businesses([biz_id], username, tenant_id)
    return alert


def authorize_businesses(biz_ids, username, tenant_id):
    from bkmonitor.iam import ActionEnum
    from bkmonitor.iam.permission import Permission
    from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id

    permission = Permission(username=username, bk_tenant_id=tenant_id)
    permission.skip_check = False
    for biz_id in set(map(int, biz_ids)):
        if str(bk_biz_id_to_bk_tenant_id(biz_id)) != str(tenant_id):
            raise PermissionDenied("分析来源不属于当前租户")
        if not permission.is_allowed_by_biz(bk_biz_id=biz_id, action=ActionEnum.VIEW_EVENT):
            raise PermissionDenied("无分析来源业务的告警查看权限")


def authorize_incident(incident):
    username, tenant_id = current_identity()
    # A fault snapshot can contain evidence from more than its primary business.
    biz_ids = [incident.bk_biz_id, *(getattr(incident.snapshot, "bk_biz_ids", None) or [])]
    authorize_businesses(biz_ids, username, tenant_id)
