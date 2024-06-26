import time

from rest_framework.viewsets import GenericViewSet
from rest_framework.decorators import action
from rest_framework.response import Response

from bkmonitor.data_source import load_data_source, UnifyQuery
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api


# Create your views here.


class TestViewSet(GenericViewSet):
    @action(methods=['GET'], detail=False)
    def test(self, request):
        group_by = ["namespace", "pod_name"]
        usage_types = ["cpu", "memory", "disk"]
        bulk_params = [
            {
                "bk_biz_id": 2,
                "group_by": group_by,
                "bcs_cluster_id": "BCS-K8S-00000",
                "usage_type": usage_type,
            }
            for usage_type in usage_types
        ]
        usages = api.kubernetes.fetch_container_usage.bulk_request(bulk_params)
        return Response(usages)

    @action(methods=['GET'], detail=False)
    def test_query(self, request):
        data_source_class = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)
        data_source = data_source_class(
            table="system.cpu_summary",
            interval=60,
            group_by=["bk_target_cloud_id"],
            metrics=[{"field": "usage", "method": "count", "alias": "A"}],
        )
        query = UnifyQuery(bk_biz_id=2, data_sources=[data_source], expression="A")
        data = query.query_data(start_time=1749394080 * 1000, end_time=1759394080 * 1000)
        return Response(data)
