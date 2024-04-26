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
from collections import defaultdict

RAW_DATA = {
    "bk_target_ip": "127.0.0.1",
    "load5": 1.381234,
    "bk_target_cloud_id": "0",
    "_time_": 1569246480,
    "_result_": 1.381234,
}
RAW_DATA_ZERO = {
    "bk_target_ip": "127.0.0.2",
    "load5": 0,
    "bk_target_cloud_id": "0",
    "_time_": 1569246420,
    "_result_": 0,
}
RAW_DATA_NONE = {
    "bk_target_ip": "127.0.0.3",
    "load5": None,
    "bk_target_cloud_id": "0",
    "_time_": 1569246420,
    "_result_": None,
}

EVENT_RAW_DATA = {
    "_time_": "2020-06-16 12:35:06",
    "_type_": 8,
    "_bizid_": 0,
    "_cloudid_": 0,
    "_server_": "127.0.0.1",
    "_host_": "127.0.0.1",
    "_title_": "",
    "dimensions": {"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": 0},
}

CORE_FILE_RAW_DATA = {
    "_time_": "2020-06-16 12:35:06",
    "_type_": 7,
    "_bizid_": 0,
    "_cloudid_": 0,
    "_server_": "127.0.0.1",
    "_host_": "127.0.0.1",
    "_title_": "",
    "_extra_": {
        "bizid": 0,
        "cloudid": 0,
        "corefile": "/data/corefile/core_101041_2018-03-10",
        "filesize": "0",
        "host": "127.0.0.1",
        "type": 7,
    },
}

FORMAT_RAW_DATA = {
    "bk_target_ip": "127.0.0.1",
    "load5": 1.38,
    "bk_target_cloud_id": "0",
    "_time_": 1569246480,
    "_result_": 1.38,
}

STANDARD_DATA = {
    "record_id": "ac6847eefd664275c7b3693829f68bab.1569246480",
    "value": 1.38,
    "values": {"time": 1569246480, "load5": 1.38, "_result_": 1.38},
    "dimensions": {"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": "0"},
    "time": 1569246480,
}

STRATEGY_CONFIG = {
    "is_enabled": True,
    "update_time": 1569044491,
    "update_user": "admin",
    "actions": [
        {
            "notice_template": {"anomaly_template": "", "recovery_template": ""},
            "notice_group_list": [
                {
                    "notice_way": {"1": ["sms"], "3": ["weixin"], "2": ["mail"]},
                    "notice_receiver": ["group#Maintainers"],
                    "id": 1,
                    "name": "ada",
                }
            ],
            "type": "notice",
            "config": {
                "alarm_end_time": "23:59:59",
                "send_recovery_alarm": False,
                "alarm_start_time": "00:00:00",
                "alarm_interval": 120,
            },
            "id": 1,
        }
    ],
    "create_user": "admin",
    "create_time": 1569044491,
    "id": 1,
    "target": [
        [{"field": "bk_target_ip", "method": "eq", "value": [{"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": 0}]}]
    ],
    "bk_biz_id": 2,
    "items": [
        {
            "query_configs": [
                {
                    "metric_field": "load5",
                    "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
                    "unit_conversion": 1.0,
                    "id": 2,
                    "agg_method": "AVG",
                    "agg_condition": [],
                    "agg_interval": 60,
                    "result_table_id": "system.cpu_load",
                    "unit": "%",
                    "data_source_label": "bk_monitor",
                    "data_type_label": "time_series",
                    "metric_id": "system.cpu_detail.idle",
                }
            ],
            "algorithms": [
                {
                    "config": [{"threshold": 12.0, "method": "gte"}],
                    "level": 1,
                    "type": "Threshold",
                    "id": 1,
                },
                {
                    "config": [{"threshold": 12.0, "method": "gte"}],
                    "level": 2,
                    "type": "Threshold",
                    "id": 2,
                },
                {
                    "config": [{"threshold": 12.0, "method": "gte"}],
                    "level": 3,
                    "type": "Threshold",
                    "id": 3,
                },
            ],
            "name": "\\u7a7a\\u95f2\\u7387",
            "no_data_config": {"is_enabled": False, "continuous": 5},
            "id": 1,
            "create_time": 1569044491,
            "update_time": 1569044491,
        }
    ],
    "detects": [
        {
            "level": 1,
            "expression": "",
            "trigger_config": {"count": 3, "check_window": 5},
            "recovery_config": {"check_window": 5},
            "connector": "and",
        },
        {
            "level": 2,
            "expression": "",
            "trigger_config": {"count": 2, "check_window": 5},
            "recovery_config": {"check_window": 5},
            "connector": "and",
        },
        {
            "level": 3,
            "expression": "",
            "trigger_config": {"count": 1, "check_window": 5},
            "recovery_config": {"check_window": 5},
            "connector": "and",
        },
    ],
    "name": "test",
    "scenario": "os",
    "source_type": "BKMONITOR",
}

