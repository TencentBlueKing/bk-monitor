# -*- coding: utf-8 -*-
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
import copy
from unittest.mock import patch

from django.test import TestCase

from apps.log_databus.models import CollectorConfig
from apps.log_esquery.esquery.dsl_builder.query_builder.query_builder_logic import (
    EsQueryBuilder,
)
from apps.log_esquery.esquery.esquery import EsQuery
from apps.log_esquery.serializers import EsQuerySearchAttrSerializer
from apps.log_search.exceptions import (
    IndexResultTableApiException,
    ScenarioNotSupportedException,
    ScenarioQueryIndexFailException,
)
from apps.log_search.models import Scenario
from apps.tests.utils import FakeRedis
from apps.utils.drf import custom_params_valid

BK_BIZ_ID = 2
STORAGE_CLUSTER_NAME = "cluster_name"
RESULT_TABLE_ID = "2_bklog.test3333"
RESULT_TABLE_NAME_ALIAS = "test3333"

SEARCH_DICT = {
    "scenario_id": Scenario.LOG,
    "indices": "2_bklog.search",
    "start_time": "2020-03-21 07:00:00",
    "end_time": "2020-03-22 23:59:59",
    "time_zone": "Asia/Shanghai",
    "query_string": "*",
    "filter": [
        {"field": "key1", "operator": "is", "value": "127.0.0.1", "condition": "and"},
        {"field": "key2", "operator": "is one of", "value": "val2", "condition": "or"},
        {"field": "key3", "operator": "is not", "value": "val3", "condition": "and"},
    ],
    "sort_list": [],
    "size": 1,
    "start": 0,
    "aggs": None,
    "highlight": None,
    "debug": True,
    "slice_search": False,
    "slice_id": 0,
    "slice_max": 0,
}

SCROLL_DICT = {
    "scenario_id": Scenario.LOG,
    "indices": "2_bklog_search_20200320*,2_bklog_search_20200321*,2_bklog_search_20200322*",
    "scroll_id": "123213",
    "scroll": "1m",
}

DSL_DICT = {
    "scenario_id": Scenario.LOG,
    "indices": "2_bklog_search_20200320*,2_bklog_search_20200321*,2_bklog_search_20200322*",
}

MAPPING_DICT = {
    "scenario_id": Scenario.LOG,
    "indices": "2_bklog_search_20200320*,2_bklog_search_20200321*,2_bklog_search_20200322*",
}

MAPPING_DICT_TIME = {
    "scenario_id": Scenario.LOG,
    "indices": "2_bklog_search",
    "start_time": "2020-12-29 16:19:47",
    "end_time": "2020-12-29 20:19:47",
    "time_zone": "Asia/Shanghai",
}

INDICES_DICT = {"scenario_id": Scenario.LOG, "indices": "2_bklog.test3333", "bk_biz_id": BK_BIZ_ID}

GET_CLUSTER_INFO_DICT = {"scenario_id": Scenario.LOG, "indices": "2_bklog.test3333", "bk_biz_id": BK_BIZ_ID}

GET_CLUSTER_INFO_EXCEPTION_DICT = {"scenario_id": Scenario.LOG, "indices": "2_bklog.test4444", "bk_biz_id": BK_BIZ_ID}

SEARCH_RESULT = {
    "scenario": Scenario.LOG,
    "indices": "2_bklog_search_20200322*,2_bklog_search_20200320*,2_bklog_search_20200321*",
    "body": {
        "from": 0,
        "size": 1,
        "query": {
            "bool": {
                "filter": [
                    {"range": {"": {"gte": 1584745200000, "lte": 1584892799000, "format": "epoch_millis"}}},
                    {
                        "bool": {
                            "should": [
                                {
                                    "bool": {
                                        "must": [{"match_phrase": {"key1": {"query": "127.0.0.1"}}}],
                                        "must_not": [],
                                    }
                                },
                                {
                                    "bool": {
                                        "must": [
                                            {
                                                "bool": {
                                                    "should": [
                                                        {"match_phrase": {"key2": "v"}},
                                                        {"match_phrase": {"key2": "a"}},
                                                        {"match_phrase": {"key2": "l"}},
                                                        {"match_phrase": {"key2": "2"}},
                                                    ]
                                                }
                                            }
                                        ],
                                        "must_not": [{"match_phrase": {"key3": {"query": "val3"}}}],
                                    }
                                },
                            ]
                        }
                    },
                ]
            }
        },
    },
}

