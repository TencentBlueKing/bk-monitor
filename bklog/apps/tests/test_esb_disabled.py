import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.api.modules.bk_login import _BKLoginApi
from apps.api.modules.bk_node import _BKNodeApi
from apps.api.modules.bkdata_query import _BkDataQueryApi
from apps.api.modules.cc import _CCApi
from apps.api.modules.cmsi import _CmsiApi
from apps.api.modules.gse import _GseApi
from apps.api.modules.job import _JobApi
from apps.api.modules.monitor import _MonitorApi
from apps.api.modules.transfer import _TransferApi
from apps.exceptions import ApiRequestError
from apps.feature_toggle.plugins.base import get_feature_toggle
from apps.log_commons import views
from apps.log_databus.tasks.itsm import failed_ticket_clean


@override_settings(ESB_DISABLED=True, ENABLE_MULTI_TENANT_MODE=False, PAAS_API_HOST="https://gateway.example.com")
class EsbDisabledTest(SimpleTestCase):
    def setUp(self):
        self.users = _BKLoginApi()
        self.account = {"bk_username": "tenant-user-id", "login_name": "alice", "display_name": "Alice"}
        self.request = RequestFactory()

    def test_gateway_business_error_is_reported(self):
        response = self.users.user_departments.after_request({"code": 1, "result": True, "data": None})
        self.assertFalse(response["result"])

    def test_old_selector_preserves_saved_tenant_user_id(self):
        self.users.lookup_users = Mock(return_value=[self.account])
        with patch.object(views, "BKLoginApi", self.users):
            response = views.list_users(self.request.get("/", {"exact_lookups": "tenant-user-id", "callback": "cb"}))
        data = json.loads(response.content.decode().removeprefix("cb(").removesuffix(")"))["data"]
        self.assertEqual(
            data, {"count": 1, "results": [{"username": "tenant-user-id", "display_name": "Alice", "logo": ""}]}
        )
        self.users.lookup_users.assert_called_once_with({"lookup_field": "bk_username", "lookups": "tenant-user-id"})

    def test_selector_search_pages_tenant_openapi_then_paginates_matches(self):
        self.assertEqual(
            self.users.list_users.url, "https://gateway.example.com/api/bk-user/prod/api/v3/open/tenant/users/"
        )
        other = {"bk_username": "other", "login_name": "other", "display_name": "Other"}
        self.users.list_users = Mock(
            side_effect=[
                {"count": 1001, "results": [self.account] + [other] * 999},
                {"count": 1001, "results": [{**self.account, "bk_username": "second-id"}]},
            ]
        )
        with patch.object(views, "BKLoginApi", self.users):
            response = views.list_users(self.request.get("/", {"fuzzy_lookups": "ALI", "page": 2, "page_size": 1}))
        self.assertEqual(
            json.loads(response.content)["data"],
            {"count": 2, "results": [{"username": "second-id", "display_name": "Alice", "logo": ""}]},
        )
        self.assertEqual(
            [c.args[0] for c in self.users.list_users.call_args_list], [{"page": n, "page_size": 1000} for n in (1, 2)]
        )

    def test_gateway_profile_and_department_use_saved_id(self):
        self.users.user_detail = Mock(return_value={**self.account, "time_zone": "UTC"})
        result = self.users.get_user({"username": "tenant-user-id"})
        self.assertEqual(
            (result["username"], result["chname"], result["time_zone"]), ("tenant-user-id", "Alice", "UTC")
        )
        self.users.user_detail.assert_called_once_with({"user_id": "tenant-user-id"})
        self.users.user_departments = Mock(return_value=[{"name": "Team", "ancestors": [{"name": "Org"}]}])
        result = self.users.list_department_profiles({"id": "tenant-user-id", "with_family": True})
        self.users.user_departments.assert_called_once_with({"user_id": "tenant-user-id", "with_ancestors": "true"})
        self.assertEqual(result[0]["family"], [{"name": "Org"}])

    @override_settings(
        FRONTEND_REPORT_DATA_ID=1,
        FRONTEND_REPORT_DATA_TOKEN="fixture",
        FRONTEND_REPORT_DATA_URL="https://events.example.com",
    )
    def test_report_is_sent_with_missing_department_or_api_error(self):
        for username, departments, dims in [
            ("alice", [{"family": [{"name": "Org"}], "name": "Team"}], ["Org", "Team", "", "", ""]),
            ("alice", [], [""] * 5),
            ("alice", ApiRequestError("offline", "request"), []),
            ("", [], []),
        ]:
            with self.subTest(username=username, dims=dims):
                reporter = views.FrontendEventViewSet()
                reporter.params_valid = Mock(
                    return_value={"dimensions": {"user_name": username}, "event_name": "view", "event_content": ""}
                )
                with (
                    patch.object(views.BKLoginApi, "list_department_profiles") as lookup,
                    patch.object(views.requests, "post") as post,
                ):
                    if isinstance(departments, Exception):
                        lookup.side_effect = departments
                    else:
                        lookup.return_value = departments
                    reporter.report(self.request.post("/"))
                    actual = post.call_args.kwargs["json"]["data"][0]["dimension"]
                    self.assertEqual([actual[k] for k in sorted(actual) if k.startswith("department_")], dims)
                    self.assertEqual(lookup.call_count, int(bool(username)))

    def test_collection_diagnostics_and_itsm(self):
        gse = _GseApi()
        self.assertEqual(gse.query_route.url, "https://gateway.example.com/api/bk-gse/prod/api/v2/data/query_route")
        self.assertEqual(
            gse.query_stream_to.url, "https://gateway.example.com/api/bk-gse/prod/api/v2/data/query_streamto"
        )
        with patch("apps.log_databus.tasks.itsm.ItsmHandler") as handler:
            failed_ticket_clean()
            handler.assert_not_called()
        self.assertEqual(get_feature_toggle("collect_itsm")().set_status({"status": "on"})["status"], "off")

    @override_settings(USE_APIGW=True)
    def test_system_clients_use_their_gateway(self):
        for client, name in [
            (_CCApi().get_app_list, "bk-cmdb"),
            (_JobApi().fast_execute_script, "bk-job"),
            (_CmsiApi().send_mail, "bk-cmsi"),
            (_BKNodeApi().create_subscription, "bk-nodeman"),
            (_BkDataQueryApi().query, "bk-base"),
            (_MonitorApi().search_alarm_strategy_v3, "bk-monitor"),
            (_TransferApi().get_data_id, "bk-monitor"),
        ]:
            with self.subTest(client=client.description):
                self.assertIn(f"/api/{name}/", client.url)


