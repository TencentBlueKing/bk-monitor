"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from unittest.mock import Mock, patch

import arrow
from django.test import TestCase

from apps.log_search.constants import LOG_ASYNC_FIELDS
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler

CLUSTERED_RT = "2_bklog_3_clustered"
INDEX_SET_ID = 3

SEARCH_DICT = {
    "bk_biz_id": 2,
    "search_mode": "sql",
    "ip_chooser": {},
    "addition": [],
    "start_time": "2025-04-28 16:23:24.431000",
    "end_time": "2025-04-28 16:38:24.432000",
    "time_range": None,
    "from_favorite_id": 0,
    "keyword": "aa__dist_051321",
    "begin": 0,
    "size": 50,
    "aggs": {},
    "sort_list": [],
    "is_scroll_search": False,
    "scroll_id": None,
    "is_return_doc_id": False,
    "is_desensitize": True,
    "track_total_hits": False,
    "custom_indices": "",
    "index_set_id": "3",
}

INDEX_SET_DATA_OBJ_LIST = [
    {
        "index_id": 3,
        "index_set_id": 3,
        "bk_biz_id": 2,
        "bk_biz_name": None,
        "source_id": None,
        "source_name": "--",
        "result_table_id": "2_bklog.dataname_lyj2",
        "time_field": "dtEventTimeStamp",
        "result_table_name": None,
        "apply_status": "normal",
        "apply_status_name": "正常",
    }
]

HITS = [
    {
        "_index": "v2_215_bklog_test_samuel_0527010_20210527_1",
        "_source": {
            "dtEventTimeStamp": str(int(arrow.now().float_timestamp * 1000)),
            "gseIndex": 1111,
            "iterationIndex": 0,
            "log": "Mon Jun  7 17:08:41 CST 2021",
            "path": "/tmp/samuel_test/out.txt",
            "serverIp": "127.0.0.1",
            "target_day": "",
            "target_month": "Jun",
            "target_time": "7",
            "target_week": "Mon",
            "target_year": "CST",
            "target_zone": "17:08:41",
            "time": str(int(arrow.now().float_timestamp * 1000)),
        },
    }
    for x in range(10000)
]

SEARCH_RESULT = {
    "took": 100,
    "_scroll_id": str(int(arrow.now().float_timestamp * 1000)),
    "hits": {
        "hits": HITS,
        "total": 100000,
    },
}

