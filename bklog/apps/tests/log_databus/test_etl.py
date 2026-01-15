"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import copy
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase

from apps.exceptions import ValidationError
from apps.log_databus.constants import (
    ETL_DELIMITER_DELETE,
    ETL_DELIMITER_END,
    ETL_DELIMITER_IGNORE,
)
from apps.log_databus.handlers.etl import EtlHandler
from apps.log_databus.handlers.etl_storage import EtlStorage
from apps.log_databus.models import CollectorConfig
from apps.log_databus.serializers import CollectorEtlStorageSerializer
from apps.log_databus.utils.es_config import is_version_less_than
from apps.log_search.constants import (
    ISO_8601_TIME_FORMAT_NAME,
    FieldBuiltInEnum,
    FieldDateFormatEnum,
)
from apps.tests.utils import FakeRedis
from apps.utils.db import array_group

# 采集相关
COLLECTOR_CONFIG_ID = 1
BK_DATA_ID = 11
SUBSCRIPTION_ID = 12
TASK_ID = 13
COLLECTOR_CONFIG = {
    "collector_config_name": "采集项名称",
    "collector_scenario_id": "row",
    "bk_biz_id": 706,
    "category_id": "application",
    "target_object_type": "HOST",
    "target_node_type": "TOPO",
    "target_nodes": [
        {"id": 12},
        {"bk_inst_id": 33, "bk_obj_id": "module"},
        {"ip": "127.0.0.1", "bk_cloud_id": 0, "bk_supplier_id": 0},
    ],
    "target_subscription_diff": [],
    "description": "这是一个描述",
    "is_active": True,
    "subscription_id": SUBSCRIPTION_ID,
}

# 清洗相关
CLUSTER_INFO = {"cluster_config": {"version": "7.2"}}

TABLE_ID = "2_log.test_table"
ETL_CONFIG = "bk_log_text"
ETL_PARAMS = {}

ETL_CONFIG_JSON = "bk_log_json"
ETL_PARAMS_JSON = {"retain_original_text": True}

ETL_CONFIG_DELIMITER = "bk_log_delimiter"
ETL_PARAMS_DELIMITER = {"separator": "|", "retain_original_text": True}
ETL_DELIMITER_CONTENT = 'val1|{"key": "val"}||val4|other message'

# SDK只返回需要的字段
ETL_DELIMITER_PREVIEW_SDK = {
    "key1": "val1",
    "key2": '{"key": "val"}',
    "key3": "",
    "key4": "val4",
    "key5": "other message",
}
# 用户预览结果
ETL_DELIMITER_PREVIEW = []
for index, val in enumerate(ETL_DELIMITER_CONTENT.split("|")):
    ETL_DELIMITER_PREVIEW.append({"field_index": index + 1, "field_name": "", "value": val})

# 用户配置的字段信息
FIELDS_DELIMITER = [
    {
        "field_index": 1,
        "field_name": "key1",
        "field_type": "string",
        "alias_name": "",
        "is_time": False,
        "is_analyzed": False,
        "is_dimension": True,
        "is_delete": False,
    },
    {
        "field_index": 2,
        "field_name": "key2",
        "field_type": "object",
        "alias_name": "",
        "is_time": False,
        "is_analyzed": False,
        "is_dimension": True,
        "is_delete": False,
    },
    {
        "field_index": 5,
        "field_name": "",
        "field_type": "",
        "alias_name": "",
        "is_time": False,
        "is_analyzed": False,
        "is_dimension": True,
        "is_delete": True,
    },
]
# 根据FIELDS_DELIMITER需要生成的META.RT.separator_field_list
ETL_DELIMITER_META_FIELDS = [
    "key1",
    "key2",
    ETL_DELIMITER_IGNORE,
    ETL_DELIMITER_IGNORE,
    ETL_DELIMITER_DELETE,
    ETL_DELIMITER_END,
]

# 给前端需要返回有配置或删除的字段
ETL_DELIMITER_RESULT = {
    1: {"field_name": "key1", "field_type": "string", "is_delete": False},
    2: {"field_name": "key2", "field_type": "object", "is_delete": False},
    5: {"field_name": "", "field_type": "", "is_delete": True},
}

# 正则
ETL_CONFIG_REGEXP = "bk_log_regexp"
ETL_PARAMS_REGEXP = {
    "separator_regexp": "(?P<request_ip>[\\d\\.]+)[^[]+\\[(?P<request_time>[^]]+)\\]",
    "retain_original_text": True,
}
ETL_REGEXP_CONTENT = '127.0.0.1 - - [30/Nov/2019:21:07:10 +0800] "GET /api/v3/object/statistics HTTP/1.0" "200"'
FIELDS_REGEXP = [
    {
        "field_name": "request_ip",
        "field_type": "string",
        "alias_name": "",
        "is_time": False,
        "is_analyzed": False,
        "is_dimension": True,
        "is_delete": False,
    },
    {
        "field_name": "request_time",
        "field_type": "string",
        "alias_name": "",
        "is_time": True,
        "is_analyzed": False,
        "is_dimension": True,
        "is_delete": False,
        "option": {"time_zone": 8, "time_format": "dd/MMM/yyyy:HH:mm:ss Z"},
    },
]

TABLE_STR = "test_table"
STORAGE_CLUSTER_ID = 2
RETENTION_TIME = 30
ALLOCATION_MIN_DAYS = 7
HOT_WARM_CONFIG = {
    "is_enabled": True,
    "hot_attr_name": "temperature",
    "hot_attr_value": "hot",
    "warm_attr_name": "temperature",
    "warm_attr_value": "warm",
}
# 不可以与内置字段重复
FIELDS_ERROR_BUILT = [
    {
        "field_name": "ip",
        "field_type": "string",
        "alias_name": "",
        "is_time": False,
        "is_analyzed": False,
        "is_dimension": True,
        "is_delete": False,
    }
]

# 整形不可以分词
FIELDS_ERROR_ANALYZED = [
    {
        "field_name": "key1",
        "field_type": "int",
        "alias_name": "",
        "is_time": False,
        "is_analyzed": True,
        "is_dimension": False,
        "is_delete": False,
    }
]

# 时间格式与类型冲突
FIELDS_ERROR_TIME_FORMAT = [
    {
        "field_name": "key1",
        "field_type": "int",
        "alias_name": "",
        "is_time": True,
        "is_analyzed": False,
        "is_dimension": True,
        "is_delete": False,
        "option": {"time_zone": 0, "time_format": "yyyy-MM-DD hh:mm:ss"},
    }
]

# 时间字段不可分词
FIELDS_ERROR_TIME_ANALYZED = [
    {
        "field_name": "key1",
        "field_type": "string",
        "alias_name": "",
        "is_time": True,
        "is_analyzed": True,
        "is_dimension": True,
        "is_delete": False,
        "option": {"time_zone": 0, "format": "yyyy-MM-DD hh:mm:ss"},
    }
]

