from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.log_search.constants import (
    ASYNC_EXPORT_EMAIL_ERR_TEMPLATE,
    ASYNC_EXPORT_EMAIL_TEMPLATE,
    ExportJobStatus,
    ExportPartStatus,
    ExportSearchType,
    IndexSetType,
)
from apps.log_search.export import state
from apps.log_search.export.api import create_export_job
from apps.log_search.export.config import NOTIFY_QUEUE, NOTIFY_TASK_NAME
from apps.log_search.export.models import ExportJob, ExportPart
from apps.log_search.export.notification import (
    build_notification_context,
    notify_terminal_job,
    send_export_notification,
)
from apps.log_search.export.scheduler import enqueue_notifications, finalize_export, pending_notifications
from apps.log_search.models import LogIndexSet, Scenario, Space


def make_job(**overrides):
    values = {
        "space_uid": "bkcc__2",
        "created_by": "tester",
        "search_params": {},
        "base_dict": {},
        "start_time": 0,
        "end_time": 4000,
        "notification_context": {"language": "zh-cn", "search_url": "https://logs.example/#/retrieve/1"},
    }
    values.update(overrides)
    return ExportJob.objects.create(**values)


class NotificationContextTests(SimpleTestCase):
    @override_settings(SITE_URL="/logs/")
    @patch("apps.log_search.export.notification.get_request_external_user_email", return_value="user@example.com")
    @patch("apps.log_search.export.notification.get_request_language_code", return_value="en")
    @patch("apps.log_search.export.notification.get_request")
    def test_context_captures_request_and_search_routes(self, request_mock, language_mock, email_mock):
        request_mock.return_value = SimpleNamespace(scheme="https", get_host=lambda: "logs.example")
        params = {"bk_biz_id": 2, "keyword": "error", "addition": [{"field": "host", "value": "a"}]}
        for kind, ids, path in (
            (IndexSetType.SINGLE.value, [3], "/logs/#/retrieve/3"),
            (IndexSetType.UNION.value, [3, 4], "/logs/#/retrieve"),
            (ExportSearchType.SCENE, [], "/logs/#/retrieve/scene"),
        ):
            with self.subTest(kind=kind):
                context = build_notification_context(params, "bkcc__2", kind, ids)
                self.assertEqual(context["language"], "en")
                self.assertEqual(context["external_user_email"], "user@example.com")
                self.assertEqual(context["search_url"].split("?")[0], f"https://logs.example{path}")
                if kind != ExportSearchType.SCENE:
                    query = parse_qs(urlsplit(context["search_url"]).fragment.split("?")[1])
                    self.assertEqual(query["spaceUid"], ["bkcc__2"])
                    self.assertEqual(query["keyword"], ["error"])
                    if kind == IndexSetType.UNION.value:
                        self.assertEqual(query["unionList"], ["[3, 4]"])
        self.assertEqual(params["addition"], [{"field": "host", "value": "a"}])


