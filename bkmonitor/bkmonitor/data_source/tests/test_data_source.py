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
from django.conf import settings
from mock import MagicMock

from bkmonitor.data_source import (
    BkApmTraceDataSource,
    BkdataTimeSeriesDataSource,
    BkMonitorLogDataSource,
    BkMonitorTimeSeriesDataSource,
    CustomEventDataSource,
    CustomTimeSeriesDataSource,
    DataSource,
    LogSearchLogDataSource,
    LogSearchTimeSeriesDataSource,
)
from constants.data_source import DataSourceLabel, DataTypeLabel


@pytest.fixture()
def mock_get_ts_data():
    from bkmonitor.data_source.models.sql import query

    get_ts_data = MagicMock()
    get_ts_data.return_value = {"list": []}

    query.DATA_SOURCE[DataSourceLabel.BK_MONITOR_COLLECTOR][DataTypeLabel.TIME_SERIES]["query"] = get_ts_data
    query.DATA_SOURCE[DataSourceLabel.CUSTOM][DataTypeLabel.TIME_SERIES]["query"] = get_ts_data
    return get_ts_data


@pytest.fixture()
def mock_get_es_data():
    from bkmonitor.data_source.models.sql import query

    get_es_data = MagicMock()
    get_es_data.return_value = {"list": []}

    query.DATA_SOURCE[DataSourceLabel.BK_MONITOR_COLLECTOR][DataTypeLabel.LOG]["query"] = get_es_data
    query.DATA_SOURCE[DataSourceLabel.CUSTOM][DataTypeLabel.EVENT]["query"] = get_es_data
    query.DATA_SOURCE[DataSourceLabel.BK_APM][DataTypeLabel.LOG]["query"] = get_es_data
    query.DATA_SOURCE[DataSourceLabel.BK_APM][DataTypeLabel.TIME_SERIES]["query"] = get_es_data
    return get_es_data


@pytest.fixture()
def mock_bk_data_query_data():
    from bkmonitor.data_source.models.sql import query

    query_data = MagicMock()
    query_data.return_value = {"list": []}

    query.DATA_SOURCE[DataSourceLabel.BK_DATA][DataTypeLabel.TIME_SERIES]["query"] = query_data
    query.DATA_SOURCE[DataSourceLabel.BK_DATA][DataTypeLabel.LOG]["query"] = query_data
    return query_data


@pytest.fixture()
def mock_es_query_search():
    from bkmonitor.data_source.models.sql import query

    es_query_search = MagicMock()
    es_query_search.return_value = {"list": []}

    query.DATA_SOURCE[DataSourceLabel.BK_LOG_SEARCH][DataTypeLabel.TIME_SERIES]["query"] = es_query_search
    query.DATA_SOURCE[DataSourceLabel.BK_LOG_SEARCH][DataTypeLabel.LOG]["query"] = es_query_search
    return es_query_search


