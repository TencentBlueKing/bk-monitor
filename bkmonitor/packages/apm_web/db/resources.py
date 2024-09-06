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

import datetime
import json

from django.utils.translation import ugettext_lazy as _
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes
from rest_framework import serializers

from apm_web.constants import (
    DEFAULT_MAX_VALUE,
    METRIC_TUPLE,
    DbCategoryEnum,
    SceneEventKey,
)
from apm_web.db.db_utils import build_db_param, get_offset
from apm_web.handlers.component_handler import ComponentHandler
from apm_web.handlers.db_handler import DbInstanceHandler, DbQuery, DbStatisticsHandler
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.models import Application
from constants.apm import OtlpKey
from core.drf_resource import Resource, api
from monitor_web.scene_view.resources.base import PageListResource
from monitor_web.scene_view.table_format import (
    LinkListTableFormat,
    LinkTableFormat,
    NumberTableFormat,
    ProgressTableFormat,
    StringTableFormat,
)


class DbQuerySerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务id")
    app_name = serializers.CharField(label="应用名称")
    page = serializers.IntegerField(label="页码", min_value=0)
    page_size = serializers.IntegerField(label="每页条数", min_value=0)
    start_time = serializers.IntegerField(required=True, label="数据开始时间")
    end_time = serializers.IntegerField(required=True, label="数据结束时间")
    filter_params = serializers.DictField(required=False, label="过滤参数", default={})
    sort = serializers.CharField(required=False, label="排序条件", allow_blank=True)
    component_instance_id = serializers.ListSerializer(
        child=serializers.CharField(), required=False, label="组件实例id(组件页面下有效)"
    )
    keyword = serializers.CharField(label="关键字", required=False, allow_blank=True)
    filter = serializers.CharField(required=False, label="筛选条件", allow_blank=True)


