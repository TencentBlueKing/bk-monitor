AvgDurationQueryTemplateDetail = {
    "id": 1,
    "name": "平均耗时",
    "query_configs": [
        {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "table": "2_bkapm_metric_tilapia.__default__",
            "metrics": [{"field": "rpc_server_handled_seconds_sum", "method": "${METHOD}", "alias": "a"}],
            "group_by": ["${GROUP_BY}"],
            "where": ["${CONDITIONS}", {"key": "service_name", "method": "eq", "value": ["example.greeter"]}],
            "interval": 60,
            "interval_unit": "s",
            "time_field": None,
            "functions": ["${FUNCTIONS}"],
        },
        {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "table": "2_bkapm_metric_tilapia.__default__",
            "metrics": [{"field": "rpc_server_handled_seconds_count", "method": "${METHOD}", "alias": "b"}],
            "where": ["${CONDITIONS}", {"key": "service_name", "method": "eq", "value": ["example.greeter"]}],
            "group_by": ["${GROUP_BY}"],
            "interval": 60,
            "interval_unit": "s",
            "time_field": None,
            "functions": ["${FUNCTIONS}"],
        },
    ],
    "expression": "a / b",
    "functions": [],
    "variables": [
        {
            "name": "METHOD",
            "type": "METHOD",
            "alias": "汇聚变量",
            "config": {"default": "SUM"},
            "description": "汇聚方法用于对监控数据进行汇聚。",
        },
        {
            "name": "GROUP_BY",
            "type": "GROUP_BY",
            "alias": "聚合维度",
            "config": {
                "default": [],
                "related_metrics": [
                    {
                        "metric_id": "custom.2_bkapm_metric_tilapia.__default__.rpc_server_handled_seconds_sum",
                        "metric_field": "rpc_server_handled_seconds_sum",
                    },
                    {
                        "metric_id": "custom.2_bkapm_metric_tilapia.__default__.rpc_server_handled_seconds_count",
                        "metric_field": "rpc_server_handled_seconds_count",
                    },
                ],
            },
            "description": "聚合维度是在监控数据中对数据进行分组的依据。",
        },
        {
            "name": "CONDITIONS",
            "type": "CONDITIONS",
            "alias": "过滤条件",
            "config": {
                "default": [{"key": "rpc_system", "method": "eq", "value": ["trpc"]}],
                "related_metrics": [
                    {
                        "metric_id": "custom.2_bkapm_metric_tilapia.__default__.rpc_server_handled_seconds_sum",
                        "metric_field": "rpc_server_handled_seconds_sum",
                    },
                    {
                        "metric_id": "custom.2_bkapm_metric_tilapia.__default__.rpc_server_handled_seconds_count",
                        "metric_field": "rpc_server_handled_seconds_count",
                    },
                ],
                "options": ["callee_service", "callee_method"],
            },
            "description": "过滤条件用于筛选出所需的监控数据。",
        },
        {
            "name": "FUNCTIONS",
            "type": "FUNCTIONS",
            "alias": "函数",
            "config": {
                "default": [{"id": "increase", "params": [{"id": "window", "value": "1m"}]}],
            },
            "description": "函数用于对监控数据进行计算处理。",
        },
    ],
}

