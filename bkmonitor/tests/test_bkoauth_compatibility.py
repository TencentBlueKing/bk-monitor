"""验证 Open/内网的真实 bkoauth 初始化、落库和无请求恢复，网络边界使用模拟响应。"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class TestBkoauthCompatibility(unittest.TestCase):
    # bkoauth 在 import 时固化配置；每个进程从真实项目配置初始化，避免 mock 配置掩盖环境差异。
    BOOTSTRAP = """
import django
from django.conf import settings
from config import default as monitor_config

settings.configure(
    INSTALLED_APPS=[
        "django.contrib.auth", "django.contrib.contenttypes",
        *(["bkoauth"] if "bkoauth" in monitor_config.INSTALLED_APPS else []),
    ],
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.environ["OAUTH_TEST_DB"]}},
    APP_CODE="test-app", SECRET_KEY="test-secret", RUN_MODE="PRODUCT", RUN_VER=monitor_config.RUN_VER,
    OAUTH_API_URL=getattr(monitor_config, "OAUTH_API_URL", ""),
    OAUTH_COOKIES_PARAMS=getattr(monitor_config, "OAUTH_COOKIES_PARAMS", {}),
    BKAUTH_BACKEND_TYPE=getattr(monitor_config, "BKAUTH_BACKEND_TYPE", ""),
    USE_TZ=True, DEFAULT_AUTO_FIELD="django.db.models.AutoField",
)
django.setup()
"""

    def setUp(self):
        self.db_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.db_directory.cleanup)
        self.db_name = str(Path(self.db_directory.name) / "oauth.sqlite3")

    def run_process(self, script, *, run_ver="open", oauth_url="https://oauth.example.com", extra_env=None):
        env = os.environ.copy()
        for key in ("DJANGO_SETTINGS_MODULE", "OAUTH_API_URL", "OAUTH_COOKIES_PARAMS", "BKAUTH_BACKEND_TYPE"):
            env.pop(key, None)
        env.update(
            BKPAAS_ENGINE_REGION=run_ver,
            DJANGO_CONF_MODULE="conf.web.development.community",
            BKAPP_DEPLOY_PLATFORM="community",
            BK_PAAS_HOST="http://localhost",
            BK_COMPONENT_API_URL="http://localhost",
            APP_ID="test-app",
            APP_TOKEN="test-secret",
            OAUTH_API_URL=oauth_url,
            OAUTH_TEST_DB=self.db_name,
        )
        env.update(extra_env or {})
        result = subprocess.run(
            [sys.executable, "-c", "import os\n" + self.BOOTSTRAP + textwrap.dedent(script)],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_open_without_oauth_preserves_disabled_app_and_login_signal(self):
        self.run_process(
            """
            import sys
            from django.contrib.auth.signals import user_logged_in
            from patches.bkoauth import patch_bkoauth_update_user_access_token
            assert "bkoauth" not in monitor_config.INSTALLED_APPS
            receivers = list(user_logged_in.receivers)
            patch_bkoauth_update_user_access_token()
            assert "bkoauth.signals" not in sys.modules
            assert user_logged_in.receivers == receivers
            """,
            oauth_url="",
        )

    def test_open_disables_automatic_login_exchange_but_preserves_other_receivers(self):
        self.run_process(
            """
            from unittest.mock import Mock, patch
            from django.contrib.auth.signals import user_logged_in
            from bkoauth.client import oauth_client
            from bkoauth.signals import update_user_access_token as original_receiver
            from patches.bkoauth import patch_bkoauth_update_user_access_token
            assert type(oauth_client).__name__ == "OAuthClientEE"
            assert oauth_client.is_enabled
            other_receiver = Mock()
            original_count = len(user_logged_in.receivers)
            assert original_receiver in user_logged_in._live_receivers(None)
            user_logged_in.connect(other_receiver)
            patch_bkoauth_update_user_access_token()
            patch_bkoauth_update_user_access_token()
            with patch.object(oauth_client, "get_access_token") as exchange:
                user_logged_in.send(sender=object, request=object(), user=Mock())
                exchange.assert_not_called()
            other_receiver.assert_called_once()
            assert len(user_logged_in.receivers) == original_count
            """,
        )

    def test_internal_login_patch_keeps_existing_exchange(self):
        self.run_process(
            """
            from unittest.mock import Mock, patch
            from django.contrib.auth.signals import user_logged_in
            from bkoauth.client import oauth_client
            from patches.bkoauth import patch_bkoauth_update_user_access_token
            assert type(oauth_client).__name__ == "OAuthClient"
            patch_bkoauth_update_user_access_token()
            patch_bkoauth_update_user_access_token()
            with patch.object(oauth_client, "get_access_token", return_value=object()) as exchange:
                request = object()
                user_logged_in.send(sender=object, request=request, user=Mock())
                exchange.assert_called_once_with(request)
            """,
            run_ver="ieod",
            extra_env={"OAUTH_COOKIES_PARAMS": json.dumps({"rtx": "bk_uid", "bk_ticket": "bk_ticket"})},
        )

    def test_open_web_persistence_and_worker_refresh_across_processes(self):
        self.verify_persistence_and_refresh("open", {"bk_token": "fake-login"})

    def test_internal_web_persistence_and_worker_refresh_across_processes(self):
        self.verify_persistence_and_refresh("ieod", {"rtx": "test-user", "bk_ticket": "fake-login"})

    def verify_persistence_and_refresh(self, run_ver, auth_params):
        extra_env = {}
        if run_ver == "ieod":
            extra_env["OAUTH_COOKIES_PARAMS"] = json.dumps({key: key for key in auth_params})
        extra_env["OAUTH_TEST_PARAMS"] = json.dumps(auth_params)
        self.run_process(
            """
            import json
            from types import SimpleNamespace
            from unittest.mock import Mock, patch
            from django.core.management import call_command
            from bkoauth.client import oauth_client
            from bkoauth.models import AccessToken
            call_command("migrate", "bkoauth", verbosity=0)
            is_open = settings.RUN_VER == "open"
            auth_params = json.loads(os.environ["OAUTH_TEST_PARAMS"])
            request = SimpleNamespace(
                user=SimpleNamespace(username="test-user"), COOKIES=auth_params,
                session={}, GET={}, META={"REMOTE_ADDR": "127.0.0.1"},
            )
            response = {"data": {"access_token": "test-access-1", "refresh_token": "test-refresh-1", "expires_in": 172800}}
            response.update({"code": 0} if is_open else {"result": True})
            with patch("bkoauth.client.rpool.post" if is_open else "bkoauth.client.rpool.get") as send:
                send.return_value = Mock(json=lambda: response)
                token = oauth_client.get_access_token(request)
                assert AccessToken.objects.get(user_id="test-user", env_name="prod").pk == token.pk
                assert send.call_count == 1
                if is_open:
                    assert send.call_args.args[0] == "https://oauth.example.com/api/v1/auth/access-tokens"
                    assert send.call_args.kwargs["json"] == dict(grant_type="authorization_code", id_provider="bk_login", **auth_params)
                    assert send.call_args.kwargs["headers"]["X-BK-APP-CODE"] == "test-app"
                else:
                    assert send.call_args.args[0] == "https://oauth.example.com/auth_api/token/"
                    assert all(send.call_args.kwargs["params"][key] == value for key, value in auth_params.items())
            """,
            run_ver=run_ver,
            extra_env=extra_env,
        )
        # 独立 Worker 进程不携带 request/Cookie，仅读取 Web 写入的数据库，并通过 refresh_token 续期。
        self.run_process(
            """
            from datetime import timedelta
            from unittest.mock import Mock, patch
            from django.utils import timezone
            from bkoauth.client import oauth_client
            from bkoauth.models import AccessToken
            is_open = settings.RUN_VER == "open"
            method = "bkoauth.client.rpool.post" if is_open else "bkoauth.client.rpool.get"
            with patch(method) as send:
                assert oauth_client.get_access_token_by_user("test-user").access_token == "test-access-1"
                send.assert_not_called()
                AccessToken.objects.update(expires=timezone.now() + timedelta(seconds=30))
                response = {"data": {"access_token": "test-access-2", "refresh_token": "test-refresh-2", "expires_in": 172800}}
                response.update({"code": 0} if is_open else {"result": True})
                send.return_value = Mock(json=lambda: response)
                token = oauth_client.get_access_token_by_user("test-user")
                assert token.access_token == "test-access-2"
                assert AccessToken.objects.get(user_id="test-user").refresh_token == "test-refresh-2"
                if is_open:
                    assert send.call_args.args[0] == "https://oauth.example.com/api/v1/auth/access-tokens/refresh"
                    assert send.call_args.kwargs["json"] == {"refresh_token": "test-refresh-1"}
                else:
                    assert send.call_args.args[0] == "https://oauth.example.com/auth_api/refresh_token/"
                    assert send.call_args.kwargs["params"]["refresh_token"] == "test-refresh-1"
            """,
            run_ver=run_ver,
            extra_env=extra_env,
        )
