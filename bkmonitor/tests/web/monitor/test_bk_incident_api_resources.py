from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_processor_incident_callbacks_use_bkmonitor_api_routes():
    source = (PROJECT_ROOT / "api/bk_incident/default.py").read_text(encoding="utf-8")

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


def test_incident_page_uses_bk_incident_diagnosis_resource():
    source = (PROJECT_ROOT / "packages/monitor_web/incident/resources.py").read_text(encoding="utf-8")

    resource_start = source.index("class IncidentResultsResource")
    resource_end = source.index("class IncidentDateHistogramResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert "api.bkdata.get_incident_analysis_results" not in resource_source
    assert resource_source.count("api.bk_incident.get_incident_diagnosis") == 2
    assert 'bk_biz_id=validated_request_data["bk_biz_id"]' in resource_source
    assert "bk_biz_id=bk_biz_ids[0]" in resource_source


def test_get_incident_diagnosis_resource_supports_optional_bk_biz_id():
    source = (PROJECT_ROOT / "api/bk_incident/default.py").read_text(encoding="utf-8")

    resource_start = source.index("class GetIncidentDiagnosisResource")
    resource_end = source.index("class UpdateIncidentDetailResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert 'bk_biz_id = serializers.IntegerField(label="业务ID", required=False)' in resource_source
    assert 'incident_id = serializers.IntegerField(label="故障ID", required=True)' in resource_source
