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

from collections import namedtuple

import mock

from alarm_backends.service.detect import DataPoint
from bkmonitor.data_source import BkMonitorTimeSeriesDataSource
from bkmonitor.data_source.unify_query.query import UnifyQuery

Strategy = namedtuple("Strategy", ["id", "scenario"])


class Item(object):
    def __init__(self, id, strategy, unit, data_sources, metric_ids, query_configs=None, query=None, name="avg(测试指标)"):
        self.id = id
        self.strategy = strategy
        self.unit = unit
        self.data_sources = data_sources
        self.metric_ids = metric_ids
        self.query_configs = query_configs
        self.query = query
        self.name = name


item_config = {
    "algorithms": [
        {
            "config": [{"threshold": 51.0, "method": "gte"}],
            "level": 3,
            "type": "Threshold",
            "id": 1,
        }
    ],
    "name": "\\u7a7a\\u95f2\\u7387",
    "no_data_config": {"is_enabled": False, "continuous": 5},
    "id": 2,
    "query_configs": [
        {
            "result_table_id": "system.cpu_detail",
            "agg_dimension": ["mocked"],
            "data_source_label": "bk_monitor",
            "agg_method": "AVG",
            "agg_condition": [],
            "agg_interval": 60,
            "data_type_label": "time_series",
            "unit": "%",
            "metric_id": "system.cpu_detail.idle",
            "metric_field": "mocked_metric",
        }
    ],
}

mocked_data_source = BkMonitorTimeSeriesDataSource.init_by_query_config(
    item_config["query_configs"][0], bk_biz_id=2, name="测试指标"
)
mock_unify_query = UnifyQuery(bk_biz_id=2, data_sources=[mocked_data_source], expression="mocked_metric")
mocked_item = Item(
    1,
    Strategy(1, "os"),
    "%",
    [mocked_data_source],
    ["system.cpu_summary"],
    item_config["query_configs"],
    mock_unify_query,
)
mock_unify_query.query_data = mocked_item.query_record = mock.MagicMock(
    return_value=[
        {"mocked": "mocked", "mocked_metric": 99, "_time_": 1569246420, "minute1": 1569246420, "_result_": 99},
        {"mocked": "mocked", "mocked_metric": 1, "_time_": 1569246360, "minute1": 1569246360, "_result_": 1},
        {"mocked": "mocked", "mocked_metric": 101, "_time_": 1569246300, "minute1": 1569246300, "_result_": 101},
    ]
)


datapoint99 = DataPoint(
    {
        "record_id": "342a08e0f85f169a7e099c18db3708ed",
        "value": 99,
        "values": {"timestamp": 1569246480, "load5": 99},
        "dimensions": {"ip": "127.0.0.1"},
        "time": 1569246480,
    },
    mocked_item,
)
datapoint50 = DataPoint(
    {
        "record_id": "2a1850513fa6018c435f9b6359b3fa7d",
        "value": 50,
        "values": {"timestamp": 1569246480, "load5": 99},
        "dimensions": {"ip": "10.0.0.1"},
        "time": 1569246480,
    },
    mocked_item,
)
datapoint6 = DataPoint(
    {
        "record_id": "a52b87cdb12520fc5000a4ff358dbc18",
        "value": 6,
        "values": {"timestamp": 1569246480, "load5": 99},
        "dimensions": {"ip": "10.0.0.2"},
        "time": 1569246480,
    },
    mocked_item,
)
datapoint_example = DataPoint(
    {
        "record_id": "a52b87cdb12520fc5000a4ff358dbc18",
        "value": 0,
        "values": {"timestamp": 1569246480, "load5": 0},
        "dimensions": {"ip": "10.0.0.2"},
        "time": 1569246480,
    },
    mocked_item,
)


def mock_datapoint_with_value(value):
    return DataPoint(
        {
            "record_id": "389518839de471c0baec4b6fb26c2538",
            "value": value,
            "values": {"timestamp": 1569246480, "mocked_metric": value},
            "dimensions": {"mocked": "mocked"},
            "time": 1569246480,
        },
        mocked_item,
    )
