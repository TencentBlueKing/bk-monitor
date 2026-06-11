"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from constants.result_table import ResultTableField


class RumDataSourceConfig:
    """RUM 数据源配置常量"""

    ES_KEYWORD_OPTION = {"es_type": "keyword"}

    # object 字段配置
    ES_OBJECT_OPTION = {"es_type": "object", "es_dynamic": True}

    # NESTED 配置
    ES_NESTED_OPTION = {"es_type": "nested"}

    # OTLP events 配置
    RUM_EVENT_OPTION = {
        **ES_NESTED_OPTION,
        "es_properties": {
            "attributes": {
                "properties": {
                    "exception": {"properties": {"message": {"type": "text"}, "stacktrace": {"type": "text"}}},
                    "message": {"type": "object"},
                }
            },
            "timestamp": {"type": "long"},
        },
    }

    # OTLP status 配置
    RUM_STATUS_OPTION = {
        **ES_OBJECT_OPTION,
        "es_properties": {"message": {"type": "text"}, "code": {"type": "integer"}},
    }

    RUM_FIELD_LIST = [
        {
            "field_name": "bk_biz_id",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            # metadata 创建结果表会进行保留字段检查，用于防止用户创建字段与内置字段冲突。
            # APM 是内置场景，无需进行保留字段检查，直接放行，此处添加该豁免很重要，是否会导致创建应用流程报错。
            "is_reserved_check": False,
            "description": "Bk Biz Id",
        },
        {
            "field_name": "app_name",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "keyword"},
            "is_config_by_user": True,
            "description": "App Name",
        },
        {
            "field_name": "attributes",
            "field_type": ResultTableField.FIELD_TYPE_OBJECT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_OBJECT_OPTION,
            "is_config_by_user": True,
            "description": "Span Attributes",
        },
        {
            "field_name": "resource",
            "field_type": ResultTableField.FIELD_TYPE_OBJECT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_OBJECT_OPTION,
            "is_config_by_user": True,
            "description": "Span Resources",
        },
        {
            "field_name": "events",
            "field_type": ResultTableField.FIELD_TYPE_NESTED,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": RUM_EVENT_OPTION,
            "is_config_by_user": True,
            "description": "Span Events",
        },
        {
            "field_name": "elapsed_time",
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Span Elapsed Time",
        },
        {
            "field_name": "end_time",
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Span End Time",
        },
        {
            "field_name": "start_time",
            "field_type": ResultTableField.FIELD_TYPE_LONG,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "long"},
            "is_config_by_user": True,
            "description": "Span Start Time",
        },
        {
            "field_name": "kind",
            "field_type": ResultTableField.FIELD_TYPE_INT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": {"es_type": "integer"},
            "is_config_by_user": True,
            "description": "Span Kind",
        },
        {
            "field_name": "links",
            "field_type": ResultTableField.FIELD_TYPE_NESTED,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_NESTED_OPTION,
            "is_config_by_user": True,
            "description": "Span Links",
        },
        {
            "field_name": "parent_span_id",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_KEYWORD_OPTION,
            "is_config_by_user": True,
            "description": "Parent Span ID",
        },
        {
            "field_name": "span_id",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_KEYWORD_OPTION,
            "is_config_by_user": True,
            "description": "Span ID",
        },
        {
            "field_name": "span_name",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_KEYWORD_OPTION,
            "is_config_by_user": True,
            "description": "Span Name",
        },
        {
            "field_name": "status",
            "field_type": ResultTableField.FIELD_TYPE_OBJECT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": RUM_STATUS_OPTION,
            "is_config_by_user": True,
            "description": "Span Status",
        },
        {
            "field_name": "trace_id",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_KEYWORD_OPTION,
            "is_config_by_user": True,
            "description": "Trace ID",
        },
        {
            "field_name": "trace_state",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": ES_KEYWORD_OPTION,
            "is_config_by_user": True,
            "description": "Trace State",
        },
    ]


RUM_RESULT_TABLE_OPTION = {
    "es_unique_field_list": ["trace_id", "span_id", "parent_span_id", "start_time", "end_time", "span_name"],
    # 以下为 UnifyQuery 查询所需的元数据：
    # 是否根据查询时间范围，指定具体日期的索引进行查询。
    "need_add_time": True,
    # 默认查询时间字段，页面查询时间范围过滤与此字段联动。
    "time_field": {"name": "end_time", "type": "long", "unit": "microsecond"},
}
