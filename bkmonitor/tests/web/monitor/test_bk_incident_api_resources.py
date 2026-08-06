import abc
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class _Field:
    def __init__(self, *args, **kwargs):
        pass


class _Serializer:
    pass


_serializers = SimpleNamespace(
    Serializer=_Serializer,
    CharField=_Field,
    IntegerField=_Field,
    ChoiceField=_Field,
    DictField=_Field,
    ListField=_Field,
    JSONField=_Field,
)


def test_processor_incident_callbacks_use_bkmonitor_api_routes():
    source = (PROJECT_ROOT / "api/bk_incident/default.py").read_text(encoding="utf-8")

    resource_start = source.index("class GetIncidentDetailResource")
    resource_end = source.index("class UpdateIncidentDetailResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert 'action = "/incident/incident/get_incident_detail/"' in resource_source
    assert 'method = "GET"' in resource_source

    resource_start = source.index("class UpdateIncidentDetailResource")
    resource_end = source.index("class GetIncidentSnapshotResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert 'action = "/incident/bkmonitor_api/update_incident_detail/"' in resource_source
    assert 'method = "POST"' in resource_source
    assert 'method = "PUT"' not in resource_source

    resource_start = source.index("class GetIncidentSnapshotResource")
    resource_end = source.index("class GetConfigResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert 'action = "/incident/bkmonitor_api/get_incident_snapshot/"' in resource_source
    assert 'method = "GET"' in resource_source


def test_incident_resources_route_remote_api_by_notice_source():
    source = (PROJECT_ROOT / "packages/monitor_web/incident/resources.py").read_text(encoding="utf-8")

    resource_start = source.index("class IncidentBaseResource")
    resource_end = source.index("class IncidentListResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert 'BKFARA_NOTICE_SOURCE = "bkfara"' in resource_source
    assert 'get("notice_source") == cls.BKFARA_NOTICE_SOURCE' in resource_source
    assert "return api.bk_incident if cls.is_bkfara_incident(incident) else api.bkdata" in resource_source
    assert "api.bk_incident.get_incident_diagnosis" in resource_source
    assert "api.bkdata.get_incident_analysis_results" in resource_source
    assert "def normalize_incident_status" in resource_source
    assert "status.lower() in IncidentStatus.get_enum_value_list()" in resource_source
    assert "incident_value = self.normalize_incident_status(incident_value)" in resource_source
    assert "incident_info[incident_key] = incident_value" in resource_source

    resource_start = source.index("class IncidentResultsResource")
    resource_end = source.index("class IncidentDateHistogramResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert "self.get_remote_analysis_results" in resource_source
    assert "api.bk_incident.get_incident_diagnosis" not in resource_source
    assert "api.bkdata.get_incident_analysis_results" not in resource_source
    assert '"extracted_info": raw_results["incident_diagnosis"].get("extracted_info", {})' in resource_source
    assert '"extracted_info": sub_panel.get("extracted_info", {})' in resource_source


def test_incident_edit_and_feedback_use_source_routed_api():
    source = (PROJECT_ROOT / "packages/monitor_web/incident/resources.py").read_text(encoding="utf-8")

    resource_start = source.index("class EditIncidentResource")
    resource_end = source.index("class IncidentAlertListResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert "self.get_remote_incident_api(incident)" in resource_source
    assert "incident_api.get_incident_detail" in resource_source
    assert "incident_api.update_incident_detail" in resource_source
    assert "api.bkdata.get_incident_detail" not in resource_source
    assert "api.bkdata.update_incident_detail" not in resource_source


def test_access_processor_marks_bkfara_incident_source():
    source = (PROJECT_ROOT / "alarm_backends/service/access/incident/processor.py").read_text(encoding="utf-8")

    resource_start = source.index("class AccessIncidentProcess")
    resource_end = source.index("def update_remote_incident_detail", resource_start)
    resource_source = source[resource_start:resource_end]

    assert 'BKFARA_NOTICE_SOURCE = "bkfara"' in resource_source
    assert 'sync_info.get("notice_source") == cls.BKFARA_NOTICE_SOURCE' in resource_source
    assert "def mark_incident_source" in resource_source
    assert 'incident_document.extra_info["notice_source"] = cls.BKFARA_NOTICE_SOURCE' in resource_source


def test_get_incident_diagnosis_resource_supports_optional_bk_biz_id():
    source = (PROJECT_ROOT / "api/bk_incident/default.py").read_text(encoding="utf-8")

    resource_start = source.index("class GetIncidentDiagnosisResource")
    resource_end = source.index("class UpdateIncidentDetailResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert 'bk_biz_id = serializers.IntegerField(label="业务ID", required=False)' in resource_source
    assert 'incident_id = serializers.IntegerField(label="故障ID", required=True)' in resource_source


def test_panel_detail_resource_proxies_bkfara_payload_without_scope_id():
    api_source = (PROJECT_ROOT / "api/bk_incident/default.py").read_text(encoding="utf-8")
    resource_start = api_source.index("class GetPanelDetailResource")
    resource_end = api_source.index("class GetIncidentDetailResource", resource_start)
    resource_source = api_source[resource_start:resource_end]

    assert 'action = "/incident/incident_analysis/get_panel_detail/"' in resource_source
    assert 'method = "POST"' in resource_source
    assert 'bk_biz_id = serializers.IntegerField(label="业务ID", required=False)' in resource_source
    assert 'incident_id = serializers.IntegerField(label="故障ID", required=True)' in resource_source
    assert "drawer_type = serializers.ChoiceField" in resource_source
    assert "detail_ref = serializers.DictField" in resource_source

    incident_source = (PROJECT_ROOT / "packages/monitor_web/incident/resources.py").read_text(encoding="utf-8")
    resource_start = incident_source.index("class IncidentPanelDetailResource")
    resource_end = incident_source.index("class IncidentDateHistogramResource", resource_start)
    resource_source = incident_source[resource_start:resource_end]

    assert "return api.bk_incident.get_panel_detail(**validated_request_data)" in resource_source
    assert "scope_id" not in resource_source

    view_source = (PROJECT_ROOT / "packages/monitor_web/incident/views.py").read_text(encoding="utf-8")
    assert 'resource.incident.incident_panel_detail, endpoint="panel_detail"' in view_source


def test_panel_detail_api_converts_bk_biz_id_and_proxy_preserves_payload_and_errors():
    api_source = (PROJECT_ROOT / "api/bk_incident/default.py").read_text(encoding="utf-8")
    base_source = api_source[
        api_source.index("class IncidentBaseResource") : api_source.index("class GetTemplateListResource")
    ]
    panel_source = api_source[
        api_source.index("class GetPanelDetailResource") : api_source.index("class GetIncidentDetailResource")
    ]

    class FakeAPIResource:
        def perform_request(self, validated_request_data):
            return validated_request_data

    namespace = {
        "abc": abc,
        "APIResource": FakeAPIResource,
        "serializers": _serializers,
        "settings": SimpleNamespace(BK_INCIDENT_APIGW_URL="", BK_COMPONENT_API_URL=""),
    }
    exec(base_source + panel_source, namespace)
    converted = namespace["GetPanelDetailResource"]().perform_request(
        {
            "bk_biz_id": 2,
            "incident_id": 9527,
            "drawer_type": "event",
            "detail_ref": {"panel": "events_analysis"},
        }
    )
    assert converted["scope_type"] == "bkcc"
    assert converted["scope_value"] == "2"
    assert "bk_biz_id" not in converted
    assert converted["detail_ref"] == {"panel": "events_analysis"}

    incident_source = (PROJECT_ROOT / "packages/monitor_web/incident/resources.py").read_text(encoding="utf-8")
    resource_source = incident_source[
        incident_source.index("class IncidentPanelDetailResource") : incident_source.index(
            "class IncidentDateHistogramResource"
        )
    ]

    class FakeRemote:
        def __init__(self):
            self.params = None

        def get_panel_detail(self, **kwargs):
            self.params = kwargs
            return {"drawer_type": "event", "payload": {"list": [{"raw": True}]}}

    remote = FakeRemote()
    namespace = {
        "IncidentBaseResource": object,
        "serializers": _serializers,
        "api": SimpleNamespace(bk_incident=remote),
    }
    exec(resource_source, namespace)
    request_data = {
        "bk_biz_id": 2,
        "incident_id": 9527,
        "drawer_type": "event",
        "detail_ref": {"panel": "events_analysis"},
    }
    result = namespace["IncidentPanelDetailResource"]().perform_request(request_data)
    assert remote.params == request_data
    assert result == {"drawer_type": "event", "payload": {"list": [{"raw": True}]}}

    def raise_remote_error(**_kwargs):
        raise RuntimeError("remote failed")

    remote.get_panel_detail = raise_remote_error
    try:
        namespace["IncidentPanelDetailResource"]().perform_request(request_data)
    except RuntimeError as error:
        assert str(error) == "remote failed"
    else:
        raise AssertionError("远端异常必须由薄代理原样抛出")


def test_incident_diagnosis_preserves_interaction_metadata():
    source = (PROJECT_ROOT / "packages/monitor_web/incident/resources.py").read_text(encoding="utf-8")
    resource_start = source.index("class IncidentDiagnosisResource")
    resource_end = source.index("class IncidentPanelDetailResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert 'content_item["interaction"] = drill_result["interaction"]' in resource_source
    assert 'display_content = raw_sub_panel.get("display")' in resource_source


def test_incident_list_returns_bkci_enabled_space_as_monitor_negative_biz_id():
    source = (PROJECT_ROOT / "packages/monitor_web/incident/resources.py").read_text(encoding="utf-8")

    resource_start = source.index("class IncidentListResource")
    resource_end = source.index("class ExportIncidentResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert "def get_enabled_space_bk_biz_id" in resource_source
    assert 'scope_identity.get("space")' in resource_source
    assert "return -int(space_id)" in resource_source
    assert 'result["enabled_spaces"].append(self.get_enabled_space_bk_biz_id(item))' in resource_source


def test_bk_incident_api_keeps_standard_scope_ids_when_converting_lists():
    source = (PROJECT_ROOT / "api/bk_incident/default.py").read_text(encoding="utf-8")

    resource_start = source.index("class IncidentBaseResource")
    resource_end = source.index("class GetTemplateListResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert "def is_standard_scope_id" in resource_source
    assert "if self.is_standard_scope_id(bk_biz_id)" in resource_source
