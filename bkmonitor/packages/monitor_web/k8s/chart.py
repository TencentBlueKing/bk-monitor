import json

from rest_framework import serializers

from bkmonitor.utils.request import get_request
from core.drf_resource import Resource
from monitor_web.grafana.resources.unify_query import GraphUnifyQueryResource
from monitor_web.k8s.core.federation import get_federated_resource_scope
from monitor_web.k8s.core.filters import load_resource_filter
from monitor_web.k8s.sharing import get_k8s_overview_graph_checker


class GraphK8sQueryResource(GraphUnifyQueryResource):
    namespace_scoped = True

    class RequestSerializer(GraphUnifyQueryResource.RequestSerializer):
        bcs_cluster_id = serializers.CharField()

        def validate(self, attrs):
            attrs = super().validate(attrs)
            configs = attrs["query_configs"]
            if attrs["promql_multi_expression"] or len(configs) != 1:
                raise serializers.ValidationError("A K8s chart target requires one PromQL query.")
            config = configs[0]
            if (
                config["data_source_label"] != "prometheus"
                or config["data_type_label"] != "time_series"
                or not config.get("promql")
            ):
                raise serializers.ValidationError("A K8s chart target requires a Prometheus time series.")
            return attrs

    def validate_request_data(self, request_data):
        checker = get_k8s_overview_graph_checker(get_request(peaceful=True))
        if checker is None:
            return super().validate_request_data(request_data)
        params = Resource.validate_request_data(self, request_data)
        checker.check(self.get_api_auth_request_data(request_data, params))
        return params

    def get_api_auth_request_data(self, request_data, validated_request_data):
        params = super().get_api_auth_request_data(request_data, validated_request_data).copy()
        # Query mode (range/instant) is independent of the shared scene's overview/detail type.
        params.pop("type", None)
        return params

    def perform_request(self, params):
        cluster_id = params["bcs_cluster_id"]
        scope = get_federated_resource_scope(params["bk_biz_id"], cluster_id) if self.namespace_scoped else None
        matchers = [f"bcs_cluster_id={json.dumps(cluster_id)}"]
        if scope is not None:
            if not scope.history_namespaces:
                return {"series": [], "metrics": [], "federated_scope": True}
            matchers.append(load_resource_filter("namespace", scope.history_namespaces).filter_string())
        # UQ applies match to every vector selector, including joins and bare metrics.
        params["query_configs"][0]["required_promql_match"] = "{" + ",".join(matchers) + "}"
        return {**super().perform_request(params), "federated_scope": scope is not None}


class GraphK8sClusterQueryResource(GraphK8sQueryResource):
    """Internal node/cluster queries have cluster scope and no Namespace dimension."""

    namespace_scoped = False
