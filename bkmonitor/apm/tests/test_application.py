# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import datetime
import json
from collections import namedtuple
from dataclasses import dataclass

import mock
import pytest
from django.test import TestCase

from apm.core.discover.precalculation.storage import PrecalculateStorage
from apm.core.handlers.application_hepler import ApplicationHelper
from apm.models import (
    ApdexConfig,
    ApmInstanceDiscover,
    CustomServiceConfig,
    NormalTypeValueConfig,
    QpsConfig,
    SamplerConfig,
)
from apm.resources import (
    ApplicationInfoResource,
    ApplyDatasourceResource,
    CreateApplicationResource,
    CreateApplicationSimpleResource,
    ListApplicationResources,
    QueryEventResource,
    QueryFieldsResource,
    QueryServiceStatisticsListResource,
    QuerySpanListResource,
    QuerySpanOptionValues,
    QuerySpanResource,
    QuerySpanStatisticsListResource,
    QueryTraceByHostInstanceResource,
    QueryTraceByIdsResource,
    QueryTraceListResource,
    QueryTraceOptionValues,
    ReleaseAppConfigResource,
)
from bkm_space.api import SpaceApi


def es_query_dsl_judge(expects):
    def _result(_self, *args, **kwargs):
        query_dict = _self.to_dict()
        assert query_dict == next(expects)
        return []

    return _result


def sql_compiler_judge(fail_method, expect_mapping):
    def _first(case_name):
        def _second(_self, *args, **kwargs):
            sql = _self.query.get_compiler(using=_self.using).as_sql()
            if sql != expect_mapping[case_name]:
                fail_method("Not equal!")
            return []

        return _second

    return _first