# 点 多种情况
DOT_HITS = [
    {
        "_index": "v2_2_bklog_bkbase_aiops_backend_tencent_dev_logs_20250303_0",
        "_type": "_doc",
        "_id": "5066754728129242324",
        "_score": None,
        "_source": {
            "dtEventTimeStamp": "2025-03-07T15:59:59.854590000Z",
            "time": "2025-03-07T15:59:59.854590000Z",
            "body": "处理信号SignalAt.DURING|Procedure.MONITOR_WORKER,信号内容：{}",
            "time_unix": 1741363199854590,
            "logs_name": None,
            "severity_text": "DEBUG",
            "__ext": {},
        },
    },
    {
        "_index": "v2_2_bklog_bkbase_aiops_backend_tencent_dev_logs_20250303_0",
        "_type": "_doc",
        "_id": "5066754728129242324",
        "_score": None,
        "_source": {
            "dtEventTimeStamp": "2025-03-07T15:59:59.854590000Z",
            "time": "2025-03-07T15:59:59.854590000Z",
            "body": "处理信号SignalAt.DURING|Procedure.MONITOR_WORKER,信号内容：{}",
            "time_unix": 1741363199854590,
            "logs_name": None,
            "severity_text": "DEBUG",
            "__ext": {},
            "attributes": {
                "worker_name": "python_backend--0--session-default___scene_service_plan_preview__-owned",
                "object_id": "",
                "line_number": 123,
                "level": "DEBUG",
            },
            "resource": {
                "service_name": "AIOPS BACKEND",
                "service.name": "unknown_service",
                "service.ppp": "unknown_service",
                "service.ddd": "unknown_service",
                "service.eee": "unknown_service",
            },
        },
    },
    {
        "_index": "v2_2_bklog_bkbase_aiops_backend_tencent_dev_logs_20250303_0",
        "_type": "_doc",
        "_id": "5066754728129242324",
        "_score": None,
        "_source": {
            "dtEventTimeStamp": "2025-03-07T15:59:59.854590000Z",
            "time": "2025-03-07T15:59:59.854590000Z",
            "body": "处理信号SignalAt.DURING|Procedure.MONITOR_WORKER,信号内容：{}",
            "time_unix": 1741363199854590,
            "logs_name": None,
            "severity_text": "DEBUG",
            "__ext": {},
            "attributes": {
                "worker_name": "python_backend--0--session-default___scene_service_plan_preview__-owned",
                "object_id": "",
                "line_number": 123,
                "level": "DEBUG",
            },
            "resource": {
                "service_name": "AIOPS BACKEND",
                "service.name": "unknown_service",
                "telemetry.sdk.language": "python",
                "telemetry.sdk.name": "opentelemetry",
                "telemetry.sdk.version2": "1.20.0",
                "telemetry.sdk.version3": "1.20.0",
                "telemetry.sdk.version.name.ddd.ggg": "1.20.0",
            },
        },
    },
    {
        "_index": "v2_2_bklog_bkbase_aiops_backend_tencent_dev_logs_20250303_0",
        "_type": "_doc",
        "_id": "5066754728129242324",
        "_score": None,
        "_source": {
            "gseIndex": 4565309,
            "severity_number": 5,
            "iterationIndex": 33,
            "flags": 0,
            "path": None,
            "span_id": "",
            "attributes": {
                "worker_name": "python_backend--0--session-default___scene_service_plan_preview__-owned",
                "message": "处理信号SignalAt.DURING|Procedure.MONITOR_WORKER,信号内容：{}",
                "session_id": "",
            },
            "tett": [
                {
                    "service_name": "AIOPS BACKEND",
                    "service.name": "unknown_service",
                    "telemetry.sdk.language": "python",
                    "telemetry.sdk.name": "opentelemetry",
                    "telemetry.sdk.version": "1.20.0",
                },
                {
                    "service_name1": "AIOPS BACKEND",
                    "service1.name": "unknown_service",
                    "telemetry1.sdk.language": "python",
                    "telemetry1.sdk.name": "opentelemetry",
                    "telemetry1.sdk.version": "1.20.0",
                },
            ],
            "trace_id": "",
            "cloudId": 0,
            "serverIp": "",
            "__ext": {},
            "dtEventTimeStamp": "2025-03-07T15:59:59.854590000Z",
            "time": "2025-03-07T15:59:59.854590000Z",
            "body": "处理信号SignalAt.DURING|Procedure.MONITOR_WORKER,信号内容：{}",
            "time_unix": 1741363199854590,
            "logs_name": None,
            "severity_text": "DEBUG",
            "resource": {
                "service_name": "AIOPS BACKEND",
                "service.name": "unknown_service",
                "telemetry.sdk.language": "python",
                "telemetry.sdk.name": "opentelemetry",
                "telemetry.sdk.version": "1.20.0",
            },
        },
    },
    {
        "_index": "v2_2_bklog_bkbase_aiops_backend_tencent_dev_logs_20250303_0",
        "_type": "_doc",
        "_id": "5066754728129242324",
        "_score": None,
        "_source": {
            "gseIndex": 4565309,
            "severity_number": 5,
            "iterationIndex": 33,
            "flags": 0,
            "path": None,
            "span_id": "",
            "attributes": {
                "worker_name": "python_backend--0--session-default___scene_service_plan_preview__-owned",
                "message": "处理信号SignalAt.DURING|Procedure.MONITOR_WORKER,信号内容：{}",
                "session_id": "",
            },
            "tett": [
                {
                    "service_name": "AIOPS BACKEND",
                    "service.name": "unknown_service",
                    "telemetry.sdk.language": "python",
                    "telemetry.sdk.name": "opentelemetry",
                    "telemetry.sdk.version": [
                        {
                            "service_name": "AIOPS BACKEND",
                            "service.name": "unknown_service",
                            "telemetry.sdk.language": "python",
                            "telemetry.sdk.name": "opentelemetry",
                            "telemetry.sdk.version": "1.20.0",
                        },
                        {
                            "service_name1": "AIOPS BACKEND",
                            "service1.name": "unknown_service",
                            "telemetry1.sdk.language": "python",
                            "telemetry1.sdk.name": "opentelemetry",
                            "telemetry1.sdk.version": "1.20.0",
                        },
                    ],
                },
                {
                    "service_name1": "AIOPS BACKEND",
                    "service1.name": "unknown_service",
                    "telemetry1.sdk.language": "python",
                    "telemetry1.sdk.name": "opentelemetry",
                    "telemetry1.sdk.version": "1.20.0",
                },
            ],
            "trace_id": "",
            "cloudId": 0,
            "serverIp": "",
            "__ext": {},
            "dtEventTimeStamp": "2025-03-07T15:59:59.854590000Z",
            "time": "2025-03-07T15:59:59.854590000Z",
            "body": "处理信号SignalAt.DURING|Procedure.MONITOR_WORKER,信号内容：{}",
            "time_unix": 1741363199854590,
            "logs_name": None,
            "severity_text": "DEBUG",
            "resource": {
                "service_name": "AIOPS BACKEND",
                "service.name": "unknown_service",
                "telemetry.sdk.language": "python",
                "telemetry.sdk.name": "opentelemetry",
                "telemetry.sdk.version": "1.20.0",
            },
        },
    },
]

