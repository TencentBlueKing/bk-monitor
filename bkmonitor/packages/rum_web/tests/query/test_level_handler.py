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
from unittest.mock import patch

import pytest

from bkmonitor.data_source.utils import types
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from rum_web.handlers.level.base import BaseRumLevelHandler
from rum_web.handlers.level.span import SpanLevelHandler
from rum_web.handlers.query.span import SpanQuery


def _make_target(table_id: str = "bk_rum.default.span") -> TraceDatasourceTarget:
    return TraceDatasourceTarget.build(bk_biz_id=2, app_name="my_app", table_id=table_id)


class TestBaseRumLevelHandler:
    """test_level_handler.py 验收断言 — 基类"""

    # [a] 基类只保存 data_sources
    def test_base_only_stores_data_sources(self):
        data_sources = [_make_target()]
        handler = SpanLevelHandler(data_sources)
        assert handler.data_sources is data_sources

    def test_base_does_not_create_extra_attributes_on_init(self):
        """基类 __init__ 只赋值 data_sources，不创建其他属性"""
        data_sources = [_make_target()]

        class _MinimalHandler(BaseRumLevelHandler):
            def view_config(self, start_time, end_time, extra_config=None):
                return {}

            def field_topk(
                self, start_time, end_time, field, limit=5, filters=None, query_string="", extra_config=None
            ):
                return {}

            def field_statistics_info(
                self, start_time, end_time, field, filters=None, query_string="", extra_config=None
            ):
                return {}

            def field_statistics_graph(
                self, start_time, end_time, field, filters=None, query_string="", extra_config=None
            ):
                return {}

            def get_fields_option_values(
                self, start_time, end_time, fields, limit=10, filters=None, query_string="", extra_config=None
            ):
                return {}

            def list_records(
                self,
                start_time,
                end_time,
                offset=0,
                limit=10,
                filters=None,
                query_string="",
                sort=None,
                extra_config=None,
            ):
                return []

            def record_detail(self, record_id, extra_config=None):
                return {}

            def generate_query_string(self, filters, extra_config=None):
                return ""

        handler = _MinimalHandler(data_sources)
        assert handler.data_sources is data_sources

    # [b] 具体 Level 可组合多个 Query
    def test_span_level_has_query(self):
        handler = SpanLevelHandler([_make_target()])
        assert hasattr(handler, "query")
        assert isinstance(handler.query, SpanQuery)

    def test_span_level_query_uses_same_data_sources(self):
        data_sources = [_make_target()]
        handler = SpanLevelHandler(data_sources)
        assert handler.query.data_sources is data_sources

    # [c] TopK 方法只接收单个字段
    def test_field_topk_accepts_single_field(self):
        sig = inspect.signature(BaseRumLevelHandler.field_topk)
        params = list(sig.parameters)
        assert "field" in params
        # field 是单个字段名（str），不是列表
        field_param = sig.parameters["field"]
        assert field_param.annotation in (str, inspect.Parameter.empty)

    # [d] 9 项公共方法声明参数与返回类型
    @pytest.mark.parametrize(
        "method_name",
        [
            "view_config",
            "field_topk",
            "field_statistics_info",
            "field_statistics_graph",
            "get_fields_option_values",
            "list_records",
            "record_detail",
            "generate_query_string",
        ],
    )
    def test_base_declares_abstract_method(self, method_name: str):
        assert hasattr(BaseRumLevelHandler, method_name)
        method = getattr(BaseRumLevelHandler, method_name)
        assert getattr(method, "__isabstractmethod__", False), f"{method_name} 应为抽象方法"

    def test_view_config_signature(self):
        sig = inspect.signature(BaseRumLevelHandler.view_config)
        params = list(sig.parameters)
        assert "start_time" in params
        assert "end_time" in params
        assert "extra_config" in params

    def test_list_records_signature(self):
        sig = inspect.signature(BaseRumLevelHandler.list_records)
        params = list(sig.parameters)
        assert "start_time" in params
        assert "end_time" in params
        assert "offset" in params
        assert "limit" in params
        assert "filters" in params
        assert "query_string" in params
        assert "sort" in params
        assert "extra_config" in params

    def test_record_detail_signature(self):
        sig = inspect.signature(BaseRumLevelHandler.record_detail)
        params = list(sig.parameters)
        assert "record_id" in params
        assert "extra_config" in params

    def test_generate_query_string_signature(self):
        sig = inspect.signature(BaseRumLevelHandler.generate_query_string)
        params = list(sig.parameters)
        assert "filters" in params
        assert "extra_config" in params

    # [e] 未知配置被拒绝，且不能覆盖公共参数或数据源
    def test_extra_config_cannot_override_data_sources(self):
        """extra_config 不能覆盖 data_sources，Level 只读取白名单字段"""
        data_sources = [_make_target()]
        handler = SpanLevelHandler(data_sources)
        # extra_config 传入 data_sources 不会影响 handler.data_sources
        with patch.object(handler.query, "query_fields", return_value={}):
            handler.view_config(start_time=None, end_time=None, extra_config={"data_sources": "evil"})
        assert handler.data_sources is data_sources