@pytest.mark.django_db
class TestApplication(TestCase):
    """验证应用相关接口"""

    databases = {"default", "monitor_api"}

    def setUp(self):
        self.get_default_storage_config = mock.patch(
            "apm.core.handlers.application_hepler.ApplicationHelper.get_default_storage_config",
            autospec=True,
            return_value={
                "es_storage_cluster": 1,
                "es_retention": 1,
                "es_number_of_replicas": 0,
                "es_shards": 1,
                "es_slice_size": 100,
            },
        )
        self.create_application_api_mock = mock.patch(
            "apm_web.models.application.api.apm_api.create_application",
            side_effect=CreateApplicationResource(),
        )
        self.auth = mock.patch("apm_web.models.application.Application.authorization", return_value={})
        self.event_report = mock.patch("apm_web.tasks.report_apm_application_event.delay", return_value={})
        self.create_async = mock.patch("apm.task.tasks.create_application_async.delay", return_value={})
        self.create_dataid = mock.patch("apm.models.datasource.ApmDataSourceConfigBase.create_data_id", return_value={})
        self.create_trace_table = mock.patch(
            "apm.models.datasource.TraceDataSource.create_or_update_result_table",
            return_value={},
        )
        self.create_metric_table = mock.patch(
            "apm.models.datasource.MetricDataSource.create_or_update_result_table",
            return_value={},
        )

        self.space_detail = mock.patch.object(
            SpaceApi,
            "get_space_detail",
            return_value=namedtuple("Space", ("display_name",))("testBiz"),
        )

        def _es_client():
            @dataclass
            class _indices:
                get_mapping = lambda *args, **kwargs: {  # noqa
                    "trace_table_id": {
                        "mappings": {
                            "properties": {
                                "attributes": {"properties": {"apdex_type": {"type": "keyword"}}},
                                "resource": {"properties": {"service": {"properties": {"name": {"type": "keyword"}}}}},
                                "span_id": {"type": "keyword"},
                                "trace_id": {"type": "keyword"},
                            }
                        }
                    }
                }

            _C = namedtuple("C", "indices")
            _c = _C(_indices())
            return _c

        self.ts_mock = mock.patch(
            "apm.models.datasource.TraceDataSource.es_client",
            new_callable=mock.PropertyMock,
            return_value=_es_client(),
        )
        self.bk_biz_id = 1
        self.app_name = "apm_demo"
        self.start_time = 1705953906
        self.end_time = 1704312306
        self.common_query_params = {
            "bk_biz_id": self.bk_biz_id,
            "app_name": self.app_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }

        self.ts_mock.start()
        self.space_detail.start()
        self.create_dataid.start()
        self.create_trace_table.start()
        self.create_metric_table.start()
        self.create_async.start()
        self.event_report.start()
        self.auth.start()
        self.get_default_storage_config.start()
        self.create_application_api_mock.start()
        self.create_application_and_datasource()

    def tearDown(self):
        self.ts_mock.stop()
        self.space_detail.stop()
        self.create_dataid.stop()
        self.create_metric_table.stop()
        self.create_trace_table.stop()
        self.create_async.stop()
        self.get_default_storage_config.stop()
        self.create_application_api_mock.stop()
        self.auth.stop()
        self.event_report.stop()

    def create_application_and_datasource(self):
        # 创建应用
        token = CreateApplicationSimpleResource()(
            bk_biz_id=self.bk_biz_id,
            app_name=self.app_name,
            enabled_profiling=False,
            enabled_trace=True,
            enabled_metric=False,
            enabled_log=False,
        )
        self.assertIsNotNone(token)

        # 创建数据源 && 获取应用信息 && 应用列表
        response = ListApplicationResources()(bk_biz_id=self.bk_biz_id)
        self.assertEqual(len(response), 1)
        self.assertEqual(response[0]["bk_biz_id"], self.bk_biz_id)
        self.assertEqual(response[0]["app_name"], self.app_name)

        application_id = response[0]["id"]
        ApplyDatasourceResource()(
            application_id=application_id,
            trace_datasource_option=ApplicationHelper.get_default_storage_config(self.bk_biz_id),
        )
        response = ApplicationInfoResource()(application_id=application_id)
        self.assertTrue("trace_config" in response)
        self.assertTrue("metric_config" in response)
        self.assertTrue(all([response["is_enabled_metric"], response["is_enabled_trace"]]))
        self.assertFalse(all([response["is_enabled_log"], response["is_enabled_profiling"]]))

    def test_es_config(self):
        """ES 配置 测试"""

        response = QueryFieldsResource()(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        self.assertEqual(
            response,
            {
                "attributes.apdex_type": "keyword",
                "resource.service.name": "keyword",
                "span_id": "keyword",
                "trace_id": "keyword",
            },
        )

    def test_es_dsl(self):
        """ES - DSL 测试"""

        mock.patch(
            "apm.utils.es_search.EsSearch.execute",
            side_effect=es_query_dsl_judge(
                iter(
                    [
                        # query_event_by_es
                        {
                            "query": {
                                "bool": {
                                    "filter": [
                                        {"nested": {"path": "events", "query": {"exists": {"field": "events.name"}}}},
                                        {
                                            "range": {
                                                "end_time": {
                                                    "gt": self.start_time * 1000000,
                                                    "lte": self.end_time * 1000000,
                                                }
                                            }
                                        },
                                        {
                                            "nested": {
                                                "path": "events",
                                                "query": {"terms": {"events.name": ["exception"]}},
                                            }
                                        },
                                    ]
                                }
                            },
                            "size": 10000,
                            "_source": ["events", "resource", "span_name"],
                        },
                        # query_span_by_es-1
                        {
                            "query": {
                                "bool": {
                                    "filter": [
                                        {
                                            "range": {
                                                "end_time": {
                                                    "gt": self.start_time * 1000000,
                                                    "lte": self.end_time * 1000000,
                                                }
                                            }
                                        }
                                    ],
                                    "must_not": [
                                        {"terms": {"span_name": ["testSpan"]}},
                                        {"terms": {"span_id": ["123456"]}},
                                    ],
                                }
                            },
                            "size": 10000,
                        },
                        # query_span_by_es-2
                        {
                            "query": {
                                "bool": {
                                    "filter": [
                                        {
                                            "range": {
                                                "end_time": {
                                                    "gt": self.start_time * 1000000,
                                                    "lte": self.end_time * 1000000,
                                                }
                                            }
                                        },
                                        {"bool": {"should": [{"exists": {"field": "attributes.http.url"}}]}},
                                    ],
                                    "must_not": [
                                        {"terms": {"span_name": ["testSpan"]}},
                                        {"terms": {"span_id": ["123456"]}},
                                    ],
                                }
                            },
                            "aggs": {
                                "group": {
                                    "composite": {
                                        "size": 10000,
                                        "sources": [
                                            {
                                                "http_url": {
                                                    "terms": {"field": "attributes.http.url", "missing_bucket": True}
                                                }
                                            }
                                        ],
                                    },
                                    "aggs": {
                                        "avg_duration": {"avg": {"field": "elapsed_time"}},
                                        "max_duration": {"max": {"field": "elapsed_time"}},
                                        "min_duration": {"min": {"field": "elapsed_time"}},
                                        "sum_duration": {"sum": {"field": "elapsed_time"}},
                                    },
                                }
                            },
                            "size": 0,
                        },
                    ]
                )
            ),
            autospec=True,
        ).start()

        # 查询 events
        with self.subTest("query_event_by_es"):
            QueryEventResource()(
                **{
                    **self.common_query_params,
                    "name": ["exception"],
                }
            )

        # 查询 span
        with self.subTest("query_span_by_es"):
            params = {
                **self.common_query_params,
                "filter_params": [
                    {"key": "span_name", "op": "!=", "value": ["testSpan"]},
                    {"key": "span_id", "op": "!=", "value": ["123456"]},
                ],
            }
            QuerySpanResource()(**params)
            params["group_keys"] = ["http_url"]
            QuerySpanResource()(**params)

    def test_unify_query_compiler(self):
        """
        UnifyQuery 查询 - 测试
        TODO 只写了普通情况 还缺少:
        # 服务统计 - 错误
        # 接口统计 - 根 Span 、 入口 Span 、 错误
        # App 关联查询
        """

        compiler_judge = sql_compiler_judge(
            self.fail,
            {
                "trace_list_with_precalculate": (
                    'unifyquery',
                    {
                        "bk_biz_id": None,
                        "query_configs": [
                            {
                                "data_type_label": "log",
                                "data_source_label": "bk_apm",
                                "reference_name": "a",
                                "table": "pre_calculate_test_table",
                                "time_field": "min_start_time",
                                "select": [
                                    'app_id',
                                    'app_name',
                                    'biz_id',
                                    'category_statistics',
                                    'error',
                                    'error_count',
                                    'hierarchy_count',
                                    'kind_statistics',
                                    'max_end_time',
                                    'min_start_time',
                                    'root_service',
                                    'root_service_category',
                                    'root_service_kind',
                                    'root_service_span_id',
                                    'root_service_span_name',
                                    'root_service_status_code',
                                    'root_span_kind',
                                    'root_span_name',
                                    'root_span_service',
                                    'service_count',
                                    'span_count',
                                    'span_max_duration',
                                    'span_min_duration',
                                    'trace_duration',
                                    'trace_id',
                                ],
                                "distinct": "",
                                "where": [],
                                "metrics": [],
                                "group_by": [],
                                "dimension_fields": [],
                                "filter_dict": {
                                    "collections.span_name__eq": ["testSpan"],
                                    "span_id__include": "123456",
                                    "app_name__eq": "apm_demo",
                                    "biz_id__eq": 1,
                                },
                                "query_string": "*",
                                "nested_paths": {},
                                "order_by": ["min_start_time desc"],
                            }
                        ],
                        "dimension_fields": [],
                        "functions": [],
                        "expression": "a",
                        "limit": 10,
                        "offset": 0,
                        "start_time": 1705953901000,
                        "end_time": 1704312311000,
                        "search_after_key": None,
                    },
                ),
                "trace_list_with_origin": (
                    'unifyquery',
                    {
                        'bk_biz_id': None,
                        'query_configs': [
                            {
                                'data_type_label': 'log',
                                'data_source_label': 'bk_apm',
                                'reference_name': 'a',
                                'table': '',
                                'time_field': 'end_time',
                                'select': [],
                                'distinct': 'trace_id',
                                'where': [],
                                'metrics': [],
                                'group_by': [],
                                'dimension_fields': [],
                                'filter_dict': {'span_name__eq': ['testSpan'], 'span_id__include': '123456'},
                                'query_string': '*',
                                'nested_paths': {},
                                'order_by': [],
                            }
                        ],
                        'dimension_fields': [],
                        'functions': [],
                        'expression': 'a',
                        'limit': 10,
                        'offset': 0,
                        'start_time': 1705953901000,
                        'end_time': 1704312311000,
                        'search_after_key': None,
                    },
                ),
                "span_list": (
                    'unifyquery',
                    {
                        'bk_biz_id': None,
                        'query_configs': [
                            {
                                'data_type_label': 'log',
                                'data_source_label': 'bk_apm',
                                'reference_name': 'a',
                                'table': '',
                                'time_field': 'end_time',
                                'select': [
                                    'attributes',
                                    'elapsed_time',
                                    'end_time',
                                    'events',
                                    'kind',
                                    'links',
                                    'parent_span_id',
                                    'resource',
                                    'span_id',
                                    'span_name',
                                    'start_time',
                                    'status',
                                    'trace_id',
                                    'trace_state',
                                ],
                                'distinct': '',
                                'where': [],
                                'metrics': [],
                                'group_by': [],
                                'dimension_fields': [],
                                'filter_dict': {'span_name__eq': ['testSpan'], 'span_id__include': '123456'},
                                'query_string': '*',
                                'nested_paths': {},
                                'order_by': ['end_time desc'],
                            }
                        ],
                        'dimension_fields': [],
                        'functions': [],
                        'expression': 'a',
                        'limit': 10,
                        'offset': 0,
                        'start_time': 1705953901000,
                        'end_time': 1704312311000,
                        'search_after_key': None,
                    },
                ),
                "service_statistics": (
                    'unifyquery',
                    {
                        'bk_biz_id': None,
                        'query_configs': [
                            {
                                'data_type_label': 'log',
                                'data_source_label': 'bk_apm',
                                'reference_name': 'a',
                                'table': '1_bkapm.trace_apm_demo',
                                'time_field': 'end_time',
                                'select': [],
                                'distinct': '',
                                'where': [],
                                'metrics': [
                                    {'field': 'resource.service.name', 'alias': 'span_count', 'method': 'count'},
                                    {'field': 'elapsed_time', 'alias': 'avg_duration', 'method': 'avg'},
                                    {'field': 'elapsed_time', 'alias': 'p50_duration', 'method': 'cp50'},
                                    {'field': 'elapsed_time', 'alias': 'p90_duration', 'method': 'cp90'},
                                ],
                                'group_by': ['resource.service.name', 'kind'],
                                'dimension_fields': [],
                                'filter_dict': {'span_name__eq': ['testSpan'], 'span_id__include': '123456'},
                                'query_string': '*',
                                'nested_paths': {},
                                'order_by': ['end_time desc'],
                            }
                        ],
                        'dimension_fields': [],
                        'functions': [],
                        'expression': 'a',
                        'limit': 10,
                        'offset': 0,
                        'start_time': 1705953901000,
                        'end_time': 1704312311000,
                        'search_after_key': {},
                    },
                ),
                "span_statistics": (
                    'unifyquery',
                    {
                        'bk_biz_id': None,
                        'query_configs': [
                            {
                                'data_type_label': 'log',
                                'data_source_label': 'bk_apm',
                                'reference_name': 'a',
                                'table': '1_bkapm.trace_apm_demo',
                                'time_field': 'end_time',
                                'select': [],
                                'distinct': '',
                                'where': [],
                                'metrics': [
                                    {'field': 'span_name', 'alias': 'span_count', 'method': 'count'},
                                    {'field': 'elapsed_time', 'alias': 'avg_duration', 'method': 'avg'},
                                    {'field': 'elapsed_time', 'alias': 'p50_duration', 'method': 'cp50'},
                                    {'field': 'elapsed_time', 'alias': 'p90_duration', 'method': 'cp90'},
                                ],
                                'group_by': ['span_name', 'resource.service.name', 'kind'],
                                'dimension_fields': [],
                                'filter_dict': {'span_name__eq': ['testSpan'], 'span_id__include': '123456'},
                                'query_string': '*',
                                'nested_paths': {},
                                'order_by': ['end_time desc'],
                            }
                        ],
                        'dimension_fields': [],
                        'functions': [],
                        'expression': 'a',
                        'limit': 10,
                        'offset': 0,
                        'start_time': 1705953901000,
                        'end_time': 1704312311000,
                        'search_after_key': {},
                    },
                ),
                "trace_options": (
                    'unifyquery',
                    {
                        'bk_biz_id': None,
                        'query_configs': [
                            {
                                'data_type_label': 'log',
                                'data_source_label': 'bk_apm',
                                'reference_name': 'a',
                                'table': 'pre_calculate_test_table',
                                'time_field': 'min_start_time',
                                'select': [],
                                'distinct': '',
                                'where': [],
                                'metrics': [{'field': 'span_name', 'alias': 'count', 'method': 'count'}],
                                'group_by': ['span_name'],
                                'dimension_fields': [],
                                'filter_dict': {'app_name__eq': 'apm_demo', 'biz_id__eq': 1},
                                'query_string': '*',
                                'nested_paths': {},
                                'order_by': ['min_start_time desc'],
                            }
                        ],
                        'dimension_fields': [],
                        'functions': [],
                        'expression': 'a',
                        'limit': 500,
                        'offset': 0,
                        'start_time': 1705953901000,
                        'end_time': 1704312311000,
                        'search_after_key': None,
                    },
                ),
                "span_options": (
                    'unifyquery',
                    {
                        'bk_biz_id': None,
                        'query_configs': [
                            {
                                'data_type_label': 'log',
                                'data_source_label': 'bk_apm',
                                'reference_name': 'a',
                                'table': '',
                                'time_field': '',
                                'select': [],
                                'distinct': '',
                                'where': [],
                                'metrics': [{'field': 'attributes.http.url', 'alias': 'count', 'method': 'count'}],
                                'group_by': ['attributes.http.url'],
                                'dimension_fields': [],
                                'filter_dict': {},
                                'query_string': '*',
                                'nested_paths': {},
                                'order_by': [],
                            }
                        ],
                        'dimension_fields': [],
                        'functions': [],
                        'expression': 'a',
                        'limit': 500,
                        'offset': 0,
                        'start_time': 1705953901000,
                        'end_time': 1704312311000,
                        'search_after_key': None,
                    },
                ),
                "query_trace_by_ids": (
                    'unifyquery',
                    {
                        'bk_biz_id': None,
                        'query_configs': [
                            {
                                'data_type_label': 'log',
                                'data_source_label': 'bk_apm',
                                'reference_name': 'a',
                                'table': 'biz_1_table',
                                'time_field': 'min_start_time',
                                'select': [
                                    'trace_id',
                                    'app_name',
                                    'error',
                                    'trace_duration',
                                    'root_service_category',
                                    'root_span_id',
                                ],
                                'distinct': '',
                                'where': [],
                                'metrics': [],
                                'group_by': [],
                                'dimension_fields': [],
                                'filter_dict': {'trace_id__eq': ['123456']},
                                'query_string': '*',
                                'nested_paths': {},
                                'order_by': ['min_start_time desc'],
                            },
                            {
                                'data_type_label': 'log',
                                'data_source_label': 'bk_apm',
                                'reference_name': 'b',
                                'table': 'biz_2_table',
                                'time_field': 'min_start_time',
                                'select': [
                                    'trace_id',
                                    'app_name',
                                    'error',
                                    'trace_duration',
                                    'root_service_category',
                                    'root_span_id',
                                ],
                                'distinct': '',
                                'where': [],
                                'metrics': [],
                                'group_by': [],
                                'dimension_fields': [],
                                'filter_dict': {'trace_id__eq': ['123456']},
                                'query_string': '*',
                                'nested_paths': {},
                                'order_by': ['min_start_time desc'],
                            },
                        ],
                        'dimension_fields': [],
                        'functions': [],
                        'expression': 'a or b',
                        'limit': 1,
                        'offset': 0,
                        'start_time': 1705953901000,
                        'end_time': 1704312311000,
                        'search_after_key': None,
                    },
                ),
                "query_trace_by_host": (
                    'unifyquery',
                    {
                        'bk_biz_id': None,
                        'query_configs': [
                            {
                                'data_type_label': 'log',
                                'data_source_label': 'bk_apm',
                                'reference_name': 'a',
                                'table': 'pre_calculate_test_table',
                                'time_field': 'min_start_time',
                                'select': ['trace_id', 'app_name', 'error', 'trace_duration', 'root_service_category'],
                                'distinct': '',
                                'where': [],
                                'metrics': [],
                                'group_by': [],
                                'dimension_fields': [],
                                'filter_dict': {'app_name__eq': 'apm_demo', 'biz_id__eq': 1},
                                'query_string': '*',
                                'nested_paths': {},
                                'order_by': ['min_start_time desc'],
                            }
                        ],
                        'dimension_fields': [],
                        'functions': [],
                        'expression': 'a',
                        'limit': 10,
                        'offset': 0,
                        'start_time': 1705953901000,
                        'end_time': 1704312311000,
                        'search_after_key': None,
                    },
                ),
            },
        )
        # mock 掉 _get_time_range 方法中计算 retention 边界时候用了当前时间的逻辑
        mock_time = mock.patch("datetime.datetime", wraps=datetime.datetime)
        t = mock_time.start()
        t.now.return_value = datetime.datetime.fromtimestamp(self.end_time)

        mock.patch(
            "apm.models.datasource.TraceDataSource.retention",
            new_callable=mock.PropertyMock,
            return_value=1,
        ).start()

        def _init_precalculate_storage(_self, *args, **kwargs):
            _self.is_valid = True
            _self.result_table_id = "pre_calculate_test_table"

        mock.patch.object(
            PrecalculateStorage,
            "__init__",
            lambda __self, *args, **kwargs: _init_precalculate_storage(__self, *args, **kwargs),
        ).start()
        params = {
            **self.common_query_params,
            "es_dsl": {"query": {"bool": {"filter": [{"terms": {"testKey": ["testValue"]}}]}}},
            "filters": [
                {"key": "span_name", "operator": "equal", "value": ["testSpan"]},
                {"key": "span_id", "operator": "like", "value": ["123456"]},
            ],
            "exclude_field": ["attributes.http.method"],
        }

        # Trace 列表
        with self.subTest("trace_list_with_precalculate"):
            with mock.patch(
                "bkmonitor.data_source.backends.base.compiler.SQLCompiler.execute_sql",
                side_effect=compiler_judge("trace_list_with_precalculate"),
                autospec=True,
            ):
                params["query_mode"] = "pre_calculation"
                # 预计算表查询
                QueryTraceListResource()(**params)

        with self.subTest("trace_list_with_origin"):
            with mock.patch(
                "bkmonitor.data_source.backends.base.compiler.SQLCompiler.execute_sql",
                side_effect=compiler_judge("trace_list_with_origin"),
                autospec=True,
            ):
                params["query_mode"] = "origin"
                # 原始查询
                QueryTraceListResource()(**params)

        # Span 列表
        with self.subTest("span_list"):
            with mock.patch(
                "bkmonitor.data_source.backends.base.compiler.SQLCompiler.execute_sql",
                side_effect=compiler_judge("span_list"),
                autospec=True,
            ):
                params.pop("query_mode", None)
                QuerySpanListResource()(**params)

        # 服务统计
        with self.subTest("service_statistics"):
            with mock.patch(
                "bkmonitor.data_source.backends.base.compiler.SQLCompiler.execute_sql",
                side_effect=compiler_judge("service_statistics"),
                autospec=True,
            ):
                params.pop("query_mode", None)
                QueryServiceStatisticsListResource()(**params)

        # 接口统计
        with self.subTest("span_statistics"):
            with mock.patch(
                "bkmonitor.data_source.backends.base.compiler.SQLCompiler.execute_sql",
                side_effect=compiler_judge("span_statistics"),
                autospec=True,
            ):
                params.pop("query_mode", None)
                QuerySpanStatisticsListResource()(**params)

        # Trace 候选值
        with self.subTest("trace_options"):
            with mock.patch(
                "bkmonitor.data_source.backends.base.compiler.SQLCompiler.execute_sql",
                side_effect=compiler_judge("trace_options"),
                autospec=True,
            ):
                QueryTraceOptionValues()(**{**self.common_query_params, "fields": ["span_name"]})

        # Span 候选值
        with self.subTest("span_options"):
            with mock.patch(
                "bkmonitor.data_source.backends.base.compiler.SQLCompiler.execute_sql",
                side_effect=compiler_judge("span_options"),
                autospec=True,
            ):
                QuerySpanOptionValues()(**{**self.common_query_params, "fields": ["attributes.http.url"]})

        # 根据 TraceIds 查询
        with self.subTest("query_trace_by_ids"):
            mock.patch.object(
                PrecalculateStorage,
                "fetch_result_table_ids",
                return_value=["biz_1_table", "biz_2_table"],
            ).start()
            with mock.patch(
                "bkmonitor.data_source.backends.base.compiler.SQLCompiler.execute_sql",
                side_effect=compiler_judge("query_trace_by_ids"),
                autospec=True,
            ):
                QueryTraceByIdsResource()(**{**self.common_query_params, "trace_ids": ["123456"]})

        # 根据主机查询 Trace
        with self.subTest("query_trace_by_host"):
            mock.patch(
                "apm.core.handlers.discover_handler.DiscoverHandler.get_host_instance",
                return_value=namedtuple("C", ("bk_biz_id", "app_name"))(self.bk_biz_id, self.app_name),
                autospec=True,
            ).start()
            with mock.patch(
                "bkmonitor.data_source.backends.base.compiler.SQLCompiler.execute_sql",
                side_effect=compiler_judge("query_trace_by_host"),
                autospec=True,
            ):
                QueryTraceByHostInstanceResource()(
                    **{
                        "bk_biz_id": self.bk_biz_id,
                        "ip": "127.0.0.1",
                        "bk_cloud_id": 0,
                        "start_time": self.start_time,
                        "end_time": self.end_time,
                    }
                )

    def _equal_application_config(self, params):
        filters = {"bk_biz_id": self.bk_biz_id, "app_name": self.app_name}
        self.assertEqual(
            params["apdex_config"],
            sorted(
                [
                    dict(i)
                    for i in ApdexConfig.objects.filter(
                        config_level="app_level", config_key=self.app_name, bk_biz_id=self.bk_biz_id
                    ).values("apdex_t", "predicate_key", "span_kind")
                ],
                key=lambda i: i["apdex_t"],
            ),
        )
        self.assertEqual(params["qps"], QpsConfig.objects.filter(**filters).get().qps)
        self.assertEqual(
            params["custom_service_config"],
            [
                dict(i)
                for i in CustomServiceConfig.objects.filter(**filters).values("name", "rule", "type", "match_type")
            ],
        )
        self.assertEqual(
            params["db_slow_command_config"],
            json.loads(NormalTypeValueConfig.objects.filter(**filters).get().value),
        )
        self.assertEqual(
            sorted(params["instance_name_config"]),
            sorted([i.discover_key for i in ApmInstanceDiscover.objects.filter(**filters)]),
        )
        self.assertEqual(
            [params["sampler_config"]],
            [dict(i) for i in SamplerConfig.objects.filter(**filters).values("sampler_type", "sampling_percentage")],
        )

    def test_application_config(self):
        """应用配置 - 测试"""

        mock.patch("apm.task.tasks.refresh_apm_application_config.delay", return_value={}).start()
        create_config_params = {
            "bk_biz_id": self.bk_biz_id,
            "app_name": self.app_name,
            "apdex_config": [
                {"apdex_t": 777, "predicate_key": "attributes.db.system", "span_kind": ""},
                {"apdex_t": 888, "predicate_key": "attributes.http.method", "span_kind": ""},
            ],
            "sampler_config": {"sampler_type": "random", "sampling_percentage": 88},
            "instance_name_config": ["resource.service.name", "net.peer.port"],
            "custom_service_config": [
                {
                    "name": "csA",
                    "rule": {'host': {'operator': 'eq', 'value': 'test.com'}},
                    "type": "http",
                    "match_type": "manual",
                },
            ],
            "service_configs": [
                {
                    "service_name": "serviceA",
                    "apdex_config": [{"apdex_t": 999, "predicate_key": "messaging.consumer_id", "span_kind": ""}],
                }
            ],
            "db_slow_command_config": {"destination": "db.is_slow", "rules": [{"match": "", "threshold": 500}]},
            "qps": 123,
        }
        # 创建应用配置
        ReleaseAppConfigResource()(**create_config_params)
        self._equal_application_config(create_config_params)

        # 更新应用配置
        update_config_params = {
            "bk_biz_id": self.bk_biz_id,
            "app_name": self.app_name,
            "apdex_config": [
                {"apdex_t": 999, "predicate_key": "attributes.db.system", "span_kind": ""},
            ],
            "sampler_config": {"sampler_type": "random", "sampling_percentage": 66},
            "instance_name_config": ["resource.service.namespace"],
            "custom_service_config": [
                {
                    "name": "csA-Copy",
                    "rule": {'host': {'operator': 'eq', 'value': 'testA.com'}},
                    "type": "http",
                    "match_type": "manual",
                },
                {
                    "name": "csB",
                    "rule": {'host': {'operator': 'eq', 'value': 'testB.com'}},
                    "type": "http",
                    "match_type": "manual",
                },
            ],
            "service_configs": [
                {"service_name": "serviceA", "apdex_config": []},
            ],
            "db_slow_command_config": {"destination": "db.is_slow", "rules": [{"match": "", "threshold": 888}]},
            "qps": 1,
        }
        ReleaseAppConfigResource()(**update_config_params)
        self._equal_application_config(update_config_params)
