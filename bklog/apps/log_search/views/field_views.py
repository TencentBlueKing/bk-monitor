"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import csv

from django.conf import settings
from rest_framework import serializers
from rest_framework.response import Response
from io import BytesIO, TextIOWrapper

from apps.generic import APIViewSet
from apps.iam.handlers.drf import ViewBusinessPermission
from apps.log_search.constants import FieldDataTypeEnum
from apps.log_search.exceptions import GetMultiResultFailException
from apps.log_search.handlers.search.search_handlers_esquery import UnionSearchHandler
from apps.log_search.permission import Permission
from apps.log_search.serializers import (
    FetchStatisticsGraphSerializer,
    FetchStatisticsInfoSerializer,
    FetchTopkListSerializer,
    FetchValueListSerializer,
    QueryFieldBaseSerializer,
)
from apps.log_search.utils import create_download_response
from apps.log_unifyquery.constants import FIELD_TYPE_MAP, AggTypeEnum
from apps.log_unifyquery.handler.field import UnifyQueryFieldHandler
from apps.utils.drf import list_route
from apps.utils.thread import MultiExecuteFunc


class FieldViewSet(APIViewSet):
    """
    字段统计&分析
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

    @list_route(methods=["POST"], url_path="fetch_distinct_count_list")
    def fetch_distinct_count_list(self, request, *args, **kwargs):
        """
        @api {get} /field/index_set/fetch_distinct_count_list/ 获取字段去重计数列表
        @apiName fetch_topk_list
        """
        count_list = []
        params = self.params_valid(QueryFieldBaseSerializer)
        fields_result = UnionSearchHandler().union_search_fields(params)
        # 去除非聚合字段和text类型字段
        fields_list = [
            field
            for field in fields_result.get("fields", [])
            if field["field_type"] != "text" and field.get("es_doc_values", False)
        ]
        multi_execute_func = MultiExecuteFunc()

        for field in fields_list:
            query_handler = UnifyQueryFieldHandler({"agg_field": field["field_name"], **params})
            multi_execute_func.append(f"distinct_count_{field['field_name']}", query_handler.get_distinct_count)

        multi_result = multi_execute_func.run(return_exception=True)

        for field in fields_list:
            field_name = field["field_name"]
            ret = multi_result.get(f"distinct_count_{field_name}")
            if isinstance(ret, Exception):
                # 子查询异常
                raise GetMultiResultFailException(
                    GetMultiResultFailException.MESSAGE.format(field_name=field_name, e=ret)
                )
            count_list.append({"field_name": field_name, "distinct_count": ret})
        return Response(count_list)

    @list_route(methods=["POST"], url_path="fetch_topk_list")
    def fetch_topk_list(self, request, *args, **kwargs):
        """
        @api {get} /field/index_set/fetch_topk_list/ 获取字段topk计数列表
        @apiName fetch_topk_list
        """
        params = self.params_valid(FetchTopkListSerializer)
        query_handler = UnifyQueryFieldHandler(params)
        total_count = query_handler.get_total_count()
        field_count = query_handler.get_field_count()
        distinct_count = query_handler.get_distinct_count()
        topk_list = query_handler.get_topk_list(params["limit"])
        return Response(
            {
                "name": params["agg_field"],
                "columns": ["_value", "_count"],
                "types": ["float", "float"],
                "limit": params["limit"],
                "total_count": total_count,
                "field_count": field_count,
                "distinct_count": distinct_count,
                "values": topk_list,
            }
        )

    @list_route(methods=["POST"], url_path="fetch_value_list")
    def fetch_value_list(self, request, *args, **kwargs):
        """
        @api {get} /field/index_set/fetch_value_list/ 获取字段值列表
        @apiName fetch_value_list
        """
        params = self.params_valid(FetchValueListSerializer)
        index = "_".join(params["result_table_ids"]).replace(".", "_")
        query_handler = UnifyQueryFieldHandler(params)
        value_list = query_handler.get_value_list(params["limit"])

        output = BytesIO()
        # 使用 TextIOWrapper 包装 BytesIO 对象以支持文本写入
        text_wrapper = TextIOWrapper(output, encoding="utf-8", newline="")
        # 使用 csv.writer 写入数据到包装的 BytesIO 对象
        csv_writer = csv.writer(text_wrapper)
        csv_writer.writerow(["value", "count", "percent"])
        for item in value_list:
            csv_writer.writerow([item[0], item[1], f"{item[2] * 100:.2f}%"])
        text_wrapper.flush()
        text_wrapper.detach()
        field_name = params["agg_field"]
        file_name = f"bk_log_search_{index}_{field_name}.csv"
        return create_download_response(output, file_name, "text/csv")

    @list_route(methods=["POST"], url_path="statistics/info")
    def fetch_statistics_info(self, request, *args, **kwargs):
        """
        @api {get} /field/index_set/statistics/info/ 获取字段统计信息
        @apiName fetch_statistics_info
        """
        params = self.params_valid(FetchStatisticsInfoSerializer)
        query_handler = UnifyQueryFieldHandler(params)

        total_count = query_handler.get_total_count()
        field_count = query_handler.get_field_count()
        distinct_count = query_handler.get_distinct_count()
        if total_count and field_count:
            # 百分比计算：默认保留两位小数
            field_percent = round(field_count / total_count, 2)
        else:
            field_percent = 0

        data = {
            "total_count": total_count,
            "field_count": field_count,
            "distinct_count": distinct_count,
            "field_percent": field_percent,
        }
        if FIELD_TYPE_MAP.get(params["field_type"], "") == FieldDataTypeEnum.INT.value:
            max_value = query_handler.get_agg_value(AggTypeEnum.MAX.value)
            min_value = query_handler.get_agg_value(AggTypeEnum.MIN.value)
            avg_value = query_handler.get_agg_value(AggTypeEnum.AVG.value)
            median_value = query_handler.get_agg_value(AggTypeEnum.MEDIAN.value)
            data["value_analysis"] = {"max": max_value, "min": min_value, "avg": avg_value, "median": median_value}

        return Response(data)

    @list_route(methods=["POST"], url_path="statistics/total")
    def fetch_statistics_total(self, request, *args, **kwargs):
        """
        @api {get} /field/index_set/statistics/total/ 获取索引集日志总条数
        @apiName fetch_total_count
        """
        params = self.params_valid(QueryFieldBaseSerializer)
        total_count = UnifyQueryFieldHandler(params).get_total_count()
        return Response({"total_count": total_count})

    @list_route(methods=["POST"], url_path="statistics/graph")
    def fetch_statistics_graph(self, request, *args, **kwargs):
        """constants.py:1515
        @api {get} /field/index_set/statistics/graph/ 获取字段统计图表
        @apiName fetch_statistics_graph
        """
        params = self.params_valid(FetchStatisticsGraphSerializer)
        query_handler = UnifyQueryFieldHandler(params)
        if FIELD_TYPE_MAP.get(params["field_type"], "") == FieldDataTypeEnum.INT.value:
            if params["distinct_count"] < params["threshold"]:
                return Response(query_handler.get_topk_list(params["threshold"]))
            else:
                return Response(query_handler.get_bucket_data(params["min"], params["max"]))
        else:
            return Response(query_handler.get_topk_ts_data(params["limit"]))
