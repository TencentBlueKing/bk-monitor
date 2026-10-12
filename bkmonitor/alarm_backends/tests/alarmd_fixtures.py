"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

DETECT_STRATEGY = {
    "bk_biz_id": 2,
    "items": [
        {
            "query_configs": [
                {
                    "metric_field": "idle",
                    "agg_dimension": ["ip", "bk_cloud_id"],
                    "id": 2,
                    "agg_method": "AVG",
                    "agg_condition": [],
                    "agg_interval": 60,
                    "result_table_id": "system.cpu_detail",
                    "unit": "%",
                    "data_type_label": "time_series",
                    "metric_id": "bk_monitor.system.cpu_detail.idle",
                    "data_source_label": "bk_monitor",
                }
            ],
            "algorithms": [
                {
                    "config": [[{"threshold": 51.0, "method": "gte"}]],
                    "level": 3,
                    "type": "Threshold",
                    "id": 2,
                },
                {
                    "config": [[{"threshold": 100, "method": "lte"}]],
                    "level": 3,
                    "type": "Threshold",
                    "id": 3,
                },
            ],
            "no_data_config": {"is_enabled": False, "continuous": 5},
            "id": 2,
            "name": "\u7a7a\u95f2\u7387",
            "target": [
                [{"field": "ip", "method": "eq", "value": [{"ip": "127.0.0.1", "bk_cloud_id": 0, "bk_supplier_id": 0}]}]
            ],
        }
    ],
    "scenario": "os",
    "actions": [
        {
            "notice_template": {"action_id": 2, "anomaly_template": "aa", "recovery_template": ""},
            "id": 2,
            "notice_group_list": [
                {
                    "notice_receiver": ["user#test"],
                    "name": "test",
                    "notice_way": {"1": ["weixin"], "3": ["weixin"], "2": ["weixin"]},
                    "notice_group_id": 1,
                    "message": "",
                    "notice_group_name": "test",
                    "id": 1,
                }
            ],
            "type": "notice",
            "config": {
                "alarm_end_time": "23:59:59",
                "send_recovery_alarm": False,
                "alarm_start_time": "00:00:00",
                "alarm_interval": 120,
            },
        }
    ],
    "detects": [
        {
            "level": 3,
            "expression": "",
            "connector": "and",
            "trigger_config": {"count": 1, "check_window": 5},
            "recovery_config": {"check_window": 5},
        }
    ],
    "update_time": 1569246480,
    "source_type": "BKMONITOR",
    "id": 1,
    "name": "test",
}


DETECT_RECORDS = [
    {
        "record_id": "342a08e0f85f169a7e099c18db3708ed.1569246480",
        "value": 99,
        "values": {"timestamp": 1569246480, "load5": 99},
        "dimensions": {"ip": "127.0.0.1"},
        "time": 1569246480,
    },
    {
        "record_id": "2a1850513fa6018c435f9b6359b3fa7d.1569246481",
        "value": 50.1,
        "values": {"timestamp": 1569246481, "load5": 50.1},
        "dimensions": {"ip": "10.0.0.1"},
        # 数据点时间戳错开，避免检测记录断言不准确
        "time": 1569246481,
    },
]


TRIGGER_STRATEGY = {
    "bk_biz_id": 2,
    "items": [
        {
            "query_configs": [
                {
                    "metric_field": "idle",
                    "agg_dimension": ["ip", "bk_cloud_id"],
                    "id": 2,
                    "agg_method": "AVG",
                    "agg_condition": [],
                    "agg_interval": 60,
                    "result_table_id": "system.cpu_detail",
                    "unit": "%",
                    "data_type_label": "time_series",
                    "metric_id": "bk_monitor.system.cpu_detail.idle",
                    "data_source_label": "bk_monitor",
                }
            ],
            "target": [
                [
                    {
                        "field": "ip",
                        "method": "eq",
                        "value": [
                            {"ip": "127.0.0.1", "bk_cloud_id": 0, "bk_supplier_id": 0},
                        ],
                    }
                ]
            ],
            "algorithms": [
                {"config": [{"threshold": 0.1, "method": "gte"}], "level": 1, "type": "Threshold", "id": 1},
                {"config": [{"threshold": 0.1, "method": "gte"}], "level": 2, "type": "Threshold", "id": 2},
                {"config": [{"threshold": 0.1, "method": "gte"}], "level": 3, "type": "Threshold", "id": 3},
            ],
            "no_data_config": {"is_enabled": False, "continuous": 5},
            "id": 1,
            "name": "\u7a7a\u95f2\u7387",
        }
    ],
    "detects": [
        {
            "expression": "",
            "connector": "and",
            "level": 1,
            "trigger_config": {"count": 3, "check_window": 5},
            "recovery_config": {"check_window": 5},
        },
        {
            "expression": "",
            "connector": "and",
            "level": 2,
            "trigger_config": {"count": 2, "check_window": 5},
            "recovery_config": {"check_window": 5},
        },
        {
            "expression": "",
            "connector": "and",
            "level": 3,
            "trigger_config": {"count": 1, "check_window": 5},
            "recovery_config": {"check_window": 5},
        },
    ],
    "scenario": "os",
    "actions": [
        {
            "notice_template": {"anomaly_template": "aa", "recovery_template": ""},
            "id": 2,
            "notice_group_list": [
                {
                    "notice_receiver": ["user#test"],
                    "name": "test",
                    "notice_way": {"1": ["weixin"], "3": ["weixin"], "2": ["weixin"]},
                    "notice_group_id": 1,
                    "message": "",
                    "notice_group_name": "test",
                    "id": 1,
                }
            ],
            "type": "notice",
            "config": {
                "alarm_end_time": "23:59:59",
                "send_recovery_alarm": False,
                "alarm_start_time": "00:00:00",
                "alarm_interval": 120,
            },
        }
    ],
    "source_type": "BKMONITOR",
    "id": 1,
    "name": "test",
}


TRIGGER_POINT = {
    "data": {
        "record_id": "55a76cf628e46c04a052f4e19bdb9dbf.1569246480",
        "value": 1.38,
        "values": {"timestamp": 1569246480, "load5": 1.38},
        "dimensions": {"ip": "10.0.0.1"},
        "time": 1569246480,
    },
    "anomaly": {
        "1": {
            "anomaly_message": "异常测试",
            "anomaly_id": "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1.1.1",
            "anomaly_time": "2019-10-10 10:10:00",
        },
        "2": {
            "anomaly_message": "异常测试",
            "anomaly_id": "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1.1.2",
            "anomaly_time": "2019-10-10 10:10:00",
        },
        "3": {
            "anomaly_message": "异常测试",
            "anomaly_id": "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1.1.3",
            "anomaly_time": "2019-10-10 10:10:00",
        },
    },
    "strategy_snapshot_key": "xxx",
}
