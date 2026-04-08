"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.data_source.backends.time_series.compiler import SQLCompiler
from bkmonitor.data_source.models.sql.query import Query as OldQuery
from bkmonitor.data_source.data_source import _filter_dict_to_conditions


def test_agg_condition_compile():
    class Query(OldQuery):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

    c = SQLCompiler(Query(using="default"), 2, 3)
    c.query.agg_condition = [
        {"key": "a", "method": "eq", "value": [1]},
        {"condition": "and", "key": "a", "method": "eq", "value": [1, 2]},
    ]
    q = c._parse_agg_condition()
    assert q is not None

    assert q.connector == "AND"
    assert q.children[0].children[0][0] == "a__eq"
    assert q.children[0].children[0][1] == [1]
    assert q.children[0].children[1][0] == "a__eq"
    assert q.children[0].children[1][1] == [1, 2]

    c.query.agg_condition = [
        {"key": "a", "method": "eq", "value": [1]},
        {"condition": "or", "key": "a", "method": "eq", "value": [1, 2]},
    ]
    q = c._parse_agg_condition()
    assert q is not None

    assert q.connector == "OR"
    assert q.children[0].children[0][0] == "a__eq"
    assert q.children[0].children[0][1] == [1]
    assert q.children[1].children[0][0] == "a__eq"
    assert q.children[1].children[0][1] == [1, 2]


def test_unify_query_condition_parse():
    filter_dict = {"a": 1, "b": 2, "c": [3, 4], "d": {"e": 5, "f": 6}, "g": [{"a": 2, "b": 1}, {"c": 3, "d": 4}]}
    conditions = [
        {"key": "a", "method": "eq", "value": ["a"]},
        {"condition": "and", "key": "b", "method": "eq", "value": ["b"]},
        {"condition": "or", "key": "x", "method": "eq", "value": ["x"]},
        {"condition": "and", "key": "y", "method": "eq", "value": ["y"]},
    ]

    assert _filter_dict_to_conditions(filter_dict, []) == [
        {"key": "a", "method": "eq", "value": ["1"]},
        {"condition": "and", "key": "b", "method": "eq", "value": ["2"]},
        {"condition": "and", "key": "c", "method": "eq", "value": ["3", "4"]},
        {"condition": "and", "key": "e", "method": "eq", "value": ["5"]},
        {"condition": "and", "key": "f", "method": "eq", "value": ["6"]},
        {"condition": "and", "key": "a", "method": "eq", "value": ["2"]},
        {"condition": "and", "key": "b", "method": "eq", "value": ["1"]},
        {"condition": "or", "key": "a", "method": "eq", "value": ["1"]},
        {"condition": "and", "key": "b", "method": "eq", "value": ["2"]},
        {"condition": "and", "key": "c", "method": "eq", "value": ["3", "4"]},
        {"condition": "and", "key": "e", "method": "eq", "value": ["5"]},
        {"condition": "and", "key": "f", "method": "eq", "value": ["6"]},
        {"condition": "and", "key": "c", "method": "eq", "value": ["3"]},
        {"condition": "and", "key": "d", "method": "eq", "value": ["4"]},
    ]
    assert _filter_dict_to_conditions({}, conditions) == conditions
    assert _filter_dict_to_conditions(filter_dict, conditions) == [
        {"key": "a", "method": "eq", "value": ["1"]},
        {"condition": "and", "key": "b", "method": "eq", "value": ["2"]},
        {"condition": "and", "key": "c", "method": "eq", "value": ["3", "4"]},
        {"condition": "and", "key": "e", "method": "eq", "value": ["5"]},
        {"condition": "and", "key": "f", "method": "eq", "value": ["6"]},
        {"condition": "and", "key": "a", "method": "eq", "value": ["a"]},
        {"condition": "and", "key": "b", "method": "eq", "value": ["b"]},
        {"condition": "and", "key": "a", "method": "eq", "value": ["2"]},
        {"condition": "and", "key": "b", "method": "eq", "value": ["1"]},
        {"condition": "or", "key": "a", "method": "eq", "value": ["1"]},
        {"condition": "and", "key": "b", "method": "eq", "value": ["2"]},
        {"condition": "and", "key": "c", "method": "eq", "value": ["3", "4"]},
        {"condition": "and", "key": "e", "method": "eq", "value": ["5"]},
        {"condition": "and", "key": "f", "method": "eq", "value": ["6"]},
        {"condition": "and", "key": "a", "method": "eq", "value": ["a"]},
        {"condition": "and", "key": "b", "method": "eq", "value": ["b"]},
        {"condition": "and", "key": "c", "method": "eq", "value": ["3"]},
        {"condition": "and", "key": "d", "method": "eq", "value": ["4"]},
        {"condition": "or", "key": "a", "method": "eq", "value": ["1"]},
        {"condition": "and", "key": "b", "method": "eq", "value": ["2"]},
        {"condition": "and", "key": "c", "method": "eq", "value": ["3", "4"]},
        {"condition": "and", "key": "e", "method": "eq", "value": ["5"]},
        {"condition": "and", "key": "f", "method": "eq", "value": ["6"]},
        {"condition": "and", "key": "x", "method": "eq", "value": ["x"]},
        {"condition": "and", "key": "y", "method": "eq", "value": ["y"]},
        {"condition": "and", "key": "a", "method": "eq", "value": ["2"]},
        {"condition": "and", "key": "b", "method": "eq", "value": ["1"]},
        {"condition": "or", "key": "a", "method": "eq", "value": ["1"]},
        {"condition": "and", "key": "b", "method": "eq", "value": ["2"]},
        {"condition": "and", "key": "c", "method": "eq", "value": ["3", "4"]},
        {"condition": "and", "key": "e", "method": "eq", "value": ["5"]},
        {"condition": "and", "key": "f", "method": "eq", "value": ["6"]},
        {"condition": "and", "key": "x", "method": "eq", "value": ["x"]},
        {"condition": "and", "key": "y", "method": "eq", "value": ["y"]},
        {"condition": "and", "key": "c", "method": "eq", "value": ["3"]},
        {"condition": "and", "key": "d", "method": "eq", "value": ["4"]},
    ]
