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

from constants.otel_query import OperatorEnum
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from bkmonitor.utils.elasticsearch.handler import QueryStringGenerator, flatten_es_dict_data
from constants.apm import OperatorGroupRelation
from core.drf_resource import Resource
from rum_web.handlers.level.factory import RumLevelHandlerFactory
from rum_web.models.application import Application
from rum_web.query.serializers import (
    RumFieldsOptionValuesRequestSerializer,
    RumGenerateQueryStringRequestSerializer,
    RumRecordsRequestSerializer,
    RumViewConfigRequestSerializer,
)
from rum_web.constants import RumQueryMode


def _get_authorized_application(bk_biz_id: int, app_name: str) -> Application:
    """获取已鉴权的 RUM 应用实例"""
    try:
        return Application.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
    except Application.DoesNotExist:
        raise ValueError(f"RUM 应用不存在: bk_biz_id={bk_biz_id}, app_name={app_name!r}")


def _build_data_sources(applications: list[Application]) -> list[TraceDatasourceTarget]:
    """从授权后的应用构造数据源目标列表"""
    return [
        TraceDatasourceTarget.build(
            bk_biz_id=app.bk_biz_id,
            app_name=app.app_name,
            table_id=app.span_result_table_id,
        )
        for app in applications
    ]


class RumRecordsResource(Resource):
    """POST /rum/search/list_records/ — 分页查询记录列表"""

    RequestSerializer = RumRecordsRequestSerializer

    def perform_request(self, data: dict[str, Any]) -> dict[str, Any]:
        application = _get_authorized_application(data["bk_biz_id"], data["app_name"])
        handler = RumLevelHandlerFactory.create(data["mode"], _build_data_sources([application]))
        response_dict = handler.list_records(
            start_time=data["start_time"],
            end_time=data["end_time"],
            offset=data["offset"],
            limit=data["limit"],
            filters=data["filters"],
            query_string=data["query_string"],
            sort=data["sort"],
            extra_config=data["extra_config"],
        )
        response_dict["data"] = [flatten_es_dict_data(data) for data in response_dict["data"]]
        return response_dict


class RumViewConfigResource(Resource):
    """GET /rum/search/view_config/ — 获取页面视图配置"""

    RequestSerializer = RumViewConfigRequestSerializer

    def perform_request(self, data: dict[str, Any]) -> dict[str, Any]:
        application = _get_authorized_application(data["bk_biz_id"], data["app_name"])
        span_handler = RumLevelHandlerFactory.create(RumQueryMode.SPAN.value, _build_data_sources([application]))
        return {
            "span_config": span_handler.view_config(
                start_time=data["start_time"],
                end_time=data["end_time"],
                extra_config=data["extra_config"],
            ),
            "view_config": {},
            "session_config": {},
        }


class RumFieldsOptionValuesResource(Resource):
    """POST /rum/search/get_fields_option_values/ — 批量查询字段可选枚举值"""

    RequestSerializer = RumFieldsOptionValuesRequestSerializer

    def perform_request(self, data: dict[str, Any]) -> dict[str, list[str]]:
        application = _get_authorized_application(data["bk_biz_id"], data["app_name"])
        handler = RumLevelHandlerFactory.create(data["mode"], _build_data_sources([application]))
        return handler.get_fields_option_values(
            start_time=data["start_time"],
            end_time=data["end_time"],
            fields=data["fields"],
            limit=data["limit"],
            filters=data["filters"],
            query_string=data["query_string"],
            extra_config=data["extra_config"],
        )


class RumGenerateQueryStringResource(Resource):
    """POST /rum/search/generate_query_string/ — 将过滤条件转换为查询字符串"""

    RequestSerializer = RumGenerateQueryStringRequestSerializer

    def perform_request(self, data: dict[str, Any]) -> str:
        generator = QueryStringGenerator(OperatorEnum.QueryStringOperatorMapping)
        for f in data["filters"]:
            generator.add_filter(
                f["key"],
                f["operator"],
                f["value"],
                f.get("options", {}).get("is_wildcard", False),
                f.get("options", {}).get("group_relation", OperatorGroupRelation.OR),
            )
        return generator.to_query_string()