class TestDataSource:
    def test_queryset(self):
        q = DataSource._get_queryset(
            select=["a", "b"],
            table="table1",
            agg_condition=[{"key": "key1", "method": "eq", "value": ["value1"]}],
            where={"key": "value"},
            group_by=["dimension1", "dimension2"],
            index_set_id=1,
            query_string="*",
            limit=1,
            order_by=["time_field1 desc"],
            time_field="time_field1",
            start_time=123456,
            end_time=654321,
        )

        assert q.query.select == ["a", "b"]
        assert q.query.table_name == "table1"
        assert q.query.agg_condition == [{"key": "key1", "method": "eq", "value": ["value1"]}]
        assert q.query.group_by == ["dimension1", "dimension2"]
        assert q.query.index_set_id == 1
        assert q.query.raw_query_string == "*"
        assert q.query.high_mark == 1 and q.query.low_mark == 0
        assert q.query.order_by == ["time_field1 desc"]
        assert q.query.time_field == "time_field1"

        assert q.query.where.connector == "AND"
        assert q.query.where.children[1:] == [("time_field1__gte", 123456), ("time_field1__lt", 654321)]

    def test_bk_monitor_time_series_query_data(self, mock_get_ts_data):
        query_config = {
            "metric_field": "pct_used",
            "extend_fields": {},
            "agg_dimension": ["bk_target_ip", "bk_target_cloud_id", "hostname"],
            "unit_conversion": 1.0,
            "result_table_id": "system.mem",
            "agg_interval": 15,
            "agg_method": "AVG",
            "agg_condition": [{"key": "hostname", "method": "eq", "value": ["host1", "host2"]}],
            "id": 1,
            "unit": "percent",
            "create_time": 1579609068,
            "update_time": 1611074908,
            "create_user": "admin",
            "update_user": "admin",
            "rt_query_config_id": 1,
        }

        mock_get_ts_data.return_value = {
            "list": [
                {
                    "time": 123456,
                    "pct_used": 123,
                    "bk_target_ip": "127.0.0.1",
                    "bk_target_cloud_id": "0",
                    "hostname": "host1_x",
                },
                {
                    "time": 123456,
                    "pct_used": 123,
                    "bk_target_ip": "127.0.0.1",
                    "bk_target_cloud_id": "0",
                    "hostname": "host2_x",
                },
            ]
        }

        data_source = BkMonitorTimeSeriesDataSource.init_by_query_config(query_config)
        data = data_source.query_data(start_time=12345, end_time=54321, limit=100)

        assert len(data) == 2
        assert (
            mock_get_ts_data.call_args[1]["sql"] == "SELECT AVG(pct_used) as pct_used FROM system.mem "
            "WHERE `time` >= 0 AND `time` < 45000 AND (`hostname` = 'host1' OR `hostname` = 'host2') "
            "GROUP BY `bk_target_ip`, `bk_target_cloud_id`, `hostname`, time(15s) "
            "ORDER BY time desc LIMIT 100"
        )

        for record in mock_get_ts_data.return_value["list"]:
            record["time"] = record["_time_"]
            record.pop("_time_")
        data = data_source.query_data()
        assert len(data) == 2
        assert (
            mock_get_ts_data.call_args[1]["sql"] == "SELECT AVG(pct_used) as pct_used FROM system.mem "
            "WHERE (`hostname` = 'host1' OR `hostname` = 'host2') "
            "GROUP BY `bk_target_ip`, `bk_target_cloud_id`, `hostname`, time(15s) "
            "ORDER BY time desc LIMIT " + str(settings.SQL_MAX_LIMIT)
        )

        query_config = {
            "metric_field": "pct_used",
            "extend_fields": {},
            "agg_dimension": ["bk_target_ip", "bk_target_cloud_id", "hostname"],
            "unit_conversion": 1.0,
            "result_table_id": "system.mem",
            "agg_interval": 120,
            "agg_method": "AVG",
            "agg_condition": [{"key": "hostname", "method": "include", "value": ["host1", "host2"]}],
            "id": 1,
            "unit": "percent",
            "create_time": 1579609068,
            "update_time": 1611074908,
            "create_user": "admin",
            "update_user": "admin",
            "rt_query_config_id": 1,
        }

        for record in mock_get_ts_data.return_value["list"]:
            record["time"] = record["_time_"]
            record.pop("_time_")
        mock_get_ts_data.return_value["list"].append(
            {
                "time": 123456,
                "pct_used": 123,
                "bk_target_ip": "127.0.0.1",
                "bk_target_cloud_id": "0",
                "hostname": "host3_x",
            }
        )

        data_source = BkMonitorTimeSeriesDataSource.init_by_query_config(query_config)
        data = data_source.query_data()
        assert len(data) == 3
        assert (
            mock_get_ts_data.call_args[1]["sql"] == "SELECT AVG(pct_used) as pct_used FROM system.mem "
            "WHERE (`hostname` =~ /host1/ OR `hostname` =~ /host2/) "
            "GROUP BY `bk_target_ip`, `bk_target_cloud_id`, `hostname`, time(120s) "
            "ORDER BY time desc LIMIT " + str(settings.SQL_MAX_LIMIT)
        )

    def test_bk_data_time_series_query_data(self, mock_bk_data_query_data):
        query_config = {
            "metric_field": "iUserNum",
            "extend_fields": {
                "result_table_name": "monitor_oss_online_1491",
                "data_source_label": "bk_data",
                "related_id": "",
            },
            "agg_dimension": ["iWorldId"],
            "unit_conversion": 1.0,
            "result_table_id": "123_monitor_oss_online_1491",
            "agg_interval": 60,
            "agg_method": "AVG",
            "agg_condition": [{"method": "neq", "value": ["61", "63"], "key": "iWorldId"}],
            "id": 1,
            "unit": "",
            "create_time": 1606118486,
            "update_time": 1606118486,
            "create_user": "admin",
            "update_user": "admin",
            "rt_query_config_id": 1,
        }

        mock_bk_data_query_data.return_value = {
            "list": [{"dtEventTimeStamp": 1232456, "iWorldId": "123", "iUserNum": "321"}]
        }

        data_source = BkdataTimeSeriesDataSource.init_by_query_config(query_config)
        data = data_source.query_data()

        assert len(data) == 1
        assert (
            mock_bk_data_query_data.call_args[1]["sql"]
            == "SELECT AVG(`iUserNum`) as `iUserNum`, `iWorldId`, `minute1`, MAX(dtEventTimeStamp) as dtEventTimeStamp "
            "FROM 123_monitor_oss_online_1491 WHERE (`iWorldId` != '61' AND `iWorldId` != '63') "
            "GROUP BY `iWorldId`, `minute1` ORDER BY dtEventTimeStamp desc LIMIT " + str(settings.SQL_MAX_LIMIT)
        )

        query_config = {
            "metric_field": "iUserNum",
            "extend_fields": {
                "result_table_name": "monitor_oss_online_1491",
                "data_source_label": "bk_data",
                "related_id": "",
            },
            "agg_dimension": ["iWorldId"],
            "unit_conversion": 1.0,
            "result_table_id": "123_monitor_oss_online_1491",
            "agg_interval": 120,
            "agg_method": "AVG",
            "agg_condition": [{"method": "exclude", "value": ["61", "63"], "key": "iWorldId"}],
            "id": 1,
            "unit": "",
            "create_time": 1606118486,
            "update_time": 1606118486,
            "create_user": "admin",
            "update_user": "admin",
            "rt_query_config_id": 1,
        }

        mock_bk_data_query_data.return_value = {
            "list": [
                {"dtEventTimeStamp": 1232456, "iWorldId": "123", "iUserNum": "321"},
                {"dtEventTimeStamp": 1232456, "iWorldId": "124", "iUserNum": "321"},
                {"dtEventTimeStamp": 1232456, "iWorldId": "61", "iUserNum": "321"},
                {"dtEventTimeStamp": 1232456, "iWorldId": "63", "iUserNum": "321"},
                {"dtEventTimeStamp": 1232456, "iWorldId": "64", "iUserNum": "321"},
            ]
        }

        data_source = BkdataTimeSeriesDataSource.init_by_query_config(query_config)
        data = data_source.query_data(start_time=123450, end_time=543210, limit=100)

        assert len(data) == 3
        assert (
            mock_bk_data_query_data.call_args[1]["sql"]
            == "SELECT AVG(`iUserNum`) as `iUserNum`, `iWorldId`, `minute2`, MAX(dtEventTimeStamp) as dtEventTimeStamp "
            "FROM 123_monitor_oss_online_1491 WHERE `dtEventTimeStamp` >= 120000 AND `dtEventTimeStamp` < 480000 "
            "GROUP BY `iWorldId`, `minute2` ORDER BY dtEventTimeStamp desc LIMIT 100"
        )

    def test_custom_time_series_query_data(self, mock_get_ts_data):
        query_config = {
            "metric_field": "test1",
            "extend_fields": {"bk_data_id": 1500001},
            "agg_dimension": [],
            "unit_conversion": 1.0,
            "result_table_id": "2_bkmonitor_time_series_1500001.base",
            "agg_interval": 15,
            "agg_method": "AVG",
            "agg_condition": [{"key": "name", "method": "eq", "value": ["name1"]}],
            "id": 1,
            "unit": "",
            "create_time": 1614592615,
            "update_time": 1614592615,
            "create_user": "admin",
            "update_user": "admin",
            "rt_query_config_id": 1,
        }

        mock_get_ts_data.return_value = {"list": [{"time": 123456, "test": 123}, {"time": 123456, "test": 123}]}

        data_source = CustomTimeSeriesDataSource.init_by_query_config(query_config)
        data = data_source.query_data(start_time=12345, end_time=54321, limit=100)

        assert len(data) == 2
        assert (
            mock_get_ts_data.call_args[1]["sql"]
            == "SELECT AVG(test1) as test1 FROM 2_bkmonitor_time_series_1500001.base "
            "WHERE `time` >= 0 AND `time` < 45000 AND `name` = 'name1' "
            "GROUP BY time(15s) ORDER BY time desc LIMIT 100"
        )

        query_config = {
            "metric_field": "test1",
            "extend_fields": {"bk_data_id": 1500001},
            "agg_dimension": ["name"],
            "unit_conversion": 1.0,
            "result_table_id": "2_bkmonitor_time_series_1500001.base",
            "agg_interval": 180,
            "agg_method": "AVG",
            "agg_condition": [{"key": "name", "method": "reg", "value": [r"^name\d+$"]}],
            "id": 1,
            "unit": "",
            "create_time": 1614592615,
            "update_time": 1614592615,
            "create_user": "admin",
            "update_user": "admin",
            "rt_query_config_id": 1,
        }

        mock_get_ts_data.return_value = {
            "list": [
                {"time": 123456, "test": 123, "name": "name1234"},
                {"time": 123456, "test": 123, "name": "name2"},
                {"time": 123456, "test": 123, "name": "name_123"},
            ]
        }

        data_source = CustomTimeSeriesDataSource.init_by_query_config(query_config)
        data = data_source.query_data(start_time=123400, end_time=543200)

        assert len(data) == 3
        assert mock_get_ts_data.call_args[1]["sql"] == (
            "SELECT AVG(test1) as test1 FROM 2_bkmonitor_time_series_1500001.base "
            "WHERE `time` >= 0 AND `time` < 540000 AND `name` =~ /^name\\d+$/ "
            f"GROUP BY `name`, time(180s) ORDER BY time desc LIMIT {settings.SQL_MAX_LIMIT}"
        )

    def test_log_search_time_series_query_data(self, mock_es_query_search):
        query_config = {
            "metric_field": "status",
            "extend_fields": {
                "time_field": "dtEventTimeStamp",
                "scenario_name": "采集接入",
                "index_set_id": 1,
                "scenario_id": "log",
                "storage_cluster_id": 1,
                "storage_cluster_name": "",
            },
            "agg_dimension": ["remote_user"],
            "unit_conversion": 1.0,
            "result_table_id": "2_bklog.nginx_access_error_1",
            "index_set_id": 1,
            "agg_interval": 60,
            "agg_method": "AVG",
            "agg_condition": [{"key": "status", "method": "is", "value": ["200"]}],
            "id": 1,
            "unit": "",
            "create_time": 1614599379,
            "update_time": 1614599379,
            "create_user": "admin",
            "update_user": "admin",
            "rt_query_config_id": 1,
        }

        mock_es_query_search.return_value = {
            "took": 3,
            "timed_out": False,
            "_shards": {"total": 5, "successful": 5, "skipped": 0, "failed": 0},
            "hits": {
                "total": 3042,
                "max_score": 0.0,
                "hits": [
                    {
                        "_score": 0.0,
                        "_type": "_doc",
                        "_id": "ajsdkfjasdfj;askldjfkl;adsjfkl;ads",
                        "_source": {
                            "dtEventTimeStamp": "1614596362000",
                            "status": 200,
                            "body_bytes_sent": "1",
                            "http_user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5)",
                            "log": '127.0.0.1 - - [01/Mar/2021:18:59:19 +0800] "GET /static/js/index.js HTTP/1.1" '
                            '200 41001 "http://example.com/"',
                            "http_referer": "http://example.com/",
                            "remote_addr": "127.0.0.1",
                            "http_x_forwarded_for": "127.0.0.1",
                            "iterationIndex": 1,
                            "cloudId": 0,
                            "request": "GET /static/js/index.js HTTP/1.1",
                            "serverIp": "127.0.0.1",
                            "time_local": "01/Mar/2021:18:59:19 +0800",
                            "gseIndex": 1,
                            "remote_user": "-",
                            "time": "1614596362000",
                            "path": "/var/logs/nginx/access.log",
                        },
                        "_index": "v2_2_bklog_nginx_access_error",
                    }
                ],
            },
            "aggregations": {
                "remote_user": {
                    "buckets": [
                        {
                            "dtEventTimeStamp": {
                                "buckets": [
                                    {
                                        "status": {"value": 1},
                                        "key_as_string": "1614600660000",
                                        "key": 1614600660000,
                                        "doc_count": 1,
                                    },
                                    {
                                        "status": {"value": 11},
                                        "key_as_string": "1614600720000",
                                        "key": 1614600720000,
                                        "doc_count": 11,
                                    },
                                    {
                                        "status": {"value": 2},
                                        "key_as_string": "1614600780000",
                                        "key": 1614600780000,
                                        "doc_count": 2,
                                    },
                                ]
                            },
                            "key": "-",
                            "doc_count": 160,
                        }
                    ],
                    "sum_other_doc_count": 0,
                    "doc_count_error_upper_bound": 0,
                }
            },
        }

        data_source = LogSearchTimeSeriesDataSource.init_by_query_config(query_config)
        data = data_source.query_data(start_time=123456, end_time=654321, limit=1000)

        assert len(data) == 3
        assert mock_es_query_search.call_args[1] == {
            "index_set_id": 1,
            "aggs": {
                "remote_user": {
                    "terms": {"field": "remote_user", "size": 10000},
                    "aggregations": {
                        "dtEventTimeStamp": {
                            "date_histogram": {"field": "dtEventTimeStamp", "interval": "60s", 'time_zone': 'UTC'},
                            "aggregations": {"status": {"avg": {"field": "status"}}},
                        }
                    },
                }
            },
            "filter": [{"field": "status", "operator": "is", "value": ["200"]}],
            "start_time": 120,
            "end_time": 600,
            "size": 1,
        }
        data, _ = data_source.query_log(start_time=123456, end_time=654321, limit=1000)
        assert len(data) == 1
        assert mock_es_query_search.call_args[1] == {
            "index_set_id": 1,
            "aggs": {
                "dtEventTimeStamp": {
                    "date_histogram": {"field": "dtEventTimeStamp", "interval": "60s", 'time_zone': 'UTC'},
                    "aggregations": {"count": {"value_count": {"field": "_index"}}},
                }
            },
            "filter": [{"field": "status", "operator": "is", "value": ["200"]}],
            "size": 1000,
            "start_time": 123,
            "end_time": 654,
        }

    def test_log_search_log_query_data(self, mock_es_query_search):
        query_config = {
            "extend_fields": {
                "index_set_id": 1,
                "scenario_id": "log",
                "scenario_name": "采集接入",
                "storage_cluster_id": 1,
                "time_field": "dtEventTimeStamp",
            },
            "agg_dimension": ["remote_user"],
            "keywords_query_string": "*",
            "id": 1,
            "result_table_id": "2_bklog.nginx_access_error_1",
            "index_set_id": 1,
            "agg_interval": 30,
            "rule": "",
            "agg_method": "COUNT",
            "keywords": "",
            "create_time": 1614603633,
            "update_time": 1614603638,
            "agg_condition": [{"key": "status", "method": "is", "value": ["200"]}],
            "rt_query_config_id": 1,
        }

        mock_es_query_search.return_value = {
            "took": 3,
            "timed_out": False,
            "_shards": {"total": 5, "successful": 5, "skipped": 0, "failed": 0},
            "hits": {
                "total": 3042,
                "max_score": 0.0,
                "hits": [
                    {
                        "_score": 0.0,
                        "_type": "_doc",
                        "_id": "ajsdkfjasdfj;askldjfkl;adsjfkl;ads",
                        "_source": {
                            "dtEventTimeStamp": "1614596362000",
                            "status": 200,
                            "body_bytes_sent": "1",
                            "http_user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5)",
                            "log": '127.0.0.1 - - [01/Mar/2021:18:59:19 +0800] "GET /static/js/index.js HTTP/1.1" '
                            '200 41001 "http://example.com/"',
                            "http_referer": "http://example.com/",
                            "remote_addr": "127.0.0.1",
                            "http_x_forwarded_for": "127.0.0.1",
                            "iterationIndex": 1,
                            "cloudId": 0,
                            "request": "GET /static/js/index.js HTTP/1.1",
                            "serverIp": "127.0.0.1",
                            "time_local": "01/Mar/2021:18:59:19 +0800",
                            "gseIndex": 1,
                            "remote_user": "-",
                            "time": "1614596362000",
                            "path": "/var/logs/nginx/access.log",
                        },
                        "_index": "v2_2_bklog_nginx_access_error",
                    }
                ],
            },
            "aggregations": {
                "remote_user": {
                    "buckets": [
                        {
                            "dtEventTimeStamp": {
                                "buckets": [
                                    {
                                        "_index": {"value": 1},
                                        "key_as_string": "1614600660000",
                                        "key": 1614600660000,
                                        "doc_count": 1,
                                    },
                                    {
                                        "_index": {"value": 2},
                                        "key_as_string": "1614600720000",
                                        "key": 1614600720000,
                                        "doc_count": 11,
                                    },
                                    {
                                        "_index": {"value": 3},
                                        "key_as_string": "1614600780000",
                                        "key": 1614600780000,
                                        "doc_count": 2,
                                    },
                                ]
                            },
                            "key": "-",
                            "doc_count": 160,
                        }
                    ],
                    "sum_other_doc_count": 0,
                    "doc_count_error_upper_bound": 0,
                }
            },
        }

        data_source = LogSearchLogDataSource.init_by_query_config(query_config)
        data = data_source.query_data(start_time=123456, end_time=654321, limit=1000)

        assert len(data) == 3
        assert mock_es_query_search.call_args[1] == {
            "index_set_id": 1,
            "aggs": {
                "remote_user": {
                    "terms": {"field": "remote_user", "size": 10000},
                    "aggregations": {
                        "dtEventTimeStamp": {
                            "date_histogram": {"field": "dtEventTimeStamp", "interval": "30s", 'time_zone': 'UTC'},
                            "aggregations": {"_index": {"value_count": {"field": "_index"}}},
                        }
                    },
                }
            },
            "filter": [{"field": "status", "operator": "is", "value": ["200"]}],
            "start_time": 120,
            "end_time": 630,
            "size": 1,
        }

        data_source.filter_dict = {"bk_biz_id": 2}
        data = data_source.query_data(start_time=123456, end_time=654321, limit=1000)

        assert len(data) == 3
        assert mock_es_query_search.call_args[1] == {
            "index_set_id": 1,
            "aggs": {
                "remote_user": {
                    "terms": {"field": "remote_user", "size": 10000},
                    "aggregations": {
                        "dtEventTimeStamp": {
                            "date_histogram": {"field": "dtEventTimeStamp", "interval": "30s", 'time_zone': 'UTC'},
                            "aggregations": {"_index": {"value_count": {"field": "_index"}}},
                        }
                    },
                }
            },
            "filter": [{"field": "status", "operator": "is", "value": ["200"]}],
            "start_time": 120,
            "end_time": 630,
            "query_string": 'bk_biz_id: "2"',
            "size": 1,
        }