# 不存在有效字段
FIELDS_ERROR_INVALID = [
    {
        "field_name": "ip",
        "field_type": "string",
        "alias_name": "",
        "is_time": False,
        "is_analyzed": False,
        "is_dimension": True,
        "is_delete": True,
    }
]

# 分隔符未带field_index
FIELDS_INDEX_INVALID = [
    {
        "field_name": "ip",
        "field_type": "string",
        "alias_name": "",
        "is_time": False,
        "is_analyzed": False,
        "is_dimension": True,
        "is_delete": False,
    }
]

# 删除字段判断
FIELDS_DELETE = [
    {
        "field_name": "ip",
        "field_type": "string",
        "alias_name": "",
        "is_time": False,
        "is_analyzed": False,
        "is_dimension": True,
        "is_delete": True,
    },
    {
        "field_name": "key1",
        "field_type": "string",
        "alias_name": "",
        "is_time": False,
        "is_analyzed": False,
        "is_dimension": True,
        "is_delete": False,
    },
]

# ETL Preview 测试数据常量
# JSON格式测试数据
ETL_PREVIEW_JSON_DATA = (
    '{"ip": "127.0.0.1", "message": "test log", "level": "info", "timestamp": "2023-01-01T10:00:00Z"}'
)
ETL_PREVIEW_JSON_PARAMS = {"retain_original_text": True}
ETL_PREVIEW_JSON_EXPECTED = [
    {"field_name": "ip", "value": "127.0.0.1"},
    {"field_name": "message", "value": "test log"},
    {"field_name": "level", "value": "info"},
    {"field_name": "timestamp", "value": "2023-01-01T10:00:00Z"},
]

# 分隔符格式测试数据
ETL_PREVIEW_DELIMITER_DATA = "127.0.0.1|2023-01-01|test message|info|GET /api/test"
ETL_PREVIEW_DELIMITER_PARAMS = {"separator": "|", "retain_original_text": True}
ETL_PREVIEW_DELIMITER_EXPECTED = [
    {"field_index": 1, "field_name": "", "value": "127.0.0.1"},
    {"field_index": 2, "field_name": "", "value": "2023-01-01"},
    {"field_index": 3, "field_name": "", "value": "test message"},
    {"field_index": 4, "field_name": "", "value": "info"},
    {"field_index": 5, "field_name": "", "value": "GET /api/test"},
]

# 正则表达式格式测试数据
ETL_PREVIEW_REGEXP_DATA = '127.0.0.1 - - [30/Nov/2019:21:07:10 +0800] "GET /api/v3/object/statistics HTTP/1.0" "200"'
ETL_PREVIEW_REGEXP_PARAMS = {
    "separator_regexp": "(?P<request_ip>[\\d\\.]+)[^[]+\\[(?P<request_time>[^]]+)\\]",
    "retain_original_text": True,
}
ETL_PREVIEW_REGEXP_EXPECTED = [
    {"field_index": 1, "field_name": "request_ip", "value": "127.0.0.1"},
    {"field_index": 2, "field_name": "request_time", "value": "30/Nov/2019:21:07:10 +0800"},
]

# 复杂JSON测试数据
ETL_PREVIEW_JSON_COMPLEX_DATA = """
{
    "timestamp": "2023-01-01T10:00:00Z",
    "level": "info",
    "message": "User login",
    "user": {
        "id": 12345,
        "name": "test_user",
        "email": "test@example.com"
    },
    "request": {
        "method": "POST",
        "url": "/api/login",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
    },
    "response": {
        "status": 200,
        "duration": 150
    }
}
"""

# 复杂分隔符测试数据
ETL_PREVIEW_DELIMITER_COMPLEX_DATA = (
    '2023-01-01T10:00:00Z|INFO|User login|127.0.0.1|POST /api/login|200|150ms|{"user_id": 12345}'
)
ETL_PREVIEW_DELIMITER_COMPLEX_EXPECTED = [
    {"field_index": 1, "field_name": "", "value": "2023-01-01T10:00:00Z"},
    {"field_index": 2, "field_name": "", "value": "INFO"},
    {"field_index": 3, "field_name": "", "value": "User login"},
    {"field_index": 4, "field_name": "", "value": "127.0.0.1"},
    {"field_index": 5, "field_name": "", "value": "POST /api/login"},
    {"field_index": 6, "field_name": "", "value": "200"},
    {"field_index": 7, "field_name": "", "value": "150ms"},
    {"field_index": 8, "field_name": "", "value": '{"user_id": 12345}'},
]

# 复杂正则表达式测试数据
ETL_PREVIEW_REGEXP_COMPLEX_DATA = (
    '127.0.0.1 - test_user [30/Nov/2019:21:07:10 +0800] "POST /api/v3/object/statistics HTTP/1.0" 200 150'
)
ETL_PREVIEW_REGEXP_COMPLEX_PARAMS = {
    "separator_regexp": '(?P<ip>[\\d\\.]+)\\s+(?P<user>\\S+)\\s+\\[(?P<timestamp>[^]]+)\\]\\s+"(?P<method>\\S+)\\s+(?P<path>\\S+)\\s+(?P<protocol>\\S+)"\\s+(?P<status>\\d+)\\s+(?P<duration>\\d+)',
    "retain_original_text": True,
}
ETL_PREVIEW_REGEXP_COMPLEX_EXPECTED = [
    {"field_index": 1, "field_name": "ip", "value": "127.0.0.1"},
    {"field_index": 2, "field_name": "user", "value": "test_user"},
    {"field_index": 3, "field_name": "timestamp", "value": "30/Nov/2019:21:07:10 +0800"},
    {"field_index": 4, "field_name": "method", "value": "POST"},
    {"field_index": 5, "field_name": "path", "value": "/api/v3/object/statistics"},
    {"field_index": 6, "field_name": "protocol", "value": "HTTP/1.0"},
    {"field_index": 7, "field_name": "status", "value": "200"},
    {"field_index": 8, "field_name": "duration", "value": "150"},
]

