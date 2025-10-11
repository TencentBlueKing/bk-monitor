"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.query_template.mock_data import CALLEE_SUCCESS_RATE_QUERY_TEMPLATE

CALLEE_SUCCESS_RATE_STRATEGY_TEMPLATE = {
    "id": 1,
    "bk_biz_id": 2,
    "app_name": "demo",
    "name": "[RPC] 被调成功率",
    "system": "RPC",
    "category": "RPC_CALLER",
    "is_enabled": True,
    "is_auto_apply": True,
    "labels": ["APM-APP(demo)", "APM-SERVICE(example)", "APM-SYSTEM(RPC)"],
    "query_template": CALLEE_SUCCESS_RATE_QUERY_TEMPLATE,
    "algorithms": [
        {"level": 2, "config": {"method": "lte", "threshold": 90}, "type": "Threshold"},
        {"level": 1, "config": {"method": "lte", "threshold": 99.9}, "type": "Threshold"},
    ],
    "detect": {
        "type": "default",
        "config": {"recovery_check_window": 5, "trigger_check_window": 5, "trigger_count": 3},
    },
    "user_group_list": [{"id": 1, "name": "应用创建者"}],
    "context": {"GROUP_BY": ["service_name", "callee_service", "callee_method"], "ALARM_THRESHOLD_VALUE": 500},
    "create_user": "admin",
    "create_time": "2025-08-04 17:43:26+0800",
    "update_user": "admin",
    "update_time": "2025-08-04 17:43:26+0800",
}

CALLEE_SUCCESS_RATE_STRATEGY_PREVIEW = {
    "id": 1,
    "name": "[RPC] 被调成功率",
    "system": "RPC",
    "category": "callee",
    "labels": CALLEE_SUCCESS_RATE_STRATEGY_TEMPLATE["labels"],
    "query_template": CALLEE_SUCCESS_RATE_QUERY_TEMPLATE,
    "algorithms": CALLEE_SUCCESS_RATE_STRATEGY_TEMPLATE["algorithms"],
    "detect": CALLEE_SUCCESS_RATE_STRATEGY_TEMPLATE["detect"],
    "user_group_list": CALLEE_SUCCESS_RATE_STRATEGY_TEMPLATE["user_group_list"],
    "context": {"GROUP_BY": ["service_name", "callee_service", "callee_method"], "ALARM_THRESHOLD_VALUE": 500},
}

STRATEGY_TEMPLATE_APPLY_LIST = [
    {
        "service_name": "example.greeter",
        "strategy_template_id": 1,
        "strategy": {"id": 1, "name": "[RPC] 被调成功率"},
    },
    {
        "service_name": "example.greeter1",
        "strategy_template_id": 1,
        "strategy": {"id": 2, "name": "[RPC] 被调成功率"},
    },
]

CHECK_STRATEGY_INSTANCE_LIST = [
    {
        "service_name": "example.greeter",
        "strategy_template_id": 1,
        "same_origin_strategy_template": None,
        "strategy": {"id": 1, "name": "[RPC] 被调成功率"},
        "has_diff": True,
        "has_been_applied": True,
    },
    {
        "service_name": "example.greeter",
        "strategy_template_id": 2,
        "same_origin_strategy_template": {"id": 1, "name": "[RPC] 被调成功率模板"},
        "strategy": None,
        "has_diff": True,
        "has_been_applied": False,
    },
    {
        "service_name": "example.greeter",
        "strategy_template_id": 2,
        "same_origin_strategy_template": None,
        "strategy": None,
        "has_diff": False,
        "has_been_applied": False,
    },
]