DOT_DICT = {
    "took": 1633,
    "timed_out": False,
    "_shards": {"total": 1502, "successful": 1502, "skipped": 1276, "failed": 0},
    "hits": {"total": 3, "max_score": None, "hits": DOT_HITS},
}

DOT_RESULT = [
    {
        "index": "v2_2_bklog_bkbase_aiops_backend_tencent_dev_logs_20250303_0",
        "__index_set_id__": 3,
        "dtEventTimeStamp": "2025-03-07T15:59:59.854590000Z",
        "time": "2025-03-07T15:59:59.854590000Z",
        "body": "处理信号SignalAt.DURING|Procedure.MONITOR_WORKER,信号内容：{}",
        "time_unix": 1741363199854590,
        "logs_name": None,
        "severity_text": "DEBUG",
        "__ext": {},
    },
    {
        "index": "v2_2_bklog_bkbase_aiops_backend_tencent_dev_logs_20250303_0",
        "__index_set_id__": 3,
        "dtEventTimeStamp": "2025-03-07T15:59:59.854590000Z",
        "time": "2025-03-07T15:59:59.854590000Z",
        "body": "处理信号SignalAt.DURING|Procedure.MONITOR_WORKER,信号内容：{}",
        "time_unix": 1741363199854590,
        "logs_name": None,
        "severity_text": "DEBUG",
        "__ext": {},
        "attributes": {
            "worker_name": "python_backend--0--session-default___scene_service_plan_preview__-owned",
            "object_id": "",
            "line_number": 123,
            "level": "DEBUG",
        },
        "resource": {
            "service_name": "AIOPS BACKEND",
            "service": {
                "name": "unknown_service",
                "ppp": "unknown_service",
                "ddd": "unknown_service",
                "eee": "unknown_service",
            },
        },
    },
    {
        "index": "v2_2_bklog_bkbase_aiops_backend_tencent_dev_logs_20250303_0",
        "__index_set_id__": 3,
        "dtEventTimeStamp": "2025-03-07T15:59:59.854590000Z",
        "time": "2025-03-07T15:59:59.854590000Z",
        "body": "处理信号SignalAt.DURING|Procedure.MONITOR_WORKER,信号内容：{}",
        "time_unix": 1741363199854590,
        "logs_name": None,
        "severity_text": "DEBUG",
        "__ext": {},
        "attributes": {
            "worker_name": "python_backend--0--session-default___scene_service_plan_preview__-owned",
            "object_id": "",
            "line_number": 123,
            "level": "DEBUG",
        },
        "resource": {
            "service_name": "AIOPS BACKEND",
            "service": {
                "name": "unknown_service",
            },
            "telemetry": {
                "sdk": {
                    "language": "python",
                    "name": "opentelemetry",
                    "version2": "1.20.0",
                    "version3": "1.20.0",
                    "version": {
                        "name": {
                            "ddd": {
                                "ggg": "1.20.0",
                            }
                        },
                    },
                }
            },
        },
    },
    {
        "index": "v2_2_bklog_bkbase_aiops_backend_tencent_dev_logs_20250303_0",
        "__index_set_id__": 3,
        "gseIndex": 4565309,
        "severity_number": 5,
        "iterationIndex": 33,
        "flags": 0,
        "path": None,
        "span_id": "",
        "attributes": {
            "worker_name": "python_backend--0--session-default___scene_service_plan_preview__-owned",
            "message": "处理信号SignalAt.DURING|Procedure.MONITOR_WORKER,信号内容：{}",
            "session_id": "",
        },
        "tett": [
            {
                "service_name": "AIOPS BACKEND",
                "service": {"name": "unknown_service"},
                "telemetry": {"sdk": {"language": "python", "name": "opentelemetry", "version": "1.20.0"}},
            },
            {
                "service_name1": "AIOPS BACKEND",
                "service1": {"name": "unknown_service"},
                "telemetry1": {"sdk": {"language": "python", "name": "opentelemetry", "version": "1.20.0"}},
            },
        ],
        "trace_id": "",
        "cloudId": 0,
        "serverIp": "",
        "__ext": {},
        "dtEventTimeStamp": "2025-03-07T15:59:59.854590000Z",
        "time": "2025-03-07T15:59:59.854590000Z",
        "body": "处理信号SignalAt.DURING|Procedure.MONITOR_WORKER,信号内容：{}",
        "time_unix": 1741363199854590,
        "logs_name": None,
        "severity_text": "DEBUG",
        "resource": {
            "service_name": "AIOPS BACKEND",
            "service": {"name": "unknown_service"},
            "telemetry": {"sdk": {"language": "python", "name": "opentelemetry", "version": "1.20.0"}},
        },
    },
    {
        "index": "v2_2_bklog_bkbase_aiops_backend_tencent_dev_logs_20250303_0",
        "__index_set_id__": 3,
        "gseIndex": 4565309,
        "severity_number": 5,
        "iterationIndex": 33,
        "flags": 0,
        "path": None,
        "span_id": "",
        "attributes": {
            "worker_name": "python_backend--0--session-default___scene_service_plan_preview__-owned",
            "message": "处理信号SignalAt.DURING|Procedure.MONITOR_WORKER,信号内容：{}",
            "session_id": "",
        },
        "tett": [
            {
                "service_name": "AIOPS BACKEND",
                "service": {"name": "unknown_service"},
                "telemetry": {
                    "sdk": {
                        "language": "python",
                        "name": "opentelemetry",
                        "version": [
                            {
                                "service_name": "AIOPS BACKEND",
                                "service": {"name": "unknown_service"},
                                "telemetry": {
                                    "sdk": {"language": "python", "name": "opentelemetry", "version": "1.20.0"}
                                },
                            },
                            {
                                "service_name1": "AIOPS BACKEND",
                                "service1": {"name": "unknown_service"},
                                "telemetry1": {
                                    "sdk": {"language": "python", "name": "opentelemetry", "version": "1.20.0"}
                                },
                            },
                        ],
                    }
                },
            },
            {
                "service_name1": "AIOPS BACKEND",
                "service1": {"name": "unknown_service"},
                "telemetry1": {"sdk": {"language": "python", "name": "opentelemetry", "version": "1.20.0"}},
            },
        ],
        "trace_id": "",
        "cloudId": 0,
        "serverIp": "",
        "__ext": {},
        "dtEventTimeStamp": "2025-03-07T15:59:59.854590000Z",
        "time": "2025-03-07T15:59:59.854590000Z",
        "body": "处理信号SignalAt.DURING|Procedure.MONITOR_WORKER,信号内容：{}",
        "time_unix": 1741363199854590,
        "logs_name": None,
        "severity_text": "DEBUG",
        "resource": {
            "service_name": "AIOPS BACKEND",
            "service": {"name": "unknown_service"},
            "telemetry": {"sdk": {"language": "python", "name": "opentelemetry", "version": "1.20.0"}},
        },
    },
]


