"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import inspect
from unittest.mock import MagicMock, patch

import pytest

from bkmonitor.data_source.utils.query import BaseQuery
from core.drf_resource import Resource
from rum_web.query.resources import (
    RumFieldStatisticsGraphResource,
    RumFieldStatisticsInfoResource,
    RumFieldsOptionValuesResource,
    RumFieldsTopKResource,
    RumGenerateQueryStringResource,
    RumRecordsResource,
    RumViewConfigResource,
)
from rum_web.query.serializers import (
    BaseRumRequestSerializer,
    BaseRumSearchSerializer,
    BaseRumTimeRangeSerializer,
    FilterSerializer,
    QueryStringFilterSerializer,
    RumFieldsOptionValuesRequestSerializer,
    RumFieldsTopKRequestSerializer,
    RumFieldStatisticsGraphRequestSerializer,
    RumFieldStatisticsInfoRequestSerializer,
    RumGenerateQueryStringRequestSerializer,
    RumRecordsRequestSerializer,
    RumViewConfigRequestSerializer,
)
from rum_web.query.views import SearchViewSet


# ─────────────────────────────────────────────────────────────────────────────
# [a] 9 个 URL、HTTP 方法、Resource 和 Level 方法一一对应
# ─────────────────────────────────────────────────────────────────────────────

EXPECTED_ROUTES = [
    # (endpoint, http_method, resource_class, level_method)
    ("list_records", "POST", RumRecordsResource, "list_records"),
    ("view_config", "GET", RumViewConfigResource, "view_config"),
    ("get_fields_option_values", "POST", RumFieldsOptionValuesResource, "get_fields_option_values"),
    ("generate_query_string", "POST", RumGenerateQueryStringResource, "generate_query_string"),
    ("fields_topk", "POST", RumFieldsTopKResource, "field_topk"),
    ("field_statistics_info", "POST", RumFieldStatisticsInfoResource, "field_statistics_info"),
    ("field_statistics_graph", "POST", RumFieldStatisticsGraphResource, "field_statistics_graph"),
]


class TestResourceRoutes:
    """[a] URL、HTTP 方法、Resource 和 Level 方法一一对应"""

    def test_search_viewset_has_resource_routes(self):
        assert hasattr(SearchViewSet, "resource_routes")
        assert len(SearchViewSet.resource_routes) > 0

    @pytest.mark.parametrize("endpoint,http_method,resource_cls,_level_method", EXPECTED_ROUTES)
    def test_route_registered(self, endpoint, http_method, resource_cls, _level_method):
        """每个 endpoint 都在 resource_routes 中注册"""
        routes = SearchViewSet.resource_routes
        matched = [r for r in routes if r.endpoint == endpoint]
        assert matched, f"endpoint '{endpoint}' 未在 SearchViewSet.resource_routes 中注册"

    @pytest.mark.parametrize("endpoint,http_method,resource_cls,_level_method", EXPECTED_ROUTES)
    def test_route_http_method(self, endpoint, http_method, resource_cls, _level_method):
        """每个 endpoint 的 HTTP 方法正确"""
        routes = SearchViewSet.resource_routes
        matched = [r for r in routes if r.endpoint == endpoint]
        assert matched
        assert matched[0].method.upper() == http_method

    @pytest.mark.parametrize("endpoint,http_method,resource_cls,_level_method", EXPECTED_ROUTES)
    def test_route_resource_class(self, endpoint, http_method, resource_cls, _level_method):
        """每个 endpoint 绑定的 Resource 类正确"""
        routes = SearchViewSet.resource_routes
        matched = [r for r in routes if r.endpoint == endpoint]
        assert matched
        assert matched[0].resource_class is resource_cls

    @pytest.mark.parametrize("endpoint,http_method,resource_cls,level_method", EXPECTED_ROUTES)
    def test_resource_calls_level_method(self, endpoint, http_method, resource_cls, level_method):
        """Resource.perform_request 内部调用了对应的 Level 方法"""
        source = inspect.getsource(resource_cls.perform_request)
        assert level_method in source, f"{resource_cls.__name__}.perform_request 未调用 Level 方法 '{level_method}'"

    def test_download_topk_endpoint_exists(self):
        """download_topk 通过 @action 注册，不在 resource_routes 中"""
        assert hasattr(SearchViewSet, "download_topk")
        assert callable(SearchViewSet.download_topk)


