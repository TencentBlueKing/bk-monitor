from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from alarm_backends.service.access.incident.processor import AccessIncidentProcess
from bkmonitor.aiops.incident.notice import IncidentNoticeHelper
from bkmonitor.aiops.incident.operation import IncidentOperationManager
from bkmonitor.documents.incident import IncidentDocument
from constants.incident import (
    ASSIGNEE_SOURCE_KEY,
    BKFARA_NOTICE_SOURCE,
    CMDB_HOST_ASSIGNEE_SOURCE,
    HOST_OWNERSHIP_EVENT_ID_KEY,
    HOST_OWNERSHIP_REVISION_KEY,
    IncidentOperationType,
    NOTICE_SOURCE_KEY,
)
from tests.web.monitor.test_access_incident_processor import (
    TestAccessIncidentProcessor as AccessFixtures,
    _FakeIncidentDocument,
    _FakeSnapshotDocument,
)


class TestHostOwnershipDocument(SimpleTestCase):
    def test_snapshot_refresh_preserves_explicit_bkfara_host_owners(self):
        incident = IncidentDocument(
            assignees=["host-owner"],
            extra_info={NOTICE_SOURCE_KEY: BKFARA_NOTICE_SOURCE, ASSIGNEE_SOURCE_KEY: CMDB_HOST_ASSIGNEE_SOURCE},
        )
        snapshot = SimpleNamespace(
            alert_entity_mapping={"a": SimpleNamespace(id="a", entity=SimpleNamespace(is_root=True))}
        )
        incident.generate_assignees(snapshot, alert_docs={"a": SimpleNamespace(assignee=["alert-owner"])})
        self.assertEqual(list(incident.assignees), ["host-owner"])
        incident.generate_assignees(SimpleNamespace(alert_entity_mapping={}))
        self.assertEqual(list(incident.assignees), ["host-owner"])

    def test_unmarked_or_legacy_sources_keep_original_alert_owner_rules(self):
        for extra_info in (
            {},
            {NOTICE_SOURCE_KEY: BKFARA_NOTICE_SOURCE},
            {NOTICE_SOURCE_KEY: "bkdata", ASSIGNEE_SOURCE_KEY: CMDB_HOST_ASSIGNEE_SOURCE},
        ):
            with self.subTest(extra_info=extra_info):
                incident = IncidentDocument(assignees=["host-owner"], extra_info=extra_info)
                snapshot = SimpleNamespace(
                    alert_entity_mapping={"a": SimpleNamespace(id="a", entity=SimpleNamespace(is_root=True))}
                )
                incident.generate_assignees(snapshot, alert_docs={"a": SimpleNamespace(assignee=["alert-owner"])})
                self.assertEqual(list(incident.assignees), ["alert-owner"])

    def test_marker_requires_nonempty_valid_incoming_owner_list(self):
        for owners in ([], None, "host-owner", [None], [" "]):
            with self.subTest(owners=owners):
                document = SimpleNamespace(assignees=["old-owner"], extra_info={})
                sync = {
                    NOTICE_SOURCE_KEY: BKFARA_NOTICE_SOURCE,
                    "incident_info": {
                        "assignees": owners,
                        "extra_info": {ASSIGNEE_SOURCE_KEY: CMDB_HOST_ASSIGNEE_SOURCE},
                    },
                }
                self.assertFalse(AccessIncidentProcess.apply_bkfara_host_ownership(sync, document))
                self.assertEqual(document.assignees, ["old-owner"])

    def test_non_bkfara_message_cannot_claim_host_ownership_with_nested_source_marker(self):
        incident = IncidentDocument(
            assignees=["injected-owner"],
            extra_info={NOTICE_SOURCE_KEY: BKFARA_NOTICE_SOURCE, ASSIGNEE_SOURCE_KEY: CMDB_HOST_ASSIGNEE_SOURCE},
        )
        self.assertFalse(AccessIncidentProcess.apply_bkfara_host_ownership({NOTICE_SOURCE_KEY: "bkdata"}, incident))
        snapshot = SimpleNamespace(
            alert_entity_mapping={"a": SimpleNamespace(id="a", entity=SimpleNamespace(is_root=True))}
        )
        incident.generate_assignees(snapshot, alert_docs={"a": SimpleNamespace(assignee=["alert-owner"])})
        self.assertEqual(list(incident.assignees), ["alert-owner"])


