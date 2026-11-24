import json
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

    def test_old_selector_search_and_saved_account(self):
        for query, method, expected in [
            ({"fuzzy_lookups": "ali"}, "search_users", {"keyword": "ali"}),
            ({"exact_lookups": "alice"}, "lookup_users", {"lookup_field": "login_name", "lookups": "alice"}),
        ]:
            with self.subTest(query=query), patch.object(views, "BKLoginApi", self.users):
                upstream = Mock(return_value=[self.account])
                setattr(self.users, method, upstream)
                response = views.list_users(self.request.get("/", {**query, "callback": "USER_LIST_CALLBACK_0"}))
                upstream.assert_called_once_with(expected)
                data = json.loads(response.content.decode().removeprefix("USER_LIST_CALLBACK_0(").removesuffix(")"))
                self.assertEqual(
                    data["data"], {"count": 1, "results": [{"username": "alice", "display_name": "Alice", "logo": ""}]}
                )

    def test_gateway_lookup_preserves_login_name(self):
        self.users.lookup_users = Mock(return_value=[{**self.account, "time_zone": "UTC"}])
        result = self.users.get_user({"username": "alice"})
        self.assertEqual((result["username"], result["chname"], result["time_zone"]), ("alice", "Alice", "UTC"))
        self.users.lookup_users.assert_called_once_with({"lookup_field": "login_name", "lookups": "alice"})

    def test_department_uses_gateway_id_and_ancestors(self):
        self.users.lookup_users = Mock(return_value=[self.account])
        self.users.user_departments = Mock(return_value=[{"name": "Team", "ancestors": [{"name": "Org"}]}])
        result = self.users.list_department_profiles({"id": "alice", "with_family": True})
        self.users.user_departments.assert_called_once_with({"bk_username": "tenant-user-id", "with_ancestors": "true"})
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
