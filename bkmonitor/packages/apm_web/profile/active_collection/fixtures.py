"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import gzip

from django.http import HttpResponse

from apm_web.profile.active_collection.constants import (
    EXECUTION_DETAIL_HOST_COLUMNS,
    EXECUTION_LIST_TASK_COLUMNS,
    HOST_QUERY_COLUMNS,
    PROCESS_PREVIEW_COLUMNS,
    TASK_LIST_COLUMNS,
)
from apm_web.profile.constants import DEFAULT_EXPORT_FORMAT

RESULT_DATA_KEY = {"flamegraph": "flame_data", "table": "table_data"}

PROCESS_PREVIEW = {
    "columns": PROCESS_PREVIEW_COLUMNS,
    "data": [
        {
            "bk_host_id": 456,
            "ip": "127.0.0.1",
            "pid": 2341,
            "process_name": "order-api",
            "command": "/data/order-api/bin/start",
            "started_at": 1788310800000,
        },
        {"bk_host_id": 457, "ip": "127.0.0.2", "err_msg": "bkmonitorbeat: exclude_pattern is invalid"},
    ],
}

_TASK_CONFIG = {
    "target_config": {"node_type": "INSTANCE", "nodes": [{"bk_host_id": 456}]},
    "process_selector": {"type": "pid_file", "config": {"pid_path": "/var/run/demo.pid"}},
    "collector_config": {"duration_sec": 30},
    "resource_guard_config": {
        "auto_stop_on_resource_pressure": True,
        "max_disk_usage": 1024,
        "min_mem_level": 100,
    },
}

TASK_LIST = {
    "columns": TASK_LIST_COLUMNS,
    "data": [
        {
            "task_id": 123,
            "name": "java-cpu-daily",
            "task_status": "enabled",
            "deployment_status": "success",
            "schedule": {
                "type": "cron",
                "cron_expression": "0 */2 * * *",
                "timezone": "Asia/Shanghai",
                "effective_start_at": 1788310800000,
                "effective_end_at": 1788915600000,
            },
            "collection_method": "java",
            "collection_type": "java_cpu",
            "creator": "admin",
            "updated_at": 1788310000000,
            **_TASK_CONFIG,
        },
        {
            "task_id": 124,
            "name": "java-cpu-once",
            "task_status": "disabled",
            "deployment_status": "outdate",
            "schedule": {"type": "once_at", "execute_at": 1788010800000, "timezone": "Asia/Shanghai"},
            "collection_method": "java",
            "collection_type": "java_cpu",
            "creator": "admin",
            "updated_at": 1788010000000,
            **_TASK_CONFIG,
        },
    ],
    "page": 1,
    "page_size": 20,
    "total": 2,
}

HOST_QUERY = {
    "columns": HOST_QUERY_COLUMNS,
    "data": [
        {
            "bk_host_id": 457,
            "ip": "127.0.0.2",
            "processes": [],
            "task": {"task_id": 12, "name": "go-cpu-daily", "schedule_type": "cron"},
            "collection_method": "golang",
            "collection_type": "go_cpu",
            "creator": "admin",
            "scheduled_at": 1788320800000,
            "started_at": 1788320801000,
            "finished_at": None,
            "duration_ms": None,
            "status": "running",
        },
        {
            "bk_host_id": 456,
            "ip": "127.0.0.1",
            "processes": [{"pid": 1234, "process_name": "java"}],
            "task": {"task_id": 123, "name": "java-cpu-daily", "schedule_type": "cron"},
            "collection_method": "java",
            "collection_type": "java_cpu",
            "creator": "admin",
            "scheduled_at": 1788310800000,
            "started_at": 1788310801000,
            "finished_at": 1788310832000,
            "duration_ms": 31000,
            "status": "succeed",
        },
        {
            "bk_host_id": 456,
            "ip": "127.0.0.1",
            "processes": [{"pid": 1234, "process_name": "workload"}],
            "task": {"name": "native-cpu", "schedule_type": "immediate"},
            "collection_method": "perf",
            "collection_type": "native_cpu",
            "creator": "admin",
            "scheduled_at": 1788010800000,
            "started_at": 1788010801000,
            "finished_at": 1788010832000,
            "duration_ms": 31000,
            "status": "outdate",
        },
    ],
}