class ListDbStatisticsResource(PageListResource):
    default_sort = "-request_count"

    class RequestSerializer(DbQuerySerializer):
        group_by_key = serializers.CharField(label="分组字段")
        metric_list = serializers.ListField(label="指标列表", child=serializers.CharField())

    def get_columns(self, column_type=None):
        return [
            StringTableFormat(id="summary", name=_("命令语句"), min_width=120),
            StringTableFormat(id="request_count", name=_("请求次数"), sortable=True, width=110),
            NumberTableFormat(
                id="avg_duration", name=_("平均耗时"), checked=True, unit="ms", decimal=2, sortable=True, width=120
            ),
            StringTableFormat(id="error_request_count", name=_("错误数"), sortable=True, width=100),
            ProgressTableFormat(id="slow_command_rate", name=_("慢语句占比"), sortable=True, width=120),
            LinkListTableFormat(
                id="operation",
                name=_("操作"),
                checked=True,
                disabled=True,
                width=90,
                links=[
                    LinkTableFormat(
                        id="trace",
                        name=_("调用链"),
                        url_format='/?bizId={bk_biz_id}/#/trace/home/?app_name={app_name}'
                        + '&search_type=scope'
                        + '&start_time={start_time}&end_time={end_time}'
                        + '&listType=span',
                        target="blank",
                        event_key=SceneEventKey.SWITCH_SCENES_TYPE,
                    ),
                    LinkTableFormat(
                        id="statistics",
                        name=_("统计"),
                        url_format='/?bizId={bk_biz_id}/#/trace/home/?app_name={app_name}'
                        + '&search_type=scope'
                        + '&start_time={start_time}&end_time={end_time}'
                        + '&listType=interfaceStatistics',
                        target="blank",
                        event_key=SceneEventKey.SWITCH_SCENES_TYPE,
                    ),
                ],
            ),
        ]

    @classmethod
    def handle_keyword(cls, params, field, keyword):
        """
        :keyword 查询
        :param params:
        :param field: 字段名称
        :param keyword: keyword
        :return:
        """
        params.append({"key": field, "operator": "like", "value": [keyword]})

    def add_extra_params(self, params):
        return {
            "bk_biz_id": params.get("bk_biz_id"),
            "app_name": params.get("app_name"),
            "start_time": datetime.datetime.fromtimestamp(params.get("start_time")).strftime("%Y-%m-%d+%H:%M:%S"),
            "end_time": datetime.datetime.fromtimestamp(params.get("end_time")).strftime("%Y-%m-%d+%H:%M:%S"),
        }

    @classmethod
    def handle_data(cls, data, params):
        res = DbStatisticsHandler.parse_buckets(data, params.get("metric_list", []))

        for item in res:
            item["operation"] = {"trace": _("调用链"), "statistics": _("统计")}
            item["avg_duration"] = item["avg_duration"] / 1000
            item["slow_command_rate"] = item["slow_command_rate"] * 100

        return res

    def handle_format(self, data, column_formats, params):
        # 格式化数据

        res = self.handle_data(data, params)

        return super(ListDbStatisticsResource, self).handle_format(res, column_formats, params)

    def get_pagination_data(self, data, params, column_type=None, skip_sorted=False):
        items = super(ListDbStatisticsResource, self).get_pagination_data(data, params, column_type)
        service_name = params.get("filter_params", {}).get(OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME))
        if service_name:
            service_name = ComponentHandler.get_component_belong_service(service_name)
        # url 拼接
        for item in items["data"]:
            tmp = {
                "span_name": {
                    "selectedCondition": {"label": "=", "value": "equal"},
                    "isInclude": True,
                    "selectedConditionValue": [item["span_name"]],
                }
            }
            if service_name:
                tmp[OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME)] = {
                    "selectedCondition": {"label": "=", "value": "equal"},
                    "isInclude": True,
                    "selectedConditionValue": [service_name],
                }

            for i in item["operation"]:
                i["url"] = i["url"] + '&conditionList=' + json.dumps(tmp)

        return items

    def perform_request(self, validated_data):
        table_id = Application.get_trace_table_id(validated_data["bk_biz_id"], validated_data["app_name"])

        if not table_id:
            raise ValueError(_("应用【{}】没有 trace 结果表").format(validated_data['app_name']))

        # 指标准入
        metric_list = [metric for metric in validated_data["metric_list"] if metric in METRIC_TUPLE]

        # 构建查询条件
        filter_params = build_db_param(validated_data)

        # keyword 搜索
        if validated_data.get("keyword"):
            self.handle_keyword(
                params=filter_params,
                field=OtlpKey.get_attributes_key(SpanAttributes.DB_STATEMENT),
                keyword=validated_data.get("keyword"),
            )

        # 设置默认排序
        if not validated_data.get("sort"):
            validated_data["sort"] = self.default_sort

        # 强制条件, 保证查到的数据是DB数据
        filter_params.append(
            {"key": OtlpKey.get_attributes_key(SpanAttributes.DB_STATEMENT), "operator": "exists", "value": [""]}
        )

        query_body = DbQuery().build_param(
            start_time=validated_data["start_time"],
            end_time=validated_data["end_time"],
            filter_params=filter_params,
        )

        # 添加aggregations
        query_body["aggs"] = {
            "group": {
                "composite": {
                    "sources": [
                        {"span_name": {"terms": {"field": "span_name", "missing_bucket": True}}},
                        {"summary": {"terms": {"field": "attributes.db.statement", "missing_bucket": True}}},
                    ],
                    "size": DEFAULT_MAX_VALUE,
                },
                "aggs": DbStatisticsHandler().build_es_dsl(
                    metric_set=set(metric_list), group_by_key=validated_data["group_by_key"]
                ),
            }
        }

        # 额外参数
        query_body["size"] = 0

        response = api.apm_api.query_es(
            {
                "table_id": table_id,
                "query_body": query_body,
            }
        )

        buckets = response["aggregations"]["group"]["buckets"]

        return self.get_pagination_data(buckets, validated_data)