RPCCalleeQueryTemplateDetail = {
    "id": 2,
    "name": "[RPC] 被调成功率（%）",
    "query_configs": [
        {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "metrics": [{"field": "rpc_server_handled_total", "method": "SUM", "alias": "a"}],
            "table": "2_bkapm_metric_tilapia.__default__",
            "data_label": "bkapm_tilapia",
            "group_by": ["${GROUP_BY}"],
            "where": [
                "${CONDITIONS}",
                {"condition": "and", "key": "code_type", "method": "eq", "value": ["${status}"]},
            ],
            "interval": 60,
            "interval_unit": "s",
            "time_field": None,
            "functions": ["${FUNCTIONS}"],
        },
        {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "metrics": [{"field": "rpc_server_handled_total", "method": "${METHOD}", "alias": "b"}],
            "table": "2_bkapm_metric_tilapia.__default__",
            "where": ["${CONDITIONS}"],
            "group_by": ["${GROUP_BY}"],
            "interval": 60,
            "interval_unit": "s",
            "time_field": None,
            "functions": ["${FUNCTIONS}"],
        },
    ],
    "expression": "(a or b < bool 0) / (b > ${ALARM_THRESHOLD_VALUE}) * 100",
    "functions": [],
    "variables": [
        {
            "name": "METHOD",
            "type": "METHOD",
            "alias": "汇聚方法变量",
            "config": {
                "default": "SUM",
            },
            "description": "汇聚方法用于对监控数据进行汇聚。",
        },
        {
            "name": "GROUP_BY",
            "type": "GROUP_BY",
            "alias": "聚合维度",
            "config": {
                "default": ["service_name", "callee_method"],
                "related_metrics": [
                    {
                        "metric_id": "custom.2_bkapm_metric_tilapia.__default__.rpc_server_handled_total",
                        "metric_field": "rpc_server_handled_total",
                    }
                ],
            },
            "description": "聚合维度是在监控数据中对数据进行分组的依据。",
        },
        {
            "name": "status",
            "type": "TAG_VALUES",
            "alias": "维度值变量",
            "config": {"default": ["success"], "related_tag": ["code_type"], "options": []},
            "description": "维度值是在监控数据中对数据进行分组的依据。",
        },
        {
            "name": "CONDITIONS",
            "type": "CONDITIONS",
            "alias": "过滤条件",
            "config": {
                "default": [{"key": "rpc_system", "method": "eq", "value": ["trpc"]}],
                "related_metrics": [
                    {
                        "metric_id": "custom.2_bkapm_metric_tilapia.__default__.rpc_server_handled_total",
                        "metric_field": "rpc_server_handled_total",
                    }
                ],
                "options": ["callee_service", "callee_method"],
            },
            "description": "过滤条件用于筛选出所需的监控数据。",
        },
        {
            "name": "FUNCTIONS",
            "type": "FUNCTIONS",
            "alias": "函数",
            "config": {
                "default": [{"id": "increase", "params": [{"id": "window", "value": "1m"}]}],
            },
            "description": "过滤条件用于筛选出所需的监控数据。",
        },
        {
            "name": "ALARM_THRESHOLD_VALUE",
            "type": "CONSTANTS",
            "data_type": "INTEGER",
            "alias": "告警起算值",
            "config": {
                "default": 500,
            },
            "description": "请根据实际业务情况进行调整。",
        },
    ],
}

QueryTemplateList = [
    {
        "id": 1,
        "name": "[RPC] 被调成功率（%）",
        "description": "模板说明",
        "create_user": "admin",
        "create_time": "2025-08-04 17:43:26+0800",
        "update_user": "admin",
        "update_time": "2025-08-04 17:43:26+0800",
    },
    {
        "id": 2,
        "name": "[RPC] 被调成功率（%）真实数据",
        "description": "模板演示数据",
        "create_user": "admin",
        "create_time": "2025-08-04 17:43:26+0800",
        "update_user": "admin",
        "update_time": "2025-08-04 17:43:26+0800",
    },
]

# 查询模板列表关联资源数量
QueryTemplateRelations = [
    {
        "query_template_id": 1,
        "relation_config_count": 2,
    },
    {
        "query_template_id": 2,
        "relation_config_count": 1,
    },
]

# 查询模板关联资源
AvgDurationQueryTemplateRelation = [
    {
        "url": "https://bkmonitor.paas3-dev.bktencent.com/?bizId=2#/strategy-config/detail/64923",
        "name": "资源名称1",
        "type": "ALERT_POLICY",
    },
    {
        "url": "https://bkmonitor.paas3-dev.bktencent.com/?bizId=2#/grafana/d/fxHySlGNz/00-jc-test",
        "name": "资源名称2",
        "type": "DASHBOARD",
    },
]

RPCCalleeQueryTemplateRelation = [
    {
        "url": "https://bkmonitor.paas3-dev.bktencent.com/?bizId=2#/strategy-config/detail/64924",
        "name": "资源名称",
        "type": "ALERT_POLICY",
    },
]


RPCCalleeQueryTemplatePreview = {
    "query_configs": [
        {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "metrics": [{"field": "rpc_server_handled_total", "method": "SUM", "alias": "a"}],
            "table": "2_bkapm_metric_tilapia.__default__",
            "data_label": "bkapm_tilapia",
            "group_by": ["service_name", "callee_method"],
            "where": [
                {"key": "rpc_system", "method": "eq", "value": ["trpc"]},
                {"condition": "and", "key": "code_type", "method": "eq", "value": ["success"]},
            ],
            "interval": 60,
            "interval_unit": "s",
            "time_field": None,
            "functions": [{"id": "increase", "params": [{"id": "window", "value": "1m"}]}],
        },
        {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "metrics": [{"field": "rpc_server_handled_total", "method": "SUM", "alias": "b"}],
            "table": "2_bkapm_metric_tilapia.__default__",
            "where": [
                {"key": "rpc_system", "method": "eq", "value": ["trpc"]},
            ],
            "group_by": ["service_name", "callee_method"],
            "interval": 60,
            "interval_unit": "s",
            "time_field": None,
            "functions": [{"id": "increase", "params": [{"id": "window", "value": "1m"}]}],
        },
    ],
    "expression": "(a or b < bool 0) / (b > 500) * 100",
    "functions": [],
}
