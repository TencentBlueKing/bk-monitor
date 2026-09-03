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

import pytest

from bkmonitor.data_source.utils.apm import APMQueryFilterMixin, TraceDatasourceTarget
from bkmonitor.data_source.utils.query import BaseQuery
from rum_web.handlers.query.span import SpanQuery


def _make_target(table_id: str = "bk_rum.default.span") -> TraceDatasourceTarget:
    return TraceDatasourceTarget.build(bk_biz_id=2, app_name="my_app", table_id=table_id)


class TestSpanQuery:
    """test_query.py 验收断言"""

    # [a] Query 复用 BaseQuery
    def test_span_query_inherits_base_query(self):
        assert issubclass(SpanQuery, BaseQuery)

    def test_span_query_inherits_apm_filter_mixin(self):
        assert issubclass(SpanQuery, APMQueryFilterMixin)

    # [b] 接收 list[TraceDatasourceTarget]
    def test_accepts_data_sources_list(self):
        data_sources = [_make_target()]
        query = SpanQuery(data_sources)
        assert query.data_sources is data_sources

    def test_accepts_multiple_data_sources(self):
        data_sources = [_make_target("bk_rum.biz2.span"), _make_target("bk_rum.biz3.span")]
        query = SpanQuery(data_sources)
        assert len(query.data_sources) == 2

    # [c] 具备 7 项原子能力（均为公开方法）
    @pytest.mark.parametrize(
        "method_name",
        [
            "query_list",
            "query_total",
            "query_field_topk",
            "query_option_values",
            "query_graph_config",
            "query_field_aggregated_value",
            "query_fields",
        ],
    )
    def test_has_public_query_method(self, method_name: str):
        assert hasattr(SpanQuery, method_name), f"SpanQuery 缺少公开查询方法: {method_name}"
        assert callable(getattr(SpanQuery, method_name))

    def test_query_list_signature(self):
        sig = inspect.signature(SpanQuery.query_list)
        params = list(sig.parameters)
        assert "start_time" in params
        assert "end_time" in params
        assert "offset" in params
        assert "limit" in params
        assert "filters" in params
        assert "query_string" in params
        assert "sort" in params

    def test_query_field_topk_signature(self):
        sig = inspect.signature(SpanQuery.query_field_topk)
        params = list(sig.parameters)
        assert "field" in params
        assert "limit" in params

    def test_query_fields_signature(self):
        sig = inspect.signature(SpanQuery.query_fields)
        params = list(sig.parameters)
        assert "start_time" in params
        assert "end_time" in params

    def test_default_sort_defined(self):
        assert SpanQuery.DEFAULT_SORT == ["-end_time"]

    def test_default_time_field_defined(self):
        assert SpanQuery.DEFAULT_TIME_FIELD == "end_time"
