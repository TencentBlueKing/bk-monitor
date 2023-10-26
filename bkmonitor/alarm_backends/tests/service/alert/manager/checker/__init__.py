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

NOTICE = {  # 通知设置
    "id": 1,
    "config_id": 55555,  # 套餐ID，如果不选套餐请置为0
    "user_groups": [],  # 告警组ID
    "signal": ["abnormal", "recovered", "ack"],
    "options": {
        "converge_config": {
            "is_enabled": True,
            "converge_func": "collect",
            "timedelta": 60,
            "count": 1,
            "condition": [
                {"dimension": "strategy_id", "value": ["self"]},
                {"dimension": "dimensions", "value": ["self"]},
                {"dimension": "alert_level", "value": ["self"]},
                {"dimension": "signal", "value": ["self"]},
                {"dimension": "bk_biz_id", "value": ["self"]},
                {"dimension": "notice_receiver", "value": ["self"]},
                {"dimension": "notice_way", "value": ["self"]},
                {"dimension": "notice_info", "value": ["self"]},
            ],
            "need_biz_converge": True,
            "sub_converge_config": {
                "timedelta": 60,
                "count": 2,
                "condition": [
                    {"dimension": "bk_biz_id", "value": ["self"]},
                    {"dimension": "notice_receiver", "value": ["self"]},
                    {"dimension": "notice_way", "value": ["self"]},
                    {"dimension": "alert_level", "value": ["self"]},
                    {"dimension": "signal", "value": ["self"]},
                ],
                "converge_func": "collect_alarm",
            },
        },
        "start_time": "00:00:00",
        "end_time": "23:59:59",
    },
    "execute_config": {
        "template_detail": {
            "interval_notify_mode": "standard",  # 间隔模式
            "notify_interval": 7200,  # 通知间隔
            "template": [  # 通知模板配置
                {
                    "signal": "abnormal",
                }
            ],
        }
    },
}

STRATEGY = {
    "bk_biz_id": 2,
    "version": "v2",
    "items": [
        {
            "target": [
                [
                    {
                        "field": "bk_target_ip",
                        "method": "eq",
                        "value": [
                            {
                                "bk_target_ip": "10.0.0.1",
                                "bk_target_cloud_id": 0,
                            },
                        ],
                    }
                ]
            ],
            "query_configs": [
                {
                    "metric_field": "idle",
                    "agg_dimension": ["ip", "bk_cloud_id"],
                    "id": 2,
                    "rt_query_config_id": 2,
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
                {"config": [{"threshold": 0.1, "method": "gte"}], "level": 1, "type": "Threshold", "id": 1},
                {"config": [{"threshold": 0.1, "method": "gte"}], "level": 2, "type": "Threshold", "id": 2},
                {"config": [{"threshold": 0.1, "method": "gte"}], "level": 3, "type": "Threshold", "id": 3},
            ],
            "no_data_config": {"is_enabled": True, "continuous": 5},
            "id": 1,
            "name": "\u7a7a\u95f2\u7387",
        }
    ],
    "detects": [
        {
            "expression": "",
            "level": 1,
            "connector": "and",
            "recovery_config": {"check_window": 5},
            "trigger_config": {"count": 3, "check_window": 5},
        },
        {
            "expression": "",
            "level": 2,
            "connector": "and",
            "recovery_config": {"check_window": 5, "status_setter": "recovery"},
            "trigger_config": {"count": 2, "check_window": 5},
        },
        {
            "expression": "",
            "level": 3,
            "connector": "and",
            "recovery_config": {"check_window": 5},
            "trigger_config": {"count": 1, "check_window": 5},
        },
    ],
    "scenario": "os",
    "actions": [],
    "notice": NOTICE,
    "source_type": "BKMONITOR",
    "id": 1,
    "name": "test",
}

ANOMALY_EVENT = {
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
    "trigger": {
        "level": "2",
        "anomaly_ids": [
            "55a76cf628e46c04a052f4e19bdb9dbf.1569246240.1.1.2",
            "55a76cf628e46c04a052f4e19bdb9dbf.1569246360.1.1.2",
            "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1.1.2",
        ],
    },
}
