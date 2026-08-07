from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.iam.backends.v4.config import resolve_callback_app_credentials
from apps.iam.handlers.compatible import V4CallbackIAM


@override_settings(
    APP_CODE="bk_log_search",
    SECRET_KEY="secret",
    BK_IAM_APIGATEWAY_URL="https://bk-iam.example/prod/",
    BK_IAM_V4_APIGATEWAY_URL="https://bkiam.example/dev",
    BK_IAM_V4_SYSTEM_ID="bklog_test",
    BK_IAM_SYSTEM_ID="bk_log_search",
    BK_APP_TENANT_ID="system",
)
class V4CallbackIAMTest(SimpleTestCase):
    def setUp(self):
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


class CompatibleIAMNonCompatModeTest(SimpleTestCase):
    @patch("apps.iam.handlers.compatible.CompatibleIAM.in_compatibility_mode", return_value=False)
    @patch("iam.IAM._do_policy_query", return_value={"op": "any"})
    @patch("iam.IAM._do_policy_query_by_actions", return_value=[])
    def test_policy_query_delegates_to_super_when_not_compatible(self, by_actions_mock, query_mock, _compat_mock):
        from apps.iam.handlers.compatible import CompatibleIAM

        client = CompatibleIAM("bk_log_search", "secret", "https://bk-iam.example/prod/", bk_tenant_id="system")
        request = MagicMock()
        self.assertEqual(client._do_policy_query(request), {"op": "any"})
        self.assertEqual(client._do_policy_query_by_actions(request), [])
        query_mock.assert_called_once()
        by_actions_mock.assert_called_once()