class LoginSettingsCompatibilityTest(SimpleTestCase):
    def test_login_strategy_and_final_gateway_template(self):
        # 设置在 Django 启动时解析，子进程避免复用当前测试进程已加载的配置。
        app_root = Path(__file__).resolve().parents[2]
        env = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "settings",
            "BK_API_URL_TMPL": "https://chart.example.test/{api_name}/",
        }
        script = """
import json
from django.conf import settings
template = settings.BK_API_URL_TMPL
from blueapps.account.components.bk_token.verification_strategy import is_esb_enabled, get_apigw_url
print(json.dumps([is_esb_enabled(), get_apigw_url("bk-login", "/verify/")]))
"""
        for switch, multi, custom, expected_esb, expected_url in [
            (None, False, True, True, "https://custom.example.test/bk-login//prod/verify/"),
            (None, True, True, False, "https://custom.example.test/bk-login//prod/verify/"),
            ("false", False, True, False, "https://custom.example.test/bk-login/prod/verify/"),
            ("false", False, False, False, "https://chart.example.test/bk-login/prod/verify/"),
        ]:
            with self.subTest(switch=switch, multi=multi, custom=custom):
                env["ENABLE_MULTI_TENANT_MODE"] = str(multi).lower()
                env["BKPAAS_MULTI_TENANT_MODE"] = str(not multi).lower()
                env.pop("BKPAAS_ESB_ENABLED", None)
                if switch is not None:
                    env["BKPAAS_ESB_ENABLED"] = switch
                env.pop("BKAPP_API_URL_TMPL", None)
                if custom:
                    env["BKAPP_API_URL_TMPL"] = "https://custom.example.test/{api_name}/"
                output = subprocess.check_output([sys.executable, "-c", script], cwd=app_root, env=env, text=True)
                self.assertEqual(json.loads(output.splitlines()[-1]), [expected_esb, expected_url])
