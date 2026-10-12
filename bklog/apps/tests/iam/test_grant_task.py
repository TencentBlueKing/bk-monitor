from unittest.mock import Mock, patch

from celery.exceptions import Retry
from django.test import SimpleTestCase, override_settings

from apps.iam.backends.v4.exceptions import V4ClientError, V4ResponseError, V4TimeoutError
from apps.iam.iam_engine.provider.capabilities import PreparedAuthorizationGrant
from apps.iam.tasks.grant import dispatch_v4_creator_grant, grant_v4_creator_action


@override_settings(BK_IAM_GRANT_MAX_ATTEMPTS=12)
class GrantV4CreatorActionTaskTest(SimpleTestCase):
    task_kwargs = {
        "tenant_id": "tenant-1",
        "operator": "operator",
        "payload": [{"resources": [{"type": "collection", "id": "28"}], "expired_at": 1893456000}],
        "role_id": "space_operator",
        "expired_at": 1893456000,
        "resource_meta": {
            "subject_id": "creator",
            "resource_system": "bk_log_search",
            "resource_type": "collection",
            "resource_id": "28",
        },
    }

    def setUp(self):
        self.writer = Mock()
        writer_patcher = patch(
            "apps.iam.tasks.grant.V4AuthorizationWriter.from_settings",
            return_value=self.writer,
        )
        self.from_settings = writer_patcher.start()
        self.addCleanup(writer_patcher.stop)

    @staticmethod
    def _run_task(*, retries: int = 0, **overrides):
        grant_v4_creator_action.push_request(retries=retries)
        try:
            grant_v4_creator_action.run(**{**GrantV4CreatorActionTaskTest.task_kwargs, **overrides})
        finally:
            grant_v4_creator_action.pop_request()

    def test_successful_grant_replays_the_frozen_request(self):
        with patch("apps.iam.tasks.grant.logger.info") as info_log:
            self._run_task()

        self.from_settings.assert_called_once_with(username="operator", bk_tenant_id="tenant-1")
        self.writer.grant_prepared.assert_called_once_with(
            PreparedAuthorizationGrant(
                payload=self.task_kwargs["payload"],
                role_id="space_operator",
                expired_at=1893456000,
            )
        )
        info_log.assert_called_once()

    def test_retryable_failure_reschedules_with_exponential_backoff(self):
        self.writer.grant_prepared.side_effect = V4TimeoutError("v4 timeout")

        with patch.object(grant_v4_creator_action, "retry", side_effect=Retry()) as retry:
            with self.assertRaises(Retry):
                self._run_task(retries=1)

        self.assertEqual(retry.call_args.kwargs["countdown"], 60)

    def test_retry_replays_the_same_expired_at(self):
        with patch("apps.iam.tasks.grant.logger.info"):
            self._run_task(retries=4)

        # add_authorization 没有幂等键，重复授权可以接受，但重算 expired_at 会让有效期随重试漂移。
        self.assertEqual(self.writer.grant_prepared.call_args.args[0].expired_at, 1893456000)

    def test_final_failure_is_not_retried(self):
        self.writer.grant_prepared.side_effect = V4ResponseError("unexpected response body")

        with patch.object(grant_v4_creator_action, "retry") as retry:
            with patch("apps.iam.tasks.grant.logger.error") as error_log:
                self._run_task()

        retry.assert_not_called()
        error_log.assert_called_once()
        self.assertIn("final failure", error_log.call_args.args[0])
        self.assertIn("failure_kind=failed_final", error_log.call_args.args[1])

    @override_settings(BK_IAM_GRANT_MAX_ATTEMPTS=3)
    def test_exhausted_attempts_stop_retrying_and_log_terminal_failure(self):
        self.writer.grant_prepared.side_effect = V4ClientError("gateway error", status_code=502)

        with patch.object(grant_v4_creator_action, "retry") as retry:
            with patch("apps.iam.tasks.grant.logger.error") as error_log:
                self._run_task(retries=2)

        retry.assert_not_called()
        error_log.assert_called_once()
        self.assertIn("attempt=3 max_attempts=3", error_log.call_args.args[1])
        self.assertIn("error_code=502", error_log.call_args.args[1])

    def test_writer_construction_failure_is_classified_instead_of_crashing_the_worker(self):
        self.from_settings.side_effect = V4TimeoutError("gateway unreachable")

        with patch.object(grant_v4_creator_action, "retry", side_effect=Retry()) as retry:
            with self.assertRaises(Retry):
                self._run_task()

        self.assertEqual(retry.call_args.kwargs["countdown"], 30)


class DispatchV4CreatorGrantTest(SimpleTestCase):
    def test_dispatch_sends_task_kwargs_as_is(self):
        task_kwargs = {"tenant_id": "tenant-1", "operator": "operator"}

        with patch.object(grant_v4_creator_action, "apply_async") as apply_async:
            dispatch_v4_creator_grant(task_kwargs)

        apply_async.assert_called_once_with(kwargs=task_kwargs)