# ─────────────────────────────────────────────────────────────────────────────
# [b] Resource 不依赖公共基类
# ─────────────────────────────────────────────────────────────────────────────


class TestResourceNoBases:
    """[b] Resource 不依赖公共基类（直接继承 Resource）"""

    @pytest.mark.parametrize(
        "resource_cls",
        [
            RumRecordsResource,
            RumViewConfigResource,
            RumFieldsOptionValuesResource,
            RumGenerateQueryStringResource,
            RumFieldsTopKResource,
            RumFieldStatisticsInfoResource,
            RumFieldStatisticsGraphResource,
        ],
    )
    def test_resource_inherits_directly_from_resource(self, resource_cls):
        assert issubclass(resource_cls, Resource)
        # 直接父类只有 Resource，不存在中间公共基类
        direct_bases = resource_cls.__bases__
        assert Resource in direct_bases, f"{resource_cls.__name__} 应直接继承 Resource"


# ─────────────────────────────────────────────────────────────────────────────
# [c] 请求协议不接受 extra_config，客户端无法覆盖 Level 配置
# ─────────────────────────────────────────────────────────────────────────────


class TestRequestProtocolNoExtraConfig:
    """[c] 请求序列化器不暴露 extra_config 字段"""

    @pytest.mark.parametrize(
        "serializer_cls",
        [
            RumRecordsRequestSerializer,
            RumViewConfigRequestSerializer,
            RumFieldsOptionValuesRequestSerializer,
            RumGenerateQueryStringRequestSerializer,
            RumFieldsTopKRequestSerializer,
            RumFieldStatisticsInfoRequestSerializer,
            RumFieldStatisticsGraphRequestSerializer,
        ],
    )
    def test_serializer_has_no_extra_config_field(self, serializer_cls):
        s = serializer_cls()
        assert "extra_config" not in s.fields, f"{serializer_cls.__name__} 不应暴露 extra_config 字段"


# ─────────────────────────────────────────────────────────────────────────────
# [d] view_config 保留 origin_field，顶层维护全量字段，分组通过字段名引用
# ─────────────────────────────────────────────────────────────────────────────


class TestViewConfigProtocol:
    """[d] view_config 协议结构验证"""

    # mock _query_info_fields 返回的原始字段列表，模拟 ES mapping 查询结果
    MOCK_INFO_FIELDS = [
        {
            "field_name": "span_name",
            "field_type": "keyword",
            "origin_field": "span_name",
            "is_agg": True,
            "is_analyzed": False,
            "is_case_sensitive": True,
            "wildcard_case_insensitive": False,
            "tokenize_on_chars": [],
        },
        {
            "field_name": "attributes.span_type",
            "field_type": "keyword",
            "origin_field": "attributes",
            "is_agg": True,
            "is_analyzed": False,
            "is_case_sensitive": True,
            "wildcard_case_insensitive": False,
            "tokenize_on_chars": [],
        },
    ]

    @pytest.fixture
    def view_config_result(self, mocker):
        """mock 掉 DB 查询和 ES 字段查询，直接调用 RumViewConfigResource 获取返回值"""
        mock_app = MagicMock()
        mock_app.bk_biz_id = 2
        mock_app.app_name = "my_app"
        mock_app.span_result_table_id = "bk_rum.default.span"
        mock_app.retention_days = 7
        mocker.patch("rum_web.query.resources._get_application", return_value=mock_app)
        mocker.patch.object(BaseQuery, "_query_info_fields", return_value=self.MOCK_INFO_FIELDS)

        return RumViewConfigResource().perform_request({"bk_biz_id": 2, "app_name": "my_app", "mode": "span"})

    def test_view_config_fields_have_origin_field(self, view_config_result):
        """每个字段都应包含 origin_field"""
        for field in view_config_result["fields"]:
            assert "origin_field" in field, f"字段 {field['field_name']} 缺少 origin_field"

    def test_view_config_groups_reference_field_names(self, view_config_result):
        """分组通过 field_names 引用字段，而非内嵌完整字段信息"""
        for group in view_config_result["groups"]:
            assert "field_names" in group
            assert isinstance(group["field_names"], list)
            for field_name in group["field_names"]:
                assert isinstance(field_name, str)

    def test_view_config_has_all_required_keys(self, view_config_result):
        required_keys = {"default_sort", "fields", "groups", "display_fields", "span_type_display_fields"}
        assert required_keys.issubset(view_config_result.keys())

    def test_view_config_nested_field_origin_field_is_top_level(self, view_config_result):
        """嵌套字段的 origin_field 应为顶层字段名"""
        nested_field = next(f for f in view_config_result["fields"] if "." in f["field_name"])
        top_level = nested_field["field_name"].split(".")[0]
        assert nested_field["origin_field"] == top_level


