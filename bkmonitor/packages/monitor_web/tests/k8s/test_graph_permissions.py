import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from bkmonitor.data_source.data_source import PrometheusTimeSeriesDataSource
from bkmonitor.middlewares.authentication import ApiTokenAuthenticationMiddleware
from bkmonitor.models import ApiAuthToken
from bkmonitor.share.handler import KubernetesApiAuthChecker
from bkmonitor.utils.common_utils import fetch_biz_id_from_request
from bkmonitor.utils.local import local
from monitor_web.grafana.permissions import GrafanaRole, GrafanaReadPermission
from monitor_web.grafana.resources.unify_query import GraphUnifyQueryResource
from monitor_web.k8s.core.federation import FederatedResourceScope
from monitor_web.k8s.views import ResourcesViewSet


@override_settings(SKIP_IAM_PERMISSION_CHECK=False)
class TestK8sGraphPermissions(SimpleTestCase):
    cluster_id = "BCS-K8S-92001"
    path = "/rest/v2/k8s/resources/graph_query/"

    def setUp(self):
        if not hasattr(ResourcesViewSet, "graph_query"):
            ResourcesViewSet.generate_endpoint()
        self.view = ResourcesViewSet.as_view({"post": "graph_query"})
        self.user = SimpleNamespace(
            username="chart-reader", tenant_id="system", is_authenticated=True, is_superuser=False
        )
        self.start_patch("monitor_web.k8s.permissions.is_biz_in_tenant", return_value=True)
        self.start_patch("bkmonitor.iam.drf.is_biz_in_tenant", return_value=True)
        self.dashboard = self.start_patch(
            "monitor_web.grafana.permissions.DashboardPermission.has_permission",
            return_value=(True, GrafanaRole.Anonymous, {}),
        )
        self.start_patch("monitor_web.grafana.permissions.GrafanaReadPermission._allow_cache_key", return_value=None)
        self.scope = self.start_patch("monitor_web.k8s.chart.get_federated_resource_scope", return_value=None)
        self.query = self.start_patch_object(GraphUnifyQueryResource, "perform_request", return_value={"series": []})
        self.iam = self.start_patch("bkmonitor.iam.drf.Permission")
        self.iam.return_value._is_allowed_request.return_value = True
        self.iam.return_value.prepare_apply_for_saas.return_value = ([], [])
        self.iam.return_value._apply_data_request.return_value = {}
        self.iam.return_value._apply_url_request.return_value = ""
        # The existing checker updates its required-key list while checking a detail query.
        self.start_patch_object(
            KubernetesApiAuthChecker, "where_params_map", deepcopy(KubernetesApiAuthChecker.where_params_map)
        )
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
            "bcs_cluster_id": self.cluster_id,
            "start_time": 60,
            "end_time": 120,
            "expression": "A",
            "query_configs": [
                {
                    "data_source_label": "prometheus",
                    "data_type_label": "time_series",
                    "promql": 'memory{namespace="alpha",pod_name="pod-a"}',
                    "where": [
                        {"key": "bcs_cluster_id", "method": "eq", "value": [self.cluster_id]},
                        {"key": "namespace", "method": "eq", "value": ["alpha"]},
                        {"key": "pod_name", "method": "eq", "value": ["pod-a"]},
                    ],
                }
            ],
        }

    def token(self, token_type="kubernetes"):
        return ApiAuthToken(
            token="isolated-share-token",
            type=token_type,
            namespaces=["biz#2"],
            params={
                "lock_search": True,
                "start_time": 60,
                "end_time": 120,
                "default_time_range": [],
                "data": {
                    "name": "k8s",
                    "path": "/k8s",
                    "params": {},
                    "query": {
                        "sceneId": "kubernetes",
                        "sceneType": "detail",
                        "dashboardId": "pod",
                        "filter-bcs_cluster_id": self.cluster_id,
                        "filter-namespace": "alpha",
                        "filter-pod_name": "pod-a",
                    },
                },
            },
        )

    def overview_token(self):
        token = self.token()
        token.params.update({"lock_search": False, "default_time_range": ["now-1h", "now"]})
        token.params["data"] = {
            "name": "k8s-new",
            "path": "/k8s-new",
            "params": {},
            "query": {
                "sceneId": "kubernetes",
                "scene": "performance",
                "cluster": self.cluster_id,
                "filterBy": json.dumps({"namespace": ["alpha"], "pod": ["pod-a"]}),
                "groupBy": json.dumps(["namespace", "pod"]),
                "activeTab": "chart",
                "from": "now-1h",
                "to": "now",
                "refreshInterval": "-1",
            },
        }
        return token

    def overview_params(self):
        params = self.params()
        params["query_configs"][0].pop("where")
        params["query_configs"][0]["filter_dict"] = {}
        return params

    def request(self, params=None, url_biz_id=2, token=None, **attrs):
        request = APIRequestFactory().post(
            f"{self.path}?bk_biz_id={url_biz_id}", params or self.params(), format="json"
        )
        request.biz_id = fetch_biz_id_from_request(request, {})
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

    def test_mismatched_business_is_denied_before_dashboard_grant(self):
        self.dashboard.return_value = (True, GrafanaRole.Viewer, {})
        response = self.request({**self.params(), "bk_biz_id": 3})
        self.assertEqual(response.status_code, 403)
        self.dashboard.assert_not_called()
        self.scope.assert_not_called()
        self.query.assert_not_called()

    def test_mismatched_business_is_denied_before_cached_grant(self):
        with (
            patch.object(GrafanaReadPermission, "_allow_cache_key", return_value="cached-chart"),
            patch("monitor_web.grafana.permissions.cache.get", return_value=True) as cache_get,
        ):
            response = self.request({**self.params(), "bk_biz_id": 3})
        self.assertEqual(response.status_code, 403)
        cache_get.assert_not_called()
        self.query.assert_not_called()

    def test_mismatched_business_is_denied_before_skip_check_grant(self):
        self.dashboard.return_value = (True, GrafanaRole.Admin, {})
        response = self.request({**self.params(), "bk_biz_id": 3}, skip_check=True)
        self.assertEqual(response.status_code, 403)
        self.dashboard.assert_not_called()
        self.query.assert_not_called()

    def test_mismatched_business_is_denied_before_share_token_grant(self):
        token = self.token()
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.request({**self.params(), "bk_biz_id": 3}, token=token)
        self.assertEqual(response.status_code, 403)
        self.query.assert_not_called()

    def test_matching_business_keeps_dashboard_access(self):
        self.dashboard.return_value = (True, GrafanaRole.Viewer, {})
        response = self.request()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.dashboard.call_args.args[2], "2")
        self.assertEqual(self.scope.call_args.args[0], 2)
        self.assertEqual(self.query.call_args.args[0]["bk_biz_id"], 2)
        self.iam.assert_not_called()

    def test_matching_business_keeps_iam_access(self):
        response = self.request()
        self.assertEqual(response.status_code, 200)
        self.iam.return_value._is_allowed_request.assert_called_once()
        self.query.assert_called_once()

    def test_matching_business_keeps_cached_access(self):
        with (
            patch.object(GrafanaReadPermission, "_allow_cache_key", return_value="cached-chart"),
            patch("monitor_web.grafana.permissions.cache.get", return_value=True) as cache_get,
        ):
            response = self.request()
        self.assertEqual(response.status_code, 200)
        cache_get.assert_called_once_with("cached-chart")
        self.dashboard.assert_not_called()
        self.iam.assert_not_called()
        self.query.assert_called_once()

    def test_matching_business_keeps_skip_check_access(self):
        response = self.request(skip_check=True)
        self.assertEqual(response.status_code, 200)
        self.iam.return_value._is_allowed_request.assert_not_called()
        self.query.assert_called_once()

    def test_other_tenant_is_denied_before_dashboard_grant(self):
        self.dashboard.return_value = (True, GrafanaRole.Viewer, {})
        with patch("monitor_web.k8s.permissions.is_biz_in_tenant", return_value=False):
            response = self.request()
        self.assertEqual(response.status_code, 403)
        self.dashboard.assert_not_called()
        self.query.assert_not_called()

    def test_legacy_detail_token_cannot_access_the_new_raw_graph_endpoint(self):
        token = self.token()
        self.iam.return_value._is_allowed_request.return_value = False
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.request(token=token)
        self.assertEqual(response.status_code, 403, response.data)
        self.iam.return_value._is_allowed_request.assert_not_called()
        self.assertIn("sceneType", response.data["message"])
        self.query.assert_not_called()

    def test_kubernetes_overview_share_keeps_access(self):
        token = self.token()
        token.params["data"]["query"]["sceneType"] = "overview"
        params = self.params()
        params["query_configs"][0].pop("where")
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.request(params, token=token)
        self.assertEqual(response.status_code, 200, response.data)
        self.iam.return_value._is_allowed_request.assert_not_called()
        self.query.assert_called_once()

    def test_kubernetes_share_rejects_other_business_at_token_middleware(self):
        token = self.token()
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.request({**self.params(), "bk_biz_id": 3}, url_biz_id=3, token=token)
        self.assertEqual(response.status_code, 403)
        self.query.assert_not_called()

    def test_kubernetes_share_still_checks_cluster_and_time_parameters(self):
        token = self.token()
        token.params["data"]["query"]["sceneType"] = "overview"
        for key, value, error in (
            ("bcs_cluster_id", "BCS-K8S-92002", "ParamsPermissionDeniedError"),
            ("start_time", 61, "SearchLockedError"),
        ):
            with self.subTest(key=key), patch.object(ApiAuthToken.objects, "get", return_value=token):
                response = self.request({**self.params(), key: value}, token=token)
            self.assertEqual(response.data["result"], False)
            self.assertEqual(response.data["error_details"]["type"], error)
            self.query.assert_not_called()

    def test_legacy_detail_token_cannot_authorize_out_of_scope_promql_with_correct_where(self):
        token = self.token()
        params = self.params()
        params["query_configs"][0]["promql"] = 'memory{namespace="foreign",pod_name="foreign-pod"}'
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.request(params, token=token)
        self.assertEqual(response.data["result"], False)
        self.assertEqual(response.data["error_details"]["type"], "ParamsPermissionDeniedError")
        self.assertIn("sceneType", response.data["message"])
        self.query.assert_not_called()

    def test_other_share_type_does_not_get_kubernetes_action_bypass(self):
        token = self.token("custom_metric")
        self.iam.return_value._is_allowed_request.return_value = False
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.request(token=token)
        self.assertEqual(response.status_code, 403)
        self.iam.return_value._is_allowed_request.assert_called()
        self.query.assert_not_called()

    def test_missing_business_is_denied_before_dashboard_grant(self):
        self.dashboard.return_value = (True, GrafanaRole.Viewer, {})
        params = self.params()
        params.pop("bk_biz_id")
        response = self.request(params)
        self.assertEqual(response.status_code, 403)
        self.dashboard.assert_not_called()
        self.query.assert_not_called()

    def test_new_overview_share_uses_the_actual_route_and_chart_payload(self):
        token = self.overview_token()
        self.iam.return_value._is_allowed_request.return_value = False
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.request(self.overview_params(), token=token)
        self.assertEqual(response.status_code, 200, response.data)
        self.iam.return_value._is_allowed_request.assert_not_called()
        config = self.query.call_args.args[0]["query_configs"][0]
        self.assertEqual(config["where"], [])
        self.assertEqual(config["required_promql_match"], '{bcs_cluster_id="BCS-K8S-92001"}')

    def test_anonymous_user_can_query_the_new_overview_share(self):
        self.user = AnonymousUser()
        self.user.tenant_id = "system"
        token = self.overview_token()
        self.iam.return_value._is_allowed_request.return_value = False
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.request(self.overview_params(), token=token)
        self.assertEqual(response.status_code, 200, response.data)
        self.iam.return_value._is_allowed_request.assert_not_called()
        self.query.assert_called_once()

    def test_new_overview_share_cannot_query_another_cluster(self):
        token = self.overview_token()
        params = self.overview_params()
        params["bcs_cluster_id"] = "BCS-K8S-92002"
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.request(params, token=token)
        self.assertEqual(response.status_code, 403)
        self.assertIn("bcs_cluster_id", response.data["message"])
        self.query.assert_not_called()

    def test_new_overview_share_without_saved_cluster_is_denied(self):
        token = self.overview_token()
        token.params["data"]["query"].pop("cluster")
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.request(self.overview_params(), token=token)
        self.assertEqual(response.status_code, 403)
        self.assertIn("data.query.cluster", response.data["message"])
        self.query.assert_not_called()

    def test_new_overview_share_preserves_the_existing_time_lock(self):
        token = self.overview_token()
        token.params.update({"lock_search": True, "default_time_range": []})
        params = self.overview_params()
        params["start_time"] = 61
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.request(params, token=token)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error_details"]["type"], "SearchLockedError")
        self.query.assert_not_called()

    def test_new_overview_share_preserves_interactive_filters(self):
        token = self.overview_token()
        params = self.overview_params()
        params["query_configs"][0]["promql"] = 'memory{namespace="beta",pod_name="pod-b"}'
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.request(params, token=token)
        self.assertEqual(response.status_code, 200, response.data)
        self.query.assert_called_once()

    def test_new_overview_share_does_not_require_namespace_on_node_or_cluster_metrics(self):
        token = self.overview_token()
        token.params["data"]["query"]["scene"] = "capacity"
        token.params["data"]["query"]["groupBy"] = json.dumps(["node"])
        params = self.overview_params()
        params["query_configs"][0]["promql"] = 'kube_node_status_capacity{node="node-a"}'
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.request(params, token=token)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            self.query.call_args.args[0]["query_configs"][0]["required_promql_match"],
            '{bcs_cluster_id="BCS-K8S-92001"}',
        )

    def test_new_overview_share_cannot_bypass_federated_namespace_scope_with_scene(self):
        token = self.overview_token()
        token.params["data"]["query"]["scene"] = "capacity"
        self.scope.return_value = FederatedResourceScope(Q(), ("alpha", "beta"))
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.request(self.overview_params(), token=token)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            self.query.call_args.args[0]["query_configs"][0]["required_promql_match"],
            '{bcs_cluster_id="BCS-K8S-92001",namespace=~"^(alpha|beta)$"}',
        )

    def test_new_overview_share_forces_saved_cluster_at_the_actual_promql_datasource(self):
        token = self.overview_token()
        params = self.overview_params()
        params["query_configs"][0]["promql"] = 'memory{bcs_cluster_id="BCS-K8S-92002"} or bare_metric'
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.request(params, token=token)
        self.assertEqual(response.status_code, 200, response.data)
        executed = self.query.call_args.args[0]
        config = {**executed["query_configs"][0], "interval": 60}
        source = PrometheusTimeSeriesDataSource(bk_biz_id=executed["bk_biz_id"], **config)
        with patch("api.unify_query.default.QueryDataByPromqlResource.request", return_value={}) as query:
            source._execute_promql(60000, 120000)
        self.assertEqual(query.call_args.kwargs["promql"], params["query_configs"][0]["promql"])
        self.assertEqual(query.call_args.kwargs["match"], '{bcs_cluster_id="BCS-K8S-92001"}')

    def test_new_overview_share_accepts_either_registered_route_identifier(self):
        for missing_key in ("name", "path"):
            with self.subTest(missing_key=missing_key):
                token = self.overview_token()
                token.params["data"].pop(missing_key)
                with patch.object(ApiAuthToken.objects, "get", return_value=token):
                    response = self.request(self.overview_params(), token=token)
                self.assertEqual(response.status_code, 200, response.data)

    def test_legacy_detail_token_without_where_is_also_denied(self):
        token = self.token()
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.request(self.overview_params(), token=token)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error_details"]["type"], "ParamsPermissionDeniedError")
        self.query.assert_not_called()

    def test_new_route_name_cannot_relax_an_explicit_legacy_detail_token(self):
        token = self.token()
        token.params["data"].update({"name": "k8s-new", "path": "/k8s-new"})
        token.params["data"]["query"]["cluster"] = self.cluster_id
        with patch.object(ApiAuthToken.objects, "get", return_value=token):
            response = self.request(self.overview_params(), token=token)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error_details"]["type"], "ParamsPermissionDeniedError")
        self.query.assert_not_called()
