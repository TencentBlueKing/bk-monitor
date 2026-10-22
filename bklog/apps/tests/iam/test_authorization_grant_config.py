from django.test import SimpleTestCase, override_settings

from apps.iam.grant_config import AuthorizationGrantConfig


class AuthorizationGrantConfigTest(SimpleTestCase):
    @override_settings(
        BK_IAM_V4_GRANT_EXPIRE_DAYS="invalid",
    )
    def test_invalid_values_fall_back_to_defaults(self):
        with self.assertLogs("iam.grant.config", level="WARNING") as logs:
            grant_config = AuthorizationGrantConfig.from_settings()

        self.assertEqual(grant_config.v4_expire_days, 365)
        self.assertEqual(len(logs.records), 1)

    @override_settings(
        BK_IAM_V4_GRANT_EXPIRE_DAYS="0",
    )
    def test_values_below_minimum_use_lower_bounds(self):
        with self.assertLogs("iam.grant.config", level="WARNING"):
            grant_config = AuthorizationGrantConfig.from_settings()

        self.assertEqual(grant_config.v4_expire_days, 1)

    @override_settings(
        BK_IAM_V4_GRANT_EXPIRE_DAYS="366",
    )
    def test_values_above_maximum_are_capped(self):
        with self.assertLogs("iam.grant.config", level="WARNING") as logs:
            grant_config = AuthorizationGrantConfig.from_settings()

        self.assertEqual(grant_config.v4_expire_days, 365)
        self.assertEqual(len(logs.records), 1)
