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
        "field": "resource.service.name",
        "distinct_count": 23,
        "list": [
            {"value": "test_project", "count": 527520, "proportions": 28.54},
            {"value": "test_project2", "count": 333130, "proportions": 18.02},
            {"value": "test_project3", "count": 252755, "proportions": 13.67},
            {"value": "test_project4", "count": 201368, "proportions": 10.89},
            {"value": "test_project5", "count": 157797, "proportions": 8.54},
        ],
    }
]

API_INFO_DATA = {
    "field": "elapsed_time",
    "total_count": 5170088,
    "field_count": 5170088,
    "distinct_count": 40,
    "field_percent": 100,
    "value_analysis": {
        "max": 80,
        "min": 1,
        "avg": 33,
        "median": 1,
    },
}

API_GRAPH_DATA = {
    "series": [
        {
            "dimensions": {"span_name": "promqlExecQueue"},
            "target": "COUNT(_index){span_name=build-metadata-query}",
            "metric_field": "_result_",
            "datapoints": [
                [4, 1744936200000],
                [3, 1744936260000],
                [9, 1744936320000],
                [7, 1744936380000],
                [5, 1744936440000],
                [0, 1744936500000],
            ],
            "alias": "_result_",
            "type": "bar",
            "dimensions_translation": {},
            "unit": "",
        },
        {
            "dimensions": {"span_name": "promqlExecQueue"},
            "target": "COUNT(_index){span_name=promqlExecQueue",
            "metric_field": "_result_",
            "datapoints": [
                [3, 1744936200000],
                [3, 1744936260000],
                [3, 1744936320000],
                [3, 1744936380000],
                [4, 1744936440000],
                [0, 1744936500000],
            ],
            "alias": "_result_",
            "type": "bar",
            "dimensions_translation": {},
            "unit": "",
        },
        {
            "dimensions": {"span_name": "SELECT"},
            "target": "COUNT(_index){span_name=SELECT}",
            "metric_field": "_result_",
            "datapoints": [
                [51, 1744936200000],
                [18, 1744936260000],
                [44, 1744936320000],
                [41, 1744936380000],
                [23, 1744936440000],
                [0, 1744936500000],
            ],
            "alias": "_result_",
            "type": "bar",
            "dimensions_translation": {},
            "unit": "",
        },
        {
            "dimensions": {"span_name": "promqlSort"},
            "target": "COUNT(_index){span_name=promqlSort}",
            "metric_field": "_result_",
            "datapoints": [
                [0, 1744936200000],
                [0, 1744936260000],
                [1, 1744936320000],
                [0, 1744936380000],
                [1, 1744936440000],
                [0, 1744936500000],
            ],
            "alias": "_result_",
            "type": "bar",
            "dimensions_translation": {},
            "unit": "",
        },
    ],
    "metrics": [],
}
