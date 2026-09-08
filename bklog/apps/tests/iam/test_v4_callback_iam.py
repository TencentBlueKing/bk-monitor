from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.iam.backends.v4.callback_client import V4CallbackIAM
from apps.iam.backends.v4.config import resolve_callback_app_credentials


@override_settings(
    APP_CODE="bk_log_search",
    SECRET_KEY="secret",
    BK_IAM_APIGATEWAY_URL="https://bk-iam.example/prod/",
    BK_IAM_V4_APIGATEWAY_URL="https://bkiam.example/dev",
    BK_IAM_V4_SYSTEM_ID="bklog_test",
    BK_IAM_SYSTEM_ID="bk_log_search",
    BK_APP_TENANT_ID="system",
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "v4-callback-iam-tests",
        }
    },
)
class V4CallbackIAMTest(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.client = V4CallbackIAM("bk_log_search", "secret", "https://bk-iam.example/prod/", bk_tenant_id="system")

    @patch("apps.iam.backends.v4.client.V4Client.retrieve_system_auth_token", return_value="v4-token")
    def test_get_token_uses_v4_api_for_v4_system(self, retrieve_mock):
        ok, message, token = self.client.get_token("bklog_test")

        self.assertTrue(ok)
        self.assertEqual(message, "success")
        self.assertEqual(token, "v4-token")
        retrieve_mock.assert_called_once_with("bklog_test")

    @override_settings(
        BK_IAM_V4_CALLBACK_APP_CODE="p2-gateway-cole",
        BK_IAM_V4_CALLBACK_APP_SECRET="callback-secret",
    )
    @patch("apps.iam.backends.v4.client.V4Client.retrieve_system_auth_token", return_value="v4-token")
    def test_get_token_uses_callback_credentials_when_configured(self, retrieve_mock):
        ok, message, token = self.client.get_token("bklog_test")

        self.assertTrue(ok)
        self.assertEqual(token, "v4-token")
        retrieve_mock.assert_called_once_with("bklog_test")

    @patch("iam.IAM.get_token", return_value=(True, "success", "v3-token"))
    def test_get_token_falls_back_to_v3_for_legacy_system(self, v3_get_token):
        ok, message, token = self.client.get_token("bk_log_search")

        self.assertTrue(ok)
        self.assertEqual(token, "v3-token")
        v3_get_token.assert_called_once_with("bk_log_search")

    @override_settings(BK_IAM_V4_SYSTEM_ID="")
    @patch("apps.iam.backends.v4.client.V4Client.retrieve_system_auth_token", return_value="v4-token")
    def test_get_token_uses_v3_system_id_when_v4_system_id_empty(self, retrieve_mock):
        ok, message, token = self.client.get_token("bk_log_search")

        self.assertTrue(ok)
        self.assertEqual(token, "v4-token")
        retrieve_mock.assert_called_once_with("bk_log_search")

    @patch("apps.iam.backends.v4.client.V4Client.retrieve_system_auth_token", side_effect=RuntimeError("boom"))
    def test_get_token_returns_false_when_v4_fetch_fails(self, _retrieve_mock):
        ok, message, token = self.client.get_token("bklog_test")

        self.assertFalse(ok)
        self.assertIn("boom", message)
        self.assertEqual(token, "")

    @patch("apps.iam.backends.v4.client.V4Client.retrieve_system_auth_token", return_value="")
    def test_get_token_returns_false_when_v4_token_empty(self, _retrieve_mock):
        ok, message, token = self.client.get_token("bklog_test")

        self.assertFalse(ok)
        self.assertIn("empty auth_token", message)
        self.assertEqual(token, "")

    @patch("apps.iam.backends.v4.config.V4Options.from_settings", side_effect=RuntimeError("invalid settings"))
    def test_get_token_returns_false_when_options_cannot_be_built(self, _options):
        ok, message, token = self.client.get_token("bklog_test")

        self.assertFalse(ok)
        self.assertIn("invalid settings", message)
        self.assertEqual(token, "")

    @patch("apps.iam.backends.v4.client.V4Client.retrieve_system_auth_token", return_value="v4-token")
    def test_successful_token_is_reused_from_cache(self, retrieve_mock):
        first = self.client.get_token("bklog_test")
        second = self.client.get_token("bklog_test")

        self.assertEqual(first, (True, "success", "v4-token"))
        self.assertEqual(second, first)
        retrieve_mock.assert_called_once_with("bklog_test")

    @patch(
        "apps.iam.backends.v4.client.V4Client.retrieve_system_auth_token",
        side_effect=[RuntimeError("temporary failure"), "v4-token"],
    )
    def test_failed_fetch_is_not_cached(self, retrieve_mock):
        first = self.client.get_token("bklog_test")
        second = self.client.get_token("bklog_test")

        self.assertFalse(first[0])
        self.assertEqual(second, (True, "success", "v4-token"))
        self.assertEqual(retrieve_mock.call_count, 2)

    @patch(
        "apps.iam.backends.v4.client.V4Client.retrieve_system_auth_token",
        side_effect=["system-token", "tenant-token"],
    )
    def test_token_cache_is_isolated_by_tenant(self, retrieve_mock):
        tenant_client = V4CallbackIAM(
            "bk_log_search",
            "secret",
            "https://bk-iam.example/prod/",
            bk_tenant_id="tenant-2",
        )

        self.assertEqual(self.client.get_token("bklog_test")[2], "system-token")
        self.assertEqual(tenant_client.get_token("bklog_test")[2], "tenant-token")
        self.assertEqual(retrieve_mock.call_count, 2)

    @patch("apps.iam.backends.v4.callback_client.cache.get", side_effect=RuntimeError("cache read failed"))
    @patch("apps.iam.backends.v4.client.V4Client.retrieve_system_auth_token", return_value="v4-token")
    def test_cache_read_failure_falls_back_to_iam(self, retrieve_mock, _cache_get):
        with self.assertLogs("root", level="WARNING"):
            result = self.client.get_token("bklog_test")

        self.assertEqual(result, (True, "success", "v4-token"))
        retrieve_mock.assert_called_once_with("bklog_test")

    @patch("apps.iam.backends.v4.callback_client.cache.set", side_effect=RuntimeError("cache write failed"))
    @patch("apps.iam.backends.v4.client.V4Client.retrieve_system_auth_token", return_value="v4-token")
    def test_cache_write_failure_keeps_fetched_token(self, retrieve_mock, _cache_set):
        with self.assertLogs("root", level="WARNING"):
            result = self.client.get_token("bklog_test")

        self.assertEqual(result, (True, "success", "v4-token"))
        retrieve_mock.assert_called_once_with("bklog_test")


@override_settings(
    APP_CODE="bk_log_search",
    SECRET_KEY="global-secret",
    BK_IAM_V4_CALLBACK_APP_CODE="p2-gateway-cole",
    BK_IAM_V4_CALLBACK_APP_SECRET="callback-secret",
)
class V4CallbackCredentialsTest(SimpleTestCase):
    def test_resolve_callback_app_credentials_uses_dedicated_values(self):
        app_code, app_secret = resolve_callback_app_credentials()
        self.assertEqual(app_code, "p2-gateway-cole")
        self.assertEqual(app_secret, "callback-secret")

    @override_settings(BK_IAM_V4_CALLBACK_APP_CODE="", BK_IAM_V4_CALLBACK_APP_SECRET="")
    def test_resolve_callback_app_credentials_falls_back_to_global_app(self):
        app_code, app_secret = resolve_callback_app_credentials()
        self.assertEqual(app_code, "bk_log_search")
        self.assertEqual(app_secret, "global-secret")

    @override_settings(BK_IAM_V4_CALLBACK_APP_CODE="callback-code", BK_IAM_V4_CALLBACK_APP_SECRET="")
    def test_partial_callback_credentials_warn_and_fall_back(self):
        with self.assertLogs("iam.v4.config", level="WARNING"):
            app_code, app_secret = resolve_callback_app_credentials()

        self.assertEqual(app_code, "bk_log_search")
        self.assertEqual(app_secret, "global-secret")


class CompatibleIAMNonCompatModeTest(SimpleTestCase):
    @patch("apps.iam.backends.v3.client.CompatibleIAM.in_compatibility_mode", return_value=False)
    @patch("iam.IAM._do_policy_query", return_value={"op": "any"})
    @patch("iam.IAM._do_policy_query_by_actions", return_value=[])
    def test_policy_query_delegates_to_super_when_not_compatible(self, by_actions_mock, query_mock, _compat_mock):
        from apps.iam.backends.v3.client import CompatibleIAM

        client = CompatibleIAM("bk_log_search", "secret", "https://bk-iam.example/prod/", bk_tenant_id="system")
        request = MagicMock()
        self.assertEqual(client._do_policy_query(request), {"op": "any"})
        self.assertEqual(client._do_policy_query_by_actions(request), [])
        query_mock.assert_called_once()
        by_actions_mock.assert_called_once()