class TestBkMonitorLogDataSource:
    def test_query_data_without_topo(self, mock_get_es_data):
        query_config = {
            "extend_fields": {},
            "agg_dimension": ["bk_target_ip"],
            "keywords_query_string": "",
            "id": 1,
            "result_table_id": "2_bkmonitor_event_1500110",
            "agg_interval": 60,
            "rule": "",
            "agg_method": "AVG",
            "keywords": "",
            "create_time": 1614652579,
            "update_time": 1614652579,
            "agg_condition": [],
            "rt_query_config_id": 1,
            "target": [
                [
                    {
                        "field": "bk_target_ip",
                        "method": "eq",
                        "value": [{"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": "0"}],
                    }
                ]
            ],
        }

        mock_get_es_data.return_value = {
            "hits": {"hits": [], "total": {"relation": "eq", "value": 251}, "max_score": None},
            "_shards": {"successful": 4, "failed": 0, "skipped": 0, "total": 4},
            "took": 8,
            "aggregations": {
                "dimensions.bk_target_cloud_id": {
                    "buckets": [
                        {
                            "dimensions.bk_target_ip": {
                                "buckets": [
                                    {
                                        "time": {
                                            "buckets": [
                                                {
                                                    "distinct": {"value": 2},
                                                    "event.count": {"value": 2},
                                                    "key_as_string": "1614334800000",
                                                    "key": 1614334800000,
                                                    "doc_count": 243,
                                                }
                                            ]
                                        },
                                        "key": "127.0.0.1",
                                        "doc_count": 243,
                                    },
                                    {
                                        "time": {
                                            "buckets": [
                                                {
                                                    "distinct": {"value": 3},
                                                    "event.count": {"value": 9},
                                                    "key_as_string": "1614334800000",
                                                    "key": 1614334800000,
                                                    "doc_count": 8,
                                                }
                                            ]
                                        },
                                        "key": "127.0.0.2",
                                        "doc_count": 8,
                                    },
                                ],
                                "sum_other_doc_count": 0,
                                "doc_count_error_upper_bound": 0,
                            },
                            "key": "0",
                            "doc_count": 251,
                        }
                    ],
                    "sum_other_doc_count": 0,
                    "doc_count_error_upper_bound": 0,
                }
            },
            "timed_out": False,
        }

        data_source = BkMonitorLogDataSource.init_by_query_config(query_config)
        data = data_source.query_data(start_time=1614334800000, end_time=1614334860000)

        assert len(data) == 2
        assert data == [
            {"bk_target_ip": "127.0.0.1", "event.count": 2.0, "_time_": 1614334800000},
            {"bk_target_ip": "127.0.0.2", "event.count": 9.0, "_time_": 1614334800000},
        ]
        assert mock_get_es_data.call_args[1] == {
            "table_id": "2_bkmonitor_event_1500110",
            "use_full_index_names": False,
            "query_body": {
                "aggregations": {
                    "dimensions.bk_target_cloud_id": {
                        "terms": {"field": "dimensions.bk_target_cloud_id", "size": 1440},
                        "aggregations": {
                            "dimensions.bk_target_ip": {
                                "terms": {"field": "dimensions.bk_target_ip", "size": 1440},
                                "aggregations": {
                                    "time": {
                                        "date_histogram": {"field": "time", "interval": "60s", "time_zone": "UTC"},
                                        "aggregations": {
                                            "event.count": {"avg": {"field": "event.count"}},
                                            "distinct": {"cardinality": {"field": "dimensions.bk_module_id"}},
                                        },
                                    }
                                },
                            }
                        },
                    }
                },
                "query": {
                    "bool": {
                        "filter": {
                            "bool": {
                                "must": [
                                    {"range": {"time": {"gte": 1614334800000}}},
                                    {"range": {"time": {"lt": 1614334860000}}},
                                ],
                            }
                        }
                    }
                },
                "size": 1,
                "sort": [{"time": "desc"}],
            },
        }

        # 验证AVG计算
        query_config["agg_dimension"] = []
        query_config["agg_method"] = "AVG"

        data_source = BkMonitorLogDataSource.init_by_query_config(query_config)
        data = data_source.query_data(start_time=1614334800000, end_time=1614334860000)

        assert len(data) == 1
        assert data == [{"event.count": 5.5, "_time_": 1614334800000}]

        # 验证AVG计算
        query_config["agg_dimension"] = ["bk_target_cloud_id"]
        query_config["agg_method"] = "SUM"
        mock_get_es_data.return_value = {
            "hits": {"hits": [], "total": {"relation": "eq", "value": 251}, "max_score": None},
            "_shards": {"successful": 4, "failed": 0, "skipped": 0, "total": 4},
            "took": 8,
            "aggregations": {
                "dimensions.bk_target_ip": {
                    "buckets": [
                        {
                            "dimensions.bk_target_cloud_id": {
                                "buckets": [
                                    {
                                        "time": {
                                            "buckets": [
                                                {
                                                    "distinct": {"value": 2},
                                                    "event.count": {"value": 2},
                                                    "key_as_string": "1614334800000",
                                                    "key": 1614334800000,
                                                    "doc_count": 243,
                                                }
                                            ]
                                        },
                                        "key": "0",
                                        "doc_count": 243,
                                    },
                                ],
                                "sum_other_doc_count": 0,
                                "doc_count_error_upper_bound": 0,
                            },
                            "key": "127.0.0.1",
                            "doc_count": 251,
                        },
                        {
                            "dimensions.bk_target_cloud_id": {
                                "buckets": [
                                    {
                                        "time": {
                                            "buckets": [
                                                {
                                                    "distinct": {"value": 3},
                                                    "event.count": {"value": 9},
                                                    "key_as_string": "1614334800000",
                                                    "key": 1614334800000,
                                                    "doc_count": 243,
                                                }
                                            ]
                                        },
                                        "key": "0",
                                        "doc_count": 243,
                                    },
                                ],
                                "sum_other_doc_count": 0,
                                "doc_count_error_upper_bound": 0,
                            },
                            "key": "127.0.0.2",
                            "doc_count": 251,
                        },
                    ],
                    "sum_other_doc_count": 0,
                    "doc_count_error_upper_bound": 0,
                }
            },
            "timed_out": False,
        }

        data_source = BkMonitorLogDataSource.init_by_query_config(query_config)
        data = data_source.query_data(start_time=1614334800000, end_time=1614334860000)

        assert len(data) == 1
        assert data == [{"event.count": 4, "bk_target_cloud_id": "0", "_time_": 1614334800000}]
        assert mock_get_es_data.call_args[1] == {
            "table_id": "2_bkmonitor_event_1500110",
            "use_full_index_names": False,
            "query_body": {
                "aggregations": {
                    "dimensions.bk_target_ip": {
                        "terms": {"field": "dimensions.bk_target_ip", "size": 1440},
                        "aggregations": {
                            "dimensions.bk_target_cloud_id": {
                                "terms": {"field": "dimensions.bk_target_cloud_id", "size": 1440},
                                "aggregations": {
                                    "time": {
                                        "date_histogram": {"field": "time", "interval": "60s", 'time_zone': 'UTC'},
                                        "aggregations": {
                                            "event.count": {"sum": {"field": "event.count"}},
                                            "distinct": {"cardinality": {"field": "dimensions.bk_module_id"}},
                                        },
                                    }
                                },
                            }
                        },
                    }
                },
                "query": {
                    "bool": {
                        "filter": {
                            "bool": {
                                "must": [
                                    {"range": {"time": {"gte": 1614334800000}}},
                                    {"range": {"time": {"lt": 1614334860000}}},
                                ]
                            },
                        }
                    }
                },
                "size": 1,
                "sort": [{"time": "desc"}],
            },
        }

        # 验证SUM计算
        query_config["agg_dimension"] = []
        query_config["agg_method"] = "SUM"

        mock_get_es_data.return_value = {
            "hits": {"hits": [], "total": {"relation": "eq", "value": 251}, "max_score": None},
            "_shards": {"successful": 4, "failed": 0, "skipped": 0, "total": 4},
            "took": 8,
            "aggregations": {
                "dimensions.bk_target_cloud_id": {
                    "buckets": [
                        {
                            "dimensions.bk_target_ip": {
                                "buckets": [
                                    {
                                        "time": {
                                            "buckets": [
                                                {
                                                    "distinct": {"value": 2},
                                                    "event.count": {"value": 2},
                                                    "key_as_string": "1614334800000",
                                                    "key": 1614334800000,
                                                    "doc_count": 243,
                                                }
                                            ]
                                        },
                                        "key": "127.0.0.1",
                                        "doc_count": 243,
                                    },
                                    {
                                        "time": {
                                            "buckets": [
                                                {
                                                    "distinct": {"value": 3},
                                                    "event.count": {"value": 9},
                                                    "key_as_string": "1614334800000",
                                                    "key": 1614334800000,
                                                    "doc_count": 8,
                                                }
                                            ]
                                        },
                                        "key": "127.0.0.2",
                                        "doc_count": 8,
                                    },
                                ],
                                "sum_other_doc_count": 0,
                                "doc_count_error_upper_bound": 0,
                            },
                            "key": "0",
                            "doc_count": 251,
                        }
                    ],
                    "sum_other_doc_count": 0,
                    "doc_count_error_upper_bound": 0,
                }
            },
            "timed_out": False,
        }

        data_source = BkMonitorLogDataSource.init_by_query_config(query_config)
        data = data_source.query_data(start_time=1614334800000, end_time=1614334860000)

        assert len(data) == 1
        assert data == [{"event.count": 4, "_time_": 1614334800000}]

    def test_query_data_with_topo(self, mock_get_es_data):
        query_config = {
            "extend_fields": {},
            "agg_dimension": ["bk_target_ip"],
            "keywords_query_string": "",
            "id": 7880,
            "result_table_id": "2_bkmonitor_event_1500110",
            "agg_interval": 30,
            "rule": "",
            "agg_method": "SUM",
            "keywords": "",
            "create_time": 1614652579,
            "update_time": 1614652579,
            "agg_condition": [],
            "rt_query_config_id": 7880,
            "target": [
                [{"field": "host_topo_node", "method": "eq", "value": [{"bk_obj_id": "set", "bk_inst_id": 812}]}]
            ],
        }

        mock_get_es_data.return_value = {
            "hits": {"hits": [], "total": {"relation": "eq", "value": 251}, "max_score": None},
            "_shards": {"successful": 4, "failed": 0, "skipped": 0, "total": 4},
            "took": 8,
            "aggregations": {
                "dimensions.bk_target_cloud_id": {
                    "buckets": [
                        {
                            "dimensions.bk_target_ip": {
                                "buckets": [
                                    {
                                        "time": {
                                            "buckets": [
                                                {
                                                    "distinct": {"value": 1},
                                                    "event.count": {"value": 1.0},
                                                    "key_as_string": "1614334800000",
                                                    "key": 1614334800000,
                                                    "doc_count": 243,
                                                }
                                            ]
                                        },
                                        "key": "127.0.0.1",
                                        "doc_count": 243,
                                    },
                                    {
                                        "time": {
                                            "buckets": [
                                                {
                                                    "distinct": {"value": 1},
                                                    "event.count": {"value": 1.5},
                                                    "key_as_string": "1614334800000",
                                                    "key": 1614334800000,
                                                    "doc_count": 8,
                                                }
                                            ]
                                        },
                                        "key": "127.0.0.2",
                                        "doc_count": 8,
                                    },
                                ],
                                "sum_other_doc_count": 0,
                                "doc_count_error_upper_bound": 0,
                            },
                            "key": "0",
                            "doc_count": 251,
                        }
                    ],
                    "sum_other_doc_count": 0,
                    "doc_count_error_upper_bound": 0,
                }
            },
            "timed_out": False,
        }

        data_source = BkMonitorLogDataSource.init_by_query_config(query_config)
        # limit=200000 验证 limit 始终为 None
        data = data_source.query_data(start_time=1614334800000, end_time=1614334860000, limit=200000)

        assert len(data) == 2
        assert data == [
            {"bk_target_ip": "127.0.0.1", "event.count": 1.0, "_time_": 1614334800000},
            {"bk_target_ip": "127.0.0.2", "event.count": 1.5, "_time_": 1614334800000},
        ]
        assert mock_get_es_data.call_args[1] == {
            "table_id": "2_bkmonitor_event_1500110",
            "use_full_index_names": False,
            "query_body": {
                "aggregations": {
                    "dimensions.bk_target_cloud_id": {
                        "terms": {"field": "dimensions.bk_target_cloud_id", "size": 1440},
                        "aggregations": {
                            "dimensions.bk_target_ip": {
                                "terms": {"field": "dimensions.bk_target_ip", "size": 1440},
                                "aggregations": {
                                    "time": {
                                        "date_histogram": {"field": "time", "interval": "30s", 'time_zone': 'UTC'},
                                        "aggregations": {
                                            "event.count": {"sum": {"field": "event.count"}},
                                            "distinct": {"cardinality": {"field": "dimensions.bk_module_id"}},
                                        },
                                    }
                                },
                            }
                        },
                    }
                },
                "query": {
                    "bool": {
                        "filter": {
                            "bool": {
                                "must": [
                                    {"range": {"time": {"gte": 1614334800000}}},
                                    {"range": {"time": {"lt": 1614334860000}}},
                                ],
                            }
                        }
                    }
                },
                "size": 1,
                "sort": [{"time": "desc"}],
            },
        }

        query_config["agg_dimension"] = []
        mock_get_es_data.return_value = {
            "hits": {"hits": [], "total": {"relation": "eq", "value": 251}, "max_score": None},
            "_shards": {"successful": 4, "failed": 0, "skipped": 0, "total": 4},
            "took": 8,
            "aggregations": {
                "dimensions.bk_target_cloud_id": {
                    "buckets": [
                        {
                            "dimensions.bk_target_ip": {
                                "buckets": [
                                    {
                                        "dimensions.bk_set_id": {
                                            "buckets": [
                                                {
                                                    "time": {
                                                        "buckets": [
                                                            {
                                                                "distinct": {"value": 1},
                                                                "event.count": {"value": 1.0},
                                                                "key_as_string": "1614334800000",
                                                                "key": 1614334800000,
                                                                "doc_count": 243,
                                                            }
                                                        ]
                                                    },
                                                    "key": "812",
                                                    "doc_count": 243,
                                                }
                                            ],
                                            "sum_other_doc_count": 0,
                                            "doc_count_error_upper_bound": 0,
                                        },
                                        "key": "127.0.0.1",
                                        "doc_count": 243,
                                    },
                                    {
                                        "dimensions.bk_set_id": {
                                            "buckets": [
                                                {
                                                    "time": {
                                                        "buckets": [
                                                            {
                                                                "distinct": {"value": 1},
                                                                "event.count": {"value": 1.5},
                                                                "key_as_string": "1614334800000",
                                                                "key": 1614334800000,
                                                                "doc_count": 8,
                                                            }
                                                        ]
                                                    },
                                                    "key": "947",
                                                    "doc_count": 8,
                                                }
                                            ],
                                            "sum_other_doc_count": 0,
                                            "doc_count_error_upper_bound": 0,
                                        },
                                        "key": "127.0.0.1",
                                        "doc_count": 8,
                                    },
                                ],
                                "sum_other_doc_count": 0,
                                "doc_count_error_upper_bound": 0,
                            },
                            "key": "0",
                            "doc_count": 251,
                        },
                        {
                            "dimensions.bk_target_ip": {
                                "buckets": [
                                    {
                                        "dimensions.bk_set_id": {
                                            "buckets": [
                                                {
                                                    "time": {
                                                        "buckets": [
                                                            {
                                                                "distinct": {"value": 1},
                                                                "event.count": {"value": 1.0},
                                                                "key_as_string": "1614334800000",
                                                                "key": 1614334800000,
                                                                "doc_count": 243,
                                                            }
                                                        ]
                                                    },
                                                    "key": "812",
                                                    "doc_count": 243,
                                                }
                                            ],
                                            "sum_other_doc_count": 0,
                                            "doc_count_error_upper_bound": 0,
                                        },
                                        "key": "127.0.0.1",
                                        "doc_count": 243,
                                    },
                                    {
                                        "dimensions.bk_set_id": {
                                            "buckets": [
                                                {
                                                    "time": {
                                                        "buckets": [
                                                            {
                                                                "distinct": {"value": 1},
                                                                "event.count": {"value": 1.5},
                                                                "key_as_string": "1614334800000",
                                                                "key": 1614334800000,
                                                                "doc_count": 8,
                                                            }
                                                        ]
                                                    },
                                                    "key": "947",
                                                    "doc_count": 8,
                                                }
                                            ],
                                            "sum_other_doc_count": 0,
                                            "doc_count_error_upper_bound": 0,
                                        },
                                        "key": "127.0.0.1",
                                        "doc_count": 8,
                                    },
                                ],
                                "sum_other_doc_count": 0,
                                "doc_count_error_upper_bound": 0,
                            },
                            "key": "1",
                            "doc_count": 251,
                        },
                    ],
                    "sum_other_doc_count": 0,
                    "doc_count_error_upper_bound": 0,
                }
            },
            "timed_out": False,
        }

        data_source = BkMonitorLogDataSource.init_by_query_config(query_config)
        data = data_source.query_data(start_time=1614334800000, end_time=1614334860000)

        assert mock_get_es_data.call_args[1] == {
            "table_id": "2_bkmonitor_event_1500110",
            "use_full_index_names": False,
            "query_body": {
                "aggregations": {
                    "dimensions.bk_target_cloud_id": {
                        "terms": {"field": "dimensions.bk_target_cloud_id", "size": 1440},
                        "aggregations": {
                            "dimensions.bk_target_ip": {
                                "terms": {"field": "dimensions.bk_target_ip", "size": 1440},
                                "aggregations": {
                                    "dimensions.bk_set_id": {
                                        "terms": {"field": "dimensions.bk_set_id", "size": 1440},
                                        "aggregations": {
                                            "time": {
                                                "date_histogram": {
                                                    "field": "time",
                                                    "interval": "30s",
                                                    "time_zone": "UTC",
                                                },
                                                "aggregations": {
                                                    "event.count": {"sum": {"field": "event.count"}},
                                                    "distinct": {"cardinality": {"field": "dimensions.bk_module_id"}},
                                                },
                                            }
                                        },
                                    }
                                },
                            }
                        },
                    }
                },
                "query": {
                    "bool": {
                        "filter": {
                            "bool": {
                                "must": [
                                    {"bool": {"must": [{"terms": {"dimensions.bk_set_id": [812]}}]}},
                                    {"range": {"time": {"gte": 1614334800000}}},
                                    {"range": {"time": {"lt": 1614334860000}}},
                                ],
                            }
                        }
                    }
                },
                "size": 1,
                "sort": [{"time": "desc"}],
            },
        }
        assert len(data) == 2
        assert data == [
            {"bk_obj_id": "set", "bk_inst_id": "812", "event.count": 2.0, "_time_": 1614334800000},
            {"bk_obj_id": "set", "bk_inst_id": "947", "event.count": 3.0, "_time_": 1614334800000},
        ]

        query_config["agg_dimension"] = ["bk_target_service_instance_id"]
        mock_get_es_data.return_value = {
            "hits": {"hits": [], "total": {"relation": "eq", "value": 251}, "max_score": None},
            "_shards": {"successful": 4, "failed": 0, "skipped": 0, "total": 4},
            "took": 542,
            "aggregations": {
                "dimensions.bk_target_cloud_id": {
                    "buckets": [
                        {
                            "dimensions.bk_target_ip": {
                                "buckets": [
                                    {
                                        "dimensions.bk_target_service_instance_id": {
                                            "buckets": [
                                                {
                                                    "time": {
                                                        "buckets": [
                                                            {
                                                                "distinct": {"value": 1},
                                                                "event.count": {"value": 243.0},
                                                                "key_as_string": "1614334800000",
                                                                "key": 1614334800000,
                                                                "doc_count": 243,
                                                            }
                                                        ]
                                                    },
                                                    "key": "7045",
                                                    "doc_count": 243,
                                                }
                                            ],
                                            "sum_other_doc_count": 0,
                                            "doc_count_error_upper_bound": 0,
                                        },
                                        "key": "127.0.0.1",
                                        "doc_count": 243,
                                    },
                                    {
                                        "dimensions.bk_target_service_instance_id": {
                                            "buckets": [
                                                {
                                                    "time": {
                                                        "buckets": [
                                                            {
                                                                "distinct": {"value": 1},
                                                                "event.count": {"value": 12.0},
                                                                "key_as_string": "1614334800000",
                                                                "key": 1614334800000,
                                                                "doc_count": 8,
                                                            }
                                                        ]
                                                    },
                                                    "key": "9348",
                                                    "doc_count": 8,
                                                }
                                            ],
                                            "sum_other_doc_count": 0,
                                            "doc_count_error_upper_bound": 0,
                                        },
                                        "key": "127.0.0.2",
                                        "doc_count": 8,
                                    },
                                ],
                                "sum_other_doc_count": 0,
                                "doc_count_error_upper_bound": 0,
                            },
                            "key": "0",
                            "doc_count": 251,
                        }
                    ],
                    "sum_other_doc_count": 0,
                    "doc_count_error_upper_bound": 0,
                }
            },
            "timed_out": False,
        }

        data_source = BkMonitorLogDataSource.init_by_query_config(query_config)
        data = data_source.query_data(start_time=1614334800000, end_time=1614334860000)

        assert len(data) == 2
        assert data == [
            {"bk_target_service_instance_id": "7045", "event.count": 243.0, "_time_": 1614334800000},
            {"bk_target_service_instance_id": "9348", "event.count": 12.0, "_time_": 1614334800000},
        ]
        assert mock_get_es_data.call_args[1] == {
            "table_id": "2_bkmonitor_event_1500110",
            "use_full_index_names": False,
            "query_body": {
                "aggregations": {
                    "dimensions.bk_target_cloud_id": {
                        "terms": {"field": "dimensions.bk_target_cloud_id", "size": 1440},
                        "aggregations": {
                            "dimensions.bk_target_ip": {
                                "terms": {"field": "dimensions.bk_target_ip", "size": 1440},
                                "aggregations": {
                                    "dimensions.bk_target_service_instance_id": {
                                        "terms": {"field": "dimensions.bk_target_service_instance_id", "size": 1440},
                                        "aggregations": {
                                            "time": {
                                                "date_histogram": {
                                                    "field": "time",
                                                    "interval": "30s",
                                                    "time_zone": "UTC",
                                                },
                                                "aggregations": {
                                                    "event.count": {"sum": {"field": "event.count"}},
                                                    "distinct": {"cardinality": {"field": "dimensions.bk_module_id"}},
                                                },
                                            }
                                        },
                                    }
                                },
                            }
                        },
                    }
                },
                "query": {
                    "bool": {
                        "filter": {
                            "bool": {
                                "must": [
                                    {"range": {"time": {"gte": 1614334800000}}},
                                    {"range": {"time": {"lt": 1614334860000}}},
                                ]
                            },
                        }
                    }
                },
                "size": 1,
                "sort": [{"time": "desc"}],
            },
        }