# V4版本ETL Preview测试数据常量
# V4版本分隔符清洗测试数据
ETL_PREVIEW_V4_DELIMITER_INPUT = "Oct 20 21:18:01 VM-152-229-centos systemd: Started Session 823716 of user root."
ETL_PREVIEW_V4_DELIMITER_PARAMS = {"separator": " ", "retain_original_text": True}
ETL_PREVIEW_V4_DELIMITER_API_REQUEST = {
    "input": ETL_PREVIEW_V4_DELIMITER_INPUT,
    "rules": [
        {
            "input_id": "__raw_data",
            "output_id": "bk_separator_object",
            "operator": {"type": "split_str", "delimiter": " ", "max_parts": None},
        }
    ],
    "filter_rules": [],
}
ETL_PREVIEW_V4_DELIMITER_API_RESPONSE = {
    "rules_output": [
        {
            "value": [
                "Oct",
                "20",
                "21:18:01",
                "VM-152-229-centos",
                "systemd:",
                "Started",
                "Session",
                "823716",
                "of",
                "user",
                "root.",
            ]
        }
    ]
}
ETL_PREVIEW_V4_DELIMITER_EXPECTED = [
    {"field_index": 1, "field_name": "", "value": "Oct"},
    {"field_index": 2, "field_name": "", "value": "20"},
    {"field_index": 3, "field_name": "", "value": "21:18:01"},
    {"field_index": 4, "field_name": "", "value": "VM-152-229-centos"},
    {"field_index": 5, "field_name": "", "value": "systemd:"},
    {"field_index": 6, "field_name": "", "value": "Started"},
    {"field_index": 7, "field_name": "", "value": "Session"},
    {"field_index": 8, "field_name": "", "value": "823716"},
    {"field_index": 9, "field_name": "", "value": "of"},
    {"field_index": 10, "field_name": "", "value": "user"},
    {"field_index": 11, "field_name": "", "value": "root."},
]

# V4版本JSON清洗测试数据
ETL_PREVIEW_V4_JSON_INPUT = (
    '{"ip": "127.0.0.1", "message": "test log", "level": "info", "timestamp": "2023-01-01T10:00:00Z"}'
)
ETL_PREVIEW_V4_JSON_PARAMS = {"retain_original_text": True}
ETL_PREVIEW_V4_JSON_API_REQUEST = {
    "input": ETL_PREVIEW_V4_JSON_INPUT,
    "rules": [{"input_id": "__raw_data", "output_id": "bk_separator_object", "operator": {"type": "json_de"}}],
    "filter_rules": [],
}
ETL_PREVIEW_V4_JSON_API_RESPONSE = {
    "rules_output": [
        {
            "value": {"ip": "127.0.0.1", "message": "test log", "level": "info", "timestamp": "2023-01-01T10:00:00Z"},
            "key_index": [
                {"type": "key", "value": "ip", "field_type": "string"},
                {"type": "key", "value": "message", "field_type": "string"},
                {"type": "key", "value": "level", "field_type": "string"},
                {"type": "key", "value": "timestamp", "field_type": "string"},
            ],
        }
    ]
}
ETL_PREVIEW_V4_JSON_EXPECTED = [
    {"field_name": "ip", "value": "127.0.0.1"},
    {"field_name": "message", "value": "test log"},
    {"field_name": "level", "value": "info"},
    {"field_name": "timestamp", "value": "2023-01-01T10:00:00Z"},
]

# V4版本正则表达式清洗测试数据
ETL_PREVIEW_V4_REGEXP_INPUT = '192.168.1.1 [25/Oct/2023:10:30:45 +0800] "GET /api/test HTTP/1.1" - status:200 user:admin up_status:ok ms:150 up:192.168.1.2 rs:1 rid:req-123 realip:192.168.1.3 host:example.com region:us-west service:api agent:Mozilla/5.0 up_stream:backend upstream_response_time:0.150 refer:https://example.com http_x_forwarded_for:192.168.1.4 original_host:api.example.com project_id:12345 tag:prod'
ETL_PREVIEW_V4_REGEXP_PARAMS = {
    "separator_regexp": '(?P<remote_addr>\\d+\\.\\d+\\.\\d+\\.\\d+) \\[(?P<logdate>[\\s\\S]+)\\] "(?P<request_method>[\\S]+) (?P<request_uri>[\\S]+) (?P<request_version>.*)" - status\\:(?P<status>\\d+) user:(?P<user>.*) up_status:(?P<up_status>.*) ms:(?P<ms>\\d+) up:(?P<up>.*) rs:(?P<rs>\\d+) rid:(?P<rid>.*) realip:(?P<realip>.*) host:(?P<host>.*) region:(?P<region>.*) service:(?P<service>.*) agent:(?P<agent>.*) up_stream:(?P<up_stream>.*)upstream_response_time:(?P<upstream_response_time>.*?) refer:(?P<refer>.*) http_x_forwarded_for:(?P<http_x_forwarded_for>.*) original_host:(?P<original_host>.*) project_id:(?P<project_id>.*) tag:(?P<route_tag>.*)',
    "retain_original_text": True,
}
ETL_PREVIEW_V4_REGEXP_API_REQUEST = {
    "input": ETL_PREVIEW_V4_REGEXP_INPUT,
    "rules": [
        {
            "input_id": "__raw_data",
            "output_id": "bk_separator_object",
            "operator": {
                "type": "regex",
                "regex": '(?P<remote_addr>\\d+\\.\\d+\\.\\d+\\.\\d+) \\[(?P<logdate>[\\s\\S]+)\\] "(?P<request_method>[\\S]+) (?P<request_uri>[\\S]+) (?P<request_version>.*)" - status\\:(?P<status>\\d+) user:(?P<user>.*) up_status:(?P<up_status>.*) ms:(?P<ms>\\d+) up:(?P<up>.*) rs:(?P<rs>\\d+) rid:(?P<rid>.*) realip:(?P<realip>.*) host:(?P<host>.*) region:(?P<region>.*) service:(?P<service>.*) agent:(?P<agent>.*) up_stream:(?P<up_stream>.*)upstream_response_time:(?P<upstream_response_time>.*?) refer:(?P<refer>.*) http_x_forwarded_for:(?P<http_x_forwarded_for>.*) original_host:(?P<original_host>.*) project_id:(?P<project_id>.*) tag:(?P<route_tag>.*)',
            },
        }
    ],
    "filter_rules": [],
}
ETL_PREVIEW_V4_REGEXP_API_RESPONSE = {
    "rules_output": [
        {
            "value": {
                "remote_addr": "192.168.1.1",
                "logdate": "25/Oct/2023:10:30:45 +0800",
                "request_method": "GET",
                "request_uri": "/api/test",
                "request_version": "HTTP/1.1",
                "status": "200",
                "user": "admin",
                "up_status": "ok",
                "ms": "150",
                "up": "192.168.1.2",
                "rs": "1",
                "rid": "req-123",
                "realip": "192.168.1.3",
                "host": "example.com",
                "region": "us-west",
                "service": "api",
                "agent": "Mozilla/5.0",
                "up_stream": "backend",
                "upstream_response_time": "0.150",
                "refer": "https://example.com",
                "http_x_forwarded_for": "192.168.1.4",
                "original_host": "api.example.com",
                "project_id": "12345",
                "route_tag": "prod",
            },
            "key_index": [
                {"type": "key", "value": "remote_addr", "field_type": "string"},
                {"type": "key", "value": "logdate", "field_type": "string"},
                {"type": "key", "value": "request_method", "field_type": "string"},
                {"type": "key", "value": "request_uri", "field_type": "string"},
                {"type": "key", "value": "request_version", "field_type": "string"},
                {"type": "key", "value": "status", "field_type": "string"},
                {"type": "key", "value": "user", "field_type": "string"},
                {"type": "key", "value": "up_status", "field_type": "string"},
                {"type": "key", "value": "ms", "field_type": "string"},
                {"type": "key", "value": "up", "field_type": "string"},
                {"type": "key", "value": "rs", "field_type": "string"},
                {"type": "key", "value": "rid", "field_type": "string"},
                {"type": "key", "value": "realip", "field_type": "string"},
                {"type": "key", "value": "host", "field_type": "string"},
                {"type": "key", "value": "region", "field_type": "string"},
                {"type": "key", "value": "service", "field_type": "string"},
                {"type": "key", "value": "agent", "field_type": "string"},
                {"type": "key", "value": "up_stream", "field_type": "string"},
                {"type": "key", "value": "upstream_response_time", "field_type": "string"},
                {"type": "key", "value": "refer", "field_type": "string"},
                {"type": "key", "value": "http_x_forwarded_for", "field_type": "string"},
                {"type": "key", "value": "original_host", "field_type": "string"},
                {"type": "key", "value": "project_id", "field_type": "string"},
                {"type": "key", "value": "route_tag", "field_type": "string"},
            ],
        }
    ]
}
ETL_PREVIEW_V4_REGEXP_EXPECTED = [
    {"field_index": 1, "field_name": "remote_addr", "value": "192.168.1.1"},
    {"field_index": 2, "field_name": "logdate", "value": "25/Oct/2023:10:30:45 +0800"},
    {"field_index": 3, "field_name": "request_method", "value": "GET"},
    {"field_index": 4, "field_name": "request_uri", "value": "/api/test"},
    {"field_index": 5, "field_name": "request_version", "value": "HTTP/1.1"},
    {"field_index": 6, "field_name": "status", "value": "200"},
    {"field_index": 7, "field_name": "user", "value": "admin"},
    {"field_index": 8, "field_name": "up_status", "value": "ok"},
    {"field_index": 9, "field_name": "ms", "value": "150"},
    {"field_index": 10, "field_name": "up", "value": "192.168.1.2"},
    {"field_index": 11, "field_name": "rs", "value": "1"},
    {"field_index": 12, "field_name": "rid", "value": "req-123"},
    {"field_index": 13, "field_name": "realip", "value": "192.168.1.3"},
    {"field_index": 14, "field_name": "host", "value": "example.com"},
    {"field_index": 15, "field_name": "region", "value": "us-west"},
    {"field_index": 16, "field_name": "service", "value": "api"},
    {"field_index": 17, "field_name": "agent", "value": "Mozilla/5.0"},
    {"field_index": 18, "field_name": "up_stream", "value": "backend"},
    {"field_index": 19, "field_name": "upstream_response_time", "value": "0.150"},
    {"field_index": 20, "field_name": "refer", "value": "https://example.com"},
    {"field_index": 21, "field_name": "http_x_forwarded_for", "value": "192.168.1.4"},
    {"field_index": 22, "field_name": "original_host", "value": "api.example.com"},
    {"field_index": 23, "field_name": "project_id", "value": "12345"},
    {"field_index": 24, "field_name": "route_tag", "value": "prod"},
]

