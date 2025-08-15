query_template_detail_by_id_1 = {
    "id": 1,
    "name": "[RPC] 被调成功率（%）",
    "query_configs": [
        {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "table": "",
            "metrics": [{"field": "rpc_server_handled_total", "method": "SUM", "alias": "a"}],
            "group_by": ["${GROUP_BY}"],
            "where": [
                "${CONDITIONS}",
                {"key": "code_type", "value": ["success", "${DIMENSION_VALUE}"], "method": "eq", "condition": "and"},
            ],
            "interval": 60,
            "time_field": "time",
            "functions": ["${FUNCTIONS}"],
        },
        {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "table": "",
            "metrics": [{"field": "rpc_server_handled_total", "method": "${METHOD}", "alias": "b"}],
            "where": ["${CONDITIONS}"],
            "group_by": ["${GROUP_BY}"],
            "interval": 60,
            "time_field": "time",
            "functions": ["${FUNCTIONS}"],
        },
    ],
    "expressions": "(a or b < bool 0) / (b > ${ALARM_THRESHOLD_VALUE}) * 100",
    "functions": [{"id": "topk", "params": [{"id": "k", "value": 5}]}],
    "variables": [
        # GROUP_BY - 维度
        # METHOD - 汇聚方法
        # DIMENSION_VALUE - 维度值
        # CONDITIONS - 条件
        # INTERVAL - 汇聚周期
        # FUNCTIONS - 函数
        # CONSTANTS - 常规变量
        {
            "name": "METHOD",
            "type": "METHOD",
            "alias": "汇聚变量",
            "default": "SUM",
            "description": "汇聚方法用于对监控数据进行汇聚。",
        },
        {
            "name": "GROUP_BY",
            "type": "GROUP_BY",
            "alias": "维度变量",
            "default": ["service", "endpoint"],
            "description": "聚合维度是在监控数据中对数据进行分组的依据。",
            "relation_value": {
                "metric_id": "bk_monitor.system.cpu_summary.usag",
                "name": "CPU使用率",
            },
            "allowed_values": ["service", "endpoint", "grpc_service", "grpc_method"],
        },
        {
            "name": "FUNCTIONS",
            "type": "FUNCTIONS",
            "alias": "函数变量",
            "default": [{"id": "increase", "params": [{"id": "window", "value": "1m"}]}],
            "description": "过滤条件用于筛选出所需的监控数据。",
        },
        {
            "name": "DIMENSION_VALUE",
            "type": "DIMENSION_VALUE",
            "alias": "维度值变量",
            "default": ["example.greeter", "SayHello"],
            "description": "维度值是在监控数据中对数据进行分组的依据。",
            "relation_value": {
                "name": "mount_point",
            },
        },
        {
            "name": "CONDITIONS",
            "type": "CONDITIONS",
            "alias": "条件变量",
            "default": [{"key": "service_name", "method": "eq", "value": ["example.greeter"]}],
            "description": "过滤条件用于筛选出所需的监控数据。",
            "relation_value": {
                "metric_id": "bk_monitor.system.cpu_summary.usag",
                "name": "CPU使用率",
            },
            "allowed_values": ["__all__"],
        },
        {
            "name": "ALARM_THRESHOLD_VALUE",
            "type": "CONSTANTS",
            "alias": "常规变量",
            "default": 0,
            "description": "请根据实际业务情况进行调整。",
            "data_type": "Integer",
        },
    ],
}