class TestCustomEventDataSource:
    def test_query_data(self, mock_get_es_data):
        query_config = {
            "bk_event_group_id": 1,
            "custom_event_id": 1,
            "id": 1,
            "agg_interval": 30,
            "agg_dimension": [],
            "agg_condition": [],
            "agg_method": "COUNT",
            "extend_fields": {"custom_event_name": "error"},
            "result_table_id": "2_bkmonitor_event_524629",
            "rt_query_config_id": 1,
            "custom_event_name": "error",
        }

        mock_get_es_data.return_value = {
            "took": 10,
            "timed_out": False,
            "_shards": {"total": 4, "successful": 4, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 84, "relation": "eq"},
                "max_score": None,
                "hits": [
                    {
                        "_index": "v2_2005000002_bkmonitor_event_524629_20210302_0",
                        "_type": "_doc",
                        "_id": "0e18c3210d6b9a2eacb9b70c84373531",
                        "_score": None,
                        "_source": {
                            "dimensions": {"location": "guangdong", "module": "db"},
                            "event": {"content": "user4 login failed"},
                            "event_name": "warning",
                            "target": "127.0.0.1",
                            "time": "1614693361136",
                        },
                        "sort": [1614693361136000000],
                    }
                ],
            },
            "aggregations": {
                "time": {
                    "buckets": [
                        {
                            "key_as_string": "1614691260000",
                            "key": 1614691260000,
                            "doc_count": 2,
                            "_index": {"value": 2},
                        },
                        {
                            "key_as_string": "1614691320000",
                            "key": 1614691320000,
                            "doc_count": 2,
                            "_index": {"value": 2},
                        },
                    ]
                }
            },
        }

        data_source = CustomEventDataSource.init_by_query_config(query_config)
        data = data_source.query_data(start_time=1614334800000, end_time=1614334860000)

        assert mock_get_es_data.call_args[1] == {
            "table_id": "2_bkmonitor_event_524629",
            "use_full_index_names": False,
            "query_body": {
                "aggregations": {
                    "time": {
                        "date_histogram": {"field": "time", "interval": "30s", "time_zone": "UTC"},
                        "aggregations": {"_index": {"value_count": {"field": "_index"}}},
                    }
                },
                "query": {
                    "bool": {
                        "filter": {
                            "bool": {
                                "must": [
                                    {
                                        "bool": {
                                            "must": [{"terms": {"event_name": ["error"]}}],
                                            "must_not": [{"terms": {"dimensions.event_type": ["recovery"]}}],
                                        }
                                    },
                                    {"range": {"time": {"gte": 1614334800000}}},
                                    {"range": {"time": {"lt": 1614334860000}}},
                                ],
                            },
                        }
                    }
                },
                "size": 1,
                "sort": [{"time": "desc"}],
            },
        }

        assert len(data) == 2
        assert data == [{"_time_": 1614691260000, "_index": 2}, {"_time_": 1614691320000, "_index": 2}]

    def test_query_data__top50(self, mock_get_es_data):
        query_config = {
            "filter_dict": {},
            "functions": [{"id": "top", "params": [{"id": "n", "value": "50"}]}],
            "agg_dimension": ["user_name"],
            "interval": 600,
            "interval_unit": "s",
            "metrics": [{"alias": "a", "field": "__INDEX__", "method": "COUNT"}],
            "result_table_id": "6_bkmonitor_event_1575757",
            "time_field": "time",
            "agg_condition": [{"key": "target", "method": "eq", "value": ["a", "b", "c"]}],
        }
        mock_get_es_data.return_value = {}

        data_source = CustomEventDataSource.init_by_query_config(query_config)
        data_source.query_data(start_time=1614334800000, end_time=1614334860000)

        assert mock_get_es_data.call_args[1] == {
            "query_body": {
                "aggregations": {
                    "dimensions.user_name": {
                        "aggregations": {
                            "time": {
                                "aggregations": {"_index": {"value_count": {"field": "_index"}}},
                                "date_histogram": {"field": "time", "interval": "60s", "time_zone": "UTC"},
                            }
                        },
                        "terms": {"field": "dimensions.user_name", "size": 1440},
                    }
                },
                "query": {
                    "bool": {
                        "filter": {
                            "bool": {
                                "must": [
                                    {"bool": {"must_not": [{"terms": {"dimensions.event_type": ["recovery"]}}]}},
                                    {"range": {"time": {"gte": 1614334800000}}},
                                    {"range": {"time": {"lt": 1614334860000}}},
                                ]
                            }
                        },
                        "minimum_should_match": 1,
                        "should": [{"bool": {"must": [{"terms": {"target": ["a", "b", "c"]}}]}}],
                    }
                },
                "size": 1,
                "sort": [{"time": "desc"}],
            },
            "table_id": "6_bkmonitor_event_1575757",
            "use_full_index_names": False,
        }


