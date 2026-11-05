from unittest.mock import patch

from django.db.models import Q
from django.test import SimpleTestCase

from bkmonitor.data_source.data_source import PrometheusTimeSeriesDataSource
from core.drf_resource.exceptions import CustomException
from monitor_web.grafana.resources.unify_query import GraphUnifyQueryResource
from monitor_web.grafana.views import GrafanaViewSet
from monitor_web.k8s.chart import GraphK8sQueryResource
from monitor_web.k8s.core.federation import FederatedResourceScope
from monitor_web.k8s.views import ResourcesViewSet


class TestFederatedChart(SimpleTestCase):
    cluster_id = "BCS-K8S-92001"

    def test_chart_route_uses_the_same_permission_as_grafana_queries(self):
        k8s = ResourcesViewSet()
        k8s.action = "graph_query"
        grafana = GrafanaViewSet()
        grafana.action = "time_series/unify_query"
        actual, expected = k8s.get_permissions()[0], grafana.get_permissions()[0]
        self.assertIsInstance(actual, type(expected))
        self.assertEqual(actual.permission.actions, expected.permission.actions)

    def graph_params(self):
        return {
            "bk_biz_id": 2,
            "bcs_cluster_id": self.cluster_id,
            "namespace_scoped": False,
            "start_time": 60,
            "end_time": 120,
            "expression": "A",
            "query_configs": [
                {
                    "data_source_label": "prometheus",
                    "data_type_label": "time_series",
                    "promql": 'sum(memory{namespace="shared"}) or bare_metric',
                    "required_promql_match": '{namespace="untrusted"}',
                    "filter_dict": {"namespace": "untrusted"},
                }
            ],
        }

    def test_graph_passes_server_match_to_unify_query(self):
        scope = FederatedResourceScope(Q(), ("alpha", "beta"))
        expected_match = '{bcs_cluster_id="BCS-K8S-92001",namespace=~"^(alpha|beta)$"}'
        with (
            patch("monitor_web.k8s.chart.get_federated_resource_scope", return_value=scope),
            patch.object(GraphUnifyQueryResource, "perform_request", return_value={"series": []}) as graph_query,
        ):
            GraphK8sQueryResource()(self.graph_params())
        config = graph_query.call_args.args[0]["query_configs"][0]
        self.assertEqual(config["required_promql_match"], expected_match)
        self.assertEqual(config["promql"], 'sum(memory{namespace="shared"}) or bare_metric')

        source = PrometheusTimeSeriesDataSource(bk_biz_id=2, **{**config, "interval": 60})
        with patch("api.unify_query.default.QueryDataByPromqlResource.request", return_value={}) as query:
            source._execute_promql(60000, 120000)
        self.assertEqual(query.call_args.kwargs["match"], expected_match[:-1] + ",namespace='untrusted'}")

    def test_graph_skips_query_when_federation_has_no_visible_metric_namespace(self):
        with (
            patch("monitor_web.k8s.chart.get_federated_resource_scope", return_value=FederatedResourceScope(Q())),
            patch.object(GraphUnifyQueryResource, "perform_request") as graph_query,
        ):
            self.assertEqual(
                GraphK8sQueryResource()(self.graph_params()), {"series": [], "metrics": [], "federated_scope": True}
            )
        graph_query.assert_not_called()

    def test_ordinary_cluster_parameter_cannot_wrap_a_different_cluster_query(self):
        with (
            patch("monitor_web.k8s.chart.get_federated_resource_scope", return_value=None),
            patch.object(GraphUnifyQueryResource, "perform_request", return_value={"series": []}) as graph_query,
        ):
            params = self.graph_params()
            params["query_configs"][0]["promql"] = 'memory{bcs_cluster_id="BCS-K8S-92002"}'
            GraphK8sQueryResource()(params)
        self.assertEqual(
            graph_query.call_args.args[0]["query_configs"][0]["required_promql_match"],
            '{bcs_cluster_id="BCS-K8S-92001"}',
        )

    def test_graph_rejects_query_modes_that_can_drop_the_required_match(self):
        params = self.graph_params()
        with self.assertRaisesMessage(CustomException, "requires one PromQL query"):
            GraphK8sQueryResource()({**params, "promql_multi_expression": True})