ES_QUERY_LOG_INDICES = "2_bklog_search_20200320*,2_bklog_search_20200321*,2_bklog_search_20200322*"
ES_QUERY_BKDATA_INDICES = "2_bklog.search_20200321*,2_bklog.search_20200322*"
ES_QUERY_ES_INDICES = "2_bklog.search"

ES_QUERY_INDICES = {
    Scenario.LOG: ES_QUERY_LOG_INDICES,
    Scenario.BKDATA: ES_QUERY_BKDATA_INDICES,
    Scenario.ES: ES_QUERY_ES_INDICES,
}

CLUSTER_INFOS = {
    "2_bklog.test3333": {
        "cluster_config": {
            "domain_name": "x.x.x.x",
            "port": 10000,
            "version": "1.0",
            "cluster_id": 231,
            "cluster_name": STORAGE_CLUSTER_NAME,
        },
        "auth_info": {"username": "admin", "password": "111111"},
    }
}

SCROLL_RESULT_LOG = {}
SCROLL_RESULT_ES = {}

QUERY_RESULT_LOG = {}
QUERY_RESULT_BKDATA = {}
QUERY_RESULT_ES = {}
QUERY_MAPPING_RESULT_LOG = {}
QUERY_MAPPING_RESULT_BKDATA = {}
QUERY_MAPPING_RESULT_ES = {}
DSL_RESULT_LOG = {"dsl": "{}"}
DSL_RESULT_BKDATA = {"dsl": "{}"}
DSL_RESULT_ES = {"dsl": "{}"}

MAPPING_RESULT_LOG = []
MAPPING_RESULT_BKDATA = []
MAPPING_RESULT_ES = []

INDICES_RESULT_WITHOUT_STORAGE = [
    {
        "result_table_id": RESULT_TABLE_ID,
        "result_table_name_alias": RESULT_TABLE_NAME_ALIAS,
        "bk_biz_id": BK_BIZ_ID,
        "collector_config_id": 231,
    }
]

INDICES_RESULT_WITH_STORAGE = [
    {
        "bk_biz_id": BK_BIZ_ID,
        "collector_config_id": 231,
        "result_table_id": RESULT_TABLE_ID,
        "result_table_name_alias": RESULT_TABLE_NAME_ALIAS,
        "storage_cluster_id": 231,
        "storage_cluster_name": STORAGE_CLUSTER_NAME,
    }
]

CONFIG_DATA = {
    "result_table_config": {"bk_biz_id": BK_BIZ_ID},
    "result_table_storage": {
        "2_bklog.test3333": {"cluster_config": {"cluster_id": 231, "cluster_name": STORAGE_CLUSTER_NAME}}
    },
}

GET_CLUSTER_INFO_EXCEPTION_CONFIG_DATA = {
    "result_table_config": {"bk_biz_id": BK_BIZ_ID},
    "result_table_storage": {
        "2_bklog.test444": {"cluster_config": {"cluster_id": 231, "cluster_name": STORAGE_CLUSTER_NAME}}
    },
}

GET_CLUSTER_INFO_RESULT = {
    "bk_biz_id": BK_BIZ_ID,
    "storage_cluster_id": 231,
    "storage_cluster_name": STORAGE_CLUSTER_NAME,
}

NESTED_FIELDS_MAPPING = [
    {
        "2_bklog_student*": {
            "mappings": {
                "properties": {
                    "name": {"type": "keyword"},
                    "address": {"type": "nested"},
                    "school": {"type": "nested", "properties": {"rank": {"type": "integer"}}},
                }
            }
        }
    }
]

