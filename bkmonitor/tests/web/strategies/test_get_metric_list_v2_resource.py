"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.models.metric_list_cache import MetricListCache
from django.db.models.query import QuerySet
from monitor_web.strategies.resources.v2 import GetMetricListV2Resource, GetStrategyV2Resource


class TestGetMetricListV2Resource:
    def test_saved_dimensions_get_names_without_metric_metadata(self):
        query = {
            "metric_id": "custom.demo.__default__.count",
            "agg_dimension": ["base62Mm45BOZ5eM2yBMRzB", "app_name"],
            "agg_condition": [{"key": "status", "method": "eq", "value": ["failed"]}],
        }
        config = {"items": [{"query_configs": [query]}]}

        result = GetStrategyV2Resource.fill_dimension_names(config)

        assert result["items"][0]["query_configs"][0]["agg_dimension_names"] == {
            "base62Mm45BOZ5eM2yBMRzB": "所属品牌",
            "app_name": "app_name",
        }
        assert query["agg_dimension"] == ["base62Mm45BOZ5eM2yBMRzB", "app_name"]
        assert query["agg_condition"] == [{"key": "status", "method": "eq", "value": ["failed"]}]

    def test_dimension_display_paths_do_not_execute_sql(self):
        from contextlib import ExitStack

        from django.db import connections

        queries: list[str] = []

        def record_query(execute, sql, params, many, context):
            queries.append(sql)
            return execute(sql, params, many, context)

        with ExitStack() as stack:
            for connection in connections.all():
                stack.enter_context(connection.execute_wrapper(record_query))
            for count in (1, 100, 1000):
                GetStrategyV2Resource.fill_dimension_names(
                    {"items": [{"query_configs": [{"agg_dimension": ["base62Mm45BOZ5eM2yBMRzB"]}] * count}]}
                )
                GetMetricListV2Resource.translate_metric(
                    {"dimensions": [{"id": "base62Mm45BOZ5eM2yBMRzB", "name": ""}] * count}
                )

        assert queries == []

    def test_dimension_names_are_readable_without_changing_cached_fields(self):
        dimensions = [
            {"id": "base62Mm45BOZ5eM2yBMRzB", "name": "base62Mm45BOZ5eM2yBMRzB"},
            {"id": "base62L6Z57G75BOZ5pm45", "name": "业务自定义名称"},
        ]

        result = GetMetricListV2Resource.translate_metric({"dimensions": dimensions})

        assert result["dimensions"] == [
            {"id": "base62Mm45BOZ5eM2yBMRzB", "name": "所属品牌"},
            {"id": "base62L6Z57G75BOZ5pm45", "name": "业务自定义名称"},
        ]
        assert dimensions[0]["name"] == dimensions[0]["id"]

    def test_serializer_accepts_zero_page_for_compatibility(self):
        serializer = GetMetricListV2Resource.RequestSerializer(
            data={
                "bk_biz_id": 2,
                "page": 0,
                "page_size": 100,
            }
        )

        assert serializer.is_valid()

    def test_page_filter_treats_zero_page_as_first_page_when_page_size_is_positive(self, mocker):
        mocker.patch.object(QuerySet, "count", return_value=2855)

        metrics, count = GetMetricListV2Resource.page_filter(
            MetricListCache.objects.all(),
            {
                "page": 0,
                "page_size": 100,
            },
        )

        assert count == 2855
        assert metrics.query.low_mark == 0
        assert metrics.query.high_mark == 100

    def test_page_filter_keeps_zero_page_size_unpaginated(self, mocker):
        mocker.patch.object(QuerySet, "count", return_value=2855)

        metrics, count = GetMetricListV2Resource.page_filter(
            MetricListCache.objects.all(),
            {
                "page": 0,
                "page_size": 0,
            },
        )

        assert count == 2855
        assert metrics.query.low_mark == 0
        assert metrics.query.high_mark is None

    def test_data_source_filter_orders_by_frequency_and_id(self):
        params = {
            "data_source_label": [],
            "data_source": [],
        }

        metrics = GetMetricListV2Resource.data_source_filter(MetricListCache.objects.all(), params)

        assert metrics.query.order_by == ("-use_frequency", "id")
