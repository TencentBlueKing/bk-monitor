from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from alarm_backends.service.access.incident.processor import AccessIncidentProcess
from bkmonitor.aiops.incident.notice import IncidentNoticeHelper
from bkmonitor.aiops.incident.operation import IncidentOperationManager
from bkmonitor.documents.incident import IncidentDocument
from constants.action import NoticeWay
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
            status="recovering",
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
                update_attributes={
                    "assignees": {"from": [], "to": ["host-owner"]},
                    "status": {"from": "recovering", "to": "abnormal"},
                },
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
                self.assertEqual(incident.status, "recovering")
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
            sync = self._host_sync_info()
            sync.update(event_id="create-event", bk_tenant_id="tenant-a")
            sync["incident_info"]["scope_id"] = "bkcc_132"
            expected_key = self.processor.notice_event_key(sync)
            self.processor.create_incident(sync)
        self.assertEqual(record.call_args.kwargs["notice_event_key"], expected_key)
        self.assertEqual(sync["incident_info"]["scope_id"], "bkcc_132")
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


class TestHostOwnershipReviewRegressions(TestHostOwnershipAccess):
    def _run_update(self, sync, incident, record=None):
        from unittest.mock import Mock

        record = record or Mock()
        with (
            patch("alarm_backends.service.access.incident.processor.api") as api,
            patch(
                "alarm_backends.service.access.incident.processor.IncidentSnapshot",
                side_effect=lambda payload: SimpleNamespace(alert_entity_mapping={}),
            ),
            patch("alarm_backends.service.access.incident.processor.IncidentSnapshotDocument", _FakeSnapshotDocument),
            patch("alarm_backends.service.access.incident.processor.IncidentDocument.get", return_value=incident),
            patch("alarm_backends.service.access.incident.processor.IncidentDocument.bulk_create"),
            patch(
                "alarm_backends.service.access.incident.processor.IncidentOperationManager.record_update_incident",
                record,
            ),
            patch.object(_FakeIncidentDocument, "generate_assignees", IncidentDocument.generate_assignees),
        ):
            self.processor.update_incident(sync)
        return record, api

    def _existing(self):
        incident = _FakeIncidentDocument(**self._base_sync_info()["incident_info"], incident_id=1001)
        incident.assignees = ["saved-owner"]
        incident.extra_info = {NOTICE_SOURCE_KEY: BKFARA_NOTICE_SOURCE, ASSIGNEE_SOURCE_KEY: CMDB_HOST_ASSIGNEE_SOURCE}
        return incident

    def test_partial_status_update_preserves_owner_and_remote_writeback(self):
        sync = self._host_sync_info()
        sync["incident_info"].pop("extra_info")
        sync["update_attributes"] = {
            "status": {"from": "abnormal", "to": "recovering"},
            "assignees": {"from": ["saved-owner"], "to": []},
        }
        incident = self._existing()
        _, api = self._run_update(sync, incident)
        self.assertEqual(incident.assignees, ["saved-owner"])
        self.assertEqual(incident.status, "recovering")
        self.assertEqual(incident.extra_info[ASSIGNEE_SOURCE_KEY], CMDB_HOST_ASSIGNEE_SOURCE)
        self.assertEqual(api.bk_incident.update_incident_detail.call_args.kwargs["assignees"], ["saved-owner"])

    def test_invalid_claim_preserves_previous_owner(self):
        for owners in (["alice,bob"], ["alice;bob"], ["<a>"], ["bad user"], [], None, "alice"):
            with self.subTest(owners=owners):
                incident = self._existing()
                sync = self._host_sync_info()
                sync["incident_info"]["assignees"] = owners
                sync["update_attributes"] = {"assignees": {"from": ["saved-owner"], "to": owners}}
                self._run_update(sync, incident)
                self.assertEqual(incident.assignees, ["saved-owner"])
                self.assertEqual(incident.extra_info[ASSIGNEE_SOURCE_KEY], CMDB_HOST_ASSIGNEE_SOURCE)

    def test_explicit_null_revokes_ownership(self):
        incident = self._existing()
        sync = self._host_sync_info()
        sync["incident_info"]["extra_info"][ASSIGNEE_SOURCE_KEY] = None
        self.assertFalse(AccessIncidentProcess.apply_bkfara_host_ownership(sync, incident))
        self.assertIsNone(incident.extra_info[ASSIGNEE_SOURCE_KEY])
        IncidentDocument.generate_assignees(incident, SimpleNamespace(alert_entity_mapping={}))
        self.assertEqual(incident.assignees, [])

    def test_update_projection_cannot_overwrite_normalized_owners(self):
        incident = self._existing()
        sync = self._host_sync_info()
        sync["incident_info"]["assignees"] = [" alice ", "alice", "bob"]
        sync["update_attributes"] = {"assignees": {"from": [], "to": "unvalidated-owner"}}
        record, api = self._run_update(sync, incident)
        self.assertEqual(incident.assignees, ["alice", "bob"])
        self.assertEqual(record.call_args.kwargs["to_value"], ["alice", "bob"])
        self.assertEqual(record.call_args.kwargs["from_value"], ["saved-owner"])
        self.assertEqual(api.bk_incident.update_incident_detail.call_args.kwargs["assignees"], ["alice", "bob"])

    def test_notification_failure_completes_receipt_and_duplicate_skips_incident_writes(self):
        from copy import deepcopy
        from unittest.mock import Mock

        sync = self._host_sync_info()
        sync.update(
            event_id="failed-notice",
            aggregate_revision=3,
            update_attributes={"assignees": {"from": ["saved-owner"], "to": ["host-owner"]}},
        )
        duplicate = deepcopy(sync)
        incident = self._existing()
        record, _ = self._run_update(sync, incident, Mock(return_value={"alice": {"result": False}}))
        self.assertEqual(incident.extra_info[HOST_OWNERSHIP_EVENT_ID_KEY], "failed-notice")
        self.assertEqual(record.call_count, 1)
        record, api = self._run_update(duplicate, incident)
        record.assert_not_called()
        api.bk_incident.update_incident_detail.assert_not_called()

    def test_invalid_claim_does_not_advance_receipt_and_corrected_event_can_apply(self):
        for source, owners in ((CMDB_HOST_ASSIGNEE_SOURCE, ["alice,bob"]), ("unknown", ["alice"])):
            incident = self._existing()
            sync = self._host_sync_info()
            sync.update(event_id="correctable", aggregate_revision=3, update_attributes={})
            sync["incident_info"]["extra_info"][ASSIGNEE_SOURCE_KEY] = source
            sync["incident_info"]["assignees"] = owners
            self._run_update(sync, incident)
            self.assertNotIn(HOST_OWNERSHIP_REVISION_KEY, incident.extra_info)
            corrected = self._host_sync_info()
            corrected.update(event_id="correctable", aggregate_revision=3, update_attributes={})
            corrected["incident_info"]["assignees"] = ["alice"]
            self._run_update(corrected, incident)
            self.assertEqual(incident.assignees, ["alice"])
            self.assertEqual(incident.extra_info[HOST_OWNERSHIP_REVISION_KEY], 3)

    def test_event_delivery_namespace_includes_scope_and_tenant(self):
        sync = self._host_sync_info()
        sync.update(event_id="same-event", bk_tenant_id="tenant-a", scope_id="bkcc_2")
        first = self.processor.notice_event_key(sync)
        sync["bk_tenant_id"] = "tenant-b"
        self.assertNotEqual(first, self.processor.notice_event_key(sync))

    def test_nested_scope_precedes_legacy_top_level_and_isolates_delivery(self):
        sync = self._host_sync_info()
        sync.update(event_id="same-event", bk_tenant_id="tenant-a", scope_id="legacy")
        sync["incident_info"]["scope_id"] = "bkcc_1"
        first = self.processor.notice_event_key(sync)
        sync["scope_id"] = "ignored"
        self.assertEqual(first, self.processor.notice_event_key(sync))
        sync["incident_info"]["scope_id"] = "bkcc_2"
        self.assertNotEqual(first, self.processor.notice_event_key(sync))
        del sync["incident_info"]["scope_id"]
        sync["scope_id"] = "bkcc_1"
        self.assertEqual(first, self.processor.notice_event_key(sync))

    def test_partial_sync_cannot_move_receipt_or_allow_old_owner_replay(self):
        for revision in (1, 10):
            incident = self._existing()
            incident.extra_info.update({HOST_OWNERSHIP_EVENT_ID_KEY: "current", HOST_OWNERSHIP_REVISION_KEY: 5})
            sync = self._host_sync_info()
            sync.update(event_id="partial", aggregate_revision=revision, update_attributes={})
            sync["incident_info"].pop("extra_info")
            self._run_update(sync, incident)
            self.assertEqual(incident.extra_info[HOST_OWNERSHIP_REVISION_KEY], 5)
            self.assertEqual(incident.extra_info[HOST_OWNERSHIP_EVENT_ID_KEY], "current")
            replay = self._host_sync_info()
            replay.update(event_id="old-owner", aggregate_revision=4, update_attributes={})
            record, api = self._run_update(replay, incident)
            record.assert_not_called()
            api.bk_incident.update_incident_detail.assert_not_called()
            self.assertEqual(incident.assignees, ["saved-owner"])