STRING_WITHOUT_FIELD_DSL = {
    "bool": {
        "should": [
            {"query_string": {"query": "Spongebob", "analyze_wildcard": True, "fields": ["*", "__*"], "lenient": True}},
            {
                "nested": {
                    "path": "address",
                    "query": {
                        "query_string": {
                            "query": "Spongebob",
                            "analyze_wildcard": True,
                            "fields": ["*", "__*"],
                            "lenient": True,
                        }
                    },
                }
            },
            {
                "nested": {
                    "path": "school",
                    "query": {
                        "query_string": {
                            "query": "Spongebob",
                            "analyze_wildcard": True,
                            "fields": ["*", "__*"],
                            "lenient": True,
                        }
                    },
                }
            },
        ]
    }
}

STRING_WITH_NESTED_FIELD_DSL = {
    "bool": {
        "must": [
            {"term": {"name": {"value": "Spongebob"}}},
            {"nested": {"path": "address", "query": {"match_phrase": {"address.house": {"query": "pineapple house"}}}}},
            {"nested": {"path": "school", "query": {"match_phrase": {"school.teacher.name": {"query": "puff"}}}}},
        ]
    }
}

STRING_WITH_FIELD_DSL = {
    "query_string": {"query": 'name: "Spongebob"', "analyze_wildcard": True, "fields": ["*", "__*"], "lenient": True}
}

SERIALIZER_PARAMS = {
    "indices": "1_log_test,2_log_tes",
    "scenario_id": "es",
    "storage_cluster_id": 6,
    "start_time": "2024-06-14 10:40:36",
    "end_time": "2024-06-14 10:55:36",
    "query_string": "*",
    "filter": [],
    "sort_list": [["dtEventTimeStamp", "desc"], ["gseIndex", "desc"], ["iterationIndex", "desc"]],
    "start": 0,
    "size": 50,
    "aggs": {},
    "highlight": {
        "pre_tags": ["<mark>"],
        "post_tags": ["</mark>"],
        "fields": {"*": {"number_of_fragments": 0}},
        "require_field_match": False,
    },
    "use_time_range": True,
    "time_zone": "Asia/Shanghai",
    "time_range": None,
    "time_field": "dtEventTimeStamp",
    "time_field_type": "date",
    "time_field_unit": "second",
    "scroll": None,
    "collapse": None,
    "include_nested_fields": False,
}

SERIALIZER_RESULT = {
    "index_set_id": None,
    "indices": "1_log_test,2_log_tes",
    "scenario_id": "es",
    "storage_cluster_id": 6,
    "time_field": "dtEventTimeStamp",
    "time_field_type": "date",
    "time_field_unit": "second",
    "use_time_range": True,
    "include_start_time": True,
    "include_end_time": True,
    "start_time": "2024-06-14 10:40:36",
    "end_time": "2024-06-14 10:55:36",
    "time_range": None,
    "time_zone": "Asia/Shanghai",
    "query_string": "*",
    "filter": [],
    "sort_list": [["dtEventTimeStamp", "desc"], ["gseIndex", "desc"], ["iterationIndex", "desc"]],
    "start": 0,
    "size": 50,
    "dtEventTimeStamp": None,
    "search_type_tag": "search",
    "aggs": {},
    "highlight": {
        "pre_tags": ["<mark>"],
        "post_tags": ["</mark>"],
        "fields": {"*": {"number_of_fragments": 0}},
        "require_field_match": False,
    },
    "collapse": None,
    "search_after": [],
    "track_total_hits": True,
    "scroll": None,
    "include_nested_fields": False,
    "slice_search": False,
    "slice_id": 0,
    "slice_max": 0,
}