@patch(
    "apps.log_search.handlers.search.mapping_handlers.MappingHandlers.is_nested_field",
    lambda _, __: False,
)
@patch("apps.utils.core.cache.cmdb_host.CmdbHostCache.get", lambda _, __: {})
class TestSearchHandler(TestCase):
    @patch(
        "apps.log_search.handlers.search.mapping_handlers.MappingHandlers.is_nested_field",
        lambda _, __: False,
    )
    @patch(
        "apps.log_search.handlers.search.mapping_handlers.MappingHandlers.get_all_fields_by_index_id",
        lambda _: ([], []),
    )
    @patch(
        "apps.log_search.handlers.search.search_handlers_esquery.SearchHandler._init_indices_str",
        lambda _: "",
    )
    @patch(
        "apps.log_search.handlers.search.search_handlers_esquery.SearchHandler.init_time_field",
        lambda _, index_set_id, scenario_id: ("dtEventTimeStamp", "time", "s"),
    )
    @patch(
        "apps.log_search.handlers.search.mapping_handlers.MappingHandlers.get_time_field",
        lambda _, __, index_set_id: "dtEventTimeStamp",
    )
    def setUp(self) -> None:
        self.search_handler = SearchHandler(
            index_set_id=INDEX_SET_ID, search_dict=SEARCH_DICT, pre_check_enable=False, can_highlight=False
        )
        self.search_handler._index_set = Mock()
        self.search_handler._index_set.max_async_count = 2010000
        self.search_handler._index_set.result_window = 10000
        self.search_handler._index_set.get_indexes = lambda has_applied: INDEX_SET_DATA_OBJ_LIST

    @patch("apps.api.BkLogApi.search", lambda _, data_api_retry_cls: SEARCH_RESULT)
    @patch(
        "apps.log_search.handlers.search.mapping_handlers.MappingHandlers.is_nested_field",
        lambda _, __: False,
    )
    @patch.object(SearchHandler, "_init_filter", return_value=[])
    def test_search_after_result(self, mock_init_filter):
        search_after_result = self.search_handler.search_after_result(
            search_result=SEARCH_RESULT, sorted_fields=LOG_ASYNC_FIELDS
        )
        logs_result = []
        for result in search_after_result:
            logs_result.extend(result["list"])
        self.assertEqual(len(logs_result), 2000000)

    @patch("apps.api.BkLogApi.scroll", lambda _, data_api_retry_cls: SEARCH_RESULT)
    @patch(
        "apps.log_search.handlers.search.mapping_handlers.MappingHandlers.is_nested_field",
        lambda _, __: False,
    )
    def test_scroll_result(self):
        scroll_result = self.search_handler.scroll_result(scroll_result=SEARCH_RESULT)
        logs_result = []
        for result in scroll_result:
            logs_result.extend(result["list"])

        self.assertEqual(len(logs_result), 2000000)

    def test_deal_query_result(self):
        dot_result = self.search_handler._deal_query_result(result_dict=DOT_DICT)
        dot_logs = dot_result["list"]
        self.assertEqual(dot_logs, DOT_RESULT)

    @patch(
        "apps.log_clustering.models.ClusteringConfig.get_by_index_set_id",
        lambda index_set_id, raise_exception: Mock(clustered_rt=CLUSTERED_RT),
    )
    def test_init_indices_str(self):
        indices_str = self.search_handler._init_indices_str()
        self.assertEqual(indices_str, CLUSTERED_RT)

    def test_extract_hits_total_and_can_scroll(self):
        self.assertEqual(SearchHandler._extract_hits_total({"hits": {"total": {"value": 42, "relation": "eq"}}}), 42)
        self.assertEqual(SearchHandler._extract_hits_total({"hits": {"total": {"value": 0, "relation": "eq"}}}), 0)
        self.assertEqual(SearchHandler._extract_hits_total({"hits": {"total": 7}}), 7)
        self.assertEqual(SearchHandler._extract_hits_total({}), 0)
        self.assertEqual(SearchHandler._extract_hits_total(None), 0)

        self.search_handler.scenario_id = "log"
        self.search_handler.is_scroll = True
        self.search_handler.size = 15000
        self.assertTrue(
            self.search_handler._can_scroll(
                {"_scroll_id": "s1", "hits": {"total": {"value": 10001, "relation": "eq"}}}
            )
        )
        self.assertFalse(
            self.search_handler._can_scroll({"_scroll_id": "s2", "hits": {"total": {"value": 0, "relation": "eq"}}})
        )

    def test_scroll_handles_dict_hits_total(self):
        search_result = {
            "_scroll_id": "s1",
            "hits": {"total": {"value": 2, "relation": "eq"}, "hits": [{"_id": "1"}]},
        }
        self.search_handler.size = 5
        self.search_handler.scroll = "5m"
        with (
            patch("apps.log_search.handlers.search.search_handlers_esquery.MAX_RESULT_WINDOW", 1),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.BkLogApi.scroll",
                side_effect=[
                    {"_scroll_id": "s2", "hits": {"total": {"value": 2, "relation": "eq"}, "hits": [{"_id": "2"}]}},
                    {"_scroll_id": "s3", "hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}},
                ],
            ),
        ):
            self.search_handler._scroll(search_result)
        self.assertEqual(len(search_result["hits"]["hits"]), 2)
        self.assertEqual(search_result["hits"]["total"], 0)

    def test_multi_search_and_deal_query_result_dict_hits_total(self):
        import copy

        part_1 = {
            "took": 5,
            "timed_out": False,
            "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
            "hits": {"total": {"value": 3, "relation": "eq"}, "hits": [{"_id": "1", "_source": {"dtEventTimeStamp": 1}}]},
        }
        part_2 = {
            "took": 4,
            "timed_out": False,
            "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
            "hits": {"total": {"value": 2, "relation": "eq"}, "hits": [{"_id": "2", "_source": {"dtEventTimeStamp": 2}}]},
        }
        self.search_handler.indices = "idx_a,idx_b"
        self.search_handler.start_time = "2026-01-01 00:00:00"
        self.search_handler.end_time = "2026-01-01 01:00:00"
        self.search_handler.storage_cluster_id = 1
        self.search_handler.sort_list = []
        self.search_handler._filter = None
        history_cluster = Mock(storage_cluster_id=2)

        def _search_by_cluster(params):
            return copy.deepcopy(part_1 if params["storage_cluster_id"] == 1 else part_2)

        with (
            patch.object(SearchHandler, "_init_filter", return_value=[]),
            patch("apps.log_search.handlers.search.search_handlers_esquery.StorageClusterRecord") as mock_record,
            patch.object(
                self.search_handler,
                "fetch_esquery_method",
                return_value=_search_by_cluster,
            ),
        ):
            mock_record.objects.filter.return_value.exclude.return_value = [history_cluster]
            merged = self.search_handler._multi_search(once_size=1)
        self.assertEqual(merged["hits"]["total"], 5)

        empty_1 = copy.deepcopy(part_1)
        empty_1["hits"] = {"total": {"value": 0, "relation": "eq"}, "hits": []}
        empty_2 = copy.deepcopy(part_2)
        empty_2["hits"] = {"total": {"value": 0, "relation": "eq"}, "hits": []}
        self.search_handler._filter = None

        def _search_empty_by_cluster(params):
            return copy.deepcopy(empty_1 if params["storage_cluster_id"] == 1 else empty_2)

        with (
            patch.object(SearchHandler, "_init_filter", return_value=[]),
            patch("apps.log_search.handlers.search.search_handlers_esquery.StorageClusterRecord") as mock_record,
            patch.object(
                self.search_handler,
                "fetch_esquery_method",
                return_value=_search_empty_by_cluster,
            ),
        ):
            mock_record.objects.filter.return_value.exclude.return_value = [history_cluster]
            merged_empty = self.search_handler._multi_search(once_size=1)
        self.assertEqual(merged_empty["hits"]["total"], 0)

        es9_result = copy.deepcopy(DOT_DICT)
        es9_result["hits"]["total"] = {"value": 3, "relation": "eq"}
        dealt = self.search_handler._deal_query_result(es9_result)
        self.assertEqual(dealt["total"], 3)

        es9_zero = copy.deepcopy(DOT_DICT)
        es9_zero["hits"] = {"total": {"value": 0, "relation": "eq"}, "hits": []}
        dealt_zero = self.search_handler._deal_query_result(es9_zero)
        self.assertEqual(dealt_zero["total"], 0)