class TestNoticeContentSafety(SimpleTestCase):
    def test_personal_markdown_escapes_untrusted_links(self):
        from constants.action import NoticeWay

        context = {
            "incident_reason": "[click](https://example.invalid) <b>bad</b>",
            "assignees": "alice",
            "incident_name": "**fake**",
            "url": "https://example.invalid/incident/1",
        }
        with (
            patch.object(IncidentNoticeHelper, "get_incident_context", return_value=context),
            patch("bkmonitor.aiops.incident.notice.IncidentSender") as sender,
            override_settings(MD_SUPPORTED_NOTICE_WAYS=[NoticeWay.QY_WEIXIN]),
        ):
            IncidentNoticeHelper._send_personal_notice(SimpleNamespace(incident_id=1), ["alice"], NoticeWay.QY_WEIXIN)
        sent_context = sender.call_args.kwargs["context"]
        self.assertIn(r"\[click\]\(", sent_context["incident_reason"])
        self.assertNotIn("<b>", sent_context["incident_reason"])
        self.assertEqual(sent_context["url"], "https://example.invalid/incident/1")

    def test_plain_text_keeps_punctuation_and_addresses(self):
        from constants.action import NoticeWay

        context = {"incident_name": "MySQL-主从延迟", "incident_reason": "10.0.0.1 (timeout)!", "assignees": "alice"}
        with (
            patch.object(IncidentNoticeHelper, "get_incident_context", return_value=context),
            patch("bkmonitor.aiops.incident.notice.IncidentSender") as sender,
            override_settings(MD_SUPPORTED_NOTICE_WAYS=[NoticeWay.WX_BOT]),
        ):
            IncidentNoticeHelper._send_personal_notice(SimpleNamespace(incident_id=1), ["alice"], NoticeWay.QY_WEIXIN)
        self.assertEqual(sender.call_args.kwargs["context"]["incident_reason"], "10.0.0.1 (timeout)!")
        self.assertEqual(context["incident_name"], "MySQL-主从延迟")

    def test_robot_markdown_escapes_text_but_preserves_template_links(self):
        from constants.action import NoticeWay
        from pathlib import Path
        from bkmonitor.utils.template import Jinja2Renderer

        context = {
            "incident_name": "[name](https://example.invalid)",
            "incident_reason": "[click](https://example.invalid)",
            "assignees": "<b>alice</b>",
            "url": "https://example.invalid/incident/1",
        }
        with (
            patch.object(IncidentNoticeHelper, "get_incident_context", return_value=context),
            patch("bkmonitor.aiops.incident.notice.IncidentSender") as sender,
            override_settings(
                WXWORK_BOT_WEBHOOK_URL="https://example.invalid", MD_SUPPORTED_NOTICE_WAYS=[NoticeWay.WX_BOT]
            ),
        ):
            IncidentNoticeHelper._send_wxwork_bot_notice(SimpleNamespace(incident_id=1), ["chat"])
        rendered_context = sender.call_args.kwargs["context"]
        template = Path(__file__).resolve().parents[3] / "templates/notice/incident/markdown_content.jinja"
        with override_settings(MD_SUPPORTED_NOTICE_WAYS=[NoticeWay.WX_BOT]):
            rendered = Jinja2Renderer.render(template.read_text(), rendered_context)
        self.assertNotIn("[click](", rendered)
        self.assertIn("[故障诊断详情](https://example.invalid/incident/1)", rendered)
        self.assertEqual(rendered_context["notice_way"], NoticeWay.WX_BOT)

    @override_settings(MD_SUPPORTED_NOTICE_WAYS=[NoticeWay.WX_BOT])
    def test_real_markdown_renderer_escapes_once_and_preserves_readable_ip_and_name(self):
        from constants.action import NoticeWay
        from bkmonitor.utils.template import Jinja2Renderer

        context = {
            "incident_reason": "10.0.0.1 [click](https://example.invalid)",
            "incident_name": "MySQL-主从延迟",
            "assignees": "alice",
        }
        IncidentNoticeHelper.prepare_notice_context(context, NoticeWay.WX_BOT)
        rendered = Jinja2Renderer.render("{{ incident_name }}: {{ incident_reason }}", context)
        self.assertEqual(rendered, r"MySQL-主从延迟: 10.0.0.1 \[click\]\(https://example.invalid\)")

    def test_subtitle_escapes_name_and_update_values_without_breaking_merge_links(self):
        from constants.action import NoticeWay
        from bkmonitor.utils.template import Jinja2Renderer

        name = "[click](https://example.invalid/injected)"
        incident = SimpleNamespace(
            incident_name=name,
            incident_reason=name,
            bk_biz_id=1,
            status="abnormal",
            level="ERROR",
            assignees=["alice"],
            end_time=None,
            begin_time=1,
            snapshot=None,
            alert_count=0,
            incident_id=1,
            id="doc-1",
            extra_info={},
        )
        with (
            override_settings(
                MD_SUPPORTED_NOTICE_WAYS=[NoticeWay.WX_BOT],
                BK_MONITOR_HOST="https://monitor.invalid",
                BK_INCIDENT_SAAS_HOST="https://fara.invalid",
            ),
            patch("bkmonitor.aiops.incident.notice.api"),
            patch.object(
                IncidentNoticeHelper,
                "_format_duration",
                return_value={"duration_range": ["start"], "duration_msg": "1秒", "duration_range_msg": ""},
            ),
        ):
            for operation in (
                IncidentOperationType.CREATE,
                IncidentOperationType.RECOVER,
                IncidentOperationType.UPDATE,
                IncidentOperationType.MERGE,
            ):
                with self.subTest(operation=operation):
                    context = IncidentNoticeHelper.get_incident_context(
                        incident,
                        operation_type=operation,
                        notice_way=NoticeWay.WX_BOT,
                        incident_key="assignees",
                        from_value=name,
                        to_value=name,
                        link_incident_name=name,
                        link_incident_doc_id="doc-2",
                    )
                    IncidentNoticeHelper.prepare_notice_context(context, NoticeWay.WX_BOT)
                    rendered = Jinja2Renderer.render("{{ subtitle }}", context)
                    self.assertNotIn(name, rendered)
                    self.assertIn(r"\[click\]\(https://example.invalid/injected\)", rendered)
                    if operation == IncidentOperationType.MERGE:
                        self.assertIn("](" + context["url"] + ")", rendered)
                        self.assertIn("](https://monitor.invalid/?bizId=1#/trace/incident/detail/doc-2)", rendered)

    def assert_mail_fields_explicitly_escaped(self, source):
        from jinja2 import Environment, nodes

        environment = Environment(autoescape=True)
        fields = {"incident_reason", "assignees", "incident_name"}
        found = set()
        for output in environment.parse(source).find_all(nodes.Output):
            for expression in output.nodes:
                names = [expression] if isinstance(expression, nodes.Name) else expression.find_all(nodes.Name)
                for name in names:
                    if name.name not in fields:
                        continue
                    # Require explicit escaping even when the rendering environment is safe.
                    self.assertIsInstance(expression, nodes.Filter)
                    self.assertIn(expression.name, {"e", "escape"})
                    self.assertIsInstance(expression.node, nodes.Name)
                    found.add(name.name)
        self.assertEqual(found, fields)
        return environment.from_string(source)

    def test_mail_template_escapes_reason_and_owner(self):
        from pathlib import Path

        template = Path(__file__).resolve().parents[3] / "templates/notice/incident/mail_content.jinja"
        html = self.assert_mail_fields_explicitly_escaped(template.read_text()).render(
            incident_reason='<a href="https://example.invalid">click</a>',
            assignees="<b>alice</b>",
            incident_name="<img src=x>",
        )
        self.assertNotIn('<a href="https://example.invalid">', html)
        self.assertIn("&lt;b&gt;alice&lt;/b&gt;", html)
        self.assertIn("&lt;img src=x&gt;", html)

    def test_removing_explicit_mail_escape_fails_even_with_autoescape_enabled(self):
        from pathlib import Path

        template = Path(__file__).resolve().parents[3] / "templates/notice/incident/mail_content.jinja"
        source = template.read_text()
        for field in ("incident_reason", "assignees", "incident_name"):
            with self.subTest(field=field), self.assertRaises(AssertionError):
                self.assert_mail_fields_explicitly_escaped(source.replace(field + " | e", field))