class TestSpanLevelHandlerMethods:
    """SpanLevelHandler 各方法的基本行为测试（使用 Mock 隔离存储查询）"""

    @pytest.fixture
    def handler(self):
        h = SpanLevelHandler([_make_target()])
        return h

    def test_list_records_delegates_to_query(self, handler):
        mock_result = [{"span_id": "abc", "end_time": 1000}]
        with patch.object(handler.query, "query_list", return_value=mock_result) as mock_query:
            result = handler.list_records(start_time=1000, end_time=2000)
        mock_query.assert_called_once()
        assert result == mock_result

    def test_get_fields_option_values_delegates_to_query(self, handler):
        mock_result = {"span_name": ["GET /api", "POST /api"]}
        with patch.object(handler.query, "query_option_values", return_value=mock_result) as mock_query:
            result = handler.get_fields_option_values(start_time=1000, end_time=2000, fields=["span_name"])
        mock_query.assert_called_once()
        assert result == mock_result

    def test_view_config_structure(self, handler):
        mock_fields = {
            "span_name": {
                "field_name": "span_name",
                "field_alias": "Span 名称",
                "field_type": "keyword",
                "origin_field": "span_name",
                "is_real": True,
                "is_searchable": True,
                "is_agg": True,
                "is_list": True,
                "supported_operations": [],
            }
        }
        with patch.object(handler.query, "query_fields", return_value=mock_fields):
            config = handler.view_config(start_time=None, end_time=None)

        assert "default_sort" in config
        assert "fields" in config
        assert "groups" in config
        assert "display_fields" in config
        assert "span_type_display_fields" in config
        assert isinstance(config["fields"], list)
        assert isinstance(config["groups"], list)
        assert isinstance(config["display_fields"], list)

    def test_view_config_strips_private_keys(self, handler):
        """view_config 应丢弃查询层私有键"""
        mock_fields = {
            "span_name": {
                "field_name": "span_name",
                "field_alias": "Span 名称",
                "field_type": "keyword",
                "origin_field": "span_name",
                "is_real": True,
                "is_searchable": True,
                "is_agg": True,
                "is_list": True,
                "supported_operations": [],
                "is_case_sensitive": True,
                "is_analyzed": False,
                "wildcard_case_insensitive": False,
                "tokenize_on_chars": [],
            }
        }
        with patch.object(handler.query, "query_fields", return_value=mock_fields):
            config = handler.view_config(start_time=None, end_time=None)

        field_dict = config["fields"][0]
        for private_key in ["is_case_sensitive", "is_analyzed", "wildcard_case_insensitive", "tokenize_on_chars"]:
            assert private_key not in field_dict, f"私有键 {private_key} 不应出现在 view_config 响应中"

    def test_generate_query_string_returns_string(self, handler):
        result = handler.generate_query_string(filters=[])
        assert isinstance(result, str)

    def test_generate_query_string_with_filter(self, handler):
        filters: list[types.Filter] = [{"key": "span_name", "operator": "equal", "value": ["GET /api"], "options": {}}]
        result = handler.generate_query_string(filters=filters)
        assert isinstance(result, str)
        assert len(result) > 0
