import json

from rest_framework import serializers

from monitor_web.grafana.resources.unify_query import GraphUnifyQueryResource
from monitor_web.k8s.core.federation import get_federated_resource_scope
from monitor_web.k8s.core.filters import load_resource_filter


class GraphK8sQueryResource(GraphUnifyQueryResource):
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

    def perform_request(self, params):
        cluster_id = params["bcs_cluster_id"]
        scope = get_federated_resource_scope(params["bk_biz_id"], cluster_id)
        matchers = [f"bcs_cluster_id={json.dumps(cluster_id)}"]
        if scope is not None:
            if not scope.history_namespaces:
                return {"series": [], "metrics": [], "federated_scope": True}
            matchers.append(load_resource_filter("namespace", scope.history_namespaces).filter_string())
        # UQ applies match to every vector selector, including joins and bare metrics.
        params["query_configs"][0]["required_promql_match"] = "{" + ",".join(matchers) + "}"
        return {**super().perform_request(params), "federated_scope": scope is not None}
