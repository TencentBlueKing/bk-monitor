from django.test import SimpleTestCase, override_settings

from apps.iam.backends.v4.config import V4Options
from apps.iam.backends.v4.gateway import resolve_v4_gateway_url


@override_settings(
    APP_CODE="bk_log_search",
    SECRET_KEY="secret",
    BK_IAM_SYSTEM_ID="bk_log_search",
    BK_COMPONENT_API_URL="https://bkapi.example.com",
    BK_IAM_APIGATEWAY_URL="https://bk-iam.apigw.o.woa.com/stage/",
)
class V4GatewayConfigTest(SimpleTestCase):
    def test_resolve_v4_gateway_url_uses_explicit_v4_setting(self):
        with self.settings(BK_IAM_V4_APIGATEWAY_URL="https://bkiam.apigw.o.woa.com/prod/"):
            self.assertEqual(resolve_v4_gateway_url(), "https://bkiam.apigw.o.woa.com/prod/")

    def test_resolve_v4_gateway_url_returns_empty_without_explicit_config(self):
        with self.settings(BK_IAM_V4_APIGATEWAY_URL=""):
            self.assertEqual(resolve_v4_gateway_url(), "")

    def test_resolve_v4_gateway_url_does_not_derive_from_component_or_v3_gateway(self):
        with self.settings(BK_IAM_V4_APIGATEWAY_URL="", BK_COMPONENT_API_URL="https://bkapi.example.com"):
            self.assertEqual(resolve_v4_gateway_url(), "")

        with self.settings(
            BK_IAM_V4_APIGATEWAY_URL="",
            BK_COMPONENT_API_URL="",
            BK_IAM_APIGATEWAY_URL="https://bk-iam.apigw.o.woa.com/stage/",
        ):
            self.assertEqual(resolve_v4_gateway_url(), "")

    def test_v4_options_from_settings_uses_v4_gateway(self):
        with self.settings(BK_IAM_V4_APIGATEWAY_URL="https://bkiam.apigw.o.woa.com/prod/"):
            options = V4Options.from_settings()
            self.assertEqual(options.gateway_url, "https://bkiam.apigw.o.woa.com/prod/")
            self.assertIn("{system_id}", options.auth_path)
