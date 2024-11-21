import logging

from rest_framework import serializers
from rest_framework.response import Response

from apm_web.profile.constants import LARGE_SERVICE_MAX_QUERY_SIZE  # 5000
from apm_web.profile.constants import NORMAL_SERVICE_MAX_QUERY_SIZE  # 10000
from apm_web.profile.constants import CallGraphResponseDataMode
from apm_web.profile.diagrams import get_diagrammer
from apm_web.profile.doris.querier import ConverterType
from apm_web.profile.resources import (
    ListApplicationServicesResource,
    QueryServicesDetailResource,
)
from apm_web.profile.serializers import ProfileQuerySerializer, QueryBaseSerializer
from apm_web.profile.views import ProfileQueryViewSet
from core.drf_resource import Resource
from monitor_web.grafana.resources.utils import get_label_values, get_labels_keys

logger = logging.getLogger("root")


class QueryGraphProfileResource(Resource):
    class RequestSerializer(ProfileQuerySerializer):
        pass

    def perform_request(self, data):
        instance = ProfileQueryViewSet()
        start, end = instance._enlarge_duration(data["start"], data["end"], offset=data.get("offset", 0))
        essentials = instance._get_essentials(data)
        logger.info(f"[Samples] query essentials: {essentials}")

        if instance.is_large_service(
            essentials["bk_biz_id"],
            essentials["app_name"],
            essentials["service_name"],
            data["data_type"],
        ):
            extra_params = {"limit": {"offset": 0, "rows": LARGE_SERVICE_MAX_QUERY_SIZE}}
        else:
            extra_params = {"limit": {"offset": 0, "rows": NORMAL_SERVICE_MAX_QUERY_SIZE}}

        query_start_time = data["filter_labels"].pop("start", "")
        query_end_time = data["filter_labels"].pop("end", "")
        if query_start_time and query_end_time:
            query_start_time, query_end_time = instance._enlarge_duration(
                query_start_time, query_end_time, offset=data.get("offset", 0)
            )
        tree_converter = instance.query(
            bk_biz_id=essentials["bk_biz_id"],
            app_name=essentials["app_name"],
            service_name=essentials["service_name"],
            start=query_start_time or start,
            end=query_end_time or end,
            profile_id=data.get("profile_id"),
            filter_labels=data.get("filter_labels"),
            result_table_id=essentials["result_table_id"],
            sample_type=data["data_type"],
            converter=ConverterType.Tree,
            extra_params=extra_params,
        )

        diagram_types = data["diagram_types"]
        options = {"sort": data.get("sort"), "data_mode": CallGraphResponseDataMode.IMAGE_DATA_MODE}
        diagram_dicts = (get_diagrammer(d_type).draw(tree_converter, **options) for d_type in diagram_types)
        data = {k: v for diagram_dict in diagram_dicts for k, v in diagram_dict.items()}
        data.update(tree_converter.get_sample_type())
        return Response(data=data)


class GetProfileApplicationServiceResource(ListApplicationServicesResource):
    pass


class GetProfileTypeResource(QueryServicesDetailResource):
    pass


class GetProfileLabelResource(Resource):
    class RequestSerializer(QueryBaseSerializer):
        pass

    def perform_request(self, data):
        limit = 1000
        instance = ProfileQueryViewSet()
        label_keys = get_labels_keys(instance=instance, validated_data=data, limit=limit)
        return {"label_keys": label_keys}


class GetProfileLabelValuesResource(Resource):
    class RequestSerializer(QueryBaseSerializer):
        label_key = serializers.CharField(label="label名")
        offset = serializers.IntegerField(label="label_values查询起点")
        rows = serializers.IntegerField(label="label_values查询条数")

    def perform_request(self, data):
        """获取 profiling 数据的 label_values 列表"""

        instance = ProfileQueryViewSet()
        results = get_label_values(instance=instance, validated_data=data)
        return Response(
            data={"label_values": [i["label_value"] for i in results.get("list", {}) if i.get("label_value")]}
        )
