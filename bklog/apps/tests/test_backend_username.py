from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.api.modules.utils import update_bkdata_auth_info
from apps.utils import local


@override_settings(ENABLE_MULTI_TENANT_MODE=False, BK_ADMIN_USERNAME=" service-login ")
class BackendUsernameTest(SimpleTestCase):
    def setUp(self):
        local._single_tenant_admin_username.cache_clear()
        self.addCleanup(local._single_tenant_admin_username.cache_clear)

    @patch.object(local.BKLoginApi, "batch_lookup_virtual_user", return_value=[{"bk_username": "virtual-id"}])
    def test_background_identity(self, lookup):
        self.assertEqual(local.get_backend_username(bk_tenant_id="system"), "virtual-id")
        with override_settings(FEATURE_TOGGLE={}):
            params = update_bkdata_auth_info({})
        self.assertEqual(params["bk_username"], "virtual-id")
        self.assertEqual(params["operator"], "virtual-id")
        lookup.assert_called_once_with(
            {
                "bk_tenant_id": "default",
                "lookup_field": "login_name",
                "lookups": "service-login",
                "bk_username": "admin",
            },
            bk_tenant_id="default",
        )

    @patch.object(local.BKLoginApi, "batch_lookup_virtual_user")
    def test_fallback_and_token(self, lookup):
        for login in (None, "", "  "):
            with override_settings(BK_ADMIN_USERNAME=login):
                self.assertEqual(local.get_backend_username(), "admin")
        with override_settings(FEATURE_TOGGLE={"bkdata_token_auth": "on"}, BKDATA_DATA_TOKEN="test-token"):
            params = update_bkdata_auth_info({"operator": "request-user"})
        self.assertEqual(params["operator"], "request-user")
        self.assertNotIn("bk_username", params)
        lookup.assert_not_called()

    @patch.object(local.BKLoginApi, "batch_lookup_virtual_user", side_effect=[[], [{"bk_username": "recovered"}]])
    def test_failed_lookup_is_retried(self, lookup):
        with self.assertRaises(local.BaseException):
            local.get_backend_username()
        self.assertEqual(local.get_backend_username(), "recovered")

    def test_lookup_sends_default_tenant_header_and_preserves_request_user(self):
        import json
        from unittest.mock import Mock

        from apps.api.base import get_request_api_headers

        response = Mock(status_code=200)
        response.json.return_value = {"code": 0, "result": True, "data": [{"bk_username": "virtual-id"}]}
        with patch("requests.sessions.Session.request", return_value=response) as send:
            self.assertEqual(local.get_backend_username(bk_tenant_id="system"), "virtual-id")
            resource = local.BKLoginApi.batch_lookup_virtual_user
            self.assertEqual(resource.headers["X-Bk-Tenant-Id"], "default")
            self.assertEqual(json.loads(resource.headers["X-Bkapi-Authorization"])["bk_username"], "admin")
            self.assertIn("/api/v3/open/tenant/virtual-users/-/lookup/", send.call_args.kwargs["url"])
            self.assertEqual(send.call_args.kwargs["params"]["lookups"], "service-login")
            self.assertEqual(
                json.loads(get_request_api_headers({"bk_username": "request-user"}))["bk_username"], "request-user"
            )
            send.assert_called_once()

    @override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_ADMIN_USERNAME=None)
    @patch.object(local.BKLoginApi, "batch_lookup_virtual_user")
    def test_multi_tenant_refreshes_admin_on_each_request(self, lookup):
        lookup.side_effect = [[{"bk_username": "before"}], [{"bk_username": "after"}]]
        self.assertEqual(local.get_backend_username(bk_tenant_id="tenant-a"), "before")
        self.assertEqual(local.get_backend_username(bk_tenant_id="tenant-a"), "after")
        self.assertEqual(lookup.call_count, 2)
        self.assertEqual(lookup.call_args.args[0]["lookups"], "bk_admin")
        self.assertEqual(lookup.call_args.kwargs["bk_tenant_id"], "tenant-a")

    @patch.object(local.BKLoginApi, "batch_lookup_virtual_user", return_value=[{"bk_username": "virtual-id"}])
    def test_etl_uses_request_user_then_background_identity(self, lookup):
        from unittest.mock import Mock
        from apps.log_databus.handlers.etl import bkbase

        with (
            patch.object(bkbase.BkDataDatabusApi, "delete_tasks") as stop,
            patch.object(bkbase.BkDataDatabusApi, "post_tasks") as start,
            patch.object(local.sys, "argv", ["celery"]),
            patch.object(local, "get_request", return_value=Mock(user=Mock(username="request-user"))) as request,
        ):
            bkbase.BKBaseEtlHandler.start_bkdata_clean("sample")
            self.assertEqual(start.call_args.kwargs["params"]["bk_username"], "request-user")
            lookup.assert_not_called()
            request.return_value = None
            bkbase.BKBaseEtlHandler.restart_bkdata_clean("sample")
            self.assertEqual(stop.call_args.kwargs["params"]["bk_username"], "virtual-id")
            self.assertEqual(start.call_args.kwargs["params"]["bk_username"], "virtual-id")
            with override_settings(BK_ADMIN_USERNAME=" "):
                bkbase.BKBaseEtlHandler.start_bkdata_clean("sample")
                self.assertEqual(start.call_args.kwargs["params"]["bk_username"], "admin")
            lookup.assert_called_once()

    @patch.object(local.BKLoginApi, "batch_lookup_virtual_user", return_value=[{"bk_username": "virtual-id"}])
    def test_route_checker_sends_resolved_operator(self, lookup):
        from unittest.mock import Mock
        from apps.log_databus.handlers.check_collector.checker import route_checker

        checker = route_checker.RouteChecker(1, Mock())
        with (
            patch.object(route_checker.GseApi, "query_route", return_value=[]) as route,
            patch.object(route_checker.GseApi, "query_stream_to", return_value=[]) as stream,
        ):
            checker.query_route()
            checker.query_stream_to({"stream_to": {"stream_to_id": 1}})
        for call in (route, stream):
            self.assertEqual(call.call_args.args[0]["operation"]["operator_name"], "virtual-id")
        lookup.assert_called_once()

    @patch.object(local.BKLoginApi, "batch_lookup_virtual_user", return_value=[{"bk_username": "virtual-id"}])
    def test_agent_checker_job_identity(self, lookup):
        from unittest.mock import Mock
        from apps.log_databus.handlers.check_collector.checker import agent_checker

        checker = agent_checker.AgentChecker(1, {}, 1, "", "", Mock())
        with (
            patch.object(agent_checker.JobHelper, "execute_script", return_value={"job_instance_id": 1}) as execute,
            patch.object(agent_checker.JobApi, "get_job_instance_status", return_value={"finished": True}) as status,
            patch.object(agent_checker.time, "sleep"),
        ):
            checker.execute_script()
            checker.get_job_ip_status()
        self.assertEqual(execute.call_args.kwargs["bk_username"], "virtual-id")
        self.assertEqual(status.call_args.kwargs["params"]["bk_username"], "virtual-id")
        lookup.assert_called_once()
