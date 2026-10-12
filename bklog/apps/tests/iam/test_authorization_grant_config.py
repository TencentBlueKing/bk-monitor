from django.test import SimpleTestCase, override_settings

from apps.iam.grant_config import (
    GRANT_RETRY_BASE_COUNTDOWN_SECONDS,
    GRANT_RETRY_MAX_COUNTDOWN_SECONDS,
    AuthorizationGrantConfig,
    retry_countdown_seconds,
)


class AuthorizationGrantConfigTest(SimpleTestCase):
    @override_settings(
        BK_IAM_V4_GRANT_EXPIRE_DAYS="invalid",
        BK_IAM_GRANT_MAX_ATTEMPTS="invalid",
    )
    def test_invalid_values_fall_back_to_defaults(self):
        with self.assertLogs("iam.grant.config", level="WARNING") as logs:
            grant_config = AuthorizationGrantConfig.from_settings()

        self.assertEqual(grant_config.v4_expire_days, 365)
        self.assertEqual(grant_config.max_attempts, 12)
        self.assertEqual(len(logs.records), 2)

    @override_settings(
        BK_IAM_V4_GRANT_EXPIRE_DAYS="0",
        BK_IAM_GRANT_MAX_ATTEMPTS="0",
    )
    def test_values_below_minimum_use_lower_bounds(self):
        with self.assertLogs("iam.grant.config", level="WARNING"):
            grant_config = AuthorizationGrantConfig.from_settings()

        self.assertEqual(grant_config.v4_expire_days, 1)
        self.assertEqual(grant_config.max_attempts, 1)

    @override_settings(
        BK_IAM_V4_GRANT_EXPIRE_DAYS="366",
        BK_IAM_GRANT_MAX_ATTEMPTS="20",
    )
    def test_values_above_maximum_are_capped_without_changing_unbounded_values(self):
        with self.assertLogs("iam.grant.config", level="WARNING") as logs:
            grant_config = AuthorizationGrantConfig.from_settings()

        self.assertEqual(grant_config.v4_expire_days, 365)
        self.assertEqual(grant_config.max_attempts, 20)
        self.assertEqual(len(logs.records), 1)


class RetryCountdownTest(SimpleTestCase):
    def test_countdown_doubles_from_the_base_interval(self):
        self.assertEqual(retry_countdown_seconds(0), GRANT_RETRY_BASE_COUNTDOWN_SECONDS)
        self.assertEqual(retry_countdown_seconds(1), GRANT_RETRY_BASE_COUNTDOWN_SECONDS * 2)
        self.assertEqual(retry_countdown_seconds(2), GRANT_RETRY_BASE_COUNTDOWN_SECONDS * 4)

    def test_countdown_is_capped_and_tolerates_out_of_range_input(self):
        self.assertEqual(retry_countdown_seconds(20), GRANT_RETRY_MAX_COUNTDOWN_SECONDS)
        self.assertEqual(retry_countdown_seconds(-1), GRANT_RETRY_BASE_COUNTDOWN_SECONDS)