@override_settings(EMAIL_TITLE={"en": "Logs", "zh": "日志平台"})
class ExportNotificationTests(TestCase):
    def setUp(self):
        self.channel = MagicMock()
        self.channel.title.side_effect = lambda template, **values: template.format(**values)
        self.channel.content.return_value = "email-body"
        channel_patch = patch("apps.log_search.export.notification.NotifyType.get_instance")
        channel_patch.start().return_value.return_value = self.channel
        self.addCleanup(channel_patch.stop)
        toggle_patch = patch("apps.log_search.export.notification.FeatureToggleObject.toggle")
        toggle_patch.start().return_value.feature_config = {"notify_type": "email"}
        self.addCleanup(toggle_patch.stop)

    def test_success_uses_full_artifact_and_remaining_retention(self):
        job = make_job(
            status=ExportJobStatus.SUCCESS,
            search_type=ExportSearchType.SCENE,
            merged_object_key="exports/1/full.jsonl.gz",
            merged_bytes=1024 * 1024,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        with patch("apps.log_search.export.notification.build_storage") as storage:
            storage.return_value.generate_download_url.return_value = "https://storage.example/full"
            send_export_notification(job)
        self.channel.send.assert_called_once_with(
            receivers="tester", title="【日志平台】场景化检索导出", content="email-body", is_external=False
        )
        call = storage.return_value.generate_download_url.call_args.kwargs
        self.assertEqual(call["file_name"], job.merged_object_key)
        self.assertGreater(call["expired"], 86000)
        self.assertLessEqual(call["expired"], 86400)
        content = self.channel.content.call_args.kwargs
        self.assertEqual(content["name"], ASYNC_EXPORT_EMAIL_TEMPLATE)
        self.assertEqual(content["file"]["download_url"], "https://storage.example/full")
        self.assertEqual(content["file"]["size"], 1)

    def test_created_at_is_rendered_in_project_timezone(self):
        """导出时间按项目时区展示，不能直接输出数据库中的 UTC 时间。"""
        job = make_job(status=ExportJobStatus.FAILED, search_type=ExportSearchType.SCENE)
        ExportJob.objects.filter(pk=job.pk).update(created_at=datetime(2026, 10, 21, 2, 0, tzinfo=dt_timezone.utc))
        job.refresh_from_db()

        send_export_notification(job)

        self.assertEqual(self.channel.content.call_args.kwargs["file"]["created_at"], "2026-10-21 10:00:00")

    def test_scene_failure_uses_the_legacy_title(self):
        send_export_notification(make_job(status=ExportJobStatus.FAILED, search_type=ExportSearchType.SCENE))
        self.assertEqual(self.channel.send.call_args.kwargs["title"], "【日志平台】场景化检索导出失败")

    def test_failure_uses_external_email_language_and_union_names(self):
        job = make_job(
            status=ExportJobStatus.FAILED,
            index_set_ids=[3, 4],
            index_set_type=IndexSetType.UNION.value,
            is_external=True,
            notification_context={"language": "en", "external_user_email": "user@example.com"},
        )
        indexes = [SimpleNamespace(index_set_name=name, indexes=[]) for name in ("first", "second")]
        with (
            patch("apps.log_search.export.notification.LogIndexSet.objects.filter", return_value=indexes),
            patch("apps.log_search.export.notification.build_storage") as storage,
        ):
            send_export_notification(job)
        storage.assert_not_called()
        self.channel.send.assert_called_once()
        self.assertEqual(self.channel.send.call_args.kwargs["receivers"], "user@example.com")
        self.assertTrue(self.channel.send.call_args.kwargs["is_external"])
        content = self.channel.content.call_args.kwargs
        self.assertEqual(content["language"], "en")
        self.assertEqual(content["name"], ASYNC_EXPORT_EMAIL_ERR_TEMPLATE)
        self.assertEqual(content["file"]["index_set_name"], "first,second")
        self.assertIn("Logs", self.channel.send.call_args.kwargs["title"])
        self.assertNotIn("检索导出", self.channel.send.call_args.kwargs["title"])

    def test_missing_external_email_skips_delivery(self):
        send_export_notification(make_job(status=ExportJobStatus.FAILED, is_external=True))
        self.channel.send.assert_not_called()

    def test_delivery_failure_does_not_change_success_or_retry(self):
        job = make_job(
            status=ExportJobStatus.SUCCESS,
            search_type=ExportSearchType.SCENE,
            merged_object_key="full.jsonl.gz",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        self.channel.send.side_effect = RuntimeError("CMSI unavailable")
        with (
            patch("apps.log_search.export.notification.build_storage"),
            patch("apps.log_search.export.notification.logger") as logger,
        ):
            send_export_notification(job)
        self.channel.send.assert_called_once()
        logger.exception.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.status, ExportJobStatus.SUCCESS)

    @patch("apps.log_search.export.api.build_notification_context")
    def test_creation_persists_notification_context(self, context_mock):
        Space.objects.create(space_uid="bkcc__2", bk_biz_id=2, space_type_id="bkcc", space_id="2", space_name="biz-2")
        index = LogIndexSet.objects.create(
            index_set_name="index", space_uid="bkcc__2", category_id="application", scenario_id=Scenario.LOG
        )
        context_mock.return_value = {"language": "en", "external_user_email": "user@example.com"}
        handler = MagicMock(base_dict={}, origin_order_by=[], is_desensitize=True)
        with (
            patch("apps.log_search.export.api.is_sharded_export_enabled", return_value=True),
            patch("apps.log_search.export.api.UnifyQueryHandler", return_value=handler),
            patch("apps.log_search.export.api.get_request_username", return_value="tester"),
            patch("apps.log_search.export.api.get_request_external_username", return_value=""),
        ):
            job = create_export_job({"space_uid": "bkcc__2", "index_set_id": index.pk, "start_time": 0, "end_time": 1})
        job.refresh_from_db()
        self.assertEqual(job.notification_context, context_mock.return_value)


@patch("apps.log_search.export.notification.send_export_notification")
class TerminalNotificationTests(TestCase):
    """终态通知由周期扫描驱动：占位成功才发送，同一个任务最多发送一次。"""

    def test_notify_terminal_job_sends_once(self, send_mock):
        job = make_job(status=ExportJobStatus.SUCCESS)
        notify_terminal_job(job.pk)
        notify_terminal_job(job.pk)
        send_mock.assert_called_once()
        self.assertEqual(send_mock.call_args.args[0].pk, job.pk)
        job.refresh_from_db()
        self.assertIsNotNone(job.notify_at)

    def test_running_job_is_not_notified(self, send_mock):
        job = make_job(status=ExportJobStatus.RUNNING)
        notify_terminal_job(job.pk)
        send_mock.assert_not_called()
        job.refresh_from_db()
        self.assertIsNone(job.notify_at)

    def test_canceled_job_is_not_claimed(self, send_mock):
        """用户主动取消的任务不发通知，也不占位。"""
        job = make_job(status=ExportJobStatus.CANCELED)
        notify_terminal_job(job.pk)
        send_mock.assert_not_called()
        job.refresh_from_db()
        self.assertIsNone(job.notify_at)

    def test_send_failure_keeps_the_claim(self, send_mock):
        """占位先于发送提交：发送失败不回退占位，不重试，也不影响后续扫描。"""
        job = make_job(status=ExportJobStatus.SUCCESS)
        send_mock.side_effect = RuntimeError("CMSI unavailable")
        with self.assertRaises(RuntimeError):
            notify_terminal_job(job.pk)
        job.refresh_from_db()
        self.assertIsNotNone(job.notify_at)
        self.assertEqual(pending_notifications(10), [])


class NotificationDispatchTests(TestCase):
    """扫描与投递：只挑终态且不在投递租约内的任务，同一批任务不会在租约内被反复投递。"""

    def test_pending_notifications_only_terminal_unnotified(self):
        pending = make_job(status=ExportJobStatus.SUCCESS)
        make_job(status=ExportJobStatus.FAILED, notify_at=timezone.now())
        make_job(status=ExportJobStatus.RUNNING)
        make_job(status=ExportJobStatus.CANCELED)
        self.assertEqual(pending_notifications(10), [pending.pk])
        state.claim_notification(pending.pk)
        self.assertEqual(pending_notifications(10), [])

    def test_enqueue_notifications_publishes_pending_jobs(self):
        job = make_job(status=ExportJobStatus.SUCCESS)
        with patch("apps.log_search.export.scheduler._send") as send:
            self.assertEqual(enqueue_notifications(10), [job.pk])
        self.assertEqual(send.call_args.args, (NOTIFY_TASK_NAME, job.pk))
        self.assertEqual(send.call_args.kwargs["queue"], NOTIFY_QUEUE)

    def test_published_job_is_not_republished_within_the_lease(self):
        """未消费的任务在租约内不会被下一轮扫描重复投递，避免刷爆共享队列。"""
        jobs = [make_job(status=ExportJobStatus.SUCCESS) for _ in range(2)]
        with patch("apps.log_search.export.scheduler._send") as send:
            for _ in range(3):
                enqueue_notifications(10)
        self.assertEqual([call.args[1] for call in send.call_args_list], [job.pk for job in jobs])
        self.assertEqual(pending_notifications(10), [])

    def test_limit_advances_past_published_jobs(self):
        """limit 用满后下一轮要推进到后面的任务，而不是被同一批占住。"""
        jobs = [make_job(status=ExportJobStatus.SUCCESS) for _ in range(3)]
        with patch("apps.log_search.export.scheduler._send") as send:
            enqueue_notifications(2)
            first = [call.args[1] for call in send.call_args_list]
            send.reset_mock()
            enqueue_notifications(2)
            second = [call.args[1] for call in send.call_args_list]
        self.assertEqual(first, [jobs[0].pk, jobs[1].pk])
        self.assertEqual(second, [jobs[2].pk])

    def test_expired_lease_republishes_lost_message(self):
        """消息丢失时租约到期会重新投递，不需要人工介入。"""
        job = make_job(status=ExportJobStatus.SUCCESS)
        ExportJob.objects.filter(pk=job.pk).update(
            notify_enqueued_at=timezone.now() - timedelta(seconds=settings.ASYNC_EXPORT_ENQUEUE_LEASE_SECONDS + 1)
        )
        with patch("apps.log_search.export.scheduler._send") as send:
            self.assertEqual(enqueue_notifications(10), [job.pk])
        self.assertEqual(send.call_count, 1)

    def test_publish_failure_releases_the_lease(self):
        job = make_job(status=ExportJobStatus.SUCCESS)
        with patch("apps.log_search.export.scheduler._send", side_effect=RuntimeError("broker down")):
            self.assertEqual(enqueue_notifications(10), [])
        job.refresh_from_db()
        self.assertIsNone(job.notify_enqueued_at)
        self.assertEqual(pending_notifications(10), [job.pk])


@patch("apps.log_search.export.notification.send_export_notification")
class FinalizationNotificationTests(TestCase):
    """收尾成功只落终态，发信交给扫描，避免收尾 worker 阻塞在通知链路上。"""

    def test_finalize_export_leaves_the_job_for_the_scan(self, send_mock):
        job = make_job(status=ExportJobStatus.RUNNING, actual_total=1, end_time=1000)
        ExportPart.objects.create(
            job=job,
            part_no=1,
            start_time=0,
            end_time=1000,
            status=ExportPartStatus.SUCCESS,
            actual_rows=1,
            actual_bytes=6,
            object_key="part-1.jsonl.gz",
            checksum="ignored",
        )
        with (
            patch("apps.log_search.export.merger.build_storage") as merger_storage,
            patch("apps.log_search.export.scheduler.build_storage"),
        ):
            merger_storage.return_value.download_fileobj.side_effect = lambda key, fh: fh.write(b'{"a":1}\n')
            result = finalize_export(job.pk)

        self.assertEqual(result.status, ExportJobStatus.SUCCESS)
        send_mock.assert_not_called()
        job.refresh_from_db()
        self.assertIsNone(job.notify_at)
        self.assertEqual(pending_notifications(10), [job.pk])

        notify_terminal_job(job.pk)
        send_mock.assert_called_once()
