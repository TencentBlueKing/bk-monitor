from django.test import SimpleTestCase, override_settings

from apps.iam.grant_config import AuthorizationGrantConfig


class AuthorizationGrantConfigTest(SimpleTestCase):
    @override_settings(
        BK_IAM_V4_GRANT_EXPIRE_DAYS="invalid",
        BK_IAM_GRANT_MAX_ATTEMPTS="invalid",
        BK_IAM_GRANT_LEASE_SECONDS="invalid",
        BK_IAM_GRANT_COMPENSATION_BATCH_SIZE="invalid",
        BK_IAM_GRANT_COMPENSATION_TIME_BUDGET_SECONDS="invalid",
    )
    def test_invalid_values_fall_back_to_defaults(self):
        with self.assertLogs("iam.grant.config", level="WARNING") as logs:
            grant_config = AuthorizationGrantConfig.from_settings()

        self.assertEqual(grant_config.v4_expire_days, 365)
        self.assertEqual(grant_config.max_attempts, 12)
        self.assertEqual(grant_config.lease_seconds, 120)
        self.assertEqual(grant_config.compensation_batch_size, 100)
        self.assertEqual(grant_config.compensation_time_budget_seconds, 50)
        self.assertEqual(len(logs.records), 5)

    @override_settings(
        BK_IAM_V4_GRANT_EXPIRE_DAYS="0",
        BK_IAM_GRANT_MAX_ATTEMPTS="0",
        BK_IAM_GRANT_LEASE_SECONDS="0",
        BK_IAM_GRANT_COMPENSATION_BATCH_SIZE="0",
        BK_IAM_GRANT_COMPENSATION_TIME_BUDGET_SECONDS="0",
    )
    def test_values_below_minimum_use_lower_bounds(self):
        with self.assertLogs("iam.grant.config", level="WARNING"):
            grant_config = AuthorizationGrantConfig.from_settings()

        self.assertEqual(grant_config.v4_expire_days, 1)
        self.assertEqual(grant_config.max_attempts, 1)
        self.assertEqual(grant_config.lease_seconds, 30)
        self.assertEqual(grant_config.compensation_batch_size, 1)
        self.assertEqual(grant_config.compensation_time_budget_seconds, 1)

    @override_settings(
        BK_IAM_V4_GRANT_EXPIRE_DAYS="366",
        BK_IAM_GRANT_MAX_ATTEMPTS="20",
        BK_IAM_GRANT_LEASE_SECONDS="300",
        BK_IAM_GRANT_COMPENSATION_BATCH_SIZE="1001",
        BK_IAM_GRANT_COMPENSATION_TIME_BUDGET_SECONDS="56",
    )
    def test_values_above_maximum_are_capped_without_changing_unbounded_values(self):
        with self.assertLogs("iam.grant.config", level="WARNING") as logs:
            grant_config = AuthorizationGrantConfig.from_settings()

        self.assertEqual(grant_config.v4_expire_days, 365)
        self.assertEqual(grant_config.max_attempts, 20)
        self.assertEqual(grant_config.lease_seconds, 300)
        self.assertEqual(grant_config.compensation_batch_size, 1000)
        self.assertEqual(grant_config.compensation_time_budget_seconds, 55)
        self.assertEqual(len(logs.records), 3)
