# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import traceback

from rest_framework.exceptions import ValidationError

from core.drf_resource import resource


def test_promql_to_query_config(mocker):
    test_cases = [
        {
            "promql": 'avg by (bk_target_ip, bk_target_cloud_id) '
            '(avg_over_time(system:disk:in_use{bk_target_ip="12.0.0.1"}[5m]))',
            "query_config": {
                "expression": "a",
                "query_configs": [
                    {
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "alias": "a",
                        "metric_id": "bk_monitor.system.disk.in_use",
                        "functions": [],
                        "result_table_id": "system.disk",
                        "agg_method": "AVG",
                        "agg_interval": 300,
                        "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
                        "agg_condition": [{"key": "bk_target_ip", "method": "eq", "value": ["12.0.0.1"]}],
                        "metric_field": "in_use",
                    }
                ],
            },
            "origin_config": """{
                "query_list": [
                    {
                        "data_source": "bkmonitor",
                        "db": "system",
                        "table_id": "system.disk",
                        "is_free_schema": false,
                        "field_name": "in_use",
                        "function": [
                            {
                                "method": "mean",
                                "dimensions": [
                                    "bk_target_ip",
                                    "bk_target_cloud_id"
                                ],
                                "position": 0,
                                "args_list": null,
                                "vargs_list": null
                            }
                        ],
                        "time_aggregation": {
                            "function": "avg_over_time",
                            "window": "5m",
                            "position": 0,
                            "vargs_list": null
                        },
                        "reference_name": "a",
                        "dimensions": null,
                        "driver": "",
                        "time_field": "",
                        "window": "",
                        "limit": 0,
                        "offset": "",
                        "offset_forward": false,
                        "slimit": 0,
                        "soffset": 0,
                        "conditions": {
                            "field_list": [
                                {
                                    "field_name": "bk_target_ip",
                                    "value": [
                                        "12.0.0.1"
                                    ],
                                    "op": "eq"
                                }
                            ],
                            "condition_list": [
                                "and"
                            ]
                        },
                        "not_combine_window": false,
                        "keep_columns": null,
                        "start_time": "",
                        "end_time": "",
                        "order_by": null,
                        "AlignInfluxdbResult": false
                    }
                ],
                "metric_merge": "a",
                "join_list": null,
                "order_by": null,
                "result_columns": null,
                "join_with_time": false,
                "keep_columns": null,
                "start_time": "",
                "end_time": "",
                "step": "",
                "type": ""
            }""",
            "raise_exception": False,
        },
        {
            "promql": 'avg by (bk_target_ip, bk_target_cloud_id) '
            '(avg_over_time(bkmonitor:system:disk:in_use{bk_target_ip="12.0.0.1"}[5m])) + '
            'sum by (bk_target_ip) (sum_over_time(bkmonitor:system:disk:free{bk_target_ip="12.0.0.2"}[1m]))',
            "query_config": {
                "expression": "a + b",
                "query_configs": [
                    {
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "alias": "a",
                        "metric_id": "bk_monitor.system.disk.in_use",
                        "functions": [],
                        "result_table_id": "system.disk",
                        "agg_method": "AVG",
                        "agg_interval": 300,
                        "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
                        "agg_condition": [{"key": "bk_target_ip", "method": "eq", "value": ["12.0.0.1"]}],
                        "metric_field": "in_use",
                    },
                    {
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "alias": "b",
                        "metric_id": "bk_monitor.system.disk.free",
                        "functions": [],
                        "result_table_id": "system.disk",
                        "agg_method": "SUM",
                        "agg_interval": 60,
                        "agg_dimension": ["bk_target_ip"],
                        "agg_condition": [{"key": "bk_target_ip", "method": "eq", "value": ["12.0.0.2"]}],
                        "metric_field": "free",
                    },
                ],
            },
            "origin_config": """{
                "query_list": [
                    {
                        "data_source": "bkmonitor",
                        "db": "system",
                        "table_id": "system.disk",
                        "is_free_schema": false,
                        "field_name": "in_use",
                        "function": [
                            {
                                "method": "mean",
                                "dimensions": [
                                    "bk_target_ip",
                                    "bk_target_cloud_id"
                                ],
                                "position": 0,
                                "args_list": null,
                                "vargs_list": null
                            }
                        ],
                        "time_aggregation": {
                            "function": "avg_over_time",
                            "window": "5m",
                            "position": 0,
                            "vargs_list": null
                        },
                        "reference_name": "a",
                        "dimensions": null,
                        "driver": "",
                        "time_field": "",
                        "window": "",
                        "limit": 0,
                        "offset": "",
                        "offset_forward": false,
                        "slimit": 0,
                        "soffset": 0,
                        "conditions": {
                            "field_list": [
                                {
                                    "field_name": "bk_target_ip",
                                    "value": [
                                        "12.0.0.1"
                                    ],
                                    "op": "eq"
                                }
                            ],
                            "condition_list": [
                                "and"
                            ]
                        },
                        "not_combine_window": false,
                        "keep_columns": null,
                        "start_time": "",
                        "end_time": "",
                        "order_by": null,
                        "AlignInfluxdbResult": false
                    },
                    {
                        "data_source": "bkmonitor",
                        "db": "system",
                        "table_id": "system.disk",
                        "is_free_schema": false,
                        "field_name": "free",
                        "function": [
                            {
                                "method": "sum",
                                "dimensions": [
                                    "bk_target_ip"
                                ],
                                "position": 0,
                                "args_list": null,
                                "vargs_list": null
                            }
                        ],
                        "time_aggregation": {
                            "function": "sum_over_time",
                            "window": "1m",
                            "position": 0,
                            "vargs_list": null
                        },
                        "reference_name": "b",
                        "dimensions": null,
                        "driver": "",
                        "time_field": "",
                        "window": "",
                        "limit": 0,
                        "offset": "",
                        "offset_forward": false,
                        "slimit": 0,
                        "soffset": 0,
                        "conditions": {
                            "field_list": [
                                {
                                    "field_name": "bk_target_ip",
                                    "value": [
                                        "12.0.0.2"
                                    ],
                                    "op": "eq"
                                }
                            ],
                            "condition_list": [
                                "and"
                            ]
                        },
                        "not_combine_window": false,
                        "keep_columns": null,
                        "start_time": "",
                        "end_time": "",
                        "order_by": null,
                        "AlignInfluxdbResult": false
                    }
                ],
                "metric_merge": "a + b",
                "join_list": null,
                "order_by": null,
                "result_columns": null,
                "join_with_time": false,
                "keep_columns": null,
                "start_time": "",
                "end_time": "",
                "step": "",
                "type": ""
            }""",
            "raise_exception": False,
        },
        {
            "promql": 'avg by (bk_target_ip, bk_target_cloud_id) '
            '(rate(bkmonitor:system:disk:in_use{bk_target_ip="12.0.0.1"}[5m]))',
            "query_config": {
                "expression": "a",
                "query_configs": [
                    {
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "alias": "a",
                        "metric_id": "bk_monitor.system.disk.in_use",
                        "functions": [{"id": "rate", "params": [{"id": "window", "value": "5m"}]}],
                        "result_table_id": "system.disk",
                        "agg_method": "AVG",
                        "agg_interval": 300,
                        "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
                        "agg_condition": [{"key": "bk_target_ip", "method": "eq", "value": ["12.0.0.1"]}],
                        "metric_field": "in_use",
                    }
                ],
            },
            "origin_config": """{
                "query_list": [
                    {
                        "data_source": "bkmonitor",
                        "db": "system",
                        "table_id": "system.disk",
                        "is_free_schema": false,
                        "field_name": "in_use",
                        "function": [
                            {
                                "method": "mean",
                                "dimensions": [
                                    "bk_target_ip",
                                    "bk_target_cloud_id"
                                ],
                                "position": 0,
                                "args_list": null,
                                "vargs_list": null
                            }
                        ],
                        "time_aggregation": {
                            "function": "rate",
                            "window": "5m",
                            "position": 0,
                            "vargs_list": null
                        },
                        "reference_name": "a",
                        "dimensions": null,
                        "driver": "",
                        "time_field": "",
                        "window": "",
                        "limit": 0,
                        "offset": "",
                        "offset_forward": false,
                        "slimit": 0,
                        "soffset": 0,
                        "conditions": {
                            "field_list": [
                                {
                                    "field_name": "bk_target_ip",
                                    "value": [
                                        "12.0.0.1"
                                    ],
                                    "op": "eq"
                                }
                            ],
                            "condition_list": [
                                "and"
                            ]
                        },
                        "not_combine_window": false,
                        "keep_columns": null,
                        "start_time": "",
                        "end_time": "",
                        "order_by": null,
                        "AlignInfluxdbResult": false
                    }
                ],
                "metric_merge": "a",
                "join_list": null,
                "order_by": null,
                "result_columns": null,
                "join_with_time": false,
                "keep_columns": null,
                "start_time": "",
                "end_time": "",
                "step": "",
                "type": ""
            }""",
            "raise_exception": False,
        },
        {
            "promql": 'avg by (bk_target_ip, bk_target_cloud_id) '
            '(sum_over_time(system:disk:in_use{bk_target_ip="12.0.0.1"}[5m]))',
            "query_config": {},
            "origin_config": """{
                "query_list":[
                    {
                        "data_source":"bkmonitor",
                        "db":"system",
                        "table_id":"system.disk",
                        "is_free_schema":false,
                        "field_name":"in_use",
                        "function":[
                            {
                                "method":"mean",
                                "dimensions":[
                                    "bk_target_ip",
                                    "bk_target_cloud_id"
                                ],
                                "position":0,
                                "args_list":null,
                                "vargs_list":null
                            }
                        ],
                        "time_aggregation":{
                            "function":"sum_over_time",
                            "window":"5m",
                            "position":0,
                            "vargs_list":null
                        },
                        "reference_name":"a",
                        "dimensions":null,
                        "driver":"",
                        "time_field":"",
                        "window":"",
                        "limit":0,
                        "offset":"",
                        "offset_forward":false,
                        "slimit":0,
                        "soffset":0,
                        "conditions":{
                            "field_list":[
                                {
                                    "field_name":"bk_target_ip",
                                    "value":[
                                        "12.0.0.1"
                                    ],
                                    "op":"eq"
                                }
                            ],
                            "condition_list":[
                                "and"
                            ]
                        },
                        "not_combine_window":false,
                        "keep_columns":null,
                        "start_time":"",
                        "end_time":"",
                        "order_by":null,
                        "AlignInfluxdbResult":false
                    }
                ],
                "metric_merge":"a",
                "join_list":null,
                "order_by":null,
                "result_columns":null,
                "join_with_time":false,
                "keep_columns":null,
                "start_time":"",
                "end_time":"",
                "step":"",
                "type":""
            }""",
            "raise_exception": True,
        },
        {
            "promql": 'stddev by (bk_target_ip, bk_target_cloud_id) '
            '(stddev_over_time(system:disk:in_use{bk_target_ip="12.0.0.1"}[5m]))',
            "query_config": {},
            "origin_config": """{
                "query_list":[
                    {
                        "data_source":"bkmonitor",
                        "db":"system",
                        "table_id":"system.disk",
                        "is_free_schema":false,
                        "field_name":"in_use",
                        "function":[
                            {
                                "method":"",
                                "dimensions":[
                                    "bk_target_ip",
                                    "bk_target_cloud_id"
                                ],
                                "position":0,
                                "args_list":null,
                                "vargs_list":null
                            }
                        ],
                        "time_aggregation":{
                            "function":"stddev_over_time",
                            "window":"5m",
                            "position":0,
                            "vargs_list":null
                        },
                        "reference_name":"a",
                        "dimensions":null,
                        "driver":"",
                        "time_field":"",
                        "window":"",
                        "limit":0,
                        "offset":"",
                        "offset_forward":false,
                        "slimit":0,
                        "soffset":0,
                        "conditions":{
                            "field_list":[
                                {
                                    "field_name":"bk_target_ip",
                                    "value":[
                                        "12.0.0.1"
                                    ],
                                    "op":"eq"
                                }
                            ],
                            "condition_list":[
                                "and"
                            ]
                        },
                        "not_combine_window":false,
                        "keep_columns":null,
                        "start_time":"",
                        "end_time":"",
                        "order_by":null,
                        "AlignInfluxdbResult":false
                    }
                ],
                "metric_merge":"a",
                "join_list":null,
                "order_by":null,
                "result_columns":null,
                "join_with_time":false,
                "keep_columns":null,
                "start_time":"",
                "end_time":"",
                "step":"",
                "type":""
            }
            """,
            "raise_exception": True,
        },
        {
            "promql": 'avg_over_time(system:disk:in_use{bk_target_ip="12.0.0.1"}[5m])',
            "query_config": {},
            "origin_config": """{
                "query_list":[
                    {
                        "data_source":"bkmonitor",
                        "db":"system",
                        "table_id":"system.disk",
                        "is_free_schema":false,
                        "field_name":"in_use",
                        "function":null,
                        "time_aggregation":{
                            "function":"avg_over_time",
                            "window":"5m",
                            "position":0,
                            "vargs_list":null
                        },
                        "reference_name":"a",
                        "dimensions":null,
                        "driver":"",
                        "time_field":"",
                        "window":"",
                        "limit":0,
                        "offset":"",
                        "offset_forward":false,
                        "slimit":0,
                        "soffset":0,
                        "conditions":{
                            "field_list":[
                                {
                                    "field_name":"bk_target_ip",
                                    "value":[
                                        "12.0.0.1"
                                    ],
                                    "op":"eq"
                                }
                            ],
                            "condition_list":[
                                "and"
                            ]
                        },
                        "not_combine_window":false,
                        "keep_columns":null,
                        "start_time":"",
                        "end_time":"",
                        "order_by":null,
                        "AlignInfluxdbResult":false
                    }
                ],
                "metric_merge":"a",
                "join_list":null,
                "order_by":null,
                "result_columns":null,
                "join_with_time":false,
                "keep_columns":null,
                "start_time":"",
                "end_time":"",
                "step":"",
                "type":""
            }""",
            "raise_exception": True,
        },
        {
            "promql": 'sum by () (system:disk:in_use{bk_target_ip="12.0.0.1"})',
            "query_config": {},
            "origin_config": """{
                "query_list":[
                    {
                        "data_source":"bkmonitor",
                        "db":"system",
                        "table_id":"system.disk",
                        "is_free_schema":false,
                        "field_name":"in_use",
                        "function":[
                            {
                                "method":"sum",
                                "dimensions":[
                                ],
                                "position":0,
                                "args_list":null,
                                "vargs_list":null
                            }
                        ],
                        "time_aggregation":{
                            "function":"",
                            "window":"",
                            "position":0,
                            "vargs_list":null
                        },
                        "reference_name":"a",
                        "dimensions":null,
                        "driver":"",
                        "time_field":"",
                        "window":"",
                        "limit":0,
                        "offset":"",
                        "offset_forward":false,
                        "slimit":0,
                        "soffset":0,
                        "conditions":{
                            "field_list":[
                                {
                                    "field_name":"bk_target_ip",
                                    "value":[
                                        "12.0.0.1"
                                    ],
                                    "op":"eq"
                                }
                            ],
                            "condition_list":[
                                "and"
                            ]
                        },
                        "not_combine_window":false,
                        "keep_columns":null,
                        "start_time":"",
                        "end_time":"",
                        "order_by":null,
                        "AlignInfluxdbResult":false
                    }
                ],
                "metric_merge":"a",
                "join_list":null,
                "order_by":null,
                "result_columns":null,
                "join_with_time":false,
                "keep_columns":null,
                "start_time":"",
                "end_time":"",
                "step":"",
                "type":""
            }
            """,
            "raise_exception": True,
        },
    ]

    for test_case in test_cases:
        mocker.patch(
            "monitor_web.custom_report.resources.api.unify_query.promql_to_struct",
            side_effect=lambda *args, **kwargs: {"data": json.loads(test_case["origin_config"])},
        )

        try:
            result = resource.strategies.promql_to_query_config(bk_biz_id=2, promql=test_case["promql"])
        except (ValidationError, Exception):
            if not test_case.get("raise_exception"):
                traceback.print_exc()

            assert test_case["raise_exception"]
            continue

        assert not test_case.get("raise_exception")
        assert result == test_case["query_config"]