EXECUTION_LIST = {
    "task_columns": EXECUTION_LIST_TASK_COLUMNS,
    "data": [
        {
            "task_name": "native-cpu",
            "schedule_type": "immediate",
            "scheduled_at": 1788411800000,
            "collection_method": "perf",
            "collection_type": "native_cpu",
            "creator": "admin",
            "started_at": 1788411801000,
            "finished_at": None,
            "duration_ms": None,
            "execution_status": "running",
            "target_count": 2,
            "status_summary": {"succeed": 1, "running": 1},
            "hosts": [{"bk_host_id": 456, "ip": "127.0.0.1"}, {"bk_host_id": 457, "ip": "127.0.0.2"}],
        },
        {
            "task_id": 123,
            "task_name": "java-cpu-daily",
            "scheduled_at": 1788010800000,
            "schedule_type": "cron",
            "collection_method": "java",
            "collection_type": "java_cpu",
            "creator": "admin",
            "started_at": 1788010801000,
            "finished_at": 1788010832000,
            "duration_ms": 31000,
            "execution_status": "outdate",
            "target_count": 2,
            "status_summary": {"outdate": 2},
            "hosts": [{"bk_host_id": 456, "ip": "127.0.0.1"}, {"bk_host_id": 457, "ip": "127.0.0.2"}],
        },
    ],
}

EXECUTION_DETAIL = {
    "host_columns": EXECUTION_DETAIL_HOST_COLUMNS,
    "task_id": 123,
    "task_name": "java-cpu-daily",
    "schedule_type": "cron",
    "scheduled_at": 1788310800000,
    "collection_method": "java",
    "collection_type": "java_cpu",
    "creator": "admin",
    "started_at": 1788310801000,
    "finished_at": 1788310832000,
    "duration_ms": 31000,
    "execution_status": "partial_succeed",
    "status_summary": {"succeed": 1, "failed": 1},
    "total_hosts": 2,
    "config": {
        "schedule": {
            "type": "cron",
            "cron_expression": "0 */2 * * *",
            "timezone": "Asia/Shanghai",
            "effective_start_at": 1788310800000,
            "effective_end_at": 1788915600000,
        },
        **_TASK_CONFIG,
        "target_config": {"node_type": "INSTANCE", "nodes": [{"bk_host_id": 456}, {"bk_host_id": 457}]},
    },
    "hosts": [
        {
            "bk_host_id": 456,
            "ip": "127.0.0.1",
            "processes": [{"pid": 1234, "process_name": "java"}],
            "status": "succeed",
            "message": "",
            "started_at": 1788310801000,
            "finished_at": 1788310832000,
            "duration_ms": 31000,
        },
        {
            "bk_host_id": 457,
            "ip": "127.0.0.2",
            "processes": [{"pid": 2345, "process_name": "java"}],
            "status": "failed",
            "message": "Profiling 发送失败",
            "started_at": 1788310801000,
            "finished_at": 1788310832000,
            "duration_ms": 31000,
        },
    ],
}

RESULT_QUERY = {
    "flame_data": {
        "id": 0,
        "name": "total",
        "value": 1000,
        "children": [
            {
                "id": "main",
                "name": "main",
                "value": 800,
                "self": 100,
                "children": [{"id": "work", "name": "work", "value": 700, "self": 700, "children": []}],
            }
        ],
    },
    "table_data": {
        "total": 1000,
        "items": [
            {"id": "total", "name": "total", "self": 0, "total": 1000},
            {"id": "work", "name": "work", "self": 700, "total": 700},
            {"id": "main", "name": "main", "self": 100, "total": 800},
        ],
    },
    "type": "cpu",
    "unit": "nanoseconds",
}

RESULT_DATA_TYPES = [
    {"key": "alloc_objects/count", "name": "ALLOC_OBJECTS"},
    {"key": "alloc_space/bytes", "name": "ALLOC_SPACE"},
    {"key": "inuse_objects/count", "name": "INUSE_OBJECTS"},
    {"key": "inuse_space/bytes", "name": "INUSE_SPACE"},
]

TOPK = {
    "target": [{"value": "127.0.0.1", "alias": "127.0.0.1", "count": 2}],
    "process_pids": [{"value": "1234", "alias": "java:1234", "count": 2}],
}


def execution_detail(validated_request_data):
    """immediate 的真实响应不含 task_id，mock 保持同一约定"""
    if validated_request_data["schedule_type"] != "immediate":
        return EXECUTION_DETAIL
    detail = {key: value for key, value in EXECUTION_DETAIL.items() if key != "task_id"}
    detail["schedule_type"] = "immediate"
    return detail


def result_query(diagram_types):
    result = {
        RESULT_DATA_KEY[diagram_type]: RESULT_QUERY[RESULT_DATA_KEY[diagram_type]] for diagram_type in diagram_types
    }
    result.update(type=RESULT_QUERY["type"], unit=RESULT_QUERY["unit"])
    return result


def topk(field):
    return TOPK.get(field, [{"value": "java-cpu-daily", "alias": "java-cpu-daily", "count": 2}])


def export_response():
    response = HttpResponse(gzip.compress(b"mock-active-profiling-pprof"), content_type="application/octet-stream")
    response["Content-Encoding"] = "gzip"
    response["Content-Disposition"] = f'attachment; filename="active-profiling-mock.{DEFAULT_EXPORT_FORMAT}"'
    return response
