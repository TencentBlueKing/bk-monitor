from datetime import timedelta
from unittest import TestCase
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from bkmonitor.aiops.incident.delivery import dispatch_once
from bkmonitor.models.incident_delivery import IncidentNoticeDelivery


@pytest.mark.django_db(transaction=True)
class TestIncidentNoticeDelivery(TestCase):
    def setUp(self):
        IncidentNoticeDelivery.objects.all().delete()

    def test_success_is_persisted_and_duplicate_does_not_send(self):
        send = Mock(return_value={"alice": {"result": True}})
        dispatch_once("event", "mail", "alice", send)
        dispatch_once("event", "mail", "alice", send)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(IncidentNoticeDelivery.objects.get().status, "sent")

    def test_claim_is_committed_before_external_send_and_blocks_another_consumer(self):
        def send():
            self.assertEqual(IncidentNoticeDelivery.objects.get().status, "sending")
            other = Mock()
            self.assertFalse(dispatch_once("event", "voice", "alice", other)["alice"]["result"])
            other.assert_not_called()
            return {"alice": {"result": True}}

        dispatch_once("event", "voice", "alice", send)

    def test_failure_is_terminal_and_does_not_block_other_recipients(self):
        for channel in ("mail", "sms", "weixin", "custom"):
            bob = Mock(return_value={"bob": {"result": False}})
            alice = Mock(return_value={"alice": {"result": True}})
            for _ in range(3):
                self.assertFalse(dispatch_once("event", channel, "bob", bob)["bob"]["result"])
                self.assertTrue(dispatch_once("event", channel, "alice", alice)["alice"]["result"])
            self.assertEqual(bob.call_count, 1)
            self.assertEqual(alice.call_count, 1)
        self.assertEqual(IncidentNoticeDelivery.objects.get(channel="custom", recipient="bob").status, "failed")

    def test_exception_or_missing_result_is_uncertain_and_never_blindly_resent(self):
        for name, send in (("timeout", Mock(side_effect=TimeoutError)), ("empty", Mock(return_value={}))):
            dispatch_once(name, "sms", "alice", send)
            dispatch_once(name, "sms", "alice", send)
            self.assertEqual(send.call_count, 1)
        self.assertEqual(IncidentNoticeDelivery.objects.filter(status="uncertain").count(), 2)

    def test_interrupted_claim_becomes_uncertain_after_timeout(self):
        send = Mock(return_value={"alice": {"result": True}})
        dispatch_once("event", "voice", "alice", send)
        IncidentNoticeDelivery.objects.update(status="sending", updated_at=timezone.now() - timedelta(hours=1))
        result = dispatch_once("event", "voice", "alice", send)
        self.assertFalse(result["alice"]["result"])
        self.assertEqual(send.call_count, 1)
        self.assertEqual(IncidentNoticeDelivery.objects.get().status, "uncertain")

    def test_distinct_channel_recipient_or_event_gets_own_receipt(self):
        for event, channel, receiver in (
            ("one", "mail", "alice"),
            ("two", "mail", "alice"),
            ("one", "voice", "alice"),
            ("one", "mail", "bob"),
        ):
            dispatch_once(event, channel, receiver, lambda: {receiver: {"result": True}})
        self.assertEqual(IncidentNoticeDelivery.objects.count(), 4)

    def test_outer_transaction_cannot_delay_claim_commit_until_after_send(self):
        from django.db import transaction

        send = Mock()
        with transaction.atomic():
            self.assertFalse(dispatch_once("event", "sms", "alice", send)["alice"]["result"])
        send.assert_not_called()
        self.assertFalse(IncidentNoticeDelivery.objects.exists())

    def test_concurrent_consumer_cannot_send_while_first_claim_is_in_flight(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from django.db import close_old_connections, connection

        if connection.settings_dict["NAME"] == ":memory:":
            self.skipTest("threaded database test requires a shared database")
        entered, release = Event(), Event()

        def first():
            try:

                def send():
                    entered.set()
                    if not release.wait(5):
                        raise TimeoutError("test release")
                    return {"alice": {"result": True}}

                return dispatch_once("concurrent", "voice", "alice", send)
            finally:
                close_old_connections()

        def second():
            try:
                send = Mock()
                self.assertFalse(dispatch_once("concurrent", "voice", "alice", send)["alice"]["result"])
                send.assert_not_called()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as workers:
            first_result = workers.submit(first)
            try:
                self.assertTrue(entered.wait(5))
                workers.submit(second).result(timeout=5)
            finally:
                release.set()
            self.assertTrue(first_result.result(timeout=5)["alice"]["result"])
        self.assertEqual(IncidentNoticeDelivery.objects.get().attempts, 1)

    def test_legacy_sender_false_can_hide_timeout_and_must_not_be_retried(self):
        from constants.incident_delivery import AMBIGUOUS_FAILURE_NOTICE_WAYS, IncidentNoticeDeliveryStatus as Status

        for channel in AMBIGUOUS_FAILURE_NOTICE_WAYS:
            send = Mock(return_value={"alice": {"result": False, "message": "timeout"}})
            dispatch_once("ambiguous", channel, "alice", send)
            dispatch_once("ambiguous", channel, "alice", send)
            self.assertEqual(send.call_count, 1)
            self.assertEqual(IncidentNoticeDelivery.objects.get(channel=channel).status, Status.UNCERTAIN)

    def test_receipt_database_failure_does_not_send_or_requeue_incident(self):
        from django.db import OperationalError

        send = Mock()
        with patch.object(
            IncidentNoticeDelivery.objects, "get_or_create", side_effect=OperationalError("missing table")
        ):
            self.assertFalse(dispatch_once("event", "sms", "alice", send)["alice"]["result"])
        send.assert_not_called()

    def test_result_write_failure_does_not_repeat_external_send(self):
        from django.db import OperationalError
        from django.db.models.query import QuerySet

        send = Mock(return_value={"alice": {"result": True}})
        original = QuerySet.update

        def update(query, **kwargs):
            if kwargs.get("status") == "sent":
                raise OperationalError("receipt write failed")
            return original(query, **kwargs)

        with patch.object(QuerySet, "update", update):
            dispatch_once("event", "sms", "alice", send)
        dispatch_once("event", "sms", "alice", send)
        send.assert_called_once()
        self.assertEqual(IncidentNoticeDelivery.objects.get().status, "sending")
