import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from requests.structures import CaseInsensitiveDict

from apps.api.base import DataAPI, get_request_api_headers
from apps.utils.log_sanitization import REDACTED_HEADER_VALUE, sanitize_headers


class GetRequestApiHeadersTest(SimpleTestCase):
    @patch("apps.api.base.get_request_username")
    def test_explicit_username_skips_request_username_lookup(self, mock_get_request_username):
        headers = json.loads(get_request_api_headers({"bk_username": "admin"}))

        self.assertEqual(headers["bk_username"], "admin")
        mock_get_request_username.assert_not_called()

    @patch("apps.api.base.get_request_username", return_value="request-user")
    def test_missing_username_uses_request_username(self, mock_get_request_username):
        headers = json.loads(get_request_api_headers({}))

        self.assertEqual(headers["bk_username"], "request-user")
        mock_get_request_username.assert_called_once_with()


class ApiLogHeaderSanitizationTest(SimpleTestCase):
    def test_sanitize_headers_redacts_credentials_without_mutating_request_headers(self):
        secret = "".join(["credential", "-", "value"])
        headers = CaseInsensitiveDict(
            {
                "Authorization": f"Bearer {secret}",
                "X-Bkapi-Authorization": json.dumps({"bk_app_code": "demo", "bk_app_secret": secret}),
                "Cookie": f"session={secret}",
                "X-Bkapi-Jwt": secret,
                "X-Api-Key": secret,
                "X-Request-Id": "request-1",
            }
        )

        sanitized = sanitize_headers(headers)

        self.assertEqual(sanitized["Authorization"], REDACTED_HEADER_VALUE)
        self.assertEqual(sanitized["X-Bkapi-Authorization"], REDACTED_HEADER_VALUE)
        self.assertEqual(sanitized["Cookie"], REDACTED_HEADER_VALUE)
        self.assertEqual(sanitized["X-Bkapi-Jwt"], REDACTED_HEADER_VALUE)
        self.assertEqual(sanitized["X-Api-Key"], REDACTED_HEADER_VALUE)
        self.assertEqual(sanitized["X-Request-Id"], "request-1")
        self.assertIn(secret, headers["X-Bkapi-Authorization"])

    @patch("apps.api.base.logger.info")
    def test_data_api_log_uses_sanitized_header_copy(self, mock_logger_info):
        secret = "".join(["credential", "-", "value"])
        api = DataAPI(method="GET", url="https://example.test/api", module="test")
        raw_response = Mock(status_code=200)
        raw_response.json.return_value = {"result": True, "data": {}, "message": "", "code": "0"}

        def fake_send(*args, **kwargs):
            api.headers = CaseInsensitiveDict(
                {
                    "X-Bkapi-Authorization": json.dumps(
                        {"bk_app_code": "demo", "bk_app_secret": secret, "bk_username": "admin"}
                    ),
                    "X-Request-Id": "request-1",
                }
            )
            return raw_response

        with patch.object(api, "_send", side_effect=fake_send):
            api._send_request({}, 10, "request-1", False, "tenant-1")

        log_message = mock_logger_info.call_args.args[0]
        self.assertNotIn(secret, log_message)
        self.assertIn(f"X-Bkapi-Authorization': '{REDACTED_HEADER_VALUE}", log_message)
        self.assertIn("X-Request-Id': 'request-1", log_message)