# ─────────────────────────────────────────────────────────────────────────────
# [e] Span 视图返回按类型配置的默认列与分组适用范围
# ─────────────────────────────────────────────────────────────────────────────


class TestSpanViewConfig:
    """[e] Span 视图 span_type_display_fields 和 groups.supported_span_types"""

    def test_span_type_display_fields_is_dict(self):
        from rum_web.constants import RumSpanType
        from rum_web.handlers.level.span import SpanLevelHandler

        handler = SpanLevelHandler(
            [
                __import__(
                    "bkmonitor.data_source.utils.apm", fromlist=["TraceDatasourceTarget"]
                ).TraceDatasourceTarget.build(bk_biz_id=2, app_name="my_app", table_id="bk_rum.default.span")
            ]
        )
        with patch.object(handler.query, "query_fields", return_value={}):
            config = handler.view_config(start_time=None, end_time=None)

        assert isinstance(config["span_type_display_fields"], dict)
        for span_type in RumSpanType:
            assert span_type.value in config["span_type_display_fields"]

    def test_groups_have_supported_span_types(self):
        from rum_web.handlers.level.span import SpanLevelHandler
        from bkmonitor.data_source.utils.apm import TraceDatasourceTarget

        handler = SpanLevelHandler(
            [TraceDatasourceTarget.build(bk_biz_id=2, app_name="my_app", table_id="bk_rum.default.span")]
        )
        with patch.object(handler.query, "query_fields", return_value={}):
            config = handler.view_config(start_time=None, end_time=None)

        for group in config["groups"]:
            assert "supported_span_types" in group
            assert isinstance(group["supported_span_types"], list)


# ─────────────────────────────────────────────────────────────────────────────
# [f] semconv 只补充别名、单位和枚举选项
# ─────────────────────────────────────────────────────────────────────────────


