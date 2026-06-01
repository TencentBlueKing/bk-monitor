from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_update_incident_detail_uses_published_apigw_method():
    source = (PROJECT_ROOT / "api/bk_incident/default.py").read_text(encoding="utf-8")
    resource_start = source.index("class UpdateIncidentDetailResource")
    resource_end = source.index("class GetIncidentSnapshotResource", resource_start)
    resource_source = source[resource_start:resource_end]

    assert 'method = "POST"' in resource_source
    assert 'method = "PUT"' not in resource_source
