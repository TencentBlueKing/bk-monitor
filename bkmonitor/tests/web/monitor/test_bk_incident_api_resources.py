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