COMPARE_STRATEGY_INSTANCE = {
    "current": {"strategy_template_id": 1},
    "applied": {"strategy_template_id": 2, "strategy": {"id": 1, "name": "[RPC] 被调成功率"}},
    "diff": [
        {
            "field": "detect",
            "current": {
                "type": "default",
                "config": {"recovery_check_window": 5, "trigger_check_window": 5, "trigger_count": 5},
            },
            "applied": {
                "type": "default",
                "config": {"recovery_check_window": 5, "trigger_check_window": 5, "trigger_count": 3},
            },
        },
        {
            "field": "algorithms",
            "current": [{"level": 2, "config": {"method": "lte", "threshold": 80}, "type": "Threshold"}],
            "applied": [{"level": 1, "config": {"method": "lte", "threshold": 89.9}, "type": "Threshold"}],
        },
        {
            "field": "user_group_list",
            "current": [{"id": 1, "name": "应用创建者"}],
            "applied": [{"id": 2, "name": "内置组"}],
        },
        {
            "field": "variables",
            "current": [
                {
                    "name": "ALARM_THRESHOLD_VALUE",
                    "type": "CONSTANTS",
                    "alias": "[整数] 告警起算值",
                    "value": 10,
                    "description": "当前请求量大于「告警起算值」时才进行检测，可用于避免在请求量较小的情况下触发告警。",
                }
            ],
            "applied": [
                {
                    "name": "ALARM_THRESHOLD_VALUE",
                    "type": "CONSTANTS",
                    "alias": "[整数] 告警起算值",
                    "value": 500,
                    "description": "当前请求量大于「告警起算值」时才进行检测，可用于避免在请求量较小的情况下触发告警。",
                }
            ],
        },
    ],
}

STRATEGY_TEMPLATE_RELATION_ALERTS = [
    {
        "id": 1,
        "alert_number": 100,
        "strategies": [
            {"strategy_id": 1000, "alert_number": 50, "service_name": "example.greeter"},
            {"strategy_id": 2000, "alert_number": 50, "service_name": "example.greeter1"},
        ],
    }
]

STRATEGY_TEMPLATE_LIST = [
    {
        "id": 1,
        "name": "[调用分析] 主调平均耗时",
        "system": "RPC",
        "category": "RPC_CALLER",
        "type": "app",
        "is_enabled": True,
        "is_auto_apply": True,
        "algorithms": [
            {"level": 2, "config": {"method": "lte", "threshold": 1000}, "type": "Threshold"},
            {"level": 1, "config": {"method": "lte", "threshold": 3000}, "type": "Threshold"},
        ],
        "user_group_list": [{"id": 1, "name": "应用创建者"}],
        "applied_service_names": ["example.greeter1", "example.greeter"],
        "create_user": "admin",
        "create_time": "2025-08-04 17:43:26+0800",
        "update_user": "admin",
        "update_time": "2025-08-04 17:43:26+0800",
    },
    {
        "id": 2,
        "name": "[调用分析] 主调平均耗时",
        "system": "RPC",
        "category": "RPC_CALLER",
        "type": "inner",
        "is_enabled": True,
        "is_auto_apply": True,
        "algorithms": [
            {"level": 2, "config": {"method": "lte", "threshold": 1000}, "type": "Threshold"},
            {"level": 1, "config": {"method": "lte", "threshold": 3000}, "type": "Threshold"},
        ],
        "user_group_list": [{"id": 1, "name": "应用创建者"}],
        "applied_service_names": ["example.greeter1", "example.greeter"],
        "create_user": "admin",
        "create_time": "2025-08-04 17:43:26+0800",
        "update_user": "admin",
        "update_time": "2025-08-04 17:43:26+0800",
    },
]

STRATEGY_TEMPLATE_OPTION_VALUES = {
    "system": [
        {"value": "RPC", "alias": "调用分析"},
        {"value": "K8S", "alias": "容器"},
        {"value": "METRIC", "alias": "自定义指标"},
        {"value": "LOG", "alias": "日志"},
        {"value": "TRACE", "alias": "调用链"},
        {"value": "EVENT", "alias": "事件"},
    ],
    "user_group_list": [{"value": 1, "alias": "应用创建者"}],
}
