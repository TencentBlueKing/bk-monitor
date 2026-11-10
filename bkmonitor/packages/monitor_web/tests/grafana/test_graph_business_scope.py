from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from bkmonitor.middlewares.authentication import ApiTokenAuthenticationMiddleware
from bkmonitor.models import ApiAuthToken
from bkmonitor.utils.common_utils import fetch_biz_id_from_request
from bkmonitor.utils.local import local
from monitor_web.grafana.permissions import GrafanaRole
from monitor_web.grafana.resources.unify_query import GraphUnifyQueryResource
from monitor_web.grafana.views import GrafanaViewSet


@override_settings(SKIP_IAM_PERMISSION_CHECK=False)
class TestGraphBusinessScope(SimpleTestCase):
    path = "/rest/v2/grafana/time_series/unify_query/"
    action = "time_series/unify_query"

    def setUp(self):
        if not hasattr(GrafanaViewSet, self.action):
            GrafanaViewSet.generate_endpoint()
        self.view = GrafanaViewSet.as_view({"post": self.action})
        self.user = SimpleNamespace(
            username="chart-reader", tenant_id="system", is_authenticated=True, is_superuser=False
        )
        self.tenant_check = self.start_patch("monitor_web.grafana.permissions.is_biz_in_tenant", return_value=True)
        self.start_patch("bkmonitor.iam.drf.is_biz_in_tenant", return_value=True)
        self.dashboard = self.start_patch(
            "monitor_web.grafana.permissions.DashboardPermission.has_permission",
            return_value=(True, GrafanaRole.Anonymous, {}),
        )
        self.cache_key = self.start_patch(
            "monitor_web.grafana.permissions.GrafanaReadPermission._allow_cache_key", return_value=None
        )
        self.query = self.start_patch_object(GraphUnifyQueryResource, "perform_request", return_value={"series": []})
        self.iam = self.start_patch("bkmonitor.iam.drf.Permission")
        self.iam.return_value._is_allowed_request.return_value = True
        self.addCleanup(local.clear)

    def start_patch(self, *args, **kwargs):
        patcher = patch(*args, **kwargs)
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def start_patch_object(self, *args, **kwargs):
        patcher = patch.object(*args, **kwargs)
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def params(self):
        return {
            "bk_biz_id": 2,
            "start_time": 60,
            "end_time": 120,
            "expression": "A",
            "query_configs": [
                {
                    "data_source_label": "prometheus",
                    "data_type_label": "time_series",
                    "promql": 'memory{namespace="alpha"}',
                }
            ],
        }

    def token(self):
        return ApiAuthToken(
            token="isolated-share-token",
            type="kubernetes",
            namespaces=["biz#2"],
            params={
                "lock_search": True,
                "start_time": 60,
                "end_time": 120,
                "default_time_range": [],
                "data": {
                    "name": "k8s",
                    "path": "/k8s",
                    "query": {"sceneId": "kubernetes", "sceneType": "overview", "dashboardId": "pod"},
                },
            },
        )

    def post(self, params=None, url_biz_id=2, route_biz_id=None, token=None, **attrs):
        path = self.path if url_biz_id is None else f"{self.path}?bk_biz_id={url_biz_id}"
        request = APIRequestFactory().post(path, self.params() if params is None else params, format="json")
        route_kwargs = {} if route_biz_id is None else {"bk_biz_id": route_biz_id}
        request.biz_id = fetch_biz_id_from_request(request, route_kwargs)
        request.user = self.user
        for key, value in attrs.items():
            setattr(request, key, value)
        force_authenticate(request, user=self.user)
        local.current_request = request
        if token:
            request.META["HTTP_AUTHORIZATION"] = f"Bearer {token.token}"
            denied = ApiTokenAuthenticationMiddleware(lambda _: None).api_token_auth(request, self.view)
            if denied is not None:
                return denied
        return self.view(request)

    def test_body_business_must_match_query_business_before_dashboard_grant(self):
        self.dashboard.return_value = (True, GrafanaRole.Viewer, {})
        response = self.post({**self.params(), "bk_biz_id": 3})
        self.assertEqual(response.status_code, 403)
        self.dashboard.assert_not_called()
        self.cache_key.assert_not_called()
        self.query.assert_not_called()

    def test_body_business_must_match_url_business(self):
        self.dashboard.return_value = (True, GrafanaRole.Viewer, {})
        response = self.post({**self.params(), "bk_biz_id": 3}, url_biz_id=None, route_biz_id=2)
        self.assertEqual(response.status_code, 403)
        self.dashboard.assert_not_called()
        self.query.assert_not_called()

    def test_business_mismatch_is_denied_before_cache_grant(self):
        self.cache_key.return_value = "cached-chart"
        with patch("monitor_web.grafana.permissions.cache.get", return_value=True) as cache_get:
            response = self.post({**self.params(), "bk_biz_id": 3})
        self.assertEqual(response.status_code, 403)
        cache_get.assert_not_called()
        self.query.assert_not_called()

    def test_business_mismatch_is_denied_before_elevated_grants(self):
        self.dashboard.return_value = (True, GrafanaRole.Admin, {})
        for attrs in ({"skip_check": True}, {"external_user": "partner"}, {}):
            with self.subTest(attrs=attrs):
                self.user.is_superuser = not attrs
                response = self.post({**self.params(), "bk_biz_id": 3}, **attrs)
                self.assertEqual(response.status_code, 403)
        self.dashboard.assert_not_called()
        self.query.assert_not_called()

    @override_settings(SKIP_IAM_PERMISSION_CHECK=True)
    def test_business_mismatch_is_denied_with_global_iam_bypass(self):
        response = self.post({**self.params(), "bk_biz_id": 3})
        self.assertEqual(response.status_code, 403)
        self.dashboard.assert_not_called()
        self.query.assert_not_called()

    def test_business_mismatch_is_denied_before_share_grant(self):
        token = self.token()
        with (
            patch.object(ApiAuthToken.objects, "get", return_value=token),
            patch("bkmonitor.share.api_auth_resource.check_api_permission") as check_share,
        ):
            response = self.post({**self.params(), "bk_biz_id": 3}, token=token)
        self.assertEqual(response.status_code, 403)
        self.dashboard.assert_not_called()
        check_share.assert_not_called()
        self.query.assert_not_called()

    def test_other_tenant_is_denied_before_every_grant(self):
        self.tenant_check.return_value = False
        self.dashboard.return_value = (True, GrafanaRole.Admin, {})
        self.cache_key.return_value = "cached-chart"
        with patch("monitor_web.grafana.permissions.cache.get", return_value=True) as cache_get:
            response = self.post(skip_check=True)
        self.assertEqual(response.status_code, 403)
        self.tenant_check.assert_called_once_with("2", "system")
        cache_get.assert_not_called()
        self.dashboard.assert_not_called()
        self.query.assert_not_called()

    def test_matching_business_keeps_dashboard_access(self):
        self.dashboard.return_value = (True, GrafanaRole.Viewer, {})
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.dashboard.call_args.args[2], "2")
        self.assertEqual(self.query.call_args.args[0]["bk_biz_id"], 2)
        self.iam.assert_not_called()

    def test_body_only_business_keeps_normal_queries(self):
        response = self.post(url_biz_id=None)
        self.assertEqual(response.status_code, 200)
        self.tenant_check.assert_called_once_with("2", "system")
        self.query.assert_called_once()

    def test_matching_string_business_keeps_normal_queries(self):
        response = self.post({**self.params(), "bk_biz_id": "2"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.query.call_args.args[0]["bk_biz_id"], 2)

    def test_negative_space_keeps_the_existing_business_contract(self):
        response = self.post({**self.params(), "bk_biz_id": -2}, url_biz_id=-2)
        self.assertEqual(response.status_code, 200)
        self.tenant_check.assert_called_once_with("-2", "system")
        self.assertEqual(self.query.call_args.args[0]["bk_biz_id"], -2)

    def test_matching_business_keeps_cached_access(self):
        self.cache_key.return_value = "cached-chart"
        with patch("monitor_web.grafana.permissions.cache.get", return_value=True):
            response = self.post()
        self.assertEqual(response.status_code, 200)
        self.dashboard.assert_not_called()
        self.query.assert_called_once()

    def test_matching_business_keeps_iam_access(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.iam.return_value._is_allowed_request.assert_called_once()
        self.query.assert_called_once()

    def test_matching_business_keeps_request_iam_bypass(self):
        response = self.post(skip_check=True)
        self.assertEqual(response.status_code, 200)
        self.iam.return_value._is_allowed_request.assert_not_called()
        self.query.assert_called_once()

    def test_missing_body_business_keeps_serializer_validation(self):
        self.dashboard.return_value = (True, GrafanaRole.Viewer, {})
        params = self.params()
        params.pop("bk_biz_id")
        response = self.post(params)
        self.assertEqual(response.status_code, 500)
        self.assertIn("bk_biz_id", response.data["message"])
        self.dashboard.assert_called_once()
        self.query.assert_not_called()

    def test_missing_business_keeps_the_existing_default_permission_behavior(self):
        response = self.post({}, url_biz_id=None)
        self.assertEqual(response.status_code, 500)
        self.tenant_check.assert_not_called()
        self.dashboard.assert_not_called()
        self.query.assert_not_called()

    def test_datasource_test_get_without_business_keeps_working(self):
        request = APIRequestFactory().get("/rest/v2/grafana/")
        request.biz_id = fetch_biz_id_from_request(request, {})
        force_authenticate(request, user=self.user)
        response = GrafanaViewSet.as_view({"get": "list"})(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, "OK")
        self.tenant_check.assert_not_called()
        self.dashboard.assert_not_called()

    def test_functions_get_without_body_business_keeps_working(self):
        self.dashboard.return_value = (True, GrafanaRole.Viewer, {})
        request = APIRequestFactory().get("/rest/v2/grafana/time_series/functions/?bk_biz_id=2")
        request.biz_id = fetch_biz_id_from_request(request, {})
        force_authenticate(request, user=self.user)
        response = GrafanaViewSet.as_view({"get": "time_series/functions"})(request)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.tenant_check.assert_not_called()

    def test_kubernetes_share_still_runs_its_existing_parameter_checks(self):
        token = self.token()
        self.iam.return_value._is_allowed_request.return_value = False
        params = {**self.params(), "start_time": 61}
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.post(params, token=token)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error_details"]["type"], "SearchLockedError")
        self.iam.return_value._is_allowed_request.assert_not_called()
        self.query.assert_not_called()