# 正常字段清洗
FIELDS = [
    {
        "field_name": "ip",
        "field_type": "string",
        "alias_name": "key1",
        "is_time": False,
        "is_analyzed": False,
        "is_dimension": False,
        "is_delete": False,
    },
    {
        "field_name": "key2",
        "field_type": "string",
        "alias_name": "",
        "is_time": False,
        "is_analyzed": True,
        "is_dimension": False,
        "is_delete": False,
    },
    {
        "field_name": "key3",
        "field_type": "int",
        "alias_name": "",
        "is_time": False,
        "is_analyzed": False,
        "is_dimension": True,
        "is_delete": False,
    },
    {
        "field_name": "time1",
        "field_type": "string",
        "alias_name": "",
        "is_time": True,
        "is_analyzed": False,
        "is_dimension": True,
        "is_delete": False,
        "option": {"time_zone": 0, "time_format": "yyyy-MM-DD hh:mm:ss"},
    },
    {
        "field_name": "delete1",
        "field_type": "int",
        "alias_name": "",
        "is_time": False,
        "is_analyzed": False,
        "is_dimension": True,
        "is_delete": True,
    },
]
# 时间字段的来源直接设为非维度
FIELDS_NOT_ES_DOC_VALUES_KEYS = ["key1", "time1"]
FIELDS_TIME_FIELD_ALIAS_NAME = "time1"
FIELDS_VALID_NUM = 4
FIELDS_TIME_FIELD_OPTION = {
    "time_zone": 0,
    "format": "yyyy-MM-DD hh:mm:ss",
    "real_path": f"{EtlStorage.separator_node_name}.time1",
}

VIEW_ROLES = [1]
ETL_PARAMS = {
    "table_id": TABLE_ID,
    "etl_config": ETL_CONFIG,
    "etl_params": ETL_PARAMS,
    "fields": FIELDS,
    "storage_cluster_id": STORAGE_CLUSTER_ID,
    "retention": RETENTION_TIME,
    "view_roles": VIEW_ROLES,
}
LOG_INDEX_DATA = {
    "index_set_name": "索引集名称",
    "project_id": 111,
    "source_id": 2,
    "scenario_id": "es",
    "view_roles": [2],
    "bkdata_project_id": 11,
}


