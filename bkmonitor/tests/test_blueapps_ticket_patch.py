"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""Run standalone with PYTHONPATH=bkmonitor python bkmonitor/tests/test_blueapps_ticket_patch.py."""

import builtins
import importlib.util
import unittest
from unittest.mock import Mock, patch

from django.conf import settings

if __name__ == "__main__":
    import django

    settings.configure(
        SECRET_KEY="ticket-regression-test",
        RUN_VER="ieod",
        ROLE="web",
        LOGIN_CACHE_EXPIRED=300,
        USE_TZ=True,
        INSTALLED_APPS=["django.contrib.auth", "django.contrib.contenttypes"],
        CACHES={
            name: {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": name}
            for name in ("default", "login_db")
        },
    )
    django.setup()

from django.contrib import auth
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sessions.backends.cache import SessionStore
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from blueapps.account.components.bk_ticket import middlewares
from patches.blueapps import authenticate, patch_ticket_authenticate


class TicketAuthenticateTests(unittest.TestCase):
    def setUp(self):
        middlewares.cache.clear()
        self.original = middlewares.LoginRequiredMiddleware.authenticate
        self.addCleanup(setattr, middlewares.LoginRequiredMiddleware, "authenticate", self.original)
        # AppConfig.ready may already have patched the shared class in the full suite.
        spec = importlib.util.spec_from_file_location("ticket_middleware_baseline", middlewares.__file__)
        baseline = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(baseline)
        self.upstream_authenticate = baseline.LoginRequiredMiddleware.authenticate
        self.user = User(pk=1, username="example-user")
        self.user.backend = "django.contrib.auth.backends.ModelBackend"
        self.user.save = Mock()

    def request(self, expired=False):
        request = RequestFactory().get("/")
        request.COOKIES["bk_ticket"] = "example-ticket"
        request.session = SessionStore("a" * 32 if expired else None)
        request.user = AnonymousUser()
        return request

    def run_authentication(self, method, request, user):
        middlewares.LoginRequiredMiddleware.authenticate = method
        middleware = middlewares.LoginRequiredMiddleware(lambda request: None)
        with (
            patch.object(auth, "authenticate", return_value=user) as backend,
            patch.object(middlewares.cache, "set", wraps=middlewares.cache.set) as cache_set,
        ):
            result = middleware.authenticate(request)
        return result, backend, cache_set

    def test_first_and_expired_session_compare_original_and_patch(self):
        for expired in (False, True):
            for method, count in ((self.upstream_authenticate, 2), (authenticate, 1)):
                with self.subTest(expired=expired, patched=method is authenticate):
                    middlewares.cache.clear()
                    request = self.request(expired)
                    old_key = request.session.session_key
                    result, backend, cache_set = self.run_authentication(method, request, self.user)
                    self.assertIs(result, self.user)
                    self.assertEqual(backend.call_count, count)
                    self.assertNotEqual(old_key, request.session.session_key)
                    self.assertEqual(
                        middlewares.cache.get(request.session.session_key), {"bk_ticket": "example-ticket"}
                    )
                    if method is authenticate:
                        cache_set.assert_called_once_with(
                            request.session.session_key, {"bk_ticket": "example-ticket"}, settings.LOGIN_CACHE_EXPIRED
                        )
                        self.assertIsNone(middlewares.cache.get(None))

    def test_cache_hit_skips_backend(self):
        request = self.request()
        self.run_authentication(authenticate, request, self.user)
        result, backend, cache_set = self.run_authentication(authenticate, request, self.user)
        self.assertIs(result, self.user)
        backend.assert_not_called()
        cache_set.assert_not_called()

    def test_switch_user_flushes_session_and_caches_after_response_save(self):
        request = self.request()
        self.run_authentication(authenticate, request, self.user)
        old_key = request.session.session_key
        other = User(pk=2, username="other-user")
        other.backend = self.user.backend
        other.save = Mock()
        request.COOKIES["bk_ticket"] = "other-ticket"
        result, backend, cache_set = self.run_authentication(authenticate, request, other)
        self.assertIs(result, other)
        self.assertEqual(backend.call_count, 1)
        self.assertIsNone(request.session.session_key)
        cache_set.assert_not_called()
        self.assertIsNone(middlewares.cache.get(None))
        SessionMiddleware(lambda request: None).process_response(request, HttpResponse())
        self.assertIsNotNone(request.session.session_key)
        self.assertNotEqual(old_key, request.session.session_key)
        result, backend, cache_set = self.run_authentication(authenticate, request, other)
        self.assertIs(result, other)
        backend.assert_called_once()
        cache_set.assert_called_once_with(
            request.session.session_key, {"bk_ticket": "other-ticket"}, settings.LOGIN_CACHE_EXPIRED
        )
        self.assertEqual(request.session[auth.SESSION_KEY], "2")
        result, backend, cache_set = self.run_authentication(authenticate, request, other)
        self.assertIs(result, other)
        backend.assert_not_called()
        cache_set.assert_not_called()

    def test_rejected_user_does_not_reuse_authenticated_old_user(self):
        request = self.request()
        self.run_authentication(authenticate, request, self.user)
        old_key = request.session.session_key
        request.COOKIES["bk_ticket"] = "disabled-user-ticket"
        # The authentication backend rejects invalid tickets and disabled users.
        result, backend, cache_set = self.run_authentication(authenticate, request, None)
        self.assertIsNone(result)
        backend.assert_called_once()
        cache_set.assert_not_called()
        self.assertIs(request.user, self.user)
        self.assertEqual(request.session.session_key, old_key)
        self.assertEqual(middlewares.cache.get(old_key), {"bk_ticket": "example-ticket"})

    def test_same_user_new_ticket_updates_cache_without_session_rotation(self):
        request = self.request()
        self.run_authentication(authenticate, request, self.user)
        old_key = request.session.session_key
        request.COOKIES["bk_ticket"] = "renewed-ticket"
        result, backend, cache_set = self.run_authentication(authenticate, request, self.user)
        self.assertIs(result, self.user)
        backend.assert_called_once()
        self.assertEqual(request.session.session_key, old_key)
        cache_set.assert_called_once_with(old_key, {"bk_ticket": "renewed-ticket"}, settings.LOGIN_CACHE_EXPIRED)

    def test_invalid_ticket_does_not_login_or_cache(self):
        for ticket in (None, "rejected-ticket"):
            request = self.request()
            if ticket is None:
                request.COOKIES.clear()
            else:
                request.COOKIES["bk_ticket"] = ticket
            result, backend, cache_set = self.run_authentication(authenticate, request, None)
            self.assertIsNone(result)
            self.assertEqual(backend.call_count, int(ticket is not None))
            cache_set.assert_not_called()
            self.assertIsNone(request.session.session_key)
            self.assertFalse(request.user.is_authenticated)

    def test_installer_preserves_class_and_is_idempotent(self):
        from blueapps.account import conf

        original_class = middlewares.LoginRequiredMiddleware
        with (
            override_settings(ROLE="web"),
            patch.object(
                conf, "ConfFixture", Mock(LOGIN_REQUIRED_MIDDLEWARE="bk_ticket.middlewares.LoginRequiredMiddleware")
            ),
        ):
            patch_ticket_authenticate()
            patch_ticket_authenticate()
        self.assertIs(middlewares.LoginRequiredMiddleware, original_class)
        self.assertIs(original_class.authenticate, authenticate)

    def test_worker_and_non_ticket_configuration_skip_installation(self):
        from blueapps.account import conf

        with override_settings(ROLE="worker"), patch("builtins.__import__", wraps=builtins.__import__) as imports:
            patch_ticket_authenticate()
        self.assertFalse(any(call.args[0].startswith("blueapps.account") for call in imports.call_args_list))
        self.assertIs(middlewares.LoginRequiredMiddleware.authenticate, self.original)
        with (
            override_settings(ROLE="web"),
            patch.object(
                conf, "ConfFixture", Mock(LOGIN_REQUIRED_MIDDLEWARE="bk_token.middlewares.LoginRequiredMiddleware")
            ),
            patch("builtins.__import__", wraps=builtins.__import__) as imports,
        ):
            patch_ticket_authenticate()
        self.assertFalse(any("bk_ticket" in call.args[0] for call in imports.call_args_list))
        self.assertIs(middlewares.LoginRequiredMiddleware.authenticate, self.original)


if __name__ == "__main__":
    unittest.main()