EVENT_STRATEGY_CONFIG = {
    "bk_biz_id": 2,
    "name": "自定义字符型",
    "scenario": "os",
    "update_user": "admin",
    "source": "bk_monitorv3",
    "id": 1,
    "create_user": "admin",
    "create_time": 1587992788,
    "update_time": 1591255506,
    "items": [
        {
            "no_data_config": {"continuous": 5, "is_enabled": False},
            "id": 1,
            "name": "PING不可达",
            "create_time": 1587992788,
            "update_time": 1591255506,
            "target": [
                [
                    {
                        "field": "bk_target_ip",
                        "method": "eq",
                        "value": [{"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": 0}],
                    },
                ]
            ],
            "query_configs": [
                {
                    "data_type_label": "event",
                    "data_source_label": "bk_monitor",
                    "result_table_id": "bk_monitor",
                    "metric_field": "ping-gse",
                    "metric_id": "bk_monitor.ping-gse",
                }
            ],
            "algorithms": [
                {
                    "config": "",
                    "level": 2,
                    "id": 1,
                    "type": "",
                }
            ],
            "query_md5": "",
        }
    ],
    "actions": [
        {
            "type": "notice",
            "config": {
                "alarm_interval": 1440,
                "alarm_end_time": "23:59:00",
                "alarm_start_time": "00:00:00",
                "send_recovery_alarm": False,
            },
            "id": 1,
            "notice_template": {
                "anomaly_template": "",
                "recovery_template": "",
                "action_id": 1,
                "create_time": 1591255486,
                "update_time": 1591255496,
            },
            "notice_group_list": [
                {
                    "notice_receiver": ["group#operator", "group#bk_bak_operator"],
                    "name": "主备负责人",
                    "webhook_url": "",
                    "notice_way": {"1": ["mail"], "2": ["mail"], "3": ["mail"]},
                    "message": "",
                    "id": 1,
                    "create_time": 1587992787,
                    "update_time": 1588689950,
                    "notice_group_id": 1,
                    "notice_group_name": "主备负责人",
                }
            ],
        }
    ],
    "detects": [
        {
            "level": 2,
            "expression": "",
            "connector": "and",
            "trigger_config": {"count": 1, "check_window": 5},
            "recovery_config": {"check_window": 5},
        }
    ],
}

