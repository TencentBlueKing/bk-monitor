"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import sqlparse
from django.core.paginator import Paginator
from django.db import models
from rest_framework import serializers
from sqlparse import sql as sql_nodes
from sqlparse import tokens as sql_tokens

from bkmonitor.utils.request import get_request_tenant_id
from bkm_space.utils import bk_biz_id_to_space_uid
from core.drf_resource import api, resource
from core.drf_resource.base import Resource, logger
from kernel_api.serializers.mixins import TimeSpanValidationPassThroughSerializer
from metadata.models import DataSource, TimeSeriesGroup


def ensure_time_series_table_belongs_to_biz(
    bk_biz_id: int | str, table_id: str, *, allow_platform: bool = True
) -> None:
    """确认时序结果表属于目标业务；调用方显式决定是否接受平台数据源。"""
    bk_tenant_id = get_request_tenant_id()
    group = TimeSeriesGroup.objects.filter(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        is_delete=False,
    ).first()
    if group is None:
        raise serializers.ValidationError({"table_id": "The time-series table does not exist."})
    if int(group.bk_biz_id) == int(bk_biz_id):
        return
    if (
        allow_platform
        and DataSource.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_data_id=group.bk_data_id,
            is_platform_data_id=True,
        ).exists()
    ):
        return
    raise serializers.ValidationError({"table_id": "The time-series table does not belong to the target space."})


def ensure_sql_reads_declared_table(sql: str, table_id: str) -> None:
    """只允许单条 SELECT 读取声明的单张结果表。"""
    statements = sqlparse.parse(sql.strip())
    if len(statements) != 1 or statements[0].get_type() != "SELECT":
        raise serializers.ValidationError({"sql": "Only one SELECT statement is supported."})
    statement = statements[0]
    flattened = [token for token in statement.flatten() if not token.is_whitespace]
    if any(token.ttype in sql_tokens.Comment for token in flattened):
        raise serializers.ValidationError({"sql": "SQL comments are not supported."})
    if sum(token.ttype is sql_tokens.DML and token.normalized == "SELECT" for token in flattened) != 1:
        raise serializers.ValidationError({"sql": "Subqueries are not supported."})
    forbidden = {"UNION", "INTERSECT", "EXCEPT", "WITH"}
    if any(
        token.ttype in sql_tokens.Keyword
        and (token.normalized.split()[0] in forbidden or token.normalized.endswith("JOIN"))
        for token in flattened
    ):
        raise serializers.ValidationError({"sql": "Joins, set operations, and CTEs are not supported."})

    significant = [token for token in statement.tokens if not token.is_whitespace]
    from_positions = [
        index
        for index, token in enumerate(significant)
        if token.ttype in sql_tokens.Keyword and token.normalized == "FROM"
    ]
    if len(from_positions) != 1 or from_positions[0] + 1 >= len(significant):
        raise serializers.ValidationError({"sql": "SQL must read exactly one declared result table."})
    table = significant[from_positions[0] + 1]
    if not isinstance(table, sql_nodes.Identifier) or isinstance(table, sql_nodes.IdentifierList):
        raise serializers.ValidationError({"sql": "SQL must read exactly one declared result table."})
    real_name = table.get_real_name()
    parent_name = table.get_parent_name()
    referenced_table = f"{parent_name}.{real_name}" if parent_name else real_name
    if referenced_table != table_id:
        raise serializers.ValidationError({"sql": "SQL may only read the declared table_id."})


