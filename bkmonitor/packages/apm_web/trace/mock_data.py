API_VIEW_CONFIG_DATA = {
    "trace_config": {
        "fields": [
            {
                "name": "time",
                "alias": "数据上报时间",
                "type": "date",
                "is_searched": True,
                "is_dimensions": True,
                "is_option_enabled": False,
                "supported_operations": [
                    {"operator": "=", "label": "=", "placeholder": "请选择或直接输入，Enter分隔"},
                ],
            },
            {
                "name": "trace_id",
                "alias": "Trace ID",
                "type": "keyword",
                "is_searched": True,
                "is_dimensions": True,
                "is_option_enabled": False,
                "supported_operations": [
                    {"operator": "=", "label": "=", "placeholder": "请选择或直接输入，Enter分隔"},
                ],
            },
            {
                "name": "root_service_category",
                "alias": "调用类型",
                "type": "keyword",
                "is_searched": True,
                "is_dimensions": True,
                "is_option_enabled": True,
                "supported_operations": [
                    {"operator": "=", "label": "=", "placeholder": "请选择或直接输入，Enter分隔"},
                ],
            },
        ],
        "default_config": {
            "display_fields": [
                {"name": "trace_id"},
                {"name": "min_start_time"},
                {"name": "root_span_name"},
                {"name": "root_service"},
                {"name": "root_service_span_name"},
                {"name": "root_service_category"},
                {"name": "root_service_status_code"},
                {"name": "trace_duration"},
                {"name": "hierarchy_count"},
                {"name": "service_count"},
            ],
            "filter_setting": [
                {"name": "trace_duration"},
                {"name": "resource.service.name"},
                {"name": "span_name"},
            ],
        },
    },
    "span_config": {
        "fields": [
            {
                "name": "time",
                "alias": "数据上报时间",
                "type": "date",
                "is_searched": True,
                "is_dimensions": True,
                "is_option_enabled": True,
                "supported_operations": [
                    {"operator": "=", "label": "=", "placeholder": "请选择或直接输入，Enter分隔"},
                ],
            },
            {
                "name": "span_name",
                "alias": "接口名称",
                "type": "keyword",
                "is_searched": True,
                "is_dimensions": True,
                "is_option_enabled": True,
                "supported_operations": [
                    {"operator": "=", "label": "=", "placeholder": "请选择或直接输入，Enter分隔"},
                ],
            },
            {
                "name": "kind",
                "alias": "类型",
                "type": "integer",
                "is_searched": True,
                "is_dimensions": True,
                "is_option_enabled": True,
                "supported_operations": [
                    {"operator": "=", "label": "=", "placeholder": "请选择或直接输入，Enter分隔"},
                ],
            },
        ],
        "default_config": {
            "display_field": [
                {"name": "span_id"},
                {"name": "span_name"},
                {"name": "start__time"},
                {"name": "end_time"},
                {"name": "elapsed_time"},
                {"name": "status.code"},
                {"name": "kind"},
                {"name": "trace_id"},
            ],
            "filter_setting": [
                {"name": "elapsed_time"},
                {"name": "resource.service.name"},
                {"name": "span_name"},
            ],
        },
    },
}

API_FIELDS_OPTION_VALUE_DATA = {
    "resource.service.name": ["example.greeter", "test_service_name"],
    "span_name": ["/200"],
    "kind": [0, 1, 2, 3, 4, 5],
    "root_service_category": ["http", "rpc", "db", "messaging", "async_backend", "all", "other"],
}

API_TOPK_DATA = [
    {
        "distinct_count": 0,
        "field": "resource.service.name",
        "list": [{"value": "test_project", "alias": "test_project", "count": 121209, "proportions": 100}],
    }
]

API_INFO_DATA = [
    {
        "field": "start_time",
        "total_count": 5170088,
        "field_count": 5170088,
        "distinct_count": 5151798,
        "field_percent": 1,
        "value_analysis": {
            "max": 1742808209140534,
            "min": 1742455412965676,
            "avg": 1742611966626709.2,
            "median": 1742583930172003.8,
        },
    }
]

API_GRAPH_DATA = {
    "series": [
        {
            "legend_name": "test01",
            "data": [
                [1742973960000, 8],
                [1742974020000, 7],
                [1742974080000, 5],
                [1742974140000, 4],
                [1742974200000, 1],
                [1742974260000, 7],
                [1742974320000, 6],
                [1742974380000, 6],
                [1742974440000, 3],
                [1742974500000, 7],
            ],
        }
    ]
}