STRATEGY_CONFIG_V3 = {
    "id": 1,
    "type": "monitor",
    "bk_biz_id": 2,
    "scenario": "os",
    "name": "测试新策略123",
    "labels": [],
    "is_enabled": True,
    "items": [
        {
            "query_configs": [
                {
                    "metric_field": "load5",
                    "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
                    "unit_conversion": 1.0,
                    "id": 2,
                    "agg_method": "AVG",
                    "agg_condition": [],
                    "agg_interval": 60,
                    "result_table_id": "system.cpu_load",
                    "unit": "%",
                    "data_source_label": "bk_monitor",
                    "data_type_label": "time_series",
                    "metric_id": "system.cpu_detail.idle",
                }
            ],
            "algorithms": [
                {
                    "config": [{"threshold": 12.0, "method": "gte"}],
                    "level": 1,
                    "type": "Threshold",
                    "id": 1,
                },
                {
                    "config": [{"threshold": 12.0, "method": "gte"}],
                    "level": 2,
                    "type": "Threshold",
                    "id": 2,
                },
                {
                    "config": [{"threshold": 12.0, "method": "gte"}],
                    "level": 3,
                    "type": "Threshold",
                    "id": 3,
                },
            ],
            "name": "\\u7a7a\\u95f2\\u7387",
            "no_data_config": {"is_enabled": False, "continuous": 5},
            "id": 1,
            "create_time": 1569044491,
            "update_time": 1569044491,
        }
    ],
    "detects": [
        {
            "level": 1,
            "expression": "",
            "trigger_config": {"count": 3, "check_window": 5},
            "recovery_config": {"check_window": 5},
            "connector": "and",
        },
        {
            "level": 2,
            "expression": "",
            "trigger_config": {"count": 2, "check_window": 5},
            "recovery_config": {"check_window": 5},
            "connector": "and",
        },
        {
            "level": 3,
            "expression": "",
            "trigger_config": {"count": 1, "check_window": 5},
            "recovery_config": {"check_window": 5},
            "connector": "and",
        },
    ],
    "notice": {  # 通知设置
        "id": 1,
        "config_id": 55555,  # 套餐ID，如果不选套餐请置为0
        "user_groups": [1],  # 告警组ID
        "signal": ["abnormal", "recovered"],
        # 触发信号，abnormal-异常，recovered-恢复，closed-关闭，execute-执行动作时, execute_success-执行成功, execute_failed-执行失败
        "options": {
            "converge_config": {
                "is_enabled": True,
                "converge_func": "collect",
                "timedelta": 60,
                "count": 1,
                "condition": [
                    {"dimension": "strategy_id", "value": ["self"]},
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
            "noise_reduce_config": {
                "is_enabled": True,
                "dimensions": ["bk_target_ip", "bk_target_cloud_id"],
                "count": 1,
            },
            "start_time": "00:00:00",
            "end_time": "23:59:59",
        },
        "config": {
            "interval_notify_mode": "standard",  # 间隔模式
            "notify_interval": 7200,  # 通知间隔
            "template": [  # 通知模板配置
                {
                    "signal": "abnormal",
                }
            ],
        },
    },
    "actions": [],
}

USER_GROUP_DATA = {
    "id": 1,
    "name": "蓝鲸业务的告警组-全职通知组",
    "desc": "用户组的说明用户组的说明用户组的说明用户组的说明用户组的说明",
    "bk_biz_id": 2,
    "need_duty": False,
    "alert_notice": [  # 告警通知配置
        {
            "time_range": "00:00:00--23:59:59",  # 生效时间段
            "notify_config": [  # 通知方式配置
                {
                    "level": 3,  # 级别
                    "type": [  # 通知渠道列表
                        "weixin",
                    ],
                },
                {"level": 2, "type": ["mail"]},
                {
                    "level": 1,
                    "type": ["voice", "wxwork-bot"],
                    "chatid": "hihihihihh;hihihiashihi",
                },
            ],
        }
    ],
    "action_notice": [  # 执行通知配置
        {
            "time_range": "00:00:00--23:59:59",  # 生效时间段
            "notify_config": [  # 通知方式
                {"phase": 3, "type": ["mail", "weixin", "voice"]},  # 执行阶段，3-执行前，2-成功时，1-失败时
                {"phase": 2, "type": ["mail", "weixin", "voice"]},
                {
                    "phase": 1,
                    "type": ["mail", "weixin", "voice", "wxwork-bot"],
                    "chatid": "hihihihihh;hihihiashihi",
                },
            ],
        }
    ],
}

USER_GROUP_WXBOT_DATA = {
    "id": 1,
    "name": "蓝鲸业务的告警组-仅限机器人",
    "desc": "用户组的说明用户组的说明用户组的说明用户组的说明用户组的说明",
    "bk_biz_id": 2,
    "need_duty": False,
    "alert_notice": [  # 告警通知配置
        {
            "time_range": "00:00:00--23:59:59",  # 生效时间段
            "notify_config": [  # 通知方式配置
                {
                    "level": 3,  # 级别
                    "type": [  # 通知渠道列表
                        "wxwork-bot",
                    ],
                    "chatid": "hihihihihh;hihihiashihi",
                },
                {
                    "level": 2,
                    "type": ["wxwork-bot"],
                    "chatid": "hihihihihh;hihihiashihi",
                },
                {
                    "level": 1,
                    "type": ["voice", "wxwork-bot"],
                    "chatid": "hihihihihh;hihihiashihi",
                },
            ],
        }
    ],
    "action_notice": [  # 执行通知配置
        {
            "time_range": "00:00:00--23:59:59",  # 生效时间段
            "notify_config": [  # 通知方式
                {
                    "phase": 3,
                    "type": ["wxwork-bot"],
                    "chatid": "hihihihihh;hihihiashihi",
                },  # 执行阶段，3-执行前，2-成功时，1-失败时
                {
                    "phase": 2,
                    "type": ["wxwork-bot"],
                    "chatid": "hihihihihh;hihihiashihi",
                },
                {
                    "phase": 1,
                    "type": ["wxwork-bot"],
                    "chatid": "hihihihihh;hihihiashihi",
                },
            ],
        }
    ],
}
