"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

from monitor_web.incident import resources as incident_resources


def test_incident_alert_view_uses_incident_biz_when_alert_event_biz_is_missing(monkeypatch):
    incident = SimpleNamespace(
        bk_biz_id=42,
        extra_info=None,
        feedback=SimpleNamespace(incident_root=None),
        snapshot=SimpleNamespace(content=SimpleNamespace(to_dict=lambda: {})),
    )
    alert = {
        "id": "178211874094129530",
        "category": "custom",
        "dimensions": [],
        "event": {"bk_biz_id": None},
    }
    captured = {}

    monkeypatch.setattr(incident_resources.IncidentDocument, "get", lambda _: incident)
    monkeypatch.setattr(
        incident_resources,
        "IncidentSnapshot",
        lambda _: SimpleNamespace(alert_entity_mapping={}),
    )
    monkeypatch.setattr(
        incident_resources.IncidentAlertViewResource,
        "get_snapshot_alerts",
        classmethod(lambda cls, snapshot, **kwargs: [alert]),
    )
    monkeypatch.setattr(
        incident_resources.resource.commons,
        "get_label",
        lambda: [{"children": [{"id": "custom"}]}],
    )

    def capture_graph_panel(alert_doc, **kwargs):
        captured["bk_biz_id"] = alert_doc.event.bk_biz_id
        return {}

    monkeypatch.setattr(incident_resources.AIOPSManager, "get_graph_panel", capture_graph_panel)

    incident_resources.IncidentAlertViewResource().perform_request({"id": 1})

    assert captured["bk_biz_id"] == 42
