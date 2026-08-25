"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework.serializers import ValidationError

from bkmonitor.data_source.format import flatten_dict_data
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from bkmonitor.utils.thread_backend import ThreadPool
from core.drf_resource import Resource
from rum_web.handlers.level.factory import RumLevelHandlerFactory
from rum_web.models.application import Application
from rum_web.query.serializers import (
    RumFieldsOptionValuesRequestSerializer,
    RumGenerateQueryStringRequestSerializer,
    RumRecordsRequestSerializer,
    RumViewConfigRequestSerializer,
    RumFieldsTopKRequestSerializer,
    RumFieldStatisticsInfoRequestSerializer,
    RumFieldStatisticsGraphRequestSerializer,
)


def _get_application(bk_biz_id: int, app_name: str) -> Application:
    """获取已鉴权的 RUM 应用实例"""
    try:
        return Application.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
    except Application.DoesNotExist:
        raise ValidationError(_("RUM 应用不存在: bk_biz_id={}, app_name={}").format(bk_biz_id, app_name))


def _build_data_sources(applications: list[Application]) -> list[TraceDatasourceTarget]:
    """从授权后的应用构造数据源目标列表，并携带 retention 以支持时间窗口补齐"""
    return [
        TraceDatasourceTarget.build(
            bk_biz_id=app.bk_biz_id,
            app_name=app.app_name,
            table_id=app.span_result_table_id,
            retention=app.retention_days,
        )
        for app in applications
    ]


class RumRecordsResource(Resource):
    """POST /rum/search/list_records/ — 分页查询记录列表"""

    RequestSerializer = RumRecordsRequestSerializer

    def perform_request(self, data: dict[str, Any]) -> dict[str, Any]:
        application = _get_application(data["bk_biz_id"], data["app_name"])
        handler = RumLevelHandlerFactory.create(data["mode"], _build_data_sources([application]))
        return {
            "list": [
                flatten_dict_data(_data)
                for _data in handler.list_records(
                    start_time=data["start_time"],
                    end_time=data["end_time"],
                    offset=data["offset"],
                    limit=data["limit"],
                    filters=data["filters"],
                    query_string=data["query_string"],
                    sort=data["sort"],
                )
            ]
        }


class RumViewConfigResource(Resource):
    """GET /rum/search/view_config/ — 获取页面视图配置

    视图配置是字段映射，与时间范围无关，时间范围交由查询层基于 retention 自动补齐，
    避免切换时间选择器时因命中索引分片变化导致页面重新加载。
    """

    RequestSerializer = RumViewConfigRequestSerializer

    def perform_request(self, data: dict[str, Any]) -> dict[str, Any]:
        application = _get_application(data["bk_biz_id"], data["app_name"])
        handler = RumLevelHandlerFactory.create(data["mode"], _build_data_sources([application]))
        return handler.view_config(
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
        )


class RumFieldsOptionValuesResource(Resource):
    """POST /rum/search/get_fields_option_values/ — 批量查询字段可选枚举值"""

    RequestSerializer = RumFieldsOptionValuesRequestSerializer

    def perform_request(self, data: dict[str, Any]) -> dict[str, list[str]]:
        application = _get_application(data["bk_biz_id"], data["app_name"])
        handler = RumLevelHandlerFactory.create(data["mode"], _build_data_sources([application]))
        return handler.get_fields_option_values(
            start_time=data["start_time"],
            end_time=data["end_time"],
            fields=data["fields"],
            limit=data["limit"],
            filters=data["filters"],
            query_string=data["query_string"],
        )


class RumGenerateQueryStringResource(Resource):
    """POST /rum/search/generate_query_string/ — 将过滤条件转换为查询字符串"""

    RequestSerializer = RumGenerateQueryStringRequestSerializer

    def perform_request(self, data: dict[str, Any]) -> str:
        application = _get_application(data["bk_biz_id"], data["app_name"])
        handler = RumLevelHandlerFactory.create(data["mode"], _build_data_sources([application]))
        return handler.generate_query_string(data["filters"])


class RumFieldsTopKResource(Resource):
    """查询字段 Top-K 值"""

    RequestSerializer = RumFieldsTopKRequestSerializer

    def perform_request(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        application = _get_application(data["bk_biz_id"], data["app_name"])
        handler = RumLevelHandlerFactory.create(data["mode"], _build_data_sources([application]))
        start_time, end_time = data["start_time"], data["end_time"]
        limit = data["limit"]
        filters, query_string = data["filters"], data["query_string"]

        if len(data["fields"]) == 1:
            return [handler.field_topk(start_time, end_time, data["fields"][0], limit, filters, query_string)]

        return ThreadPool().map_ignore_exception(
            lambda field: handler.field_topk(start_time, end_time, field, limit, filters, query_string),
            data["fields"],
        )


class RumFieldStatisticsInfoResource(Resource):
    """查询字段统计信息"""

    RequestSerializer = RumFieldStatisticsInfoRequestSerializer

    def perform_request(self, data: dict[str, Any]) -> dict[str, Any]:
        application = _get_application(data["bk_biz_id"], data["app_name"])
        handler = RumLevelHandlerFactory.create(data["mode"], _build_data_sources([application]))
        return handler.field_statistics_info(
            start_time=data["start_time"],
            end_time=data["end_time"],
            field=data["field"],
            filters=data["filters"],
            query_string=data["query_string"],
        )


class RumFieldStatisticsGraphResource(Resource):
    """查询字段统计图表配置"""

    RequestSerializer = RumFieldStatisticsGraphRequestSerializer

    def perform_request(self, data: dict[str, Any]) -> dict[str, Any]:
        application = _get_application(data["bk_biz_id"], data["app_name"])
        handler = RumLevelHandlerFactory.create(data["mode"], _build_data_sources([application]))
        return handler.field_statistics_graph(
            start_time=data["start_time"],
            end_time=data["end_time"],
            field=data["field"],
            filters=data["filters"],
            query_string=data["query_string"],
            extra_config={"time_alignment": data["time_alignment"], "query_method": data["query_method"]},
        )
