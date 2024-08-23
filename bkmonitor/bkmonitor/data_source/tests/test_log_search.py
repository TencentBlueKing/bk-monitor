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


import sys

from bkmonitor.data_source.handler import DataQueryHandler


class TestLogSearch(object):
    def setup_method(self, method):
        self.q_obj = DataQueryHandler("bk_log_search", "time_series")
        print("before {}: {}".format(method, self.q_obj), file=sys.stderr)  # noqa

    def teardown_method(self, method):
        self.q_obj = None
        print("after {}: {}".format(method, self.q_obj), file=sys.stderr)  # noqa

    def test_table_name(self):
        qs = self.q_obj.table("2_bklog_test")
        sql, params = qs.query.sql_with_params()
        assert params == {
            "indices": "2_bklog_test",
            "time_field": "dtEventTimeStamp",
            "aggs": {
                "dtEventTimeStamp": {
                    "date_histogram": {"field": "dtEventTimeStamp", "interval": "60s", "time_zone": "UTC"},
                    "aggregations": {"count": {"value_count": {"field": "_index"}}},
                }
            },
            "size": 1,
        }

    def test_index_set_id(self):
        q_obj = self.q_obj.table("2_bklog_test")

        index_set_id = 1
        qs = q_obj.dsl_index_set_id(index_set_id)
        _, params = qs.query.sql_with_params()
        assert params["index_set_id"] == index_set_id
        assert params.get("indices") is None
        assert params.get("time_field") is None

    def test_select(self):
        q_obj = self.q_obj.table("2_bklog_test")

        qs = q_obj.select()
        _, params = qs.query.sql_with_params()
        assert params["aggs"]["dtEventTimeStamp"]["aggregations"] == {"count": {"value_count": {"field": "_index"}}}

        qs = q_obj.select("age")
        _, params = qs.query.sql_with_params()
        assert params["aggs"]["dtEventTimeStamp"]["aggregations"] == {"age": {"value_count": {"field": "age"}}}

        qs = q_obj.select("avg(age)")
        _, params = qs.query.sql_with_params()
        assert params["aggs"]["dtEventTimeStamp"]["aggregations"] == {"age": {"avg": {"field": "age"}}}

        qs = q_obj.select("avg(age) as _age")
        _, params = qs.query.sql_with_params()
        assert params["aggs"]["dtEventTimeStamp"]["aggregations"] == {"_age": {"avg": {"field": "age"}}}

        qs = q_obj.select("avg(age) as _age").select("count(age) as _age")
        _, params = qs.query.sql_with_params()
        assert params["aggs"]["dtEventTimeStamp"]["aggregations"] == {"_age": {"avg": {"field": "age"}}}

    def test_group_by(self):
        q_obj = self.q_obj.table("2_bklog_test")

        qs = q_obj.group_by("username")
        _, params = qs.query.sql_with_params()
        assert params["aggs"]["username"]["terms"]["field"] == "username"

        qs = q_obj.group_by("username", "age")
        _, params = qs.query.sql_with_params()
        assert params["aggs"]["age"]["terms"]["field"] == "age"
        assert params["aggs"]["age"]["aggregations"]["username"]["terms"]["field"] == "username"

        qs = q_obj.group_by("username", "time(300s)")
        _, params = qs.query.sql_with_params()
        assert params["aggs"]["username"]["aggregations"]["dtEventTimeStamp"]["date_histogram"]["interval"] == "300s"

    def test_time_field(self):
        q_obj = self.q_obj.table("2_bklog_test")

        default_time_field = "dtEventTimeStamp"
        _, params = q_obj.query.sql_with_params()
        assert params["time_field"] == default_time_field

        other_time_field = "time"
        qs = q_obj.time_field(other_time_field)
        _, params = qs.query.sql_with_params()
        assert params["time_field"] == other_time_field

    def test_agg_condition(self):
        q_obj = self.q_obj.table("2_bklog_test")

        # test 1: convert field(compatible)
        agg_condition = [
            {"key": "serverIp", "method": "is", "value": "127.0.0.1"},
            {"condition": "and", "key": "time", "method": "gt", "value": "123"},
        ]
        query_filter = [
            {"field": "serverIp", "operator": "is", "value": "127.0.0.1"},
            {"condition": "and", "field": "time", "operator": "gt", "value": "123"},
        ]
        qs = q_obj.agg_condition(agg_condition)
        _, params = qs.query.sql_with_params()
        assert params["filter"] == query_filter

        # test 2
        agg_condition = [
            {"field": "serverIp", "operator": "is", "value": "127.0.0.1"},
            {"condition": "and", "field": "time", "operator": "gt", "value": "123"},
        ]
        qs = q_obj.agg_condition(agg_condition)
        _, params = qs.query.sql_with_params()
        assert params["filter"] == agg_condition

    def test_query_string(self):
        q_obj = self.q_obj.table("2_bklog_test")

        query_string = "log:system"
        qs = q_obj.dsl_raw_query_string(query_string)
        _, params = qs.query.sql_with_params()
        assert params["query_string"] == query_string
