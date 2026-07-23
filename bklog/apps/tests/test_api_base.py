import json
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.api.base import get_request_api_headers


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
