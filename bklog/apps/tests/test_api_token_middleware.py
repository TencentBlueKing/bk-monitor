from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.middleware.api_token_middleware import ApiTokenAuthenticationMiddleware


class ApiTokenAuthenticationMiddlewareTest(SimpleTestCase):
    def test_authenticated_request_without_token_skips_parent_login_check(self):
        request = SimpleNamespace(META={}, user=SimpleNamespace(is_authenticated=True))
        middleware = ApiTokenAuthenticationMiddleware(Mock())

        with patch(
            "apps.middleware.api_token_middleware.LoginRequiredMiddleware.process_view",
            return_value="login-check",
        ) as process_view:
            result = middleware.process_view(request, Mock())

        self.assertIsNone(result)
        process_view.assert_not_called()

    def test_callable_authenticated_request_without_token_skips_parent_login_check(self):
        request = SimpleNamespace(META={}, user=SimpleNamespace(is_authenticated=Mock(return_value=True)))
        middleware = ApiTokenAuthenticationMiddleware(Mock())

        with patch(
            "apps.middleware.api_token_middleware.LoginRequiredMiddleware.process_view",
            return_value="login-check",
        ) as process_view:
            result = middleware.process_view(request, Mock())

        self.assertIsNone(result)
        request.user.is_authenticated.assert_called_once_with()
        process_view.assert_not_called()

    def test_unauthenticated_request_without_token_uses_parent_login_check(self):
        request = SimpleNamespace(META={}, user=SimpleNamespace(is_authenticated=False))
        middleware = ApiTokenAuthenticationMiddleware(Mock())

        with patch(
            "apps.middleware.api_token_middleware.LoginRequiredMiddleware.process_view",
            return_value="login-check",
        ) as process_view:
            result = middleware.process_view(request, Mock(), "arg", key="value")

        self.assertEqual(result, "login-check")
        process_view.assert_called_once()

    def test_request_with_token_keeps_token_auth_flow(self):
        request = SimpleNamespace(META={"HTTP_X_BKLOG_TOKEN": "token"}, user=SimpleNamespace(is_authenticated=True))
        record = SimpleNamespace(type="custom")
        middleware = ApiTokenAuthenticationMiddleware(Mock())

        with (
            patch("apps.middleware.api_token_middleware.ApiAuthToken.objects.get", return_value=record) as get_token,
            patch.object(middleware, "_handle_authentication") as handle_authentication,
            patch("apps.middleware.api_token_middleware.LoginRequiredMiddleware.process_view") as process_view,
        ):
            result = middleware.process_view(request, Mock())

        self.assertIsNone(result)
        get_token.assert_called_once_with(token="token")
        handle_authentication.assert_called_once_with(request, record, "token")
        process_view.assert_not_called()