class TestBkApmTraceDataSource:
    def test_query_data(self, mock_get_es_data):
        query_config = {
            "table": "2_bkapm_trace_app",
            "time_field": "end_time",
            "metrics": [{"field": "span_name", "alias": "total_count", "method": "count"}],
            "group_by": ["span_name"],
            "filter_dict": {},
            "query_string": "*",
            "order_by": ["end_time desc"],
        }

        mock_get_es_data.return_value = {
            "took": 15,
            "timed_out": False,
            "_shards": {"total": 2, "successful": 2, "skipped": 0, "failed": 0},
            "hits": {"total": {"value": 10000, "relation": "gte"}, "max_score": None, "hits": []},
            "aggregations": {
                "span_name": {
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                    "buckets": [
                        {"key": "Sub", "doc_count": 2109, "total_count": {"value": 2109}},
                        {"key": "Add", "doc_count": 2086, "total_count": {"value": 2086}},
                    ],
                }
            },
        }

        data_source = BkApmTraceDataSource.init_by_query_config(query_config)
        data = data_source.query_data(start_time=1614334800, end_time=1614334860, limit=30)

        assert mock_get_es_data.call_args[1] == {
            "query_body": {
                "aggregations": {
                    "span_name": {
                        "aggregations": {"total_count": {"value_count": {"field": "span_name"}}},
                        "terms": {"field": "span_name", "size": 30},
                    }
                },
                "query": {
                    "bool": {
                        "filter": {
                            "bool": {
                                "must": [
                                    {"range": {"end_time": {"gte": 1614334800000}}},
                                    {"range": {"end_time": {"lt": 1614334860000}}},
                                ]
                            }
                        }
                    }
                },
                "size": 0,
                "sort": [{"end_time": "desc"}],
            },
            "table_id": "2_bkapm_trace_app",
            "use_full_index_names": True,
        }

        assert len(data) == 2
        assert data == [{'span_name': 'Sub', 'total_count': 2109}, {'span_name': 'Add', 'total_count': 2086}]

    def test_query_data__search_after(self, mock_get_es_data):
        query_config = {
            "table": "2_bkapm_trace_app",
            "time_field": "end_time",
            "where": [],
            "metrics": [
                {"field": "span_name", "alias": "total_count", "method": "count"},
                {"field": "elapsed_time", "alias": "avg_duration", "method": "avg"},
                {"field": "elapsed_time", "alias": "p50_duration", "method": "cp50"},
                {"field": "elapsed_time", "alias": "p90_duration", "method": "cp90"},
            ],
            "group_by": ["span_name", "resource.service.name", "kind"],
            "filter_dict": {},
            "query_string": "*",
            "order_by": ["end_time desc"],
        }

        mock_get_es_data.return_value = {
            "took": 34,
            "timed_out": False,
            "_shards": {"total": 2, "successful": 2, "skipped": 0, "failed": 0},
            "hits": {"total": {"value": 10000, "relation": "gte"}, "max_score": None, "hits": []},
            "aggregations": {
                "_group_": {
                    "meta": {},
                    "after_key": {
                        "span_name": "/grpc.crayon.query.TimeSeriesQueryService/Query",
                        "service_name": "example.greeter",
                        "kind": 3,
                    },
                    "buckets": [
                        {
                            "key": {
                                "span_name": "/grpc.crayon.query.TimeSeriesQueryService/Query",
                                "service_name": "example.greeter",
                                "kind": 3,
                            },
                            "doc_count": 2239,
                            "avg_duration": {"value": 200376.66234926306},
                            "total_count": {"value": 2239},
                            "p50_duration": {"values": {"50.0": 202000.26666666666}},
                            "error_count": {"meta": {}, "doc_count": 2239, "count": {"value": 2239}},
                            "p90_duration": {"values": {"90.0": 281324.76296296297}},
                        }
                    ],
                }
            },
        }

        data_source = BkApmTraceDataSource.init_by_query_config(query_config)
        data = data_source.query_data(start_time=1614334800, end_time=1614334860, limit=1, search_after_key={})

        assert mock_get_es_data.call_args[1] == {
            "query_body": {
                "aggregations": {
                    "_group_": {
                        "aggregations": {
                            "avg_duration": {"avg": {"field": "elapsed_time"}},
                            "p50_duration": {"percentiles": {"field": "elapsed_time", "percents": [50]}},
                            "p90_duration": {"percentiles": {"field": "elapsed_time", "percents": [90]}},
                            "total_count": {"value_count": {"field": "span_name"}},
                        },
                        "composite": {
                            "size": 1,
                            "sources": [
                                {"span_name": {"terms": {"field": "span_name"}}},
                                {"resource.service.name": {"terms": {"field": "resource.service.name"}}},
                                {"kind": {"terms": {"field": "kind"}}},
                            ],
                        },
                    }
                },
                "query": {
                    "bool": {
                        "filter": {
                            "bool": {
                                "must": [
                                    {"range": {"end_time": {"gte": 1614334800000}}},
                                    {"range": {"end_time": {"lt": 1614334860000}}},
                                ]
                            }
                        }
                    }
                },
                "size": 0,
                "sort": [{"end_time": "desc"}],
            },
            "table_id": "2_bkapm_trace_app",
            "use_full_index_names": True,
        }

        assert len(data) == 1
        assert data == [
            {
                "_after_key_": {
                    "kind": 3,
                    "service_name": "example.greeter",
                    "span_name": "/grpc.crayon.query.TimeSeriesQueryService/Query",
                },
                "avg_duration": 200376.66234926306,
                "kind": 3,
                "p50_duration": 202000.26666666666,
                "p90_duration": 281324.76296296297,
                "resource.service.name": None,
                "span_name": "/grpc.crayon.query.TimeSeriesQueryService/Query",
                "total_count": 2239,
            }
        ]

    def test_query_log(self, mock_get_es_data):
        select = [
            "trace_id",
            "span_id",
            "parent_span_id",
            "span_name",
            "trace_state",
            "kind",
            "status",
            "resource",
            "time",
            "start_time",
            "end_time",
            "elapsed_time",
        ]
        query_config = {
            "table": "2_bkapm_trace_app",
            "time_field": "end_time",
            "where": [{"condition": "and", "key": "parent_span_id", "method": "eq", "value": [""]}],
            "query_string": "*",
            "order_by": ["end_time desc"],
            "select": select,
        }

        mock_get_es_data.return_value = {
            "took": 5,
            "timed_out": False,
            "_shards": {"total": 2, "successful": 2, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 10000, "relation": "gte"},
                "max_score": None,
                "hits": [
                    {
                        "_index": "v2_2_bkapm_trace_app_20240821_0",
                        "_type": "_doc",
                        "_id": "4168651124563384611",
                        "_score": None,
                        "_source": {
                            "parent_span_id": "e1109836411e69f7",
                            "span_name": "/grpc.example.greeter.Greeter/SayHi",
                            "start_time": 1724350530600514,
                            "trace_id": "7253273218cd0ae249eed00351918fef",
                            "trace_state": "g=w:1;s:5;r:4",
                            "span_id": "33bd671493c9f305",
                            "resource": {
                                "telemetry.sdk.language": "go",
                                "container_name": "test.example.greeter.con",
                                "service.name": "example.greeter",
                            },
                            "kind": 3,
                            "end_time": 1724350530711449,
                            "elapsed_time": 110935,
                            "time": "1724350531000",
                            "status": {"code": 2, "message": "type:business, code:1, msg:random error"},
                        },
                        "sort": [1724350530711449],
                    },
                ],
            },
        }

        data_source = BkApmTraceDataSource.init_by_query_config(query_config)
        data, __ = data_source.query_log(start_time=1614334800, end_time=1614334860, limit=1)

        assert mock_get_es_data.call_args[1] == {
            "query_body": {
                "_source": select,
                "query": {
                    "bool": {
                        "filter": {
                            "bool": {
                                "must": [
                                    {"range": {"end_time": {"gte": 1614334800000}}},
                                    {"range": {"end_time": {"lt": 1614334860000}}},
                                ]
                            }
                        },
                        "minimum_should_match": 1,
                        "should": [{"bool": {"must": [{"terms": {"parent_span_id": [""]}}]}}],
                    }
                },
                "size": 1,
                "sort": [{"end_time": "desc"}],
            },
            "table_id": "2_bkapm_trace_app",
            "use_full_index_names": True,
        }

        assert len(data) == 1
        assert data == [
            {
                "elapsed_time": 110935,
                "end_time": 1724350530711449,
                "kind": 3,
                "parent_span_id": "e1109836411e69f7",
                "resource": {
                    "container_name": "test.example.greeter.con",
                    "service.name": "example.greeter",
                    "telemetry.sdk.language": "go",
                },
                "span_id": "33bd671493c9f305",
                "span_name": "/grpc.example.greeter.Greeter/SayHi",
                "start_time": 1724350530600514,
                "status": {"code": 2, "message": "type:business, code:1, msg:random error"},
                "time": "1724350531000",
                "trace_id": "7253273218cd0ae249eed00351918fef",
                "trace_state": "g=w:1;s:5;r:4",
            }
        ]