query_template_detail_by_id_2 = {
    "id": 2,
    "name": "[RPC] 被调成功率（%）真实数据",
    "query_configs": [
        {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "metrics": [{"field": "rpc_server_handled_total", "method": "SUM", "alias": "a"}],
            "table": "2_bkapm_metric_tilapia.__default__",
            "data_label": "bkapm_tilapia",
            "index_set_id": None,
            "group_by": [],
            "where": [
                "${CONDITIONS}",
                {"condition": "and", "key": "code_type", "method": "eq", "value": ["${status}"]},
            ],
            "interval": 60,
            "interval_unit": "s",
            "time_field": None,
            "filter_dict": {},
            "functions": [],
        },
        {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "metrics": [{"field": "rpc_server_handled_total", "method": "${METHOD}", "alias": "b"}],
            "table": "2_bkapm_metric_tilapia.__default__",
            "data_label": "bkapm_tilapia",
            "index_set_id": None,
            "group_by": ["${GROUP_BY}"],
            "where": ["${CONDITIONS}"],
            "interval": 60,
            "interval_unit": "s",
            "time_field": None,
            "filter_dict": {},
            "functions": ["${FUNCTIONS}"],
        },
    ],
    "expression": "((a or b < bool  0) /  b * 100) * ${weight_factor}",
    "functions": [],
    "alias": "c",
    "variables": [
        {
            "name": "METHOD",
            "type": "METHOD",
            "alias": "汇聚方法变量",
            "default": "SUM",
            "description": "汇聚方法用于对监控数据进行汇聚。",
        },
        {
            "name": "GROUP_BY",
            "type": "GROUP_BY",
            "alias": "维度变量",
            "default": [],
            "description": "聚合维度是在监控数据中对数据进行分组的依据。",
            "relation_value": {
                "metric_id": "custom.2_bkapm_metric_tilapia.__default__.rpc_server_handled_total",
                "name": "rpc_server_handled_total",
            },
            "allowed_values": ["__all__"],
        },
        {
            "name": "FUNCTIONS",
            "type": "FUNCTIONS",
            "alias": "函数变量",
            "default": [],
            "description": "过滤条件用于筛选出所需的监控数据。",
        },
        {
            "name": "status",
            "type": "DIMENSION_VALUE",
            "alias": "状态——维度值变量",
            "default": ["success"],
            "description": "维度值是在监控数据中对数据进行分组的依据。",
            "relation_value": {
                "name": "code_type",
            },
        },
        {
            "name": "CONDITIONS",
            "type": "CONDITIONS",
            "alias": "条件变量",
            "default": [{"key": "service_name", "method": "eq", "value": ["example.greeter"]}],
            "description": "选择一个期望的服务名称",
            "relation_value": {
                "metric_id": "custom.2_bkapm_metric_tilapia.__default__.rpc_server_handled_total",
                "name": "rpc_server_handled_total",
            },
            "allowed_values": ["__all__"],
        },
        {
            "name": "weight_factor",
            "type": "CONSTANTS",
            "alias": "加权系数——常规变量",
            "default": 1,
            "description": "请根据实际业务情况进行调整。",
            "data_type": "Integer",
        },
    ],
}


query_template_list = [
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
query_template_relations = [
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
query_template_relation_by_id_1 = [
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

query_template_relation_by_id_2 = [
    {
        "url": "https://bkmonitor.paas3-dev.bktencent.com/?bizId=2#/strategy-config/detail/64924",
        "name": "资源名称",
        "type": "ALERT_POLICY",
    },
]

query_template_preview_by_id_2 = {
    "id": 2,
    "name": "[RPC] 被调成功率（%）真实数据",
    "query_configs": [
        {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "metrics": [{"field": "rpc_server_handled_total", "method": "SUM", "alias": "a"}],
            "table": "2_bkapm_metric_tilapia.__default__",
            "data_label": "bkapm_tilapia",
            "index_set_id": None,
            "group_by": [],
            "where": [
                {"key": "service_name", "method": "eq", "value": ["example.greeter"]},
                {"condition": "and", "key": "code_type", "method": "eq", "value": ["success"]},
            ],
            "interval": 60,
            "interval_unit": "s",
            "time_field": None,
            "filter_dict": {},
            "functions": [],
        },
        {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "metrics": [{"field": "rpc_server_handled_total", "method": "SUM", "alias": "b"}],
            "table": "2_bkapm_metric_tilapia.__default__",
            "data_label": "bkapm_tilapia",
            "index_set_id": None,
            "group_by": [],
            "where": [{"key": "service_name", "method": "eq", "value": ["example.greeter"]}],
            "interval": 60,
            "interval_unit": "s",
            "time_field": None,
            "filter_dict": {},
            "functions": [],
        },
    ],
    "expression": "((a or b < bool  0) /  b * 100) * 1",
    "functions": [],
    "alias": "c",
}
