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
import pytest

from constants.data_source import DataSourceLabel, DataTypeLabel
from monitor_web.grafana.resources.unify_query import DimensionUnifyQuery

get_dimension_data_return = {
    "values": {
        "bk_biz_id": ["2", "4"],
        "ip": [
            "127.0.0.1",
        ],
        "id": ["7878", "785858"],
        "bk_supplier_id": [],
    }
}


def get_params_by_bkmonitor_timeseries(dimension_field, data_source_label, data_type_label=DataTypeLabel.TIME_SERIES):
    return {
        "dimension_field": dimension_field,
        "target": [],
        "bk_biz_id": 2,
        "query_configs": [
            {
                "data_source_label": data_source_label,
                "data_type_label": data_type_label,
                "metrics": [{"field": "usage", "method": "AVG", "alias": "a", "display": False}],
                "table": "system.cpu_summary",
                "group_by": ["bk_target_ip", "bk_target_cloud_id"],
                "where": [],
                "filter_dict": {},
                "time_field": "time",
                "query_string": "",
            }
        ],
        "start_time": 1630379732,
        "end_time": 1630383332,
        "slimit": 1000,
    }


@pytest.mark.django_db
class TestDimensionUnifyQuery:
    """
    测试拉取维度
    """

    resource_name = "resource.grafana.dimension_unify_query"

    def test_bkmonitor_time_series_by_single_target(self, mocker):
        """
        时序数据下的单指标查询
        """
        mocker.patch(
            "api.unify_query.default.GetDimensionDataResource.perform_request", return_value=get_dimension_data_return
        )
        dimension_unify_query = DimensionUnifyQuery()
        params = get_params_by_bkmonitor_timeseries(
            dimension_field="bk_biz_id", data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR
        )
        data = dimension_unify_query.perform_request(params)
        data.sort(key=lambda x: x["value"])
        assert data == [{"label": "2", "value": "2"}, {"label": "4", "value": "4"}]

    def test_bkmonitor_time_series_by_more_target(self, mocker):
        """
        时序数据下的多指标查询
        """
        mocker.patch(
            "api.unify_query.default.GetDimensionDataResource.perform_request", return_value=get_dimension_data_return
        )
        dimension_unify_query = DimensionUnifyQuery()
        params = get_params_by_bkmonitor_timeseries(
            dimension_field="bk_biz_id|ip", data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR
        )
        data = dimension_unify_query.perform_request(params)
        data.sort(key=lambda x: x["value"])
        assert data == [
            {"label": "2|127.0.0.1", "value": "2|127.0.0.1"},
            {"label": "4|127.0.0.1", "value": "4|127.0.0.1"},
        ]

    def test_bkmonitor_time_series_by_more_target_with_none_data(self, mocker):
        """
        时序数据下的多指标查询（包含不存在数据）
        """
        mocker.patch(
            "api.unify_query.default.GetDimensionDataResource.perform_request", return_value=get_dimension_data_return
        )
        dimension_unify_query = DimensionUnifyQuery()
        params = get_params_by_bkmonitor_timeseries(
            dimension_field="bk_biz_id|bk_supplier_id|ip", data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR
        )
        data = dimension_unify_query.perform_request(params)
        data.sort(key=lambda x: x["value"])
        assert data == [
            {"label": "2||127.0.0.1", "value": "2||127.0.0.1"},
            {"label": "4||127.0.0.1", "value": "4||127.0.0.1"},
        ]

    def test_custom_time_series_by_single_target(self, mocker):
        """
        自定义时序下的单指标查询
        """
        mocker.patch(
            "api.unify_query.default.GetDimensionDataResource.perform_request", return_value=get_dimension_data_return
        )
        dimension_unify_query = DimensionUnifyQuery()
        params = get_params_by_bkmonitor_timeseries(
            dimension_field="bk_biz_id", data_source_label=DataSourceLabel.CUSTOM
        )
        data = dimension_unify_query.perform_request(params)
        data.sort(key=lambda x: x["value"])
        assert data == [{"label": "2", "value": "2"}, {"label": "4", "value": "4"}]

    def test_custom_time_series_by_more_target(self, mocker):
        """
        自定义时序下的多指标查询
        """
        mocker.patch(
            "api.unify_query.default.GetDimensionDataResource.perform_request", return_value=get_dimension_data_return
        )
        dimension_unify_query = DimensionUnifyQuery()
        params = get_params_by_bkmonitor_timeseries(
            dimension_field="bk_biz_id|ip", data_source_label=DataSourceLabel.CUSTOM
        )
        data = dimension_unify_query.perform_request(params)
        data.sort(key=lambda x: x["value"])
        assert data == [
            {"label": "2|127.0.0.1", "value": "2|127.0.0.1"},
            {"label": "4|127.0.0.1", "value": "4|127.0.0.1"},
        ]

    def test_custom_time_series_by_more_target_with_none_data(self, mocker):
        """
        自定义时序下的多指标查询（包含不存在数据）
        """
        mocker.patch(
            "api.unify_query.default.GetDimensionDataResource.perform_request", return_value=get_dimension_data_return
        )
        dimension_unify_query = DimensionUnifyQuery()
        params = get_params_by_bkmonitor_timeseries(
            dimension_field="bk_biz_id|bk_supplier_id|ip", data_source_label=DataSourceLabel.CUSTOM
        )
        data = dimension_unify_query.perform_request(params)
        data.sort(key=lambda x: x["value"])
        assert data == [
            {"label": "2||127.0.0.1", "value": "2||127.0.0.1"},
            {"label": "4||127.0.0.1", "value": "4||127.0.0.1"},
        ]

    def test_log_search_timeseries(self, mocker):
        """
        日志时序型数据源下的单指标查询
        """
        params = {
            "bk_biz_id": 2,
            "dimension_field": "span_name",
            "end_time": 1630726117,
            "expression": "a",
            "query_configs": [
                {
                    "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    "filter_dict": {},
                    "functions": [],
                    "group_by": ["span_name"],
                    "index_set_id": 72,
                    "interval": 60,
                    "metrics": [{"alias": "a", "field": "elapsed_time", "method": "AVG"}],
                    "table": "2_bklog.bkmonitor_otlp",
                    "time_field": "dtEventTimeStamp",
                    "where": [
                        {"key": "resource.service.name", "method": "eq", "value": ["test-service"]},
                        {"condition": "and", "key": "span_name", "method": "include", "value": ["query"]},
                    ],
                }
            ],
            "start_time": 1630722517,
        }
        es_query_search_return = {
            "_shards": {"failed": 0, "skipped": 0, "successful": 3, "total": 3},
            "aggregations": {
                "resource.service.name": {
                    "buckets": [
                        {
                            "doc_count": 8051,
                            "key": "test-service",
                            "span_name": {
                                "buckets": [
                                    {
                                        "doc_count": 1025,
                                        "dtEventTimeStamp": {
                                            "buckets": [
                                                {
                                                    "a": {"value": 2808.74358974359},
                                                    "doc_count": 39,
                                                    "key": 1630724520000,
                                                    "key_as_string": "1630724520000",
                                                },
                                                {
                                                    "a": {"value": 2004.3939393939395},
                                                    "doc_count": 33,
                                                    "key": 1630726080000,
                                                    "key_as_string": "1630726080000",
                                                },
                                            ]
                                        },
                                        "key": "influxdb-client-query",
                                    },
                                    {
                                        "doc_count": 1025,
                                        "dtEventTimeStamp": {
                                            "buckets": [
                                                {
                                                    "a": {"value": 2993.7179487179487},
                                                    "doc_count": 39,
                                                    "key": 1630724520000,
                                                    "key_as_string": "1630724520000",
                                                },
                                                {
                                                    "a": {"value": 2242.818181818182},
                                                    "doc_count": 33,
                                                    "key": 1630726080000,
                                                    "key_as_string": "1630726080000",
                                                },
                                            ]
                                        },
                                        "key": "influxdb-query-select",
                                    },
                                    {
                                        "doc_count": 971,
                                        "dtEventTimeStamp": {
                                            "buckets": [
                                                {
                                                    "a": {"value": 246.14705882352942},
                                                    "doc_count": 34,
                                                    "key": 1630724520000,
                                                    "key_as_string": "1630724520000",
                                                },
                                                {
                                                    "a": {"value": 305.35483870967744},
                                                    "doc_count": 31,
                                                    "key": 1630726080000,
                                                    "key_as_string": "1630726080000",
                                                },
                                            ]
                                        },
                                        "key": "handle-ts-query",
                                    },
                                ],
                                "doc_count_error_upper_bound": 0,
                                "sum_other_doc_count": 0,
                            },
                        }
                    ],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                }
            },
            "hits": {
                "hits": [
                    {
                        "_id": "2092de7866a41f26e7edf2f147e0bb0d",
                        "_index": "v2_2_bklog_bkmonitor_otlp_20210902_0",
                        "_score": 0.0,
                        "_source": {
                            "attributes": {
                                "promql_stmt": "avg by(bk_target_ip, bk_target_cloud_id) (avg_over_time(a[1m] "
                                "offset -59s999ms)) + on(bk_target_ip, bk_target_cloud_id) "
                                "group_right() avg by(bk_target_ip, bk_target_cloud_id) "
                                "(avg_over_time(b[1m] offset -59s999ms))"
                            },
                            "cloudId": 0,
                            "dtEventTimeStamp": "1630724613000",
                            "elapsed_time": 368,
                            "end_time": 1630724613411993,
                            "events": [],
                            "gseIndex": 490469,
                            "iterationIndex": 0,
                            "kind": 1,
                            "links": [],
                            "parent_span_id": "b8387415713cca21",
                            "path": "",
                            "resource": {"bk_data_id": 1500096, "service.name": "test-service"},
                            "serverIp": "127.0.0.1",
                            "span_id": "990f5a2181ca54f1",
                            "span_name": "handle-ts-query",
                            "start_time": 1630724613411625,
                            "status": {"code": 1},
                            "time": "1630724613000",
                            "trace_id": "a3314795fdf896b8356303c367aa4e0e",
                            "trace_state": "",
                        },
                        "_type": "_doc",
                    }
                ],
                "max_score": 0.0,
                "total": 8051,
            },
            "timed_out": False,
            "took": 13,
        }
        mocker.patch(
            "api.log_search.default.ESQuerySearchResource.perform_request", return_value=es_query_search_return
        )
        dimension_unify_query = DimensionUnifyQuery()
        data = dimension_unify_query.request(params)
        assert {item["value"] for item in data} == {"influxdb-query-select", "handle-ts-query", "influxdb-client-query"}
        assert sorted(data, key=lambda x: x["value"]) == sorted(
            [
                {"label": "influxdb-query-select", "value": "influxdb-query-select"},
                {"label": "handle-ts-query", "value": "handle-ts-query"},
                {"label": "influxdb-client-query", "value": "influxdb-client-query"},
            ],
            key=lambda x: x["value"],
        )

    def test_log_search_log(self, mocker):
        """
        日志关键字数据源下的单指标查询
        """
        params = {
            "bk_biz_id": 2,
            "dimension_field": "path",
            "end_time": 1630723218,
            "expression": "a",
            "query_configs": [
                {
                    "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
                    "data_type_label": DataTypeLabel.LOG,
                    "filter_dict": {},
                    "functions": [],
                    "group_by": ["serverIp", "path"],
                    "index_set_id": "104",
                    "interval": 60,
                    "metrics": [{"alias": "a", "field": "_index", "method": "COUNT"}],
                    "query_string": '"access-tokens" AND NOT iam',
                    "table": "2_bklog.dillon_test",
                    "time_field": "dtEventTimeStamp",
                    "where": [],
                }
            ],
            "start_time": 1630719618,
        }
        es_query_search_return = {
            "_shards": {"failed": 0, "skipped": 0, "successful": 3, "total": 3},
            "aggregations": {
                "path": {
                    "buckets": [
                        {
                            "doc_count": 139,
                            "dtEventTimeStamp": {
                                "buckets": [
                                    {
                                        "_index": {"value": 2},
                                        "doc_count": 2,
                                        "key": 1630719660000,
                                        "key_as_string": "1630719660000",
                                    },
                                    {
                                        "_index": {"value": 2},
                                        "doc_count": 2,
                                        "key": 1630723200000,
                                        "key_as_string": "1630723200000",
                                    },
                                ]
                            },
                            "key": "/var/log/messages",
                        }
                    ],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                }
            },
            "hits": {
                "hits": [
                    {
                        "_id": "6a425a1ca64f1f4e526f147fd1a39aba",
                        "_index": "v2_2_bklog_dillon_test_20210831_0",
                        "_score": 0.0,
                        "_source": {
                            "cloudId": 0,
                            "dtEventTimeStamp": "1630719736000",
                            "gseIndex": 412144,
                            "iterationIndex": 2,
                            "log": "Sep  4 09:42:15 VM-1-56-centos ssm: [GIN] 2021/09/04 - "
                            "09:42:15 | 200 |    1.285774ms |       127.0.0.1 | POST   "
                            '  "/api/v1/auth/access-tokens/verify"',
                            "path": "/var/log/messages",
                            "serverIp": "127.0.0.1",
                            "time": "1630719736000",
                        },
                        "_type": "_doc",
                    }
                ],
                "max_score": 0.0,
                "total": 139,
            },
            "timed_out": False,
            "took": 15,
        }
        mocker.patch(
            "api.log_search.default.ESQuerySearchResource.perform_request", return_value=es_query_search_return
        )
        dimension_unify_query = DimensionUnifyQuery()
        data = dimension_unify_query.request(params)
        assert data == [{"label": "/var/log/messages", "value": "/var/log/messages"}]

    def test_bkmonitor_log(self, mocker):
        """
        监控日志关键字下的单指标查询
        """
        params = {
            "bk_biz_id": 2,
            "dimension_field": "event_name",
            "end_time": 1630664129,
            "expression": "a",
            "query_configs": [
                {
                    "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                    "data_type_label": DataTypeLabel.LOG,
                    "filter_dict": {},
                    "functions": [],
                    "group_by": ["event_name"],
                    "interval": 60,
                    "metrics": [{"alias": "a", "field": "event.count", "method": "AVG"}],
                    "table": "2_bkmonitor_event_1500137",
                    "time_field": "time",
                    "where": [],
                }
            ],
            "start_time": 1630660529,
        }
        get_es_data_return = {
            "hits": {
                "hits": [
                    {
                        "sort": [1630659967000000000],
                        "_type": "_doc",
                        "_source": {
                            "event_name": "login_count",
                            "time": "1630659967000",
                            "target": "0:127.0.0.1",
                            "dimensions": {
                                "bk_biz_id": "2",
                                "bk_module_id": "34",
                                "bk_collect_config_id": "40",
                                "bk_target_topo_id": "",
                                "bk_target_topo_level": "",
                                "file_path": "this is file_path",
                                "bk_target_service_category_id": "",
                                "bk_target_ip": "127.0.0.1",
                                "bk_set_id": "7",
                                "bk_target_service_instance_id": "",
                                "bk_target_cloud_id": "0",
                            },
                            "event": {"content": "this is origin_event_content", "count": 92},
                        },
                        "_score": None,
                        "_index": "v2_2_bkmonitor_event_1500137_20210903_0",
                        "_id": "7ef80e597d346b3a4da498c8521599a6",
                    }
                ],
                "total": {"relation": "eq", "value": 180},
                "max_score": None,
            },
            "_shards": {"successful": 4, "failed": 0, "skipped": 0, "total": 4},
            "took": 16,
            "aggregations": {
                "event_name": {
                    "buckets": [
                        {
                            "time": {
                                "buckets": [
                                    {
                                        "a": {"value": 80.0},
                                        "key_as_string": "1630656420000",
                                        "key": 1630656420000,
                                        "doc_count": 3,
                                    },
                                    {
                                        "a": {"value": 92.0},
                                        "key_as_string": "1630659960000",
                                        "key": 1630659960000,
                                        "doc_count": 3,
                                    },
                                ]
                            },
                            "key": "login_count",
                            "doc_count": 180,
                        },
                        {
                            "time": {
                                "buckets": [
                                    {
                                        "a": {"value": 80.0},
                                        "key_as_string": "1630656420000",
                                        "key": 1630656420000,
                                        "doc_count": 3,
                                    },
                                    {
                                        "a": {"value": 92.0},
                                        "key_as_string": "1630659960000",
                                        "key": 1630659960000,
                                        "doc_count": 3,
                                    },
                                ]
                            },
                            "key": "login_failed_count",
                            "doc_count": 180,
                        },
                    ],
                    "sum_other_doc_count": 0,
                    "doc_count_error_upper_bound": 0,
                }
            },
            "timed_out": False,
        }
        dimension_unify_query = DimensionUnifyQuery()
        mocker.patch("api.metadata.default.GetEsDataResource.perform_request", return_value=get_es_data_return)
        data = dimension_unify_query.request(params)
        data.sort(key=lambda x: x["value"])
        assert data == [
            {"label": "login_count", "value": "login_count"},
            {"label": "login_failed_count", "value": "login_failed_count"},
        ]

    def test_custon_event(self, mocker):
        """
        自定义事件下的单指标查询
        """
        params = {
            "bk_biz_id": 2,
            "dimension_field": "kind",
            "end_time": 1630663645,
            "expression": "a",
            "query_configs": [
                {
                    "data_source_label": DataSourceLabel.CUSTOM,
                    "data_type_label": DataTypeLabel.EVENT,
                    "filter_dict": {},
                    "functions": [],
                    "group_by": ["kind"],
                    "interval": 60,
                    "metrics": [{"alias": "a", "field": "BackOff", "method": "COUNT"}],
                    "table": "2_bkmonitor_event_1500114",
                    "time_field": "time",
                    "where": [],
                }
            ],
            "start_time": 1630660045,
        }
        get_es_data_return = {
            "_shards": {"failed": 0, "skipped": 0, "successful": 4, "total": 4},
            "aggregations": {
                "dimensions.kind": {
                    "buckets": [
                        {
                            "doc_count": 12,
                            "key": "Pod",
                            "time": {
                                "buckets": [
                                    {
                                        "a": {"value": 1},
                                        "doc_count": 1,
                                        "key": 1630660260000,
                                        "key_as_string": "1630660260000",
                                    },
                                    {
                                        "a": {"value": 1},
                                        "doc_count": 1,
                                        "key": 1630663560000,
                                        "key_as_string": "1630663560000",
                                    },
                                ]
                            },
                        }
                    ],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                }
            },
            "hits": {
                "hits": [
                    {
                        "_id": "2a1d2d80f82acd33c5e423d6daee0504",
                        "_index": "v2_2_bkmonitor_event_1500114_20210819_0",
                        "_score": None,
                        "_source": {
                            "dimensions": {
                                "kind": "Pod",
                                "name": "bkmonitorbeat-267ks",
                                "namespace": "bk-monitoring",
                                "uid": "33ae0afb-03e5-11ec-b225-5254004edcb5",
                            },
                            "event": {"content": "Back-off restarting failed container", "count": 1},
                            "event_name": "BackOff",
                            "target": "kubelet",
                            "time": "1630663594000",
                        },
                        "_type": "_doc",
                        "sort": [1630663594000000000],
                    }
                ],
                "max_score": None,
                "total": {"relation": "eq", "value": 12},
            },
            "timed_out": False,
            "took": 14,
        }
        dimension_unify_query = DimensionUnifyQuery()
        mocker.patch("api.metadata.default.GetEsDataResource.perform_request", return_value=get_es_data_return)
        data = dimension_unify_query.request(params)
        data.sort(key=lambda x: x["value"])
        assert data == [{"label": "Pod", "value": "Pod"}]