class TimeSeriesGroupListResource(Resource):
    """时序分组列表查询接口"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", default=0)
        search_key = serializers.CharField(label="名称", required=False, allow_blank=True)
        page_size = serializers.IntegerField(default=10, label="获取的条数")
        page = serializers.IntegerField(default=1, label="页数")
        is_platform = serializers.BooleanField(required=False, label="是否查询平台级数据")

    def perform_request(self, validated_request_data):
        bk_tenant_id = get_request_tenant_id()
        bk_biz_id = validated_request_data.get("bk_biz_id")
        logger.info("TimeSeriesGroupListResource: try to get time series group list, bk_biz_id->[%s]", bk_biz_id)

        # 查询平台级数据源ID
        platform_data_ids = set(
            DataSource.objects.filter(bk_tenant_id=bk_tenant_id, is_platform_data_id=True).values_list(
                "bk_data_id", flat=True
            )
        )

        # 构建查询
        queryset = TimeSeriesGroup.objects.filter(
            bk_tenant_id=bk_tenant_id,
            is_delete=False,
        ).order_by("-last_modify_time")

        # 过滤
        if validated_request_data.get("is_platform"):
            queryset = queryset.filter(bk_data_id__in=platform_data_ids)
        elif validated_request_data.get("bk_biz_id"):
            queryset = queryset.filter(bk_biz_id=validated_request_data["bk_biz_id"])

        # 搜索
        if validated_request_data.get("search_key"):
            search_key = validated_request_data["search_key"]
            conditions = models.Q(time_series_group_name__contains=search_key)
            try:
                search_key_int = int(search_key)
                conditions |= models.Q(time_series_group_id=search_key_int) | models.Q(bk_data_id=search_key_int)
            except ValueError:
                pass
            queryset = queryset.filter(conditions)

        # 分页
        total = queryset.count()
        paginator = Paginator(queryset, validated_request_data["page_size"])
        page_data = paginator.page(validated_request_data["page"])

        # 转换数据
        result_list = []
        for obj in page_data:
            result_list.append(
                {
                    "time_series_group_id": obj.time_series_group_id,
                    "bk_data_id": obj.bk_data_id,
                    "bk_biz_id": obj.bk_biz_id,
                    "bk_tenant_id": obj.bk_tenant_id,
                    "table_id": obj.table_id,
                    "time_series_group_name": obj.time_series_group_name,
                    "label": obj.label,
                    "is_enable": obj.is_enable,
                    "is_delete": obj.is_delete,
                    "creator": obj.creator,
                    "create_time": obj.create_time.strftime("%Y-%m-%d %H:%M:%S%z"),
                    "last_modify_user": obj.last_modify_user,
                    "last_modify_time": obj.last_modify_time.strftime("%Y-%m-%d %H:%M:%S%z"),
                    "is_split_measurement": obj.is_split_measurement,
                    "is_platform": obj.bk_data_id in platform_data_ids,
                }
            )

        return {"list": result_list, "total": total}


class ExecuteRangeQueryResource(Resource):
    """执行范围查询接口 (用于 AI MCP 请求)"""

    RequestSerializer = TimeSpanValidationPassThroughSerializer

    def perform_request(self, validated_request_data):
        return resource.grafana.graph_promql_query(**validated_request_data)


class ExecuteSQLQueryResource(Resource):
    """执行 BkBase SQL 查询接口 (用于 AI MCP 请求)"""

    class RequestSerializer(TimeSpanValidationPassThroughSerializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务 ID")
        table_id = serializers.CharField(required=True, allow_blank=False, label="BkBase 结果表 ID")
        sql = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True, label="SQL 查询语句")
        start_time = serializers.CharField(required=True, allow_blank=False, label="开始时间")
        end_time = serializers.CharField(required=True, allow_blank=False, label="结束时间")
        step = serializers.CharField(required=False, default="5m", allow_blank=False, label="查询步长")
        limit = serializers.IntegerField(required=False, default=10, min_value=1, label="返回条数")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        table_id = validated_request_data["table_id"]
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        if not space_uid:
            raise serializers.ValidationError({"bk_biz_id": "Unable to resolve space_uid from bk_biz_id."})

        query_params = {
            "query_list": [
                {
                    "data_source": "bkdata",
                    "table_id": table_id,
                    "is_regexp": False,
                    "function": [],
                    "time_aggregation": {},
                    "is_dom_sampled": False,
                    "reference_name": "a",
                    "conditions": {},
                    "query_string": "*",
                    "sql": validated_request_data["sql"],
                    "is_prefix": False,
                }
            ],
            "metric_merge": "a",
            "start_time": validated_request_data["start_time"],
            "end_time": validated_request_data["end_time"],
            "step": validated_request_data["step"],
            "timezone": "UTC",
            "instant": False,
            "limit": validated_request_data["limit"],
            "space_uid": space_uid,
        }

        logger.info(
            "ExecuteSQLQueryResource: try to execute sql query, "
            "bk_biz_id->[%s], table_id->[%s], space_uid->[%s], limit->[%s]",
            bk_biz_id,
            table_id,
            space_uid,
            query_params["limit"],
        )

        return api.unify_query.query_raw(**query_params)
