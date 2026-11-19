"""Server-side identity and alert authorization for deterministic conversations."""

from rest_framework.exceptions import NotAuthenticated, PermissionDenied

from ai_whale.alert_analysis_session import owned_alert_id


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


def check_alert_session(session_code):
    from ai_whale.alert_analysis_session import SESSION_PREFIX

    if not isinstance(session_code, str) or not session_code.startswith(SESSION_PREFIX):
        return
    username, tenant_id = current_identity()
    try:
        alert_id = owned_alert_id(session_code, username, tenant_id)
    except ValueError as exc:
        raise PermissionDenied("不能访问其他用户的告警会话") from exc
    authorized_alert(alert_id)


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


def authorize_content_ids(interface, ids, session_code=None):
    """The legacy ID-only mutation APIs must not bypass session ownership checks."""
    from ai_whale.alert_analysis_session import history, response_data, SessionPreparationError

    username, _ = current_identity()
    remaining = set(map(str, ids))
    if not remaining:
        return
    sessions = response_data(interface.list_chat_sessions(username=username))
    if isinstance(sessions, dict):
        rows = sessions.get("results")
        if not isinstance(rows, list) or sessions.get("next") or sessions.get("count", 0) > len(rows):
            raise SessionPreparationError("Cannot verify ownership from incomplete session list")
        sessions = rows
    if not isinstance(sessions, list):
        raise SessionPreparationError("Invalid session list")
    for session in sessions:
        code = session.get("session_code")
        if not code or (session_code is not None and code != session_code):
            continue
        # Check the matched conversation before returning any right to mutate its messages.
        matching = remaining.intersection(str(row.get("id")) for row in history(interface, code))
        if matching:
            check_alert_session(code)
            remaining.difference_update(matching)
        if not remaining:
            return
    raise PermissionDenied("不能修改其他用户或其他会话的消息")


def check_alert_history(session_code, records):
    """Recheck historical evidence permissions before returning it or feeding it to the model."""
    from ai_whale.alert_analysis_session import SESSION_PREFIX, snapshot_event
    from bkmonitor.documents import IncidentDocument

    if not session_code.startswith(SESSION_PREFIX):
        return
    checked = set()
    for row in records:
        if not snapshot_event(row):
            continue
        source = row["property"]["extra"]["alert_analysis_message"].get("payload", {}).get("source")
        if not source:
            continue
        doc_id = source.get("monitor_incident_id")
        if not doc_id or doc_id in checked:
            if not doc_id:
                raise PermissionDenied("历史分析来源不可验证")
            continue
        incident = IncidentDocument.get(str(doc_id), fetch_remote=False)
        if incident is None:
            raise PermissionDenied("历史分析来源已不可用")
        authorize_incident(incident)
        checked.add(doc_id)