class TestNoticeDeliveryRouting(SimpleTestCase):
    def test_queue_acknowledges_completed_sync_without_sleep_or_notification_requeue(self):
        from unittest.mock import Mock

        processor = object.__new__(AccessIncidentProcess)
        processor.queue_name = "incident-test"
        processor.client = Mock()
        processor.handle_sync_info = Mock(return_value={"alice": {"result": False}})
        processor.process()
        callback = processor.client.start_consuming.call_args.kwargs["callback"]
        channel = Mock()
        with patch("alarm_backends.service.access.incident.processor.time.sleep") as sleep:
            callback(channel, SimpleNamespace(delivery_tag=9), {}, '{"incident_id":1}')
        channel.basic_ack.assert_called_once_with(9)
        channel.basic_nack.assert_not_called()
        sleep.assert_not_called()

    def test_channel_receipts_are_scoped_per_recipient_and_operation(self):
        from constants.action import NoticeWay

        incident = SimpleNamespace(incident_id=1)
        targets = [{"notice_way": NoticeWay.SMS, "receivers": ["alice", "bob"]}]

        def dispatch(key, channel, recipient, send):
            return send()

        with (
            patch.object(IncidentNoticeHelper, "_get_configured_notice_targets", return_value=targets),
            patch.object(
                IncidentNoticeHelper,
                "_send_notice_by_way",
                side_effect=lambda **kw: {user: {"result": True} for user in kw["receivers"]},
            ) as send,
            patch("bkmonitor.aiops.incident.notice.dispatch_once", side_effect=dispatch) as receipt,
        ):
            IncidentNoticeHelper.send_incident_notice(
                incident,
                operation_type=IncidentOperationType.UPDATE,
                notice_event_key="event-key",
                incident_key="assignees",
            )
            IncidentNoticeHelper.send_incident_notice(
                incident, operation_type=IncidentOperationType.RECOVER, notice_event_key="event-key"
            )
        self.assertEqual(
            [call.kwargs["receivers"] for call in send.call_args_list], [["alice"], ["bob"], ["alice"], ["bob"]]
        )
        self.assertNotEqual(receipt.call_args_list[0].args[0], receipt.call_args_list[2].args[0])