class TestHostOwnershipAccess(SimpleTestCase):
    setUp = AccessFixtures.setUp
    _base_sync_info = AccessFixtures._base_sync_info

    def _host_sync_info(self):
        sync = self._base_sync_info()
        sync[NOTICE_SOURCE_KEY] = BKFARA_NOTICE_SOURCE
        sync["incident_info"].update(
            {
                "assignees": ["host-owner"],
                "incident_reason": "disk full\n主机负责人：192.0.2.1（host-owner）",
                "extra_info": {ASSIGNEE_SOURCE_KEY: CMDB_HOST_ASSIGNEE_SOURCE},
                "send_notice": True,
            }
        )
        return sync

    def test_duplicate_or_older_host_event_cannot_override_new_owner_or_resend(self):
        incident = _FakeIncidentDocument(
            incident_id=1001,
            assignees=["new-owner"],
            extra_info={
                NOTICE_SOURCE_KEY: BKFARA_NOTICE_SOURCE,
                ASSIGNEE_SOURCE_KEY: CMDB_HOST_ASSIGNEE_SOURCE,
                HOST_OWNERSHIP_EVENT_ID_KEY: "event-2",
                HOST_OWNERSHIP_REVISION_KEY: 2,
            },
        )
        for event_id, revision in (("event-2", 2), ("event-1", 1)):
            sync = self._host_sync_info()
            sync.update(
                event_id=event_id,
                aggregate_revision=revision,
                update_attributes={"assignees": {"from": [], "to": ["host-owner"]}},
            )
            with (
                self.subTest(event_id=event_id),
                patch("alarm_backends.service.access.incident.processor.IncidentDocument.get", return_value=incident),
                patch(
                    "alarm_backends.service.access.incident.processor.IncidentOperationManager.record_update_incident"
                ) as record,
                patch(
                    "alarm_backends.service.access.incident.processor.IncidentSnapshotDocument.bulk_create"
                ) as snapshot,
            ):
                self.processor.update_incident(sync)
                self.assertEqual(incident.assignees, ["new-owner"])
                record.assert_not_called()
                snapshot.assert_not_called()

    @patch("alarm_backends.service.access.incident.processor.api")
    @patch("alarm_backends.service.access.incident.processor.IncidentSnapshot")
    @patch("alarm_backends.service.access.incident.processor.IncidentSnapshotDocument", _FakeSnapshotDocument)
    @patch("alarm_backends.service.access.incident.processor.IncidentDocument", _FakeIncidentDocument)
    @patch("alarm_backends.service.access.incident.processor.IncidentOperationManager.record_create_incident")
    def test_host_create_preserves_owner_through_writeback_and_notice(self, record, snapshot, api):
        snapshot.side_effect = lambda payload: SimpleNamespace(alert_entity_mapping={})
        with patch.object(_FakeIncidentDocument, "generate_assignees", IncidentDocument.generate_assignees):
            self.processor.create_incident(self._host_sync_info())
        self.assertEqual(api.bk_incident.update_incident_detail.call_args.kwargs["assignees"], ["host-owner"])
        self.assertTrue(record.call_args.kwargs["should_send_notice"])
        self.assertEqual(record.call_args.kwargs["assignees"], ["host-owner"])
        self.assertIn("主机负责人", record.call_args.kwargs["incident_document"].incident_reason)
        api.bkdata.update_incident_detail.assert_not_called()

    @patch("alarm_backends.service.access.incident.processor.api")
    @patch("alarm_backends.service.access.incident.processor.IncidentSnapshot")
    @patch("alarm_backends.service.access.incident.processor.IncidentSnapshotDocument", _FakeSnapshotDocument)
    @patch("alarm_backends.service.access.incident.processor.IncidentOperationManager.record_update_incident")
    def test_host_update_replaces_existing_es_owners_and_notifies_even_from_unassigned(self, record, snapshot, api):
        snapshot.side_effect = lambda payload: SimpleNamespace(alert_entity_mapping={})
        incident = _FakeIncidentDocument(**self._base_sync_info()["incident_info"], incident_id=1001)
        sync = self._host_sync_info()
        sync["update_attributes"] = {"assignees": {"from": [], "to": ["host-owner"]}}
        with (
            patch("alarm_backends.service.access.incident.processor.IncidentDocument.get", return_value=incident),
            patch("alarm_backends.service.access.incident.processor.IncidentDocument.bulk_create"),
            patch.object(_FakeIncidentDocument, "generate_assignees", IncidentDocument.generate_assignees),
        ):
            self.processor.update_incident(sync)
        self.assertEqual(incident.assignees, ["host-owner"])
        self.assertEqual(api.bk_incident.update_incident_detail.call_args.kwargs["assignees"], ["host-owner"])
        self.assertTrue(record.call_args.kwargs["notify_assignee_change"])
        self.assertTrue(record.call_args.kwargs["should_send_notice"])
        self.assertIn("主机负责人", incident.incident_reason)


