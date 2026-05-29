from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from bkmonitor.documents.incident import IncidentDocument


class _FakeHit:
    def __init__(self, payload):
        self.payload = payload

    def to_dict(self):
        return dict(self.payload)


class _FakeSearch:
    def __init__(self, payload):
        self.payload = payload

    def filter(self, *args, **kwargs):
        return self

    def execute(self):
        return SimpleNamespace(hits=[_FakeHit(self.payload)])


class TestIncidentDocument(SimpleTestCase):
    def test_get_routes_bkfara_document_detail_to_bk_incident(self):
        payload = {
            "id": "17100000001001",
            "incident_id": 1001,
            "incident_name": "真实故障",
            "extra_info": {"notice_source": "bkfara"},
        }
        with patch.object(IncidentDocument, "search", return_value=_FakeSearch(payload)):
            with patch("bkmonitor.documents.incident.api") as mock_api:
                mock_api.bk_incident.get_incident_detail = Mock(return_value={"incident_name": "远端真实故障"})

                incident = IncidentDocument.get("17100000001001")

        mock_api.bk_incident.get_incident_detail.assert_called_once_with(incident_id=1001)
        mock_api.bkdata.get_incident_detail.assert_not_called()
        self.assertEqual(incident.incident_name, "远端真实故障")

    def test_get_keeps_local_real_name_when_remote_returns_anonymous_name(self):
        payload = {
            "id": "17100000001001",
            "incident_id": 1001,
            "incident_name": "本地真实故障",
            "extra_info": {"notice_source": "bkfara"},
        }
        with patch.object(IncidentDocument, "search", return_value=_FakeSearch(payload)):
            with patch("bkmonitor.documents.incident.api") as mock_api:
                mock_api.bk_incident.get_incident_detail = Mock(
                    return_value={"incident_name": "new_incident_1710000000"}
                )

                incident = IncidentDocument.get("17100000001001")

        self.assertEqual(incident.incident_name, "本地真实故障")
