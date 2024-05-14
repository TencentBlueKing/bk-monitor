# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from django.conf import settings
from rest_framework import serializers
from rest_framework.response import Response

from apps.generic import APIViewSet
from apps.iam.handlers.drf import ViewBusinessPermission

# from apps.log_search.models import LogIndexSet
from apps.log_search.permission import Permission
from apps.log_search.serializers import (
    FetchStatisticsGraphSerializer,
    FetchStatisticsInfoSerializer,
    FetchTopkListSerializer,
)
from apps.utils.drf import list_route

value_list = [[100, 12], [50, 11], [14, 5], [67, 1], [0, 10], [20, 9], [15, 7], [99, 3]]
FieldTypeMap = {
    "keyword": "string",
    "text": "string",
    "integer": "int",
    "long": "int",
    "double": "int",
    "bool": "string",
    "conflict": "string",
}


class FieldViewSet(APIViewSet):
    """
    字段分析
    """

    serializer_class = serializers.Serializer

    def get_permissions(self):
        if settings.BKAPP_IS_BKLOG_API:
            # 只在后台部署时做白名单校验
            auth_info = Permission.get_auth_info(self.request, raise_exception=False)
            # ESQUERY白名单不需要鉴权
            if auth_info and auth_info["bk_app_code"] in settings.ESQUERY_WHITE_LIST:
                return []

        return [ViewBusinessPermission()]

    @list_route(methods=["POST"], url_path="fetch_topk_list")
    def fetch_topk_list(self, request, *args, **kwargs):
        """
        @api {get} /field/index_set/$index_set_id/fetch_topk_list/ 获取字段topk计数列表
        @apiName fetch_topk_list
        """
        params = self.params_valid(FetchTopkListSerializer)
        values = sorted(value_list, key=lambda x: x[1])[: params["limit"]]
        total_count = 120
        field_count = sum([field[1] for field in value_list])
        return Response(
            {
                "name": params["agg_field"],
                "columns": ["_value", "_count"],
                "types": ["float", "float"],
                "limit": params["limit"],
                "total_count": total_count,
                "field_count": field_count,
                "values": values,
            }
        )

    @list_route(methods=["POST"], url_path="statistics/info")
    def fetch_statistics_info(self, request, *args, **kwargs):
        """
        @api {get} /field/index_set/$index_set_id/statistics/info/ 获取字段统计信息
        @apiName fetch_statistics_info
        """
        params = self.params_valid(FetchStatisticsInfoSerializer)
        total_count = 120
        field_count = 58
        distinct_count = 8
        field_percent = round(field_count / total_count, 2)

        max_value = max(value[0] for value in value_list)
        min_value = min(value[0] for value in value_list)
        avg_value = sum(value[0] for value in value_list) / len(value_list)
        median_value = 50
        data = {
            "total_count": total_count,
            "field_count": field_count,
            "distinct_count": distinct_count,
            "field_percent": field_percent,
        }
        if FieldTypeMap[params["field_type"]] == "int":
            data["value_analysis"] = {"max": max_value, "min": min_value, "avg": avg_value, "median": median_value}

        return Response(data)

    @list_route(methods=["POST"], url_path="statistics/graph")
    def fetch_statistics_graph(self, request, *args, **kwargs):
        """constants.py:1515
        @api {get} /field/index_set/$index_set_id/statistics/graph/ 获取字段统计图表
        @apiName fetch_statistics_graph
        """
        params = self.params_valid(FetchStatisticsGraphSerializer)
        return Response(
            {
                "series": [
                    {
                        "name": params["agg_field"],
                        "columns": ["_value", "_count"],
                        "types": ["float", "float"],
                        "values": value_list,
                    }
                ]
            }
        )