class TestQueryFieldsSemconvEnrichment:
    """[f] query_fields 通过 SpanSpec 补充 field_alias / field_unit / field_display_type / option_values / is_real"""

    @staticmethod
    def _build_query():
        from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
        from rum_web.handlers.query.span import SpanQuery

        target = TraceDatasourceTarget.build(bk_biz_id=2, app_name="my_app", table_id="bk_rum.default.span")
        return SpanQuery([target])

    def test_enriches_alias_unit_display_type_and_is_real(self, mocker):
        from semconv.rum.trace import SpanSpec

        base_fields = {
            "elapsed_time": {"field_name": "elapsed_time", "field_type": "long", "origin_field": "elapsed_time"},
            "start_time": {"field_name": "start_time", "field_type": "date", "origin_field": "start_time"},
        }
        mocker.patch.object(BaseQuery, "_query_fields", return_value=base_fields)

        result = self._build_query().query_fields(None, None)

        elapsed_spec = SpanSpec.from_field("elapsed_time")
        assert result["elapsed_time"]["field_alias"] == (elapsed_spec.field_alias or "elapsed_time")
        assert result["elapsed_time"]["field_unit"] == elapsed_spec.field_unit
        assert result["elapsed_time"]["is_real"] is True

        # start_time 含 DATETIME 展示类型
        assert result["start_time"]["field_display_type"] == "datetime"
        assert result["start_time"]["is_real"] is True

    def test_enriches_option_values_from_enum(self, mocker):
        from rum_web.constants import RumSpanType

        base_fields = {
            "attributes.span_type": {
                "field_name": "attributes.span_type",
                "field_type": "keyword",
                "origin_field": "attributes",
            },
        }
        mocker.patch.object(BaseQuery, "_query_fields", return_value=base_fields)

        result = self._build_query().query_fields(None, None)

        option_values = result["attributes.span_type"]["option_values"]
        assert isinstance(option_values, list)
        assert all("value" in item and "alias" in item for item in option_values)

        registered_values = {item["value"] for item in option_values}
        for span_type in RumSpanType:
            assert span_type.value in registered_values

    def test_unknown_field_keeps_name_as_alias_without_extra_keys(self, mocker):
        base_fields = {
            "unknown.field": {"field_name": "unknown.field", "field_type": "keyword", "origin_field": "unknown"},
        }
        mocker.patch.object(BaseQuery, "_query_fields", return_value=base_fields)

        result = self._build_query().query_fields(None, None)

        # 未注册字段：别名为字段名本身，且不上浮单位 / 枚举候选值
        assert result["unknown.field"]["field_alias"] == "unknown.field"
        assert "field_unit" not in result["unknown.field"]
        assert "option_values" not in result["unknown.field"]
        assert result["unknown.field"]["is_real"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 序列化器继承链测试
# ─────────────────────────────────────────────────────────────────────────────


class TestSerializerInheritance:
    """请求序列化器按「应用上下文 → 时间范围 → 检索条件」单链继承"""

    def test_filter_serializer_value_is_string_list(self):
        """FilterSerializer.value 收敛为字符串列表（child=CharField，只接受字符串）"""
        s = FilterSerializer(data={"key": "span_name", "operator": "equal", "value": ["100", "true"]})
        assert s.is_valid(), s.errors
        assert all(isinstance(v, str) for v in s.validated_data["value"])

    def test_filter_serializer_coerces_int_to_string(self):
        """FilterSerializer.value 的 CharField 会将整数强制转换为字符串（DRF 默认行为）"""
        s = FilterSerializer(data={"key": "elapsed_time", "operator": "gt", "value": [100]})
        assert s.is_valid(), s.errors
        assert s.validated_data["value"] == ["100"]

    def test_query_string_filter_serializer_value_preserves_type(self):
        """QueryStringFilterSerializer.value 保留 JSON 原类型"""
        s = QueryStringFilterSerializer(data={"key": "elapsed_time", "operator": "gt", "value": [100, True]})
        s.is_valid()
        values = s.validated_data["value"]
        assert 100 in values
        assert True in values

    def test_base_rum_request_serializer_has_mode(self):
        s = BaseRumRequestSerializer()
        assert "mode" in s.fields
        assert "bk_biz_id" in s.fields
        assert "app_name" in s.fields

    def test_base_rum_time_range_serializer_inherits_base(self):
        assert issubclass(BaseRumTimeRangeSerializer, BaseRumRequestSerializer)

    def test_base_rum_search_serializer_inherits_time_range(self):
        assert issubclass(BaseRumSearchSerializer, BaseRumTimeRangeSerializer)

    def test_records_serializer_inherits_search(self):
        assert issubclass(RumRecordsRequestSerializer, BaseRumSearchSerializer)

    def test_view_config_serializer_allows_optional_time(self):
        """view_config 的 start_time / end_time 允许不传"""
        s = RumViewConfigRequestSerializer(data={"bk_biz_id": 2, "app_name": "my_app", "mode": "span"})
        assert s.is_valid(), s.errors

    def test_generate_query_string_serializer_inherits_base_not_time_range(self):
        """generate_query_string 直接继承 BaseRumRequestSerializer，不需要时间范围"""
        assert issubclass(RumGenerateQueryStringRequestSerializer, BaseRumRequestSerializer)
        assert not issubclass(RumGenerateQueryStringRequestSerializer, BaseRumTimeRangeSerializer)

    def test_generate_query_string_uses_json_filter(self):
        """generate_query_string 使用 QueryStringFilterSerializer，保留 JSON 原类型"""
        s = RumGenerateQueryStringRequestSerializer()
        filters_field = s.fields["filters"]
        child_serializer = filters_field.child
        assert isinstance(child_serializer, QueryStringFilterSerializer)
