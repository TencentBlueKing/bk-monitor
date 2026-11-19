"""Exercise serializers and orchestration with isolated ES/IAM/API dependencies."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
from django.conf import settings
from rest_framework.exceptions import PermissionDenied

from ai_whale import alert_analysis_access as access
from ai_whale.alert_analysis_session import session_code_for


def module(monkeypatch, name, **attrs):
    value = ModuleType(name)
    value.__dict__.update(attrs)
    monkeypatch.setitem(sys.modules, name, value)
    return value


@pytest.fixture(autouse=True)
def django_settings():
    if not settings.configured:
        settings.configure(USE_I18N=False, AIDEV_AGENT_APP_CODE="monitor")


@pytest.fixture
def api(monkeypatch):
    class Resource:
        def request(self, params):
            serializer = self.RequestSerializer(data=params)
            serializer.is_valid(raise_exception=True)
            return self.perform_request(serializer.validated_data)

    incident = SimpleNamespace(id="456", incident_id="7", bk_biz_id="2")
    incident_doc = Mock(get=Mock(return_value=incident))
    diagnosis = Mock()
    diagnosis.get_remote_analysis_results.return_value = {
        "incident_diagnosis": {
            "sub_panels": {
                "summary": {"status": "finished", "content": "summary"},
                "logs_analysis": {"status": "running", "content": {"groups": []}},
                "internal_dag": {"status": "finished", "content": "must not copy"},
            }
        }
    }
    diagnosis.format_diagnosis.side_effect = lambda raw, name, biz: {
        "sub_panel": name,
        "contents": raw["incident_diagnosis"]["sub_panels"][name]["content"],
    }
    diagnosis_cls = Mock(return_value=diagnosis)
    diagnosis_cls.is_bkfara_incident.return_value = True
    detail = Mock(request=Mock(return_value={"drawer_type": "log", "payload": {"list": []}}))
    module(monkeypatch, "bkmonitor.documents", IncidentDocument=incident_doc)
    module(monkeypatch, "core.drf_resource", Resource=Resource)
    module(
        monkeypatch,
        "monitor_web.incident.resources",
        IncidentDiagnosisResource=diagnosis_cls,
        IncidentPanelDetailResource=Mock(return_value=detail),
        IncidentResultsResource=SimpleNamespace(_content_valid=lambda value: bool(value)),
    )
    path = Path(__file__).parents[1] / "resources" / "alert_analysis.py"
    spec = importlib.util.spec_from_file_location("isolated_alert_analysis", path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    loaded.authorized_alert = Mock(return_value=SimpleNamespace(incident_id="456", bk_biz_id="2"))
    loaded.authorize_incident = Mock()
    return SimpleNamespace(
        module=loaded, doc=incident_doc, diagnosis=diagnosis, detail=detail, params={"alert_id": "123", "bk_biz_id": 2}
    )


def test_result_uses_server_relationship_and_one_snapshot(api):
    result = api.module.AlertAnalysisResultsResource().request(api.params)
    assert result["subject"] == {"type": "alert", "alert_id": "123"}
    assert result["source"] == {"type": "incident_analysis", "monitor_incident_id": "456", "incident_id": 7}
    assert result["analysis"]["status"] == "running"
    assert set(result["analysis"]["sub_panels"]) == {"summary", "logs_analysis"}
    api.diagnosis.get_remote_analysis_results.assert_called_once()
    api.module.authorize_incident.assert_called_once_with(api.doc.get.return_value)


def test_missing_relationship_does_not_call_fault_api(api):
    api.module.authorized_alert.return_value.incident_id = None
    result = api.module.AlertAnalysisResultsResource().request(api.params)
    assert result["analysis"]["reason"] == "no_related_incident"
    assert result["source"] is None
    api.doc.get.assert_not_called()
    api.diagnosis.get_remote_analysis_results.assert_not_called()
    assert api.module.AlertAnalysisRelatedIncidentResource().request(api.params) == {"incident": {}}


def test_wrong_business_denied_before_remote_read(api):
    api.doc.get.return_value.bk_biz_id = "3"
    with pytest.raises(PermissionDenied):
        api.module.AlertAnalysisResultsResource().request(api.params)
    api.diagnosis.get_remote_analysis_results.assert_not_called()


def test_denied_alert_never_fetches_fault(api):
    api.module.authorized_alert.side_effect = PermissionDenied()
    with pytest.raises(PermissionDenied):
        api.module.AlertAnalysisResultsResource().request(api.params)
    api.doc.get.assert_not_called()


def test_detail_cannot_override_incident_id(api):
    params = {
        **api.params,
        "incident_id": 999,
        "drawer_type": "log",
        "detail_ref": {"panel": "logs_analysis", "incident_task_id": 8},
    }
    api.module.AlertAnalysisPanelDetailResource().request(params)
    sent = api.detail.request.call_args.args[0]
    assert sent["incident_id"] == 7
    assert "alert_id" not in sent
    assert sent["detail_ref"] == params["detail_ref"]


def test_panel_choice_rejects_fault_only_payload(api):
    serializer = api.module.AlertAnalysisDiagnosisResource.RequestSerializer(
        data={**api.params, "sub_panel": "internal_dag"}
    )
    assert not serializer.is_valid()


def test_64bit_id_remains_a_string(api):
    serializer = api.module.AlertAnalysisSerializer(data={"alert_id": "9999999999999999999", "bk_biz_id": 2})
    assert serializer.is_valid()
    assert serializer.validated_data["alert_id"] == "9999999999999999999"


def test_session_owner_is_checked_before_alert_lookup(monkeypatch):
    monkeypatch.setattr(access, "current_identity", lambda: ("alice", "tenant"))
    lookup = Mock()
    monkeypatch.setattr(access, "authorized_alert", lookup)
    with pytest.raises(PermissionDenied):
        access.check_alert_session(session_code_for("123", "bob", "tenant"))
    lookup.assert_not_called()
    access.check_alert_session(session_code_for("123", "alice", "tenant"))
    lookup.assert_called_once_with("123")


@pytest.mark.parametrize("authenticated,token", [(False, None), (True, "share-token")])
def test_anonymous_and_shared_credentials_cannot_initialize(monkeypatch, authenticated, token):
    request = SimpleNamespace(user=SimpleNamespace(username="alice", is_authenticated=authenticated), token=token)
    module(monkeypatch, "bkmonitor.utils.request", get_request=lambda: request, get_request_tenant_id=lambda: "tenant")
    from rest_framework.exceptions import NotAuthenticated

    with pytest.raises((NotAuthenticated, PermissionDenied)):
        access.current_identity()


def test_permission_checks_all_source_businesses_and_tenant(monkeypatch):
    permission = Mock(is_allowed_by_biz=Mock(return_value=True))
    module(monkeypatch, "bkmonitor.iam", ActionEnum=SimpleNamespace(VIEW_EVENT="view_event"))
    module(monkeypatch, "bkmonitor.iam.permission", Permission=Mock(return_value=permission))
    module(
        monkeypatch, "bkmonitor.utils.tenant", bk_biz_id_to_bk_tenant_id=lambda biz: "tenant" if biz == 2 else "other"
    )
    access.authorize_businesses([2], "alice", "tenant")
    assert permission.skip_check is False
    permission.is_allowed_by_biz.assert_called_once_with(bk_biz_id=2, action="view_event")
    with pytest.raises(PermissionDenied):
        access.authorize_businesses([3], "alice", "tenant")
    permission.is_allowed_by_biz.return_value = False
    with pytest.raises(PermissionDenied):
        access.authorize_businesses([2], "alice", "tenant")


def test_id_only_mutation_cannot_change_another_users_snapshot(monkeypatch):
    monkeypatch.setattr(access, "current_identity", lambda: ("alice", "tenant"))
    monkeypatch.setattr(access, "authorized_alert", Mock())
    code = session_code_for("123", "alice", "tenant")
    interface = Mock()
    interface.list_chat_sessions.return_value = {"result": True, "data": [{"session_code": code}]}
    interface.get_chat_session_contents.return_value = {"result": True, "data": [{"id": 1}]}
    access.authorize_content_ids(interface, [1])
    with pytest.raises(PermissionDenied):
        access.authorize_content_ids(interface, [2])
    with pytest.raises(PermissionDenied):
        access.authorize_content_ids(interface, [1], "different-session")


def test_history_permissions_are_rechecked_after_revocation(monkeypatch):
    code = session_code_for("123", "alice", "tenant")
    incident = SimpleNamespace(id="456")
    module(monkeypatch, "bkmonitor.documents", IncidentDocument=SimpleNamespace(get=lambda *a, **kw: incident))
    checker = Mock(side_effect=PermissionDenied())
    monkeypatch.setattr(access, "authorize_incident", checker)
    records = [
        {
            "role": "ai",
            "property": {
                "extra": {
                    "alert_analysis_message": {
                        "eventId": "snapshot",
                        "payload": {"source": {"monitor_incident_id": "456"}},
                    }
                }
            },
        }
    ]
    with pytest.raises(PermissionDenied):
        access.check_alert_history(code, records)
    checker.assert_called_once_with(incident)


@pytest.fixture
def session_api(api, monkeypatch):
    class LockError(Exception):
        pass

    module(monkeypatch, "redis.exceptions", LockError=LockError)
    module(monkeypatch, "ai_whale.resources.resources", aidev_interface=object())
    module(monkeypatch, "utils.redis_client", RedisClient=Mock(return_value=object()))
    api.module.current_identity = Mock(return_value=("alice", "tenant"))
    api.module.ensure_session = Mock(return_value={"status": "ready", "session_code": "server-code"})
    api.lock_error = LockError
    return api


def test_session_uses_authenticated_identity_not_client_input(session_api):
    api = session_api
    result = api.module.AlertAnalysisSessionContextResource().request(
        {**api.params, "username": "bob", "tenant_id": "foreign", "session_code": "client-code"}
    )
    assert result["session_code"] == "server-code"
    kwargs = api.module.ensure_session.call_args.kwargs
    assert kwargs["username"] == "alice" and kwargs["tenant_id"] == "tenant"
    assert kwargs["agent_code"] == "monitor"
    assert kwargs["context_factory"]()["subject"]["alert_id"] == "123"


def test_session_busy_is_retryable(session_api):
    from rest_framework.exceptions import APIException

    session_api.module.ensure_session.side_effect = session_api.lock_error()
    with pytest.raises(APIException) as error:
        session_api.module.AlertAnalysisSessionContextResource().request(session_api.params)
    assert error.value.status_code == 409


def test_upstream_failure_does_not_leak_response_body(session_api):
    from rest_framework.exceptions import APIException

    session_api.module.ensure_session.side_effect = RuntimeError("private upstream response")
    with pytest.raises(APIException) as error:
        session_api.module.AlertAnalysisSessionContextResource().request(session_api.params)
    assert error.value.status_code == 502
    assert "private" not in str(error.value)


def test_session_permission_failure_remains_permission_failure(session_api):
    session_api.module.ensure_session.side_effect = PermissionDenied()
    with pytest.raises(PermissionDenied):
        session_api.module.AlertAnalysisSessionContextResource().request(session_api.params)


def test_finished_but_empty_panels_are_unavailable(api):
    api.diagnosis.get_remote_analysis_results.return_value = {
        "incident_diagnosis": {"sub_panels": {"summary": {"status": "finished", "content": None}}}
    }
    result = api.module.AlertAnalysisResultsResource().request(api.params)
    assert result["analysis"]["status"] == "unavailable"
    assert result["analysis"]["sub_panels"]["summary"]["enabled"] is False