class TestHostOwnershipNotice(SimpleTestCase):
    def test_enabled_personal_channel_includes_host_owner_with_explicit_receivers(self):
        incident = SimpleNamespace(
            assignees=["host-owner"],
            extra_info={NOTICE_SOURCE_KEY: BKFARA_NOTICE_SOURCE, ASSIGNEE_SOURCE_KEY: CMDB_HOST_ASSIGNEE_SOURCE},
        )
        targets = IncidentNoticeHelper._get_configured_notice_targets(
            incident,
            {
                "module": {
                    "im": {"is_select": True, "receivers": ["configured-user"]},
                    "email": {"is_select": False, "users": ["disabled-user"]},
                    "group_robot": {"is_select": True, "chat_ids": ["chat-1"]},
                }
            },
        )
        self.assertEqual(targets[0]["receivers"], ["configured-user", "host-owner"])
        self.assertEqual(targets[1]["receivers"], ["chat-1"])
        self.assertEqual(len(targets), 2)

    def test_unmarked_incident_does_not_add_new_recipients(self):
        incident = SimpleNamespace(assignees=["host-owner"], extra_info={NOTICE_SOURCE_KEY: BKFARA_NOTICE_SOURCE})
        targets = IncidentNoticeHelper._get_configured_notice_targets(
            incident, {"module": {"im": {"is_select": True, "users": ["configured-user"]}}}
        )
        self.assertEqual(targets[0]["receivers"], ["configured-user"])

    @override_settings(ENABLE_BK_INCIDENT_NOTICE=True)
    def test_only_explicit_host_owner_updates_can_send_update_notices(self):
        for marker, key, enabled, expected in (
            (True, "assignees", True, 1),
            (False, "assignees", True, 0),
            (True, "level", True, 0),
            (True, "assignees", False, 0),
        ):
            with (
                self.subTest(marker=marker, key=key, enabled=enabled),
                patch("bkmonitor.aiops.incident.operation.IncidentOperationDocument.bulk_create"),
                patch.object(IncidentOperationManager, "_send_incident_notice") as send,
            ):
                IncidentOperationManager.record_update_incident(
                    1001,
                    1710000000,
                    key,
                    "ERROR" if key == "level" else [],
                    "WARN" if key == "level" else ["host-owner"],
                    should_send_notice=enabled,
                    notify_assignee_change=marker,
                    incident_document=SimpleNamespace(assignees=["host-owner"]),
                )
                self.assertEqual(send.call_count, expected)
                if expected:
                    self.assertEqual(send.call_args.args[1], IncidentOperationType.UPDATE)
