import copy
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from alarm_backends.service.access.incident.processor import AccessIncidentProcess


class _FakeSnapshotContent:
    def __init__(self, data):
        self._data = data
        self.incident_alerts = data.get("incident_alerts", [])

    def to_dict(self):
        return copy.deepcopy(self._data)


class _FakeSnapshotDocument:
    def __init__(self, **kwargs):
        self.incident_id = kwargs["incident_id"]
        self.status = kwargs["status"]
        self.alerts = kwargs["alerts"]
        self.events = kwargs["events"]
        self.content = _FakeSnapshotContent(kwargs["content"])

    @classmethod
    def bulk_create(cls, docs, action=None):
        return docs


class _FakeIncidentDocument:
    def __init__(self, **kwargs):
        self.incident_id = kwargs.get("incident_id")
        self.incident_name = kwargs.get("incident_name")
        self.incident_reason = kwargs.get("incident_reason")
        self.status = kwargs.get("status")
        self.level = kwargs.get("level")
        self.bk_biz_id = kwargs.get("bk_biz_id")
        self.assignees = kwargs.get("assignees", [])
        self.handlers = kwargs.get("handlers", [])
        self.labels = kwargs.get("labels", [])
        self.extra_info = kwargs.get("extra_info") or {}
        self.snapshot = kwargs.get("snapshot")
        self.id = kwargs.get("id", f"{kwargs.get('create_time', 0)}{self.incident_id}")
        self.end_time = kwargs.get("end_time")

    def generate_handlers(self, snapshot):
        return None

    def generate_assignees(self, snapshot):
        return None

    @classmethod
    def bulk_create(cls, docs, action=None):
        return docs


class TestAccessIncidentProcessor(SimpleTestCase):
    def setUp(self):
        self.processor = object.__new__(AccessIncidentProcess)
        self.processor.actions = []
        self.processor.check_incident_actions = lambda sync_info: False
        self.processor.update_alert_incident_relations = lambda *args, **kwargs: {}
        self.processor.generate_incident_labels = lambda *args, **kwargs: None
        self.processor.generate_alert_operations = lambda *args, **kwargs: None

    def _base_sync_info(self):
        return {
            "incident_id": 1001,
            "incident_stage": "stage_rca",
            "incident_actions": [],
            "rca_time": 1710000000,
            "fpp_snapshot_id": "fpp:None",
            "scope": {"bk_biz_ids": [132], "alerts": [177], "events": []},
            "incident_info": {
                "incident_name": "故障A",
                "incident_reason": "root cause",
                "status": "abnormal",
                "level": "ERROR",
                "labels": [],
                "assignees": [],
                "handlers": [],
                "create_time": 1710000000,
                "update_time": 1710000060,
                "begin_time": 1710000000,
                "bk_biz_id": 132,
                "send_notice": False,
                "notice_config": {
                    "operation": "fault_occurred",
                    "module": {"im": {"is_select": True, "groups": ["incident-owner"], "level": "ERROR"}},
                },
            },
        }

    @patch("alarm_backends.service.access.incident.processor.api")
    @patch("alarm_backends.service.access.incident.processor.IncidentSnapshot")
    @patch("alarm_backends.service.access.incident.processor.IncidentSnapshotDocument", _FakeSnapshotDocument)
    @patch("alarm_backends.service.access.incident.processor.IncidentDocument", _FakeIncidentDocument)
    @patch("alarm_backends.service.access.incident.processor.IncidentOperationManager.record_create_incident")
    def test_create_incident_passes_send_notice_flag(self, mock_record_create, mock_snapshot_model, mock_api):
        mock_snapshot_model.side_effect = lambda payload: SimpleNamespace(alert_entity_mapping={})
        mock_api.bkdata.update_incident_detail = Mock()

        self.processor.create_incident(self._base_sync_info())

        self.assertFalse(mock_record_create.call_args.kwargs["should_send_notice"])
        self.assertIn("notice_config", mock_record_create.call_args.kwargs)

    @patch("alarm_backends.service.access.incident.processor.api")
    @patch("alarm_backends.service.access.incident.processor.IncidentSnapshot")
    @patch("alarm_backends.service.access.incident.processor.IncidentSnapshotDocument", _FakeSnapshotDocument)
    @patch("alarm_backends.service.access.incident.processor.IncidentOperationManager.record_update_incident")
    def test_update_incident_passes_send_notice_flag(self, mock_record_update, mock_snapshot_model, mock_api):
        mock_snapshot_model.side_effect = lambda payload: SimpleNamespace(alert_entity_mapping={})
        mock_api.bkdata.update_incident_detail = Mock()
        incident_document = _FakeIncidentDocument(
            incident_id=1001,
            incident_name="故障A",
            incident_reason="root cause",
            status="abnormal",
            level="ERROR",
            labels=[],
            assignees=[],
            handlers=[],
            bk_biz_id=132,
            create_time=1710000000,
            snapshot=None,
        )
        sync_info = self._base_sync_info()
        sync_info["update_attributes"] = {"status": {"from": "abnormal", "to": "recovered"}}
        sync_info["incident_info"]["status"] = "recovered"

        with (
            patch(
                "alarm_backends.service.access.incident.processor.IncidentDocument.get",
                return_value=incident_document,
            ),
            patch(
                "alarm_backends.service.access.incident.processor.IncidentDocument.bulk_create",
                return_value=None,
            ),
        ):
            self.processor.update_incident(sync_info)

        self.assertFalse(mock_record_update.call_args.kwargs["should_send_notice"])
        self.assertIn("notice_config", mock_record_update.call_args.kwargs)
