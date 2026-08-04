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

    def generate_handlers(self, snapshot, alert_docs=None):
        return None

    def generate_assignees(self, snapshot, alert_docs=None):
        return None

    @classmethod
    def bulk_create(cls, docs, action=None):
        return docs


class _AttrDictLike:
    """模拟 Elasticsearch DSL 的 AttrDict：支持下标赋值，不提供 update。"""

    def __init__(self):
        self.data = {}

    def __bool__(self):
        return bool(self.data)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value


class TestAccessIncidentProcessor(SimpleTestCase):
    def setUp(self):
        self.processor = object.__new__(AccessIncidentProcess)
        self.processor.actions = []
        self.processor.check_incident_actions = lambda sync_info: False
        self.processor.update_alert_incident_relations = lambda *args, **kwargs: {}
        self.processor.generate_incident_labels = lambda *args, **kwargs: None
        self.processor.generate_alert_operations = lambda *args, **kwargs: None

    @patch("alarm_backends.service.access.incident.processor.AlertDocument.mget")
    def test_get_snapshot_alert_documents_batches_unique_alert_ids(self, mock_mget):
        snapshot = SimpleNamespace(
            content=SimpleNamespace(
                incident_alerts=[
                    {"id": "1"},
                    {"id": "2"},
                    {"id": "1"},
                ]
            )
        )
        alert_documents = [SimpleNamespace(id="1"), SimpleNamespace(id="2")]
        mock_mget.return_value = alert_documents

        result = self.processor.get_snapshot_alert_documents(snapshot)

        mock_mget.assert_called_once_with(["1", "2"])
        self.assertEqual(result, {"1": alert_documents[0], "2": alert_documents[1]})

    @patch("alarm_backends.service.access.incident.processor.logger.warning")
    @patch("alarm_backends.service.access.incident.processor.time.monotonic", return_value=11)
    def test_log_slow_stage_contains_incident_context(self, mock_monotonic, mock_warning):
        sync_info = {
            "incident_id": 1001,
            "sync_type": "update",
            "scope": {"alerts": ["1"]},
        }

        self.processor.log_slow_stage(sync_info, stage="alert_document_lookup", started_at=0)

        mock_warning.assert_called_once()
        log_message = mock_warning.call_args.args[0]
        self.assertIn("incident_id=%s", log_message)
        self.assertIn("stage=%s", log_message)
        self.assertEqual(mock_warning.call_args.args[1:5], (1001, "update", 1, "alert_document_lookup"))

    def test_mark_bkfara_source_persists_process_info_on_attr_dict(self):
        incident_document = SimpleNamespace(extra_info=_AttrDictLike())

        self.processor.mark_incident_source(
            {"notice_source": "bkfara"},
            incident_document,
            {"scope_id": "bkcc_132", "task_id": 9876},
        )

        self.assertEqual(incident_document.extra_info["notice_source"], "bkfara")
        self.assertEqual(incident_document.extra_info["scope_id"], "bkcc_132")
        self.assertEqual(incident_document.extra_info["task_id"], 9876)

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
    @patch("alarm_backends.service.access.incident.processor.IncidentDocument", _FakeIncidentDocument)
    @patch("alarm_backends.service.access.incident.processor.IncidentOperationManager.record_create_incident")
    def test_create_incident_reads_timeout_from_api_resources(self, mock_record_create, mock_snapshot_model, mock_api):
        mock_snapshot_model.side_effect = lambda payload: SimpleNamespace(alert_entity_mapping={})
        get_incident_snapshot = Mock(
            TIMEOUT=300,
            return_value={"incident_alerts": [{"id": 177}], "rca_summary": {"bk_biz_ids": [132]}},
        )
        update_incident_detail = Mock(TIMEOUT=300)
        mock_api.bkdata = SimpleNamespace(
            get_incident_snapshot=get_incident_snapshot,
            update_incident_detail=update_incident_detail,
        )
        sync_info = self._base_sync_info()
        sync_info["fpp_snapshot_id"] = "snapshot-1"

        self.processor.create_incident(sync_info)

        get_incident_snapshot.assert_called_once_with(snapshot_id="snapshot-1")
        update_incident_detail.assert_called_once()
        mock_record_create.assert_called_once()

    @patch("alarm_backends.service.access.incident.processor.time.time", return_value=1710000099)
    @patch("alarm_backends.service.access.incident.processor.api")
    @patch("alarm_backends.service.access.incident.processor.IncidentSnapshot")
    @patch("alarm_backends.service.access.incident.processor.IncidentSnapshotDocument", _FakeSnapshotDocument)
    @patch("alarm_backends.service.access.incident.processor.IncidentDocument", _FakeIncidentDocument)
    @patch("alarm_backends.service.access.incident.processor.IncidentOperationManager.record_create_incident")
    def test_create_incident_routes_bkfara_notice_to_bk_incident(
        self, mock_record_create, mock_snapshot_model, mock_api, mock_time
    ):
        mock_snapshot_model.side_effect = lambda payload: SimpleNamespace(alert_entity_mapping={})
        mock_api.bkdata.update_incident_detail = Mock()
        mock_api.bk_incident.update_incident_detail = Mock()
        sync_info = self._base_sync_info()
        sync_info["notice_source"] = "bkfara"
        sync_info["incident_info"]["scope_id"] = "bkcc_132"
        sync_info["incident_info"]["task_id"] = 9876

        self.processor.create_incident(sync_info)

        mock_api.bk_incident.update_incident_detail.assert_called_once()
        self.assertEqual(mock_api.bk_incident.update_incident_detail.call_args.kwargs["assignees"], [])
        self.assertEqual(mock_api.bk_incident.update_incident_detail.call_args.kwargs["handlers"], [])
        self.assertEqual(mock_api.bk_incident.update_incident_detail.call_args.kwargs["labels"], [])
        self.assertEqual(
            mock_api.bk_incident.update_incident_detail.call_args.kwargs["bkmonitor_received_time"], 1710000099
        )
        self.assertNotIn("incident_name", mock_api.bk_incident.update_incident_detail.call_args.kwargs)
        self.assertNotIn("incident_reason", mock_api.bk_incident.update_incident_detail.call_args.kwargs)
        self.assertNotIn("level", mock_api.bk_incident.update_incident_detail.call_args.kwargs)
        self.assertNotIn("status", mock_api.bk_incident.update_incident_detail.call_args.kwargs)
        self.assertNotIn("bk_biz_id", mock_api.bk_incident.update_incident_detail.call_args.kwargs)
        mock_api.bkdata.update_incident_detail.assert_not_called()
        self.assertEqual(mock_record_create.call_args.kwargs["incident_document"].extra_info["notice_source"], "bkfara")
        self.assertEqual(mock_record_create.call_args.kwargs["incident_document"].extra_info["scope_id"], "bkcc_132")
        self.assertEqual(mock_record_create.call_args.kwargs["incident_document"].extra_info["task_id"], 9876)
        self.assertFalse(mock_record_create.call_args.kwargs["should_send_notice"])

    @patch("alarm_backends.service.access.incident.processor.api")
    @patch("alarm_backends.service.access.incident.processor.IncidentSnapshot")
    @patch("alarm_backends.service.access.incident.processor.IncidentSnapshotDocument", _FakeSnapshotDocument)
    @patch("alarm_backends.service.access.incident.processor.IncidentDocument", _FakeIncidentDocument)
    @patch("alarm_backends.service.access.incident.processor.IncidentOperationManager.record_create_incident")
    def test_create_incident_without_notice_source_keeps_bkdata_route(
        self, mock_record_create, mock_snapshot_model, mock_api
    ):
        mock_snapshot_model.side_effect = lambda payload: SimpleNamespace(alert_entity_mapping={})
        mock_api.bkdata.update_incident_detail = Mock()
        mock_api.bk_incident.update_incident_detail = Mock()

        self.processor.create_incident(self._base_sync_info())

        mock_api.bkdata.update_incident_detail.assert_called_once()
        mock_api.bk_incident.update_incident_detail.assert_not_called()
        self.assertFalse(mock_record_create.call_args.kwargs["should_send_notice"])

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

    @patch("alarm_backends.service.access.incident.processor.time.time", return_value=1710000099)
    @patch("alarm_backends.service.access.incident.processor.api")
    @patch("alarm_backends.service.access.incident.processor.IncidentSnapshot")
    @patch("alarm_backends.service.access.incident.processor.IncidentSnapshotDocument", _FakeSnapshotDocument)
    @patch("alarm_backends.service.access.incident.processor.IncidentOperationManager.record_update_incident")
    def test_update_bkfara_status_syncs_new_status_without_received_time(
        self, mock_record_update, mock_snapshot_model, mock_api, mock_time
    ):
        mock_snapshot_model.side_effect = lambda payload: SimpleNamespace(alert_entity_mapping={})
        mock_api.bk_incident.update_incident_detail = Mock()
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
        sync_info["notice_source"] = "bkfara"
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

        status_sync_call = mock_api.bk_incident.update_incident_detail.call_args_list[-1]
        self.assertEqual(status_sync_call.kwargs["assignees"], [])
        self.assertEqual(status_sync_call.kwargs["handlers"], [])
        self.assertEqual(status_sync_call.kwargs["labels"], [])
        self.assertEqual(status_sync_call.kwargs["end_time"], 1710000060)
        self.assertNotIn("status", status_sync_call.kwargs)
        self.assertNotIn("bkmonitor_received_time", status_sync_call.kwargs)
        self.assertEqual(incident_document.extra_info["notice_source"], "bkfara")

    @patch("alarm_backends.service.access.incident.processor.api")
    @patch("alarm_backends.service.access.incident.processor.IncidentSnapshot")
    @patch("alarm_backends.service.access.incident.processor.IncidentSnapshotDocument", _FakeSnapshotDocument)
    @patch("alarm_backends.service.access.incident.processor.IncidentOperationManager.record_update_incident")
    def test_update_bkfara_merge_persists_merge_info_for_existing_incident(
        self, mock_record_update, mock_snapshot_model, mock_api
    ):
        mock_snapshot_model.side_effect = lambda payload: SimpleNamespace(alert_entity_mapping={})
        mock_api.bk_incident.update_incident_detail = Mock()
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
        sync_info["notice_source"] = "bkfara"
        sync_info["update_attributes"] = {"status": {"from": "ABNORMAL", "to": "MERGED"}}
        sync_info["incident_info"]["status"] = "MERGED"
        sync_info["incident_info"]["merge_info"] = {
            "origin_incident_id": 1001,
            "origin_incident_name": "故障A",
            "origin_created_at": 1710000000,
            "target_incident_id": 1002,
            "target_incident_name": "故障B",
            "target_created_at": 1710000100,
        }

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

        self.assertEqual(incident_document.status, "merged")
        self.assertEqual(incident_document.extra_info["notice_source"], "bkfara")
        self.assertEqual(incident_document.extra_info["merge_info"]["origin_incident_doc_id"], "17100000001001")
        self.assertEqual(incident_document.extra_info["merge_info"]["target_incident_doc_id"], "17100001001002")
        self.assertEqual(mock_record_update.call_args.kwargs["from_value"], "abnormal")
        self.assertEqual(mock_record_update.call_args.kwargs["to_value"], "merged")