class TestOwnershipRevocationOrder(SimpleTestCase):
    def test_old_revocation_cannot_clear_new_assignment_and_old_assignment_cannot_reactivate(self):
        for incoming, stored in ((None, CMDB_HOST_ASSIGNEE_SOURCE), (CMDB_HOST_ASSIGNEE_SOURCE, None)):
            incident = SimpleNamespace(
                extra_info={
                    NOTICE_SOURCE_KEY: BKFARA_NOTICE_SOURCE,
                    ASSIGNEE_SOURCE_KEY: stored,
                    HOST_OWNERSHIP_EVENT_ID_KEY: "new",
                    HOST_OWNERSHIP_REVISION_KEY: 3,
                }
            )
            event = {
                NOTICE_SOURCE_KEY: BKFARA_NOTICE_SOURCE,
                "event_id": "old",
                "aggregate_revision": 2,
                "incident_info": {"extra_info": {ASSIGNEE_SOURCE_KEY: incoming}},
            }
            self.assertTrue(AccessIncidentProcess.duplicate_host_ownership_event(event, incident))

    def test_revocation_advances_receipt(self):
        incident = SimpleNamespace(extra_info={NOTICE_SOURCE_KEY: BKFARA_NOTICE_SOURCE, ASSIGNEE_SOURCE_KEY: None})
        event = {
            NOTICE_SOURCE_KEY: BKFARA_NOTICE_SOURCE,
            "event_id": "revoke",
            "aggregate_revision": 4,
            "incident_info": {"extra_info": {ASSIGNEE_SOURCE_KEY: None}},
        }
        AccessIncidentProcess.remember_host_ownership_event(event, incident)
        self.assertEqual(incident.extra_info[HOST_OWNERSHIP_REVISION_KEY], 4)

    def test_receipt_is_monotonic_even_when_called_after_an_accepted_assignment(self):
        incident = SimpleNamespace(
            assignees=["alice"],
            extra_info={
                NOTICE_SOURCE_KEY: BKFARA_NOTICE_SOURCE,
                ASSIGNEE_SOURCE_KEY: CMDB_HOST_ASSIGNEE_SOURCE,
                HOST_OWNERSHIP_EVENT_ID_KEY: "current",
                HOST_OWNERSHIP_REVISION_KEY: 5,
            },
        )
        for source in (CMDB_HOST_ASSIGNEE_SOURCE, None):
            incident.extra_info[ASSIGNEE_SOURCE_KEY] = source
            for revision in (4, 5, True, 0):
                event = {
                    NOTICE_SOURCE_KEY: BKFARA_NOTICE_SOURCE,
                    "event_id": "older",
                    "aggregate_revision": revision,
                    "incident_info": {"assignees": ["alice"], "extra_info": {ASSIGNEE_SOURCE_KEY: source}},
                }
                AccessIncidentProcess.remember_host_ownership_event(event, incident)
                self.assertEqual(incident.extra_info[HOST_OWNERSHIP_REVISION_KEY], 5)
                self.assertEqual(incident.extra_info[HOST_OWNERSHIP_EVENT_ID_KEY], "current")