class TestEtl(TestCase):
    def test_etl_time(self):
        formsts = FieldDateFormatEnum.get_choices_list_dict()
        for format in formsts:
            if format["id"] in [ISO_8601_TIME_FORMAT_NAME, "strict_date_time"]:
                # arrow1.3.0解析rfc3339格式异常,这里跳过
                continue
            try:
                etl_handler = EtlHandler.get_instance()
                etl_time = etl_handler.etl_time(format["id"], 8, format["description"])
            except Exception as e:  # pylint: disable=broad-except
                etl_time = {"epoch_millis": "exception:" + str(e)}
            print(f"[{format['id']}][{format['name']}] {format['description']} => {etl_time}")
            self.assertEqual(etl_time["epoch_millis"], "1136185445000")

    def test_etl_param(self):
        etl_param = {
            "table_id": TABLE_ID,
            "etl_config": ETL_CONFIG_JSON,
            "etl_params": ETL_PARAMS_JSON,
            "fields": FIELDS,
            "storage_cluster_id": STORAGE_CLUSTER_ID,
            "retention": RETENTION_TIME,
            "view_roles": VIEW_ROLES,
            "allocation_min_days": 3,
        }

        with self.assertRaises(ValidationError):
            etl_param["fields"] = FIELDS_ERROR_BUILT
            CollectorEtlStorageSerializer(data=etl_param).is_valid(raise_exception=True)

        with self.assertRaises(ValidationError):
            etl_param["fields"] = FIELDS_ERROR_ANALYZED
            CollectorEtlStorageSerializer(data=etl_param).is_valid(raise_exception=True)

        with self.assertRaises(ValidationError):
            etl_param["fields"] = FIELDS_ERROR_TIME_FORMAT
            CollectorEtlStorageSerializer(data=etl_param).is_valid(raise_exception=True)

        with self.assertRaises(ValidationError):
            etl_param["fields"] = FIELDS_ERROR_TIME_ANALYZED
            CollectorEtlStorageSerializer(data=etl_param).is_valid(raise_exception=True)

        with self.assertRaises(ValidationError):
            etl_param["fields"] = FIELDS_ERROR_INVALID
            CollectorEtlStorageSerializer(data=etl_param).is_valid(raise_exception=True)

        with self.assertRaises(ValidationError):
            etl_param["etl_config"] = ETL_CONFIG_DELIMITER
            etl_param["fields"] = FIELDS_INDEX_INVALID
            CollectorEtlStorageSerializer(data=etl_param).is_valid(raise_exception=True)

        etl_param["etl_config"] = ETL_CONFIG_JSON
        etl_param["fields"] = FIELDS_DELETE
        CollectorEtlStorageSerializer(data=etl_param).is_valid(raise_exception=True)
        return True

    @patch("apps.api.TransferApi.create_result_table", lambda _: {"table_id": TABLE_ID})
    @patch("apps.api.TransferApi.modify_result_table", lambda _: {"table_id": TABLE_ID})
    @patch("apps.api.TransferApi.get_result_table", lambda _: {"table_id": TABLE_ID})
    @patch("apps.api.TransferApi.get_cluster_info", lambda _: [CLUSTER_INFO])
    @FakeRedis("apps.utils.cache.cache")
    @patch("apps.log_databus.handlers.etl.EtlHandler._update_or_create_index_set")
    @patch("apps.log_databus.tasks.collector.modify_result_table.delay", return_value=None)
    def test_bk_log_text(self, mock_modify_delay, mock_index_set):
        collector_config = CollectorConfig.objects.create(**COLLECTOR_CONFIG)
        mock_index_set.return_value = LOG_INDEX_DATA

        # 直接入库
        etl_storage = EtlStorage.get_instance(ETL_CONFIG)
        result = etl_storage.update_or_create_result_table(
            collector_config,
            table_id=TABLE_ID,
            storage_cluster_id=STORAGE_CLUSTER_ID,
            retention=RETENTION_TIME,
            allocation_min_days=ALLOCATION_MIN_DAYS,
            storage_replies=1,
            fields=FIELDS,
            etl_params=ETL_PARAMS,
            hot_warm_config=HOT_WARM_CONFIG,
        )
        doc_values_nums = [item for item in result["params"]["field_list"] if "es_doc_values" in item.get("option", {})]
        self.assertEqual(result["params"]["time_alias_name"], "utctime")
        self.assertEqual(len(doc_values_nums), 0, "直接入库不需要设置任何doc_values")
        self.assertTrue(
            "es_doc_values" not in result["params"]["time_option"], "time_option必须设置且不可设置doc_values"
        )

        etl_config = etl_storage.parse_result_table_config(result["params"])
        self.assertIsInstance(etl_config["etl_params"]["es_unique_field_list"], list)
        self.assertEqual(etl_config["etl_params"]["separator_node_action"], "")
        return True

    @patch("apps.api.TransferApi.create_result_table", lambda _: {"table_id": TABLE_ID})
    @patch("apps.api.TransferApi.modify_result_table", lambda _: {"table_id": TABLE_ID})
    @patch("apps.api.TransferApi.get_result_table", lambda _: {"table_id": TABLE_ID})
    @patch("apps.api.TransferApi.get_cluster_info", lambda _: [CLUSTER_INFO])
    @FakeRedis("apps.utils.cache.cache")
    @patch("apps.log_databus.handlers.etl.EtlHandler._update_or_create_index_set")
    @patch("apps.log_databus.tasks.collector.modify_result_table.delay", return_value=None)
    def test_bk_log_json(self, mock_modify_delay, mock_index_set):
        """
        JSON清洗
        """
        collector_config = CollectorConfig.objects.create(**COLLECTOR_CONFIG)
        mock_index_set.return_value = LOG_INDEX_DATA

        etl_storage = EtlStorage.get_instance(ETL_CONFIG_JSON)
        result = etl_storage.update_or_create_result_table(
            collector_config,
            table_id=TABLE_ID,
            storage_cluster_id=STORAGE_CLUSTER_ID,
            retention=RETENTION_TIME,
            allocation_min_days=ALLOCATION_MIN_DAYS,
            storage_replies=1,
            fields=FIELDS,
            etl_params=ETL_PARAMS_JSON,
            hot_warm_config=HOT_WARM_CONFIG,
        )
        built_in_keys = FieldBuiltInEnum.get_choices()
        fields_not_doc_values = []
        fields_user = {}
        for item in result["params"]["field_list"]:
            # 用户清洗字段
            if item["field_name"].lower() not in built_in_keys:
                if "es_doc_values" in item["option"]:
                    fields_not_doc_values.append(item["field_name"])
                source_field = item["alias_name"] if item.get("alias_name") else item["field_name"]
                fields_user[source_field] = item
        self.assertEqual(fields_not_doc_values, FIELDS_NOT_ES_DOC_VALUES_KEYS)
        self.assertEqual(len(fields_user), FIELDS_VALID_NUM, "清洗字段数不一致")
        # 时间字段
        self.assertEqual(fields_user["time1"]["option"]["es_type"], "keyword")
        self.assertEqual(result["params"]["time_alias_name"], "time1")
        self.assertTrue(
            "es_doc_values" not in result["params"]["time_option"], "time_option必须设置且不可设置doc_values"
        )
        # option
        self.assertEqual(result["params"]["option"]["separator_fields_remove"], "delete1")

        # 字段解析
        etl_param = copy.deepcopy(result["params"])
        etl_config = etl_storage.parse_result_table_config(etl_param)

        self.assertIsInstance(etl_config["etl_params"]["es_unique_field_list"], list)
        self.assertEqual(etl_config["etl_params"]["separator_node_action"], "json")

        etl_fields = array_group(etl_config["fields"], "field_name", True)
        self.assertEqual(etl_fields["ip"]["alias_name"], "key1")
        self.assertTrue(etl_fields["key2"]["is_analyzed"])
        self.assertTrue(etl_fields["key3"]["is_dimension"])
        self.assertEqual(etl_fields["time1"]["option"]["es_type"], "date")
        self.assertTrue(etl_fields["time1"]["is_time"])
        self.assertTrue(etl_fields["time1"]["is_dimension"])
        self.assertTrue(etl_fields["delete1"]["is_delete"])
        return True

    @patch("apps.api.TransferApi.create_result_table", lambda _: {"table_id": TABLE_ID})
    @patch("apps.api.TransferApi.modify_result_table", lambda _: {"table_id": TABLE_ID})
    @patch("apps.api.TransferApi.get_result_table", lambda _: {"table_id": TABLE_ID})
    @patch("apps.api.TransferApi.get_cluster_info", lambda _: [CLUSTER_INFO])
    @FakeRedis("apps.utils.cache.cache")
    @patch("apps.log_databus.handlers.etl_storage.utils.transfer.preview")
    @patch("apps.log_databus.handlers.etl.EtlHandler._update_or_create_index_set")
    @patch("apps.log_databus.tasks.collector.modify_result_table.delay", return_value=None)
    def test_bk_log_regexp(self, mock_modify_delay, mock_index_set, mock_preview):
        """
        正则清洗
        """
        collector_config = CollectorConfig.objects.create(**COLLECTOR_CONFIG)
        mock_index_set.return_value = LOG_INDEX_DATA

        mock_preview.return_value = {"request_time": "30/Nov/2019:21:07:10 +0800", "request_ip": "127.0.0.1"}

        etl_storage = EtlStorage.get_instance(ETL_CONFIG_REGEXP)
        # 预览
        settings.ENVIRONMENT = "stag"
        etl_preview = etl_storage.etl_preview(ETL_REGEXP_CONTENT, ETL_PARAMS_REGEXP)
        self.assertEqual(etl_preview[0]["field_name"], "request_ip")

        # 清洗
        result = etl_storage.update_or_create_result_table(
            collector_config,
            table_id=TABLE_ID,
            storage_cluster_id=STORAGE_CLUSTER_ID,
            retention=RETENTION_TIME,
            allocation_min_days=ALLOCATION_MIN_DAYS,
            fields=FIELDS_REGEXP,
            storage_replies=1,
            etl_params=ETL_PARAMS_REGEXP,
            hot_warm_config=HOT_WARM_CONFIG,
        )
        built_in_keys = FieldBuiltInEnum.get_choices()
        fields_not_doc_values = []
        fields_user = {}
        for item in result["params"]["field_list"]:
            # 用户清洗字段
            if item["field_name"].lower() not in built_in_keys:
                if "es_doc_values" in item["option"]:
                    fields_not_doc_values.append(item["field_name"])
                source_field = item["alias_name"] if item.get("alias_name") else item["field_name"]
                fields_user[source_field] = item
        # 时间字段
        self.assertEqual(fields_user["request_ip"]["option"]["es_type"], "keyword")
        self.assertEqual(result["params"]["time_alias_name"], "request_time")
        self.assertTrue(
            "es_doc_values" not in result["params"]["time_option"], "time_option必须设置且不可设置doc_values"
        )

        # 字段解析
        etl_param = copy.deepcopy(result["params"])
        etl_config = etl_storage.parse_result_table_config(etl_param)

        etl_fields = array_group(etl_config["fields"], "field_name", True)
        self.assertEqual(etl_fields["request_time"]["option"]["es_type"], "date")
        return True

    @patch("apps.api.TransferApi.create_result_table", lambda _: {"table_id": TABLE_ID})
    @patch("apps.api.TransferApi.modify_result_table", lambda _: {"table_id": TABLE_ID})
    @patch("apps.api.TransferApi.get_result_table", lambda _: {"table_id": TABLE_ID})
    @patch("apps.api.TransferApi.get_cluster_info", lambda _: [CLUSTER_INFO])
    @FakeRedis("apps.utils.cache.cache")
    @patch("apps.log_databus.handlers.etl_storage.utils.transfer.preview")
    @patch("apps.log_databus.handlers.etl.EtlHandler._update_or_create_index_set")
    @patch("apps.log_databus.tasks.collector.modify_result_table.delay", return_value=None)
    def test_bk_log_delimiter(self, mock_modify_delay, mock_index_set, mock_preview):
        """
        分隔符清洗
        """
        collector_config = CollectorConfig.objects.create(**COLLECTOR_CONFIG)
        mock_index_set.return_value = LOG_INDEX_DATA
        mock_preview.return_value = ETL_DELIMITER_PREVIEW_SDK

        etl_storage = EtlStorage.get_instance(ETL_CONFIG_DELIMITER)
        # 预览
        settings.ENVIRONMENT = "stag"
        etl_preview = etl_storage.etl_preview(ETL_DELIMITER_CONTENT, ETL_PARAMS_DELIMITER)
        self.assertEqual(etl_preview, ETL_DELIMITER_PREVIEW)

        # 清洗
        result = etl_storage.update_or_create_result_table(
            collector_config,
            table_id=TABLE_ID,
            storage_cluster_id=STORAGE_CLUSTER_ID,
            retention=RETENTION_TIME,
            allocation_min_days=ALLOCATION_MIN_DAYS,
            fields=FIELDS_DELIMITER,
            storage_replies=1,
            etl_params=ETL_PARAMS_DELIMITER,
            hot_warm_config=HOT_WARM_CONFIG,
        )

        # 字段解析
        etl_param = copy.deepcopy(result["params"])
        etl_config = etl_storage.parse_result_table_config(etl_param)
        user_fields = list(filter(lambda x: not x.get("is_built_in", False), etl_config["fields"]))

        # 比较用户字段
        self.assertEqual(len(user_fields), 3)
        for field in user_fields:
            etl_field = ETL_DELIMITER_RESULT.get(field["field_index"], False)
            if not etl_field:
                self.assertTrue(etl_field, f"ETL结果异常: 第{field['field_index']}列不存在")
            self.assertEqual(field["field_name"], etl_field["field_name"])
            self.assertEqual(field["field_type"], etl_field["field_type"])
            self.assertEqual(field["is_delete"], etl_field["is_delete"])

        # 比较 META信息
        self.assertEqual(etl_config["etl_params"]["separator_field_list"], ETL_DELIMITER_META_FIELDS)

        return True

    def test_check_es_version(self):
        self.assertTrue(is_version_less_than("5.6", "7.3"))
        self.assertTrue(is_version_less_than("7.2", "7.3"))
        self.assertFalse(is_version_less_than("7.3", "7.3"))
        self.assertTrue(is_version_less_than("5.X", "7.3"))
        self.assertTrue(is_version_less_than("7.X", "7.3"))
        self.assertFalse(is_version_less_than("8.X", "7.3"))
        self.assertFalse(is_version_less_than("7.5.0", "7.3"))

    def test_etl_preview_delimiter_empty_separator(self):
        """
        测试分隔符格式的etl_preview方法 - 空分隔符异常
        """
        from apps.log_databus.handlers.etl_storage.bk_log_delimiter import BkLogDelimiterEtlStorage
        from apps.exceptions import ValidationError

        # 测试数据
        test_data = "127.0.0.1|2023-01-01|test message"
        etl_params = {"separator": "", "retain_original_text": True}

        # 创建EtlStorage实例
        etl_storage = BkLogDelimiterEtlStorage()

        # 验证异常
        with self.assertRaises(ValidationError):
            etl_storage.etl_preview(test_data, etl_params)

    def test_etl_preview_regexp_empty_regexp(self):
        """
        测试正则表达式格式的etl_preview方法 - 空正则表达式异常
        """
        from apps.log_databus.handlers.etl_storage.bk_log_regexp import BkLogRegexpEtlStorage
        from apps.exceptions import ValidationError

        # 测试数据
        test_data = "127.0.0.1 - - [30/Nov/2019:21:07:10 +0800]"
        etl_params = {"separator_regexp": "", "retain_original_text": True}

        # 创建EtlStorage实例
        etl_storage = BkLogRegexpEtlStorage()

        # 验证异常
        with self.assertRaises(ValidationError):
            etl_storage.etl_preview(test_data, etl_params)

    def test_etl_preview_regexp_no_match(self):
        """
        测试正则表达式格式的etl_preview方法 - 无匹配异常
        """
        from apps.log_databus.handlers.etl_storage.bk_log_regexp import BkLogRegexpEtlStorage
        from apps.exceptions import ValidationError

        # 测试数据
        test_data = "this is not a log format"
        etl_params = {
            "separator_regexp": "(?P<request_ip>[\\d\\.]+)[^[]+\\[(?P<request_time>[^]]+)\\]",
            "retain_original_text": True,
        }

        # 创建EtlStorage实例
        etl_storage = BkLogRegexpEtlStorage()

        # 验证异常
        with self.assertRaises(ValidationError):
            etl_storage.etl_preview(test_data, etl_params)

    def test_etl_preview_json_complex(self):
        """
        测试复杂JSON格式的etl_preview方法
        """
        from apps.log_databus.handlers.etl_storage.bk_log_json import BkLogJsonEtlStorage

        # 创建EtlStorage实例
        etl_storage = BkLogJsonEtlStorage()

        # 调用etl_preview方法
        result = etl_storage.etl_preview(ETL_PREVIEW_JSON_COMPLEX_DATA, ETL_PREVIEW_JSON_PARAMS)

        # 验证返回结果不为空且包含预期字段
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

        # 验证包含预期的顶级字段
        field_names = [field["field_name"] for field in result]
        expected_fields = ["timestamp", "level", "message", "user", "request", "response"]
        for expected_field in expected_fields:
            self.assertIn(expected_field, field_names)

    def test_etl_preview_json_nested_objects(self):
        """
        测试JSON格式的etl_preview方法 - 嵌套对象
        """
        from apps.log_databus.handlers.etl_storage.bk_log_json import BkLogJsonEtlStorage

        # 嵌套对象测试数据
        test_data = """
        {
            "level": "info",
            "message": "User action",
            "user": {
                "id": 12345,
                "profile": {
                    "name": "test_user",
                    "email": "test@example.com"
                }
            },
            "context": {
                "request_id": "req-123",
                "session_id": "sess-456"
            }
        }
        """
        etl_params = {"retain_original_text": True}

        # 创建EtlStorage实例
        etl_storage = BkLogJsonEtlStorage()

        # 调用etl_preview方法
        result = etl_storage.etl_preview(test_data, etl_params)

        # 验证返回结果不为空
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

        # 验证包含预期的顶级字段
        field_names = [field["field_name"] for field in result]
        expected_fields = ["level", "message", "user", "context"]
        for expected_field in expected_fields:
            self.assertIn(expected_field, field_names)

        # 验证字段值
        field_dict = {field["field_name"]: field["value"] for field in result}
        self.assertEqual(field_dict["level"], "info")
        self.assertEqual(field_dict["message"], "User action")

        # 验证嵌套对象字段值（JSON字符串形式）
        self.assertIn("id", field_dict["user"])
        self.assertIn("profile", field_dict["user"])
        self.assertIn("request_id", field_dict["context"])
        self.assertIn("session_id", field_dict["context"])

    @patch("apps.api.BkDataDatabusApi.databus_clean_debug")
    def test_etl_preview_v4_delimiter(self, mock_api):
        """
        测试V4版本分隔符格式的etl_preview方法
        """
        from apps.log_databus.handlers.etl_storage.bk_log_delimiter import BkLogDelimiterEtlStorage

        # Mock API响应
        mock_api.return_value = ETL_PREVIEW_V4_DELIMITER_API_RESPONSE

        # 创建EtlStorage实例
        etl_storage = BkLogDelimiterEtlStorage()

        # 调用etl_preview_v4方法
        result = etl_storage.etl_preview_v4(ETL_PREVIEW_V4_DELIMITER_INPUT, ETL_PREVIEW_V4_DELIMITER_PARAMS)

        # 验证API调用参数
        mock_api.assert_called_once_with(ETL_PREVIEW_V4_DELIMITER_API_REQUEST)

        # 验证返回结果与预期常量一致
        self.assertEqual(result, ETL_PREVIEW_V4_DELIMITER_EXPECTED)

    @patch("apps.api.BkDataDatabusApi.databus_clean_debug")
    def test_etl_preview_v4_json(self, mock_api):
        """
        测试V4版本JSON格式的etl_preview方法
        """
        from apps.log_databus.handlers.etl_storage.bk_log_json import BkLogJsonEtlStorage

        # Mock API响应
        mock_api.return_value = ETL_PREVIEW_V4_JSON_API_RESPONSE

        # 创建EtlStorage实例
        etl_storage = BkLogJsonEtlStorage()

        # 调用etl_preview_v4方法
        result = etl_storage.etl_preview_v4(ETL_PREVIEW_V4_JSON_INPUT, ETL_PREVIEW_V4_JSON_PARAMS)

        # 验证API调用参数
        mock_api.assert_called_once_with(ETL_PREVIEW_V4_JSON_API_REQUEST)

        # 验证返回结果与预期常量一致
        self.assertEqual(result, ETL_PREVIEW_V4_JSON_EXPECTED)

    @patch("apps.api.BkDataDatabusApi.databus_clean_debug")
    def test_etl_preview_v4_regexp(self, mock_api):
        """
        测试V4版本正则表达式格式的etl_preview方法
        """
        from apps.log_databus.handlers.etl_storage.bk_log_regexp import BkLogRegexpEtlStorage

        # Mock API响应
        mock_api.return_value = ETL_PREVIEW_V4_REGEXP_API_RESPONSE

        # 创建EtlStorage实例
        etl_storage = BkLogRegexpEtlStorage()

        # 调用etl_preview_v4方法
        result = etl_storage.etl_preview_v4(ETL_PREVIEW_V4_REGEXP_INPUT, ETL_PREVIEW_V4_REGEXP_PARAMS)

        # 验证API调用参数
        mock_api.assert_called_once_with(ETL_PREVIEW_V4_REGEXP_API_REQUEST)

        # 验证返回结果与预期常量一致
        self.assertEqual(result, ETL_PREVIEW_V4_REGEXP_EXPECTED)

    @patch("apps.api.BkDataDatabusApi.databus_clean_debug")
    def test_etl_preview_v4_delimiter_empty_separator(self, mock_api):
        """
        测试V4版本分隔符格式的etl_preview方法 - 空分隔符异常
        """
        from apps.log_databus.handlers.etl_storage.bk_log_delimiter import BkLogDelimiterEtlStorage
        from apps.exceptions import ValidationError

        # 创建EtlStorage实例
        etl_storage = BkLogDelimiterEtlStorage()

        # 空分隔符参数
        etl_params = {"separator": "", "retain_original_text": True}

        # 验证异常
        with self.assertRaises(ValidationError):
            etl_storage.etl_preview_v4(ETL_PREVIEW_V4_DELIMITER_INPUT, etl_params)

        # 验证API未被调用
        mock_api.assert_not_called()

    @patch("apps.api.BkDataDatabusApi.databus_clean_debug")
    def test_etl_preview_v4_regexp_empty_regexp(self, mock_api):
        """
        测试V4版本正则表达式格式的etl_preview方法 - 空正则表达式异常
        """
        from apps.log_databus.handlers.etl_storage.bk_log_regexp import BkLogRegexpEtlStorage
        from apps.exceptions import ValidationError

        # 创建EtlStorage实例
        etl_storage = BkLogRegexpEtlStorage()

        # 空正则表达式参数
        etl_params = {"separator_regexp": "", "retain_original_text": True}

        # 验证异常
        with self.assertRaises(ValidationError):
            etl_storage.etl_preview_v4(ETL_PREVIEW_V4_REGEXP_INPUT, etl_params)

        # 验证API未被调用
        mock_api.assert_not_called()

    @patch("apps.api.BkDataDatabusApi.databus_clean_debug")
    def test_etl_preview_v4_api_error(self, mock_api):
        """
        测试V4版本etl_preview方法 - API调用异常
        """
        from apps.log_databus.handlers.etl_storage.bk_log_delimiter import BkLogDelimiterEtlStorage
        from apps.exceptions import ApiRequestError

        # Mock API异常
        mock_api.side_effect = ApiRequestError("API调用失败")

        # 创建EtlStorage实例
        etl_storage = BkLogDelimiterEtlStorage()

        # 验证异常
        with self.assertRaises(ApiRequestError):
            etl_storage.etl_preview_v4(ETL_PREVIEW_V4_DELIMITER_INPUT, ETL_PREVIEW_V4_DELIMITER_PARAMS)

    @patch("apps.api.BkDataDatabusApi.databus_clean_debug")
    def test_etl_preview_v4_empty_response(self, mock_api):
        """
        测试V4版本etl_preview方法 - 空响应处理
        """
        from apps.log_databus.handlers.etl_storage.bk_log_delimiter import BkLogDelimiterEtlStorage

        # Mock空响应（新格式：rules_output是数组）
        mock_api.return_value = {"rules_output": [{"value": []}]}

        # 创建EtlStorage实例
        etl_storage = BkLogDelimiterEtlStorage()

        # 调用etl_preview_v4方法
        result = etl_storage.etl_preview_v4(ETL_PREVIEW_V4_DELIMITER_INPUT, ETL_PREVIEW_V4_DELIMITER_PARAMS)

        # 验证返回空结果
        self.assertEqual(result, [])

    @patch("apps.api.BkDataDatabusApi.databus_clean_debug")
    def test_etl_preview_v4_delimiter_special_characters(self, mock_api):
        """
        测试V4版本分隔符格式的etl_preview方法 - 特殊字符分隔符
        """
        from apps.log_databus.handlers.etl_storage.bk_log_delimiter import BkLogDelimiterEtlStorage

        # 特殊字符分隔符测试数据
        test_input = "field1\tfield2\tfield3\tfield4"
        test_params = {"separator": "\t", "retain_original_text": True}

        # Mock API响应
        mock_api.return_value = {"rules_output": [{"value": ["field1", "field2", "field3", "field4"]}]}

        # 创建EtlStorage实例
        etl_storage = BkLogDelimiterEtlStorage()

        # 调用etl_preview_v4方法
        result = etl_storage.etl_preview_v4(test_input, test_params)

        # 验证返回结果
        expected = [
            {"field_index": 1, "field_name": "", "value": "field1"},
            {"field_index": 2, "field_name": "", "value": "field2"},
            {"field_index": 3, "field_name": "", "value": "field3"},
            {"field_index": 4, "field_name": "", "value": "field4"},
        ]
        self.assertEqual(result, expected)

    @patch("apps.api.BkDataDatabusApi.databus_clean_debug")
    def test_etl_preview_v4_json_nested_objects(self, mock_api):
        """
        测试V4版本JSON格式的etl_preview方法 - 嵌套对象
        """
        from apps.log_databus.handlers.etl_storage.bk_log_json import BkLogJsonEtlStorage

        # 嵌套对象测试数据
        test_input = """
        {
            "level": "info",
            "message": "User action",
            "user": {
                "id": 12345,
                "profile": {
                    "name": "test_user",
                    "email": "test@example.com"
                }
            },
            "context": {
                "request_id": "req-123",
                "session_id": "sess-456"
            }
        }
        """

        # Mock API响应
        mock_api.return_value = {
            "rules_output": [
                {
                    "value": {
                        "level": "info",
                        "message": "User action",
                        "user": {"id": 12345, "profile": {"name": "test_user", "email": "test@example.com"}},
                        "context": {"request_id": "req-123", "session_id": "sess-456"},
                    },
                    "key_index": [
                        {
                            "type": "key",
                            "value": "context",
                            "children": [
                                {"type": "key", "value": "request_id", "field_type": "string"},
                                {"type": "key", "value": "session_id", "field_type": "string"},
                            ],
                            "field_type": "dict",
                        },
                        {"type": "key", "value": "level", "field_type": "string"},
                        {"type": "key", "value": "message", "field_type": "string"},
                        {
                            "type": "key",
                            "value": "user",
                            "children": [
                                {"type": "key", "value": "id", "field_type": "long"},
                                {
                                    "type": "key",
                                    "value": "profile",
                                    "children": [
                                        {"type": "key", "value": "email", "field_type": "string"},
                                        {"type": "key", "value": "name", "field_type": "string"},
                                    ],
                                    "field_type": "dict",
                                },
                            ],
                            "field_type": "dict",
                        },
                    ],
                }
            ]
        }

        # 创建EtlStorage实例
        etl_storage = BkLogJsonEtlStorage()

        # 调用etl_preview_v4方法
        result = etl_storage.etl_preview_v4(test_input, ETL_PREVIEW_V4_JSON_PARAMS)

        # 验证返回结果包含预期字段
        field_names = [field["field_name"] for field in result]
        expected_fields = ["level", "message", "user", "context"]
        for expected_field in expected_fields:
            self.assertIn(expected_field, field_names)