@FakeRedis("apps.utils.cache.cache")
class TestEsquery(TestCase):
    @patch(
        "apps.log_esquery.esquery.client.QueryClientLog.QueryClientLog.mapping", return_value=QUERY_MAPPING_RESULT_LOG
    )
    @patch("apps.log_esquery.esquery.client.QueryClientEs.QueryClientEs.mapping", return_value=QUERY_MAPPING_RESULT_ES)
    @patch(
        "apps.log_esquery.esquery.client.QueryClientBkData.QueryClientBkData.mapping",
        return_value=QUERY_MAPPING_RESULT_BKDATA,
    )
    def test_search_debug(self, *args, **kwargs):
        """
        测试 esquery.search()
        """
        # 原生ES bkdata 第三方ES
        scenario_list = [Scenario.LOG, Scenario.BKDATA, Scenario.ES]

        for scenario in scenario_list:
            assert_result = copy.deepcopy(SEARCH_RESULT)

            params = copy.deepcopy(SEARCH_DICT)
            params.update({"scenario_id": scenario})
            assert_result.update({"scenario": scenario})

            res = EsQuery(params).search()

            # response indices排序
            res["indices"] = ",".join(sorted(res["indices"].split(",")))

            # assert value indices排序
            assert_result["indices"] = ",".join(sorted(ES_QUERY_INDICES[scenario].split(",")))

            self.maxDiff = 10000
            self.assertEqual(res, assert_result)

    @patch("apps.log_esquery.esquery.client.QueryClientLog.QueryClientLog.query", return_value=QUERY_RESULT_LOG)
    @patch("apps.log_esquery.esquery.client.QueryClientEs.QueryClientEs.query", return_value=QUERY_RESULT_ES)
    @patch(
        "apps.log_esquery.esquery.client.QueryClientBkData.QueryClientBkData.query", return_value=QUERY_RESULT_BKDATA
    )
    @patch(
        "apps.log_esquery.esquery.client.QueryClientLog.QueryClientLog.mapping", return_value=QUERY_MAPPING_RESULT_LOG
    )
    @patch("apps.log_esquery.esquery.client.QueryClientEs.QueryClientEs.mapping", return_value=QUERY_MAPPING_RESULT_ES)
    @patch(
        "apps.log_esquery.esquery.client.QueryClientBkData.QueryClientBkData.mapping",
        return_value=QUERY_MAPPING_RESULT_BKDATA,
    )
    def test_search(self, *args, **kwargs):
        # 原生ES
        params = copy.deepcopy(SEARCH_DICT)
        params.pop("debug")

        res = EsQuery(params).search()
        if res.get("indices"):
            # response indices排序
            res["indices"] = ",".join(sorted(res["indices"].split(",")))

        self.assertEqual(res, {})

        # BKDATA
        params = copy.deepcopy(SEARCH_DICT)
        params.pop("debug")
        params.update({"scenario_id": Scenario.BKDATA})

        res = EsQuery(params).search()
        if res.get("indices"):
            res["indices"] = ",".join(sorted(res["indices"].split(",")))
        self.assertEqual(res, {})

        # 第三方ES
        params = copy.deepcopy(SEARCH_DICT)
        params.pop("debug")
        params.update({"scenario_id": Scenario.ES})

        res = EsQuery(params).search()
        if res.get("indices"):
            res["indices"] = ",".join(sorted(res["indices"].split(",")))
        self.assertEqual(res, {})

    @patch("apps.log_esquery.esquery.client.QueryClientEs.QueryClientEs.scroll", return_value=SCROLL_RESULT_ES)
    @patch("apps.log_esquery.esquery.client.QueryClientLog.QueryClientLog.scroll", return_value=SCROLL_RESULT_LOG)
    def test_scroll(self, *args, **kwargs):
        """
        测试 esquery.scroll()
        """
        # 原生ES
        params = copy.deepcopy(SCROLL_DICT)
        result = EsQuery(params).scroll()
        self.assertEqual(result, SCROLL_RESULT_LOG)

        # 第三方ES
        params = copy.deepcopy(SCROLL_DICT)
        params.update({"scenario_id": Scenario.ES})
        result = EsQuery(params).scroll()

        self.assertEqual(result, SCROLL_RESULT_ES)

    def test_scroll_exception(self):
        """
        测试 scroll不支持bkdata场景 ScenarioNotSupportedException
        """
        params = copy.deepcopy(SCROLL_DICT)
        params.update({"scenario_id": Scenario.BKDATA})

        with self.assertRaises(ScenarioNotSupportedException):
            EsQuery(params).scroll()

    @patch("apps.log_esquery.esquery.client.QueryClientEs.QueryClientEs.query", return_value={})
    @patch("apps.log_esquery.esquery.client.QueryClientBkData.QueryClientBkData.query", return_value={})
    @patch("apps.log_esquery.esquery.client.QueryClientLog.QueryClientLog.query", return_value={})
    def test_dsl(self, *args, **kwargs):
        """
        测试 esquery.dsl()
        """
        # 原生ES
        params = copy.deepcopy(DSL_DICT)
        result = EsQuery(params).dsl()
        self.assertEqual(result, DSL_RESULT_LOG)

        # bkdata
        params = copy.deepcopy(DSL_DICT)
        params.update({"scenario_id": Scenario.BKDATA})
        result = EsQuery(params).dsl()
        self.assertEqual(result, DSL_RESULT_BKDATA)

        # 第三方ES
        params = copy.deepcopy(DSL_DICT)
        params.update({"scenario_id": Scenario.ES})
        result = EsQuery(params).dsl()
        self.assertEqual(result, DSL_RESULT_ES)

    @patch("apps.log_esquery.esquery.client.QueryClientEs.QueryClientEs.mapping", return_value={})
    @patch("apps.log_esquery.esquery.client.QueryClientBkData.QueryClientBkData.mapping", return_value={})
    @patch("apps.log_esquery.esquery.client.QueryClientLog.QueryClientLog.mapping", return_value={})
    def test_mapping(self, *args, **kwargs):
        # 原生ES
        params = copy.deepcopy(MAPPING_DICT)
        result = EsQuery(params).mapping()
        self.assertEqual(result, MAPPING_RESULT_LOG)

        # bkdata
        params = copy.deepcopy(MAPPING_DICT)
        params.update({"scenario_id": Scenario.BKDATA})
        result = EsQuery(params).mapping()
        self.assertEqual(result, MAPPING_RESULT_BKDATA)

        # 第三方ES
        params = copy.deepcopy(MAPPING_DICT)
        params.update({"scenario_id": Scenario.ES})
        result = EsQuery(params).mapping()
        self.assertEqual(result, MAPPING_RESULT_ES)

    @patch("apps.log_esquery.esquery.client.QueryClientEs.QueryClientEs.mapping", return_value={})
    @patch("apps.log_esquery.esquery.client.QueryClientBkData.QueryClientBkData.mapping", return_value={})
    @patch("apps.log_esquery.esquery.client.QueryClientLog.QueryClientLog.mapping", return_value={})
    def test_mapping_time(self, *args, **kwargs):
        # 自定义时间
        params = copy.deepcopy(MAPPING_DICT_TIME)
        params.update({"scenario_id": Scenario.LOG})
        result = EsQuery(params).mapping()
        self.assertEqual(result, MAPPING_RESULT_LOG)

    @patch("apps.api.TransferApi.get_result_table_storage", lambda _: CLUSTER_INFOS)
    def test_indices(self):
        """
        测试 EsQuery.indices()
        """
        # 测试数据库添加一条CollectorConfig数据
        CollectorConfig.objects.create(
            collector_config_id=231,
            collector_config_name="test3333",
            bk_app_code="bk_log_search",
            collector_scenario_id="row",
            bk_biz_id=BK_BIZ_ID,
            category_id="os",
            target_object_type="HOST",
            target_node_type="TOPO",
            target_nodes=[{"bk_inst_id": 52, "bk_obj_id": "module"}],
            target_subscription_diff={},
            description="test3333",
            is_active=True,
            bk_data_id=1500586,
            table_id="2_bklog.test3333",
            subscription_id=2103,
            task_id_list=["1331697"],
        )

        params = copy.deepcopy(INDICES_DICT)
        result = EsQuery(params).indices()
        self.assertEqual(result, INDICES_RESULT_WITHOUT_STORAGE)

        params.update({"with_storage": True})
        result = EsQuery(params).indices()
        self.assertEqual(result, INDICES_RESULT_WITH_STORAGE)

    def test_indices_exception(self):
        """
        测试 ScenarioQueryIndexFailException
        """
        # bkdata
        params = copy.deepcopy(INDICES_DICT)
        params.update({"scenario_id": Scenario.BKDATA})

        # 删除 bk_biz_id 键值对
        params.pop("bk_biz_id")

        with self.assertRaises(ScenarioQueryIndexFailException):
            EsQuery(params).indices()

    @patch("apps.utils.thread.MultiExecuteFunc.append", return_value=[])
    @patch("apps.utils.thread.MultiExecuteFunc.run", return_value=CONFIG_DATA)
    def test_get_cluster_info(self, *args, **kwargs):
        """
        测试 EsQuery.get_cluster_info()
        """
        params = copy.deepcopy(GET_CLUSTER_INFO_DICT)
        result = EsQuery(params).get_cluster_info()

        self.assertEqual(result, GET_CLUSTER_INFO_RESULT)

    @patch("apps.utils.thread.MultiExecuteFunc.append", return_value=[])
    @patch("apps.utils.thread.MultiExecuteFunc.run")
    def test_get_cluster_info_exception(self, config_data, *args, **kwargs):
        """
        测试 IndexResultTableApiException
        """
        params = copy.deepcopy(GET_CLUSTER_INFO_EXCEPTION_DICT)

        config_data.return_value = copy.deepcopy(GET_CLUSTER_INFO_EXCEPTION_CONFIG_DATA).pop("result_table_config")
        with self.assertRaises(IndexResultTableApiException):
            EsQuery(params).get_cluster_info()

        config_data.return_value = copy.deepcopy(GET_CLUSTER_INFO_EXCEPTION_CONFIG_DATA).pop("result_table_storage")
        with self.assertRaises(IndexResultTableApiException):
            EsQuery(params).get_cluster_info()

        GET_CLUSTER_INFO_EXCEPTION_CONFIG_DATA.update({"result_table_storage": {}})
        config_data.return_value = GET_CLUSTER_INFO_EXCEPTION_CONFIG_DATA
        with self.assertRaises(IndexResultTableApiException):
            EsQuery(params).get_cluster_info()

    def test_query_string_convert(self):
        """
        测试query_string dsl转换
        """
        params = copy.deepcopy(NESTED_FIELDS_MAPPING)
        res = EsQueryBuilder.build_query_string("Spongebob", params).to_dict().get("query")
        self.assertEqual(res, STRING_WITHOUT_FIELD_DSL)

        params = copy.deepcopy(NESTED_FIELDS_MAPPING)
        res = (
            EsQueryBuilder.build_query_string(
                'name: "Spongebob" AND address.house: "pineapple house" AND school.teacher.name: "puff"', params
            )
            .to_dict()
            .get("query")
        )
        self.assertEqual(res, STRING_WITH_NESTED_FIELD_DSL)

        params = copy.deepcopy(NESTED_FIELDS_MAPPING)
        res = EsQueryBuilder.build_query_string('name: "Spongebob"', params).to_dict().get("query")
        self.assertEqual(res, STRING_WITH_FIELD_DSL)

    def test_params_valid_serializer(self):
        """
        测试params_valid内部执行的 serializer序列化
        """
        serialize_params = copy.deepcopy(SERIALIZER_PARAMS)
        serialize_result = copy.deepcopy(SERIALIZER_RESULT)
        scenario_ids = ["es", "log", "bkdata"]

        for scenario_id in scenario_ids:
            serialize_params.update({"scenario_id": scenario_id})
            serialize_result.update({"scenario_id": scenario_id})
            # 验证不传入track_total_hits的情况
            serialize_params.pop("track_total_hits", "pass")
            serialize_result.pop("track_total_hits", "pass")
            res = custom_params_valid(EsQuerySearchAttrSerializer, serialize_params)
            if scenario_id in ["es", "log"]:
                serialize_result.update({"track_total_hits": True})
            elif scenario_id == "bkdata":
                serialize_result.update({"track_total_hits": False})
            self.assertEqual(res, serialize_result)

            # 验证track_total_hits为True的情况
            serialize_params.update({"track_total_hits": True})
            serialize_result.update({"track_total_hits": True})
            res = custom_params_valid(EsQuerySearchAttrSerializer, serialize_params)
            self.assertEqual(res, serialize_result)

            # 验证track_total_hits为False的情况
            serialize_params.update({"track_total_hits": False})
            serialize_result.update({"track_total_hits": False})
            res = custom_params_valid(EsQuerySearchAttrSerializer, serialize_params)
            self.assertEqual(res, serialize_result)