class ListDbSpanResource(PageListResource):
    RequestSerializer = DbQuerySerializer

    def get_columns(self, column_type=None):
        return [
            StringTableFormat(id="start_time", name=_("时间"), sortable=True, width=150),
            StringTableFormat(id="summary", name=_("命令语句"), min_width=120),
            NumberTableFormat(
                id="elapsed_time", name=_("请求耗时"), checked=True, unit="ms", decimal=0, sortable=True, width=100
            ),
            StringTableFormat(id="db_instance", name=_("DB实例"), width=100),
            LinkListTableFormat(
                id="operation",
                name=_("操作"),
                checked=True,
                disabled=True,
                links=[
                    LinkTableFormat(
                        id="detail",
                        name=_("详情"),
                        url_format='/?bizId={bk_biz_id}/#/trace/home/?app_name={app_name}'
                        + '&search_type=accurate'
                        + '&search_id=spanID'
                        + '&trace_id={span_id}',
                        target="blank",
                        event_key=SceneEventKey.SWITCH_SCENES_TYPE,
                    ),
                ],
                width=60,
            ),
        ]

    def add_extra_params(self, params):
        return {
            "bk_biz_id": params.get("bk_biz_id"),
            "app_name": params.get("app_name"),
        }

    @staticmethod
    def build_sort(validated_data):
        """
        构建排序参数
        :param validated_data:
        :return:
        """
        es_dsl = {}
        if validated_data.get("sort"):
            field_name = str(validated_data.get("sort")).replace("-", "")
            item = {field_name: {"order": "asc"}}
            if validated_data.get("sort").startswith("-"):
                item[field_name]["order"] = "desc"
            es_dsl["sort"] = [item]
        return es_dsl

    @classmethod
    def deal_filter(cls, validated_data):
        """
        filter = db_slow 时, 特殊处理
        """

        if str(validated_data.get("filter")) == DbCategoryEnum.DB_SLOW:
            # 慢命令查询
            validated_data.get("filter_params", {})["attributes.db.is_slow"] = 1
            validated_data.pop("filter")

    @classmethod
    def handle_keyword(cls, params, field, keyword):
        """
        :keyword 查询
        :param params:
        :param field: 字段名称
        :param keyword: keyword
        :return:
        """
        params.append({"key": field, "operator": "like", "value": [keyword]})

    def perform_request(self, validated_data):
        if validated_data.get("filter"):
            self.deal_filter(validated_data)

        filter_params = build_db_param(validated_data)
        # 排序处理
        es_dsl = self.build_sort(validated_data)
        # keyword 搜索
        if validated_data.get("keyword"):
            self.handle_keyword(
                params=filter_params,
                field=OtlpKey.get_attributes_key(SpanAttributes.DB_STATEMENT),
                keyword=validated_data.get("keyword"),
            )
        # 强制条件, 保证查到的数据是DB数据
        filter_params.append(
            {"key": OtlpKey.get_attributes_key(SpanAttributes.DB_STATEMENT), "operator": "exists", "value": [""]}
        )
        body = {
            "bk_biz_id": validated_data["bk_biz_id"],
            "app_name": validated_data["app_name"],
            "start_time": validated_data["start_time"],
            "end_time": validated_data["end_time"],
            "offset": get_offset(validated_data),
            "limit": validated_data["page_size"],
            "filters": filter_params,
            "es_dsl": es_dsl,
            "exclude_field": ["links", "events"],
        }

        res = api.apm_api.query_span_list(body)

        obj = DbInstanceHandler(validated_data["bk_biz_id"], validated_data["app_name"])
        data = []
        for item in res["data"]:
            db_instance = obj.get_instance(item)
            start_time = datetime.datetime.fromtimestamp(int(item["start_time"]) // 1000000).strftime(
                '%Y-%m-%d %H:%M:%S'
            )
            data.append(
                {
                    "start_time": start_time,
                    "summary": item.get("attributes", {}).get("db.statement"),
                    "elapsed_time": item["elapsed_time"] / 1000,
                    "db_instance": db_instance,
                    "operation": {"detail": _("详情")},
                    "span_id": item.get("span_id"),
                }
            )

        column_formats, column_format_map = self.get_columns_config(data=data, column_type=None)
        # 格式化数据
        data = self.handle_format(data, column_formats, validated_data)

        return {
            "columns": [column.column() for column in column_formats],
            "data": data,
            "filter": DbCategoryEnum.get_db_filter_fields(),
            "total": res.get("total"),
        }


class ListDbSystemResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")
        group_by_key = serializers.CharField(label="分组字段")
        service_name = serializers.CharField(label="服务名称", required=False)

    def perform_request(self, validated_data):
        table_id = Application.get_trace_table_id(validated_data["bk_biz_id"], validated_data["app_name"])
        if not table_id:
            raise ValueError(_("应用【{}】没有trace 结果表").format(validated_data['app_name']))

        node = ServiceHandler.get_node(
            validated_data["bk_biz_id"], validated_data["app_name"], validated_data["service_name"]
        )
        # 服务名称处理
        service_name = validated_data.get("service_name")
        predicate_value = node["extra_data"]["predicate_value"]
        if service_name and predicate_value and predicate_value in service_name:
            return [
                {
                    "id": predicate_value,
                    "name": predicate_value,
                    "app_name": validated_data.get("app_name"),
                    "service_name": validated_data.get("service_name"),
                }
            ]

        # 添加服务查询条件
        filters = None
        if service_name:
            filters = [
                {
                    "key": OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME),
                    "operator": "equal",
                    "value": [service_name],
                }
            ]
        query_body = DbQuery().build_param(
            filter_params=filters,
        )

        # 添加aggregations
        group_by_key = validated_data["group_by_key"]
        query_body["aggs"] = {group_by_key: {"terms": {"field": group_by_key, "size": DEFAULT_MAX_VALUE}}}
        # 额外条件
        query_body["size"] = 0

        response = api.apm_api.query_es(
            {
                "table_id": table_id,
                "query_body": query_body,
            }
        )

        buckets = response["aggregations"][validated_data["group_by_key"]]["buckets"]
        data = []
        for item in buckets:
            data.append(
                {
                    "id": item.get("key"),
                    "name": item.get("key"),
                    "app_name": validated_data.get("app_name"),
                    "service_name": validated_data.get("service_name"),
                }
            )

        return data
