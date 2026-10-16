"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import gzip
import itertools
import json
import string
from types import SimpleNamespace

import pytest
from django.db.models import Q
from django.http import HttpResponse
from django.urls import reverse
from rest_framework.test import APIRequestFactory

from apm.models import ProfileDataSource
from apm_web.models import ActiveProfilingTask
from apm_web.profile.active_collection.constants import META_CONFIG
from apm_web.profile.active_collection.constants import (
    BUILTIN_EVENT_GROUP_LABEL,
    BUILTIN_EVENT_GROUP_NAME,
    BUILTIN_PROFILING_APP_NAME,
    EXECUTION_DETAIL_HOST_COLUMNS,
    EXECUTION_LIST_TASK_COLUMNS,
    HOST_QUERY_COLUMNS,
    PROCESS_PREVIEW_COLUMNS,
    PROCESS_PREVIEW_MAX_HOSTS,
    PROCESS_SELECTOR_MAX_HOST_PIDS,
    PROCESS_SELECTOR_MAX_PID_PATHS,
    PROCESS_SELECTOR_MAX_PIDS,
    PROCESS_SELECTOR_MAX_TEXT_LENGTH,
    RUNNING_EXECUTION_WINDOW_MS,
    TASK_LIST_COLUMNS,
)
from apm_web.profile.active_collection.handlers import (
    ActiveProfilingEventQueryHandler,
    ActiveProfilingNodeManHandler,
)
from apm_web.profile.active_collection.resources import (
    ActiveProfilingMetaConfigResource,
    CancelExecutionResource,
    DeleteTaskResource,
    EditTaskResource,
    EnableActiveCollectionResource,
    ExecutionDetailResource,
    ExportResultsResource,
    ListExecutionsResource,
    ListTasksResource,
    PreviewProcessesResource,
    QueryHostsResource,
    QueryResultDataTypesResource,
    QueryResultsResource,
    QueryTopKResource,
    SubmitTaskResource,
    SwitchTaskResource,
)
from apm_web.profile.active_collection.serializers import (
    EnableRequestSerializer,
    EventListRequestSerializer,
    ExecutionCancelRequestSerializer,
    ExecutionDetailRequestSerializer,
    PlannedTaskSubmitRequestSerializer,
    ProcessPreviewRequestSerializer,
    ResultDataTypesRequestSerializer,
    ResultExportRequestSerializer,
    ResultQueryRequestSerializer,
    TaskEditRequestSerializer,
    TaskListRequestSerializer,
    TaskSubmitRequestSerializer,
    TopKRequestSerializer,
)
from apm_web.profile.active_collection.views import (
    ActiveProfilingMetaConfigViewSet,
    EnableViewSet,
    ExecutionsListViewSet,
    ExecutionsViewSet,
    HostsViewSet,
    ProcessesViewSet,
    ResultsViewSet,
    TasksViewSet,
    TopKViewSet,
)
from apm_web.profile.diagrams import get_diagrammer
from apm_web.profile.diagrams.tree_converter import TreeConverter
from apm_web.profile.doris.converter import DorisProfileConverter
from apm_web.profile.views import ProfileQueryViewSet
from apm_web.tasks import stop_expired_active_profiling_tasks
from bkmonitor.iam.drf import ViewBusinessPermission
from core.errors.api import BKAPIError

PROCESS_PREVIEW_REQUEST = {
    "bk_biz_id": 2,
    "target_config": {"node_type": "INSTANCE", "nodes": [{"bk_host_id": 456}]},
    "process_selector": {"type": "command", "config": {"match_pattern": "/data/order-api", "exclude_pattern": ""}},
}

DYNAMIC_COMMAND_SELECTOR = {
    "type": "command",
    "config": {"match_pattern": "/data/order-api", "exclude_pattern": "", "enable_dynamic_collection": True},
}
STATIC_COMMAND_SELECTOR = {
    "type": "command",
    "config": {
        "match_pattern": "/data/order-api",
        "exclude_pattern": "",
        "enable_dynamic_collection": False,
        "host_pids": [{"bk_host_id": 456, "pid": 2341}, {"bk_host_id": 456, "pid": 2342}],
    },
}

RESOURCE_GUARD_CONFIG = {
    "auto_stop_on_resource_pressure": True,
    "max_disk_usage": 1024,
    "min_mem_level": 100,
}

TASK_SUBMIT_REQUEST = {
    "bk_biz_id": 2,
    "name": "java-cpu-daily",
    "collection_method": "java",
    "collection_type": "java_cpu",
    "target_config": {"node_type": "INSTANCE", "nodes": [{"bk_host_id": 456}]},
    "process_selector": {"type": "pid_file", "config": {"pid_path": "/var/run/demo.pid"}},
    "schedule": {
        "type": "cron",
        "cron_expression": "0 */2 * * *",
        "timezone": "Asia/Shanghai",
        "effective_start_at": 1788310800000,
        "effective_end_at": 1788915600000,
    },
    "collector_config": {"duration_sec": 30},
    "resource_guard_config": RESOURCE_GUARD_CONFIG,
}

GOLANG_TASK_SUBMIT_REQUEST = {
    "bk_biz_id": 2,
    "name": "go-cpu-once",
    "collection_method": "golang",
    "collection_type": "go_cpu",
    "target_config": {"node_type": "INSTANCE", "nodes": [{"bk_host_id": 456}]},
    "schedule": {
        "type": "immediate",
        "execute_at": 1788310800000,
        "timezone": "Asia/Shanghai",
    },
    "collector_config": {"ip_address": "127.0.0.1", "port": 6060, "duration_sec": 30},
    "resource_guard_config": RESOURCE_GUARD_CONFIG,
}

EVENT_LIST_REQUEST = {
    "bk_biz_id": 2,
    "start_time": 1787706000000,
    "end_time": 1788510800000,
    "filters": {
        "ips": [],
        "task_name": "",
        "process_names": [],
        "process_pids": [],
        "schedule_types": [],
        "collection_methods": [],
        "collection_types": [],
        "status": "",
    },
    "offset": 0,
    "limit": 20,
}

EXECUTION_DETAIL_REQUEST = {
    "bk_biz_id": 2,
    "schedule_type": "cron",
    "scheduled_at": 1788310800000,
    "task_id": 123,
}

RESULT_QUERY_REQUEST = {
    "bk_biz_id": 2,
    "scheduled_at": 1788310800000,
    "bk_host_id": 456,
    "started_at": 1788310801000,
    "finished_at": 1788310832000,
    "data_type": "cpu/nanoseconds",
    "diagram_types": ["flamegraph", "table"],
}


def _patch_profile(mocker, profile):
    mocker.patch.object(ProfileDataSource.objects, "filter", return_value=mocker.Mock(first=lambda: profile))


def test_meta_config_enabled_when_profile_data_id_exists(mocker):
    _patch_profile(mocker, mocker.Mock(bk_data_id=1001))
    event_group = mocker.patch("core.drf_resource.api.metadata.single_query_event_group")

    result = ActiveProfilingMetaConfigResource().request({"bk_biz_id": 2})

    assert result == {**META_CONFIG, "enabled": True}
    # 事件分组与 Profiling 数据源由 enable 一起创建，开通状态只看 Profiling 数据源
    event_group.assert_not_called()


@pytest.mark.parametrize("bk_data_id", [None, -1])
def test_meta_config_disabled_until_profile_data_id_exists(mocker, bk_data_id):
    profile = None if bk_data_id is None else mocker.Mock(bk_data_id=bk_data_id)
    _patch_profile(mocker, profile)

    assert ActiveProfilingMetaConfigResource().request({"bk_biz_id": 2})["enabled"] is False


@pytest.fixture
def enable_apis(mocker):
    mocker.patch("apm_web.profile.active_collection.resources.get_request_username", return_value="admin")
    mocks = {
        name: mocker.patch(f"core.drf_resource.api.metadata.{name}", return_value=return_value)
        for name, return_value in [
            ("single_query_event_group", []),
            ("get_data_id", {"bk_data_id": 1001}),
            ("create_data_id", {"bk_data_id": 1002}),
            ("create_event_group", {"event_group_id": 555}),
        ]
    }
    mocks["apply_datasource"] = mocker.patch.object(ProfileDataSource, "apply_datasource")
    return mocks


def test_enable_creates_builtin_profiling_datasource_and_event_group(enable_apis):
    enable_apis["get_data_id"].side_effect = BKAPIError(system_name="metadata", url="", result={})

    assert EnableActiveCollectionResource().request({"bk_biz_id": 2}) is None

    enable_apis["apply_datasource"].assert_called_once_with(
        bk_biz_id=2, app_name=BUILTIN_PROFILING_APP_NAME, option=True
    )
    assert enable_apis["create_data_id"].call_args.kwargs["data_name"] == f"2_{BUILTIN_EVENT_GROUP_NAME}"
    enable_apis["create_event_group"].assert_called_once_with(
        operator="admin",
        bk_data_id=1002,
        bk_biz_id=2,
        event_group_name=BUILTIN_EVENT_GROUP_NAME,
        label=BUILTIN_EVENT_GROUP_LABEL,
        data_label=BUILTIN_EVENT_GROUP_NAME,
    )


def test_enable_skips_existing_event_group(enable_apis):
    enable_apis["single_query_event_group"].return_value = [{"event_group_id": 555}]

    assert EnableActiveCollectionResource().request({"bk_biz_id": 2}) is None

    enable_apis["get_data_id"].assert_not_called()
    enable_apis["create_data_id"].assert_not_called()
    enable_apis["create_event_group"].assert_not_called()


def test_enable_reuses_existing_event_data_id(enable_apis):
    EnableActiveCollectionResource().request({"bk_biz_id": 2})

    enable_apis["create_data_id"].assert_not_called()
    assert enable_apis["create_event_group"].call_args.kwargs["bk_data_id"] == 1001


MATCHED_PROCESS = {
    "pid": 2341,
    "process_name": "java",
    "command": "java -jar app.jar",
    "started_at": 1789032616000,
}


@pytest.fixture
def fast_execute_script(mocker):
    mock = mocker.patch("core.drf_resource.resource.commons.fast_execute_script")
    mock.return_value = {
        "success": [
            {
                "bk_host_id": 456,
                "ip": "127.0.0.1",
                "log_content": json.dumps({"processes": [MATCHED_PROCESS]}),
            }
        ],
        "pending": [],
        "failed": [],
    }
    return mock


def test_preview_processes_returns_matched_rows(fast_execute_script):
    result = PreviewProcessesResource().request(PROCESS_PREVIEW_REQUEST)

    assert result["columns"] == PROCESS_PREVIEW_COLUMNS
    assert result["data"] == [{"bk_host_id": 456, "ip": "127.0.0.1", **MATCHED_PROCESS}]


def test_preview_processes_returns_host_row_when_nothing_matched(fast_execute_script):
    fast_execute_script.return_value["success"][0]["log_content"] = json.dumps({"processes": []})

    assert PreviewProcessesResource().request(PROCESS_PREVIEW_REQUEST)["data"] == [
        {"bk_host_id": 456, "ip": "127.0.0.1"}
    ]


def test_preview_processes_reports_failed_hosts_with_beat_error(fast_execute_script):
    fast_execute_script.return_value["failed"] = [
        {"bk_host_id": 457, "ip": "127.0.0.2", "errmsg": "invalid exclude_pattern", "exit_code": 1}
    ]

    assert PreviewProcessesResource().request(PROCESS_PREVIEW_REQUEST)["data"] == [
        {"bk_host_id": 456, "ip": "127.0.0.1", **MATCHED_PROCESS},
        {"bk_host_id": 457, "ip": "127.0.0.2", "err_msg": "invalid exclude_pattern"},
    ]


def test_preview_processes_keeps_user_input_out_of_the_script(fast_execute_script):
    """选择器只能经 base64 进入脚本参数，脚本体必须是不含用户输入的常量"""
    injection = '"; rm -rf / #'
    PreviewProcessesResource().request(
        {
            **PROCESS_PREVIEW_REQUEST,
            "process_selector": {"type": "command", "config": {"match_pattern": injection, "exclude_pattern": ""}},
        }
    )

    kwargs = fast_execute_script.call_args.kwargs
    assert injection not in kwargs["script_content"]
    assert (
        kwargs["script_content"]
        == 'echo "$1" | base64 -d | /usr/local/gse/plugins/bin/bkmonitorbeat -active-profile-match\n'
    )
    assert json.loads(base64.b64decode(kwargs["script_param"])) == {
        "process_selector": {"type": "command", "match_pattern": injection, "exclude_pattern": ""}
    }
    assert set(kwargs["script_param"]) <= set(string.ascii_letters + string.digits + "+/=")


@pytest.mark.parametrize(
    ("selector", "cli_selector"),
    [
        (
            {"type": "pid_file", "config": {"pid_path": "/var/run/a.pid;/var/run/b.pid"}},
            {"type": "pid_file", "pid_path": "/var/run/a.pid;/var/run/b.pid"},
        ),
        ({"type": "pid", "config": {"pids": "2341;2342"}}, {"type": "pid", "pids": "2341;2342"}),
    ],
)
def test_preview_processes_sends_selector_to_all_hosts_in_one_job(fast_execute_script, selector, cli_selector):
    PreviewProcessesResource().request(
        {
            **PROCESS_PREVIEW_REQUEST,
            "target_config": {"node_type": "INSTANCE", "nodes": [{"bk_host_id": 456}, {"bk_host_id": 457}]},
            "process_selector": selector,
        }
    )

    fast_execute_script.assert_called_once()
    kwargs = fast_execute_script.call_args.kwargs
    assert kwargs["host_list"] == [{"bk_host_id": 456}, {"bk_host_id": 457}]
    # 采集端的选择器是扁平结构，config 展开后下发
    assert json.loads(base64.b64decode(kwargs["script_param"])) == {"process_selector": cli_selector}


def test_preview_processes_rejects_too_many_hosts(fast_execute_script):
    nodes = [{"bk_host_id": index} for index in range(PROCESS_PREVIEW_MAX_HOSTS + 1)]

    with pytest.raises(ValueError):
        PreviewProcessesResource().request(
            {**PROCESS_PREVIEW_REQUEST, "target_config": {"node_type": "INSTANCE", "nodes": nodes}}
        )

    fast_execute_script.assert_not_called()


@pytest.mark.parametrize("exclude_pattern", ["[unclosed", "(?P<name>", "*"])
def test_process_selector_rejects_invalid_exclude_pattern(exclude_pattern):
    serializer = ProcessPreviewRequestSerializer(
        data={
            **PROCESS_PREVIEW_REQUEST,
            "process_selector": {
                "type": "command",
                "config": {"match_pattern": "java", "exclude_pattern": exclude_pattern},
            },
        }
    )

    assert not serializer.is_valid()


GOLANG_PLANNED_TASK_SUBMIT_REQUEST = {
    **GOLANG_TASK_SUBMIT_REQUEST,
    "schedule": TASK_SUBMIT_REQUEST["schedule"],
}


IMMEDIATE_SCHEDULE = {"type": "immediate", "execute_at": 1788310800000, "timezone": "Asia/Shanghai"}

IMMEDIATE_TASK_SUBMIT_REQUEST = {**TASK_SUBMIT_REQUEST, "schedule": IMMEDIATE_SCHEDULE}


TWO_HOSTS_TARGET_CONFIG = {"node_type": "INSTANCE", "nodes": [{"bk_host_id": 456}, {"bk_host_id": 457}]}


@pytest.fixture
def immediate_apis(mocker):
    mocker.patch("apm_web.profile.active_collection.resources.get_request_tenant_id", return_value="system")
    mocker.patch("apm_web.profile.active_collection.resources.get_request_username", return_value="admin")
    profile_datasource = mocker.patch("apm_web.profile.active_collection.handlers.ProfileDataSource")
    profile_datasource.objects.filter.return_value.first.return_value.bk_data_id = 777

    def submit_job(**kwargs):
        bk_host_id = kwargs["target_server"]["host_id_list"][0]
        return {"job_instance_id": 1000 + bk_host_id, "step_instance_id": 2000 + bk_host_id}

    return {
        "job": mocker.patch("core.drf_resource.api.job.fast_execute_script", side_effect=submit_job),
        "event_group": mocker.patch(
            "core.drf_resource.api.metadata.single_query_event_group",
            return_value=[{"bk_data_id": 555, "token": "event-token"}],
        ),
        "hosts": mocker.patch(
            "core.drf_resource.api.cmdb.get_host_by_id",
            return_value=[
                SimpleNamespace(bk_host_id=456, bk_host_innerip="127.0.0.1", bk_host_innerip_v6=""),
                SimpleNamespace(bk_host_id=457, bk_host_innerip="", bk_host_innerip_v6="fd00::9"),
            ],
        ),
        "report_tool": mocker.patch("apm_web.profile.active_collection.handlers.custom_report_tool"),
        "profile_datasource": profile_datasource,
    }


def decode_cli_config(call):
    """作业平台传输层 base64 之内还有一层 base64，才是脚本读到的 $1"""
    return json.loads(base64.b64decode(base64.b64decode(call.kwargs["script_param"])))


def sent_events(report_tool):
    return [call.args[0][0] for call in report_tool.return_value.send_data_by_http.call_args_list]


def event_content(event):
    return json.loads(event["event"]["content"])


def test_submit_immediate_task_dispatches_one_job_per_host(immediate_apis):
    assert (
        SubmitTaskResource().request({**IMMEDIATE_TASK_SUBMIT_REQUEST, "target_config": TWO_HOSTS_TARGET_CONFIG})
        is None
    )

    job_calls = immediate_apis["job"].call_args_list
    assert [call.kwargs["target_server"] for call in job_calls] == [{"host_id_list": [456]}, {"host_id_list": [457]}]
    kwargs = job_calls[0].kwargs
    assert (kwargs["bk_scope_type"], kwargs["bk_scope_id"], kwargs["account_alias"]) == ("biz", 2, "root")
    assert base64.b64decode(kwargs["script_content"]).decode() == (
        'echo "$1" | base64 -d | /usr/local/gse/plugins/bin/bkmonitorbeat '
        "-c /usr/local/gse/plugins/etc/bkmonitorbeat.conf -active-profile-run\n"
    )
    assert decode_cli_config(job_calls[0]) == {
        "bk_tenant_id": "system",
        "bk_biz_id": 2,
        "bk_host_id": 456,
        "name": "java-cpu-daily",
        "creator": "admin",
        "schedule": IMMEDIATE_SCHEDULE,
        "collection_method": "java",
        "collection_type": "java_cpu",
        "process_selector": {"type": "pid_file", "pid_path": "/var/run/demo.pid"},
        "collector_config": TASK_SUBMIT_REQUEST["collector_config"],
        "resource_guard_config": RESOURCE_GUARD_CONFIG,
        "event_data_id": 555,
        "profile_data_id": 777,
        "profile_app_name": BUILTIN_PROFILING_APP_NAME,
        "profile_service_name": "active_allocation",
    }
    assert decode_cli_config(job_calls[1])["bk_host_id"] == 457


def test_submit_immediate_task_reports_started_event_per_host(immediate_apis):
    SubmitTaskResource().request({**IMMEDIATE_TASK_SUBMIT_REQUEST, "target_config": TWO_HOSTS_TARGET_CONFIG})

    immediate_apis["report_tool"].assert_called_with(555)
    assert immediate_apis["report_tool"].return_value.send_data_by_http.call_args.args[1] == "event-token"
    assert immediate_apis["report_tool"].return_value.send_data_by_http.call_args.kwargs == {"parallel": False}

    first, second = sent_events(immediate_apis["report_tool"])
    assert first["event_name"] == "active_profiling_started"
    assert (first["target"], second["target"]) == ("127.0.0.1", "fd00::9")
    assert first["dimension"] == {
        "bk_tenant_id": "system",
        "bk_biz_id": "2",
        "task_name": "java-cpu-daily",
        "creator": "admin",
        "bk_host_id": "456",
        "schedule_type": "immediate",
        "scheduled_at": "1788310800000",
        "collection_method": "java",
        "collection_type": "java_cpu",
        "status": "running",
    }
    content = event_content(first)
    assert content == {
        "schema_version": 1,
        "started_at": first["timestamp"],
        "job": {"job_instance_id": 1456, "step_instance_id": 2456},
        "config": {
            "schedule": IMMEDIATE_SCHEDULE,
            "target_config": {"node_type": "INSTANCE", "nodes": [{"bk_host_id": 456}]},
            "process_selector": TASK_SUBMIT_REQUEST["process_selector"],
            "collector_config": TASK_SUBMIT_REQUEST["collector_config"],
            "resource_guard_config": RESOURCE_GUARD_CONFIG,
        },
    }


@pytest.mark.parametrize(
    ("process_selector", "cli_selector"),
    [
        (
            {"type": "pid", "config": {"pids": "2341;2342"}},
            {"type": "pid", "pids": "2341;2342"},
        ),
        (
            {"type": "pid_file", "config": {"pid_path": "/var/run/a.pid;/var/run/b.pid"}},
            {"type": "pid_file", "pid_path": "/var/run/a.pid;/var/run/b.pid"},
        ),
        # 关闭动态采集时 host_pids 原样下发到每台主机，由采集端按本机 bk_host_id 取用
        (
            STATIC_COMMAND_SELECTOR,
            {
                "type": "command",
                "match_pattern": "/data/order-api",
                "exclude_pattern": "",
                "enable_dynamic_collection": False,
                "host_pids": [{"bk_host_id": 456, "pid": 2341}, {"bk_host_id": 456, "pid": 2342}],
            },
        ),
    ],
)
def test_submit_immediate_sends_same_selector_to_every_target(immediate_apis, process_selector, cli_selector):
    SubmitTaskResource().request(
        {
            **IMMEDIATE_TASK_SUBMIT_REQUEST,
            "target_config": TWO_HOSTS_TARGET_CONFIG,
            "process_selector": process_selector,
        }
    )

    job_calls = immediate_apis["job"].call_args_list
    assert [call.kwargs["target_server"] for call in job_calls] == [{"host_id_list": [456]}, {"host_id_list": [457]}]
    assert [decode_cli_config(call)["process_selector"] for call in job_calls] == [cli_selector] * 2
    # Event 快照保持页面提交的结构，每台主机写入同一份
    assert [
        event_content(event)["config"]["process_selector"] for event in sent_events(immediate_apis["report_tool"])
    ] == [process_selector] * 2


def test_submit_immediate_golang_task_omits_process_selector(immediate_apis):
    SubmitTaskResource().request(GOLANG_TASK_SUBMIT_REQUEST)

    assert "process_selector" not in decode_cli_config(immediate_apis["job"].call_args)
    assert "process_selector" not in event_content(sent_events(immediate_apis["report_tool"])[0])["config"]


def test_submit_immediate_job_failure_reports_failed_finished_and_continues(immediate_apis):
    submit_job = immediate_apis["job"].side_effect

    def fail_first_host(**kwargs):
        if kwargs["target_server"]["host_id_list"] == [456]:
            raise BKAPIError(system_name="bk-job", url="", result={"message": "agent not ready"})
        return submit_job(**kwargs)

    immediate_apis["job"].side_effect = fail_first_host

    assert (
        SubmitTaskResource().request({**IMMEDIATE_TASK_SUBMIT_REQUEST, "target_config": TWO_HOSTS_TARGET_CONFIG})
        is None
    )

    failed, started = sent_events(immediate_apis["report_tool"])
    assert (failed["event_name"], failed["dimension"]["status"]) == ("active_profiling_finished", "failed")
    assert not {"process_names", "process_pids"} & set(failed["dimension"])
    content = event_content(failed)
    assert content["started_at"] == content["finished_at"] == failed["timestamp"]
    assert (content["execution_duration_ms"], content["processes"]) == (0, [])
    assert "agent not ready" in content["message"]
    assert (started["event_name"], started["dimension"]["bk_host_id"]) == ("active_profiling_started", "457")


def test_submit_immediate_event_report_failure_does_not_block_other_hosts(immediate_apis):
    immediate_apis["report_tool"].return_value.send_data_by_http.side_effect = ConnectionError("proxy down")

    assert (
        SubmitTaskResource().request({**IMMEDIATE_TASK_SUBMIT_REQUEST, "target_config": TWO_HOSTS_TARGET_CONFIG})
        is None
    )

    assert immediate_apis["job"].call_count == 2


def test_submit_immediate_requires_enabled_event_group(immediate_apis):
    immediate_apis["event_group"].return_value = []

    with pytest.raises(ValueError):
        SubmitTaskResource().request(IMMEDIATE_TASK_SUBMIT_REQUEST)

    immediate_apis["job"].assert_not_called()


def test_submit_immediate_requires_enabled_profile_datasource(immediate_apis):
    immediate_apis["profile_datasource"].objects.filter.return_value.first.return_value = None

    with pytest.raises(ValueError):
        SubmitTaskResource().request(IMMEDIATE_TASK_SUBMIT_REQUEST)

    immediate_apis["job"].assert_not_called()


def test_submit_immediate_leaves_target_empty_when_host_query_fails(immediate_apis):
    immediate_apis["hosts"].side_effect = BKAPIError(system_name="cmdb", url="", result={})

    SubmitTaskResource().request(IMMEDIATE_TASK_SUBMIT_REQUEST)

    assert sent_events(immediate_apis["report_tool"])[0]["target"] == ""


def test_submit_immediate_task_keeps_user_input_out_of_the_script(immediate_apis):
    injection = '"; rm -rf / #'
    SubmitTaskResource().request(
        {
            **IMMEDIATE_TASK_SUBMIT_REQUEST,
            "name": injection,
            "process_selector": {
                "type": "command",
                "config": {"match_pattern": injection, "exclude_pattern": "", "enable_dynamic_collection": True},
            },
        }
    )

    kwargs = immediate_apis["job"].call_args.kwargs
    assert injection not in base64.b64decode(kwargs["script_content"]).decode()
    shell_visible_param = base64.b64decode(kwargs["script_param"]).decode()
    assert set(shell_visible_param) <= set(string.ascii_letters + string.digits + "+/=")


@pytest.fixture
def planned_apis(mocker):
    """计划下发只替换 DataID 与节点管理接口，新建的订阅 ID 从 9001 递增"""
    mocker.patch("apm_web.profile.active_collection.handlers.get_request_tenant_id", return_value="system")
    profile_datasource = mocker.patch("apm_web.profile.active_collection.handlers.ProfileDataSource")
    profile_datasource.objects.filter.return_value.first.return_value.bk_data_id = 777
    subscription_ids = itertools.count(9001)
    return {
        "event_group": mocker.patch(
            "core.drf_resource.api.metadata.single_query_event_group",
            return_value=[{"bk_data_id": 555, "token": "event-token"}],
        ),
        "create": mocker.patch(
            "core.drf_resource.api.node_man.create_subscription",
            side_effect=lambda **kwargs: {"subscription_id": next(subscription_ids)},
        ),
        "update": mocker.patch("core.drf_resource.api.node_man.update_subscription"),
        "switch": mocker.patch("core.drf_resource.api.node_man.switch_subscription"),
        "run": mocker.patch("core.drf_resource.api.node_man.run_subscription"),
        "profile_datasource": profile_datasource,
    }


@pytest.fixture
def nodeman_apis(planned_apis, mocker):
    """下发用例不连库，计划回写换成空操作"""
    mocker.patch.object(ActiveProfilingTask, "save")
    return planned_apis


def planned_task(task_id, bk_host_ids=(456,), is_enabled=True, subscription_id=0, **overrides):
    """不落库的计划，id 即下发给 Beat 的 task_id"""
    config = {
        **TASK_SUBMIT_REQUEST,
        "target_config": {"node_type": "INSTANCE", "nodes": [{"bk_host_id": bk_host_id} for bk_host_id in bk_host_ids]},
        **overrides,
    }
    return ActiveProfilingTask(
        id=task_id,
        bk_biz_id=2,
        is_enabled=is_enabled,
        subscription_id=subscription_id,
        create_user="admin",
        **{field: config.get(field, {}) for field in ActiveProfilingTask.CONFIG_FIELDS},
    )


def beat_task(task_id, bk_host_id=456, **overrides):
    """下发给 Beat 的单机 task：立即执行的单机配置再加 task_id"""
    return {
        "task_id": task_id,
        "bk_tenant_id": "system",
        "bk_biz_id": 2,
        "bk_host_id": bk_host_id,
        "name": TASK_SUBMIT_REQUEST["name"],
        "creator": "admin",
        "schedule": TASK_SUBMIT_REQUEST["schedule"],
        "collection_method": "java",
        "collection_type": "java_cpu",
        "process_selector": {"type": "pid_file", "pid_path": "/var/run/demo.pid"},
        "collector_config": TASK_SUBMIT_REQUEST["collector_config"],
        "resource_guard_config": RESOURCE_GUARD_CONFIG,
        "event_data_id": 555,
        "profile_data_id": 777,
        "profile_app_name": BUILTIN_PROFILING_APP_NAME,
        "profile_service_name": "active_allocation",
        **overrides,
    }


def sent_host_tasks(call):
    return call.kwargs["steps"][0]["params"]["context"]["host_tasks"]


def create_planned_task(**overrides):
    SubmitTaskResource().request({**TASK_SUBMIT_REQUEST, **overrides})
    return ActiveProfilingTask.objects.get(bk_biz_id=2, name=overrides.get("name", TASK_SUBMIT_REQUEST["name"]))


@pytest.mark.django_db
def test_submit_planned_task_persists_full_config(planned_apis):
    assert SubmitTaskResource().request(TASK_SUBMIT_REQUEST) is None

    task = ActiveProfilingTask.objects.get(bk_biz_id=2, name="java-cpu-daily")
    assert task.collection_method == "java"
    assert task.collection_type == "java_cpu"
    assert task.schedule == TASK_SUBMIT_REQUEST["schedule"]
    assert task.process_selector == TASK_SUBMIT_REQUEST["process_selector"]
    assert task.resource_guard_config == RESOURCE_GUARD_CONFIG
    assert task.deployment_status == "success"
    assert task.is_enabled


@pytest.mark.django_db
def test_submit_immediate_task_creates_no_row(immediate_apis):
    assert SubmitTaskResource().request(GOLANG_TASK_SUBMIT_REQUEST) is None

    assert not ActiveProfilingTask.objects.exists()


@pytest.mark.django_db
def test_submit_golang_task_stores_empty_process_selector(planned_apis):
    SubmitTaskResource().request(GOLANG_PLANNED_TASK_SUBMIT_REQUEST)

    assert ActiveProfilingTask.objects.get(name="go-cpu-once").process_selector == {}


@pytest.mark.django_db
def test_submit_rejects_duplicated_name_in_same_biz(planned_apis):
    create_planned_task()

    with pytest.raises(ValueError):
        SubmitTaskResource().request(TASK_SUBMIT_REQUEST)


@pytest.mark.django_db
def test_submit_allows_same_name_in_other_biz(planned_apis):
    create_planned_task()
    SubmitTaskResource().request({**TASK_SUBMIT_REQUEST, "bk_biz_id": 3})

    assert ActiveProfilingTask.objects.filter(name=TASK_SUBMIT_REQUEST["name"]).count() == 2


@pytest.mark.django_db
def test_list_tasks_returns_created_task(planned_apis, mocker):
    mocker.patch("apm_web.profile.active_collection.resources.time.time", return_value=1788310800)
    task = create_planned_task()

    result = ListTasksResource().request({"bk_biz_id": 2, "page": 1, "page_size": 20})

    assert result["columns"] == TASK_LIST_COLUMNS
    assert (result["page"], result["page_size"], result["total"]) == (1, 20, 1)
    assert result["data"] == [
        {
            "task_id": task.id,
            "task_status": "enabled",
            "deployment_status": "success",
            "creator": task.create_user,
            "updated_at": int(task.update_time.timestamp() * 1000),
            "name": "java-cpu-daily",
            "collection_method": "java",
            "collection_type": "java_cpu",
            "target_config": TASK_SUBMIT_REQUEST["target_config"],
            "process_selector": TASK_SUBMIT_REQUEST["process_selector"],
            "schedule": TASK_SUBMIT_REQUEST["schedule"],
            "collector_config": TASK_SUBMIT_REQUEST["collector_config"],
            "resource_guard_config": RESOURCE_GUARD_CONFIG,
        }
    ]


@pytest.mark.parametrize(
    ("deployment_status", "schedule", "now_sec", "expected"),
    [
        ("success", TASK_SUBMIT_REQUEST["schedule"], 1788915600 + 1, "outdate"),
        (
            "success",
            {"type": "once_at", "execute_at": 1788310800000, "timezone": "Asia/Shanghai"},
            1788310800 + 1,
            "outdate",
        ),
        (
            "success",
            {"type": "cron", "cron_expression": "0 */2 * * *", "timezone": "Asia/Shanghai"},
            1788915600 + 1,
            "success",
        ),
        ("failed", TASK_SUBMIT_REQUEST["schedule"], 1788915600 + 1, "failed"),
        ("deploying", {"type": "once_at", "execute_at": 1788310800000}, 1788310800 + 1, "deploying"),
    ],
)
def test_list_tasks_displays_expired_only_for_finished_successful_schedules(
    mocker, deployment_status, schedule, now_sec, expected
):
    mocker.patch("apm_web.profile.active_collection.resources.time.time", return_value=now_sec)
    task = SimpleNamespace(deployment_status=deployment_status, schedule=schedule)

    assert ListTasksResource._display_deployment_status(task) == expected


@pytest.mark.django_db
def test_list_tasks_paginates_and_isolates_biz(planned_apis):
    create_planned_task()
    create_planned_task(name="java-cpu-hourly")
    create_planned_task(bk_biz_id=3, name="other-biz")

    result = ListTasksResource().request({"bk_biz_id": 2, "page": 2, "page_size": 1})

    assert result["total"] == 2
    assert len(result["data"]) == 1


@pytest.mark.django_db
def test_edit_task_updates_in_place_and_resets_deployment_status(planned_apis):
    task = create_planned_task()
    ActiveProfilingTask.objects.filter(id=task.id).update(deployment_status="failed")

    EditTaskResource().request({**TASK_SUBMIT_REQUEST, "task_id": task.id, "name": "java-cpu-hourly"})

    task.refresh_from_db()
    assert task.name == "java-cpu-hourly"
    assert task.deployment_status == "success"
    assert ActiveProfilingTask.objects.count() == 1


@pytest.mark.django_db
def test_edit_task_keeps_its_own_name(planned_apis):
    task = create_planned_task()

    EditTaskResource().request({**TASK_SUBMIT_REQUEST, "task_id": task.id, "collector_config": {"duration_sec": 60}})

    task.refresh_from_db()
    assert task.collector_config == {"duration_sec": 60}


@pytest.mark.django_db
def test_edit_task_rejects_other_task_name(planned_apis):
    task = create_planned_task()
    create_planned_task(name="java-cpu-hourly")

    with pytest.raises(ValueError):
        EditTaskResource().request({**TASK_SUBMIT_REQUEST, "task_id": task.id, "name": "java-cpu-hourly"})


@pytest.mark.django_db
def test_switch_task_toggles_status(planned_apis):
    task = create_planned_task()

    SwitchTaskResource().request({"bk_biz_id": 2, "task_id": task.id, "enabled": False})

    task.refresh_from_db()
    assert not task.is_enabled
    assert task.deployment_status == "success"
    assert planned_apis["run"].call_args.kwargs["actions"] == {"bkmonitorbeat_active_profile": "STOP"}


@pytest.mark.django_db
def test_delete_task_requires_disabled_first(planned_apis):
    task = create_planned_task()

    with pytest.raises(ValueError):
        DeleteTaskResource().request({"bk_biz_id": 2, "task_id": task.id})

    assert ActiveProfilingTask.objects.filter(id=task.id).exists()


@pytest.mark.django_db
def test_delete_task_soft_deletes_and_frees_name(planned_apis):
    task = create_planned_task()
    SwitchTaskResource().request({"bk_biz_id": 2, "task_id": task.id, "enabled": False})

    DeleteTaskResource().request({"bk_biz_id": 2, "task_id": task.id})

    assert planned_apis["run"].call_args.kwargs["actions"] == {"bkmonitorbeat_active_profile": "UNINSTALL_AND_DELETE"}
    assert not ActiveProfilingTask.objects.filter(id=task.id).exists()
    assert ActiveProfilingTask.origin_objects.filter(id=task.id, is_deleted=True).exists()
    create_planned_task()


@pytest.mark.django_db
def test_task_operations_reject_other_biz_task(planned_apis):
    task = create_planned_task()

    with pytest.raises(ValueError):
        SwitchTaskResource().request({"bk_biz_id": 3, "task_id": task.id, "enabled": False})


@pytest.mark.django_db
def test_each_planned_task_owns_subscription(planned_apis):
    first = create_planned_task()
    second = create_planned_task(name="java-cpu-hourly")

    assert (first.subscription_id, second.subscription_id) == (9001, 9002)
    created_task_ids = [sent_host_tasks(call)["456"][0]["task_id"] for call in planned_apis["create"].call_args_list]
    assert created_task_ids == [first.id, second.id]
    planned_apis["update"].assert_not_called()


def test_nodeman_deploy_creates_subscription_for_new_task(nodeman_apis):
    task = planned_task(1)

    assert ActiveProfilingNodeManHandler(2).deploy(task) is True

    kwargs = nodeman_apis["create"].call_args.kwargs
    assert kwargs["bk_tenant_id"] == "system"
    assert kwargs["scope"] == {
        "bk_biz_id": 2,
        "object_type": "HOST",
        "node_type": "INSTANCE",
        "nodes": [{"bk_host_id": 456}],
    }
    assert kwargs["run_immediately"] is True
    step = kwargs["steps"][0]
    assert (step["id"], step["type"]) == ("bkmonitorbeat_active_profile", "PLUGIN")
    assert step["config"] == {
        "plugin_name": "bkmonitorbeat",
        "plugin_version": "0.0.4",
        "config_templates": [{"name": "bkmonitorbeat_active_profile.conf", "version": "latest"}],
    }
    assert step["params"]["context"] == {"host_tasks": {"456": [beat_task(1)]}}
    assert task.subscription_id == 9001
    nodeman_apis["switch"].assert_called_once_with(bk_tenant_id="system", subscription_id=9001, action="enable")
    nodeman_apis["update"].assert_not_called()
    assert task.deployment_status == "success"


def test_nodeman_deploy_puts_all_hosts_into_one_subscription(nodeman_apis):
    task = planned_task(
        1,
        bk_host_ids=(456, 457),
        process_selector={"type": "pid", "config": {"pids": "2341;2342"}},
    )

    ActiveProfilingNodeManHandler(2).deploy(task)

    nodeman_apis["create"].assert_called_once()
    assert nodeman_apis["create"].call_args.kwargs["scope"]["nodes"] == [{"bk_host_id": 456}, {"bk_host_id": 457}]
    assert sent_host_tasks(nodeman_apis["create"].call_args) == {
        "456": [beat_task(1, process_selector={"type": "pid", "pids": "2341;2342"})],
        "457": [beat_task(1, bk_host_id=457, process_selector={"type": "pid", "pids": "2341;2342"})],
    }


@pytest.mark.parametrize(("is_enabled", "run_immediately"), [(True, True), (False, False)])
def test_nodeman_deploy_updates_existing_subscription(nodeman_apis, is_enabled, run_immediately):
    task = planned_task(1, is_enabled=is_enabled, subscription_id=8001)

    ActiveProfilingNodeManHandler(2).deploy(task)

    nodeman_apis["create"].assert_not_called()
    kwargs = nodeman_apis["update"].call_args.kwargs
    assert (kwargs["bk_tenant_id"], kwargs["subscription_id"]) == ("system", 8001)
    # 停用中的计划只更新订阅内容，不能把配置推回主机
    assert kwargs["run_immediately"] is run_immediately


def test_nodeman_deploy_failure_marks_task_failed(nodeman_apis):
    task = planned_task(1)
    nodeman_apis["create"].side_effect = BKAPIError(system_name="bk-nodeman", url="", result={"message": "failed"})

    assert ActiveProfilingNodeManHandler(2).deploy(task) is False

    assert task.subscription_id == 0
    nodeman_apis["switch"].assert_not_called()
    assert task.deployment_status == "failed"


@pytest.mark.parametrize(
    ("is_enabled", "switch_action", "run_action"), [(True, "enable", "START"), (False, "disable", "STOP")]
)
def test_nodeman_switch_starts_or_stops_subscription(nodeman_apis, is_enabled, switch_action, run_action):
    task = planned_task(1, is_enabled=is_enabled, subscription_id=8001)

    assert ActiveProfilingNodeManHandler(2).switch(task) is True

    nodeman_apis["switch"].assert_called_once_with(bk_tenant_id="system", subscription_id=8001, action=switch_action)
    nodeman_apis["run"].assert_called_once_with(
        bk_tenant_id="system", subscription_id=8001, actions={"bkmonitorbeat_active_profile": run_action}
    )
    nodeman_apis["update"].assert_not_called()
    assert task.deployment_status == "success"


def test_nodeman_switch_creates_missing_subscription(nodeman_apis):
    task = planned_task(1)

    ActiveProfilingNodeManHandler(2).switch(task)

    nodeman_apis["create"].assert_called_once()
    nodeman_apis["run"].assert_not_called()
    assert task.subscription_id == 9001


def test_nodeman_uninstall_removes_config_and_subscription(nodeman_apis):
    task = planned_task(1, is_enabled=False, subscription_id=8001)

    assert ActiveProfilingNodeManHandler(2).uninstall(task) is True

    nodeman_apis["switch"].assert_called_once_with(bk_tenant_id="system", subscription_id=8001, action="disable")
    nodeman_apis["run"].assert_called_once_with(
        bk_tenant_id="system", subscription_id=8001, actions={"bkmonitorbeat_active_profile": "UNINSTALL_AND_DELETE"}
    )


def test_nodeman_uninstall_skips_task_without_subscription(nodeman_apis):
    assert ActiveProfilingNodeManHandler(2).uninstall(planned_task(1, is_enabled=False)) is True

    nodeman_apis["switch"].assert_not_called()
    nodeman_apis["run"].assert_not_called()


def test_submit_planned_task_requires_enabled_biz_before_persisting(planned_apis, mocker):
    planned_apis["profile_datasource"].objects.filter.return_value.first.return_value = None
    create_task = mocker.patch.object(ActiveProfilingTask, "create_task")

    with pytest.raises(ValueError):
        SubmitTaskResource().request(TASK_SUBMIT_REQUEST)

    create_task.assert_not_called()
    planned_apis["create"].assert_not_called()


def test_edit_task_updates_subscription_to_new_hosts(nodeman_apis, mocker):
    task = planned_task(1, subscription_id=8001)
    mocker.patch.object(ActiveProfilingTask, "get_task", return_value=task)
    mocker.patch.object(ActiveProfilingTask, "check_duplicated_name")

    EditTaskResource().request(
        {
            **TASK_SUBMIT_REQUEST,
            "task_id": 1,
            "target_config": {"node_type": "INSTANCE", "nodes": [{"bk_host_id": 457}]},
        }
    )

    # 移出范围的主机由节点管理移除本订阅的配置文件
    assert nodeman_apis["update"].call_args.kwargs["scope"]["nodes"] == [{"bk_host_id": 457}]
    assert sent_host_tasks(nodeman_apis["update"].call_args) == {"457": [beat_task(1, bk_host_id=457)]}


def test_delete_task_keeps_row_when_nodeman_uninstall_fails(nodeman_apis, mocker):
    task = planned_task(1, is_enabled=False, subscription_id=8001)
    nodeman_apis["run"].side_effect = BKAPIError(system_name="bk-nodeman", url="", result={})
    mocker.patch.object(ActiveProfilingTask, "get_task", return_value=task)
    delete = mocker.patch.object(ActiveProfilingTask, "delete")

    with pytest.raises(ValueError):
        DeleteTaskResource().request({"bk_biz_id": 2, "task_id": 1})

    delete.assert_not_called()
    assert task.deployment_status == "failed"


STOP_NOW_MS = 1788411900000
ONE_DAY_MS = 24 * 3600 * 1000


@pytest.fixture
def expired_task_apis(nodeman_apis, mocker):
    """定时清理不连库：查询返回下面填入的计划，时间固定在 STOP_NOW_MS"""
    mocker.patch("apm_web.tasks.time").time.return_value = STOP_NOW_MS / 1000
    mocker.patch("apm_web.tasks.bk_biz_id_to_bk_tenant_id", return_value="system")
    objects = mocker.patch.object(ActiveProfilingTask, "objects")
    tasks = []
    objects.filter.return_value.exclude.return_value = tasks
    return {
        **nodeman_apis,
        "objects": objects,
        "tasks": tasks,
        "set_tenant": mocker.patch("apm_web.tasks.set_local_tenant_id"),
    }


def once_at_task(task_id, execute_at):
    schedule = {"type": "once_at", "execute_at": execute_at, "timezone": "Asia/Shanghai"}
    return planned_task(task_id, subscription_id=8000 + task_id, schedule=schedule)


def cron_task(task_id, **schedule_overrides):
    schedule = {**TASK_SUBMIT_REQUEST["schedule"], **schedule_overrides}
    return planned_task(task_id, subscription_id=8000 + task_id, schedule=schedule)


def test_stop_expired_tasks_disables_tasks_one_day_after_last_run(expired_task_apis):
    endless_schedule = {k: v for k, v in TASK_SUBMIT_REQUEST["schedule"].items() if k != "effective_end_at"}
    expired_task_apis["tasks"].extend(
        [
            once_at_task(1, STOP_NOW_MS - ONE_DAY_MS - 1),
            cron_task(2, effective_end_at=STOP_NOW_MS - ONE_DAY_MS - 1),
            once_at_task(3, STOP_NOW_MS - ONE_DAY_MS + 1),
            planned_task(4, subscription_id=8004, schedule=endless_schedule),
        ]
    )

    stop_expired_active_profiling_tasks()

    # 最后一次执行过去 1 天的计划走手动停用的同一流程；没设生效结束时间的 cron 一直有效
    assert [task.is_enabled for task in expired_task_apis["tasks"]] == [False, False, True, True]
    assert [call.kwargs["subscription_id"] for call in expired_task_apis["switch"].call_args_list] == [8001, 8002]
    assert {call.kwargs["action"] for call in expired_task_apis["switch"].call_args_list} == {"disable"}
    assert [call.kwargs for call in expired_task_apis["run"].call_args_list] == [
        {
            "bk_tenant_id": "system",
            "subscription_id": subscription_id,
            "actions": {"bkmonitorbeat_active_profile": "STOP"},
        }
        for subscription_id in (8001, 8002)
    ]
    assert [task.deployment_status for task in expired_task_apis["tasks"][:2]] == ["outdate", "outdate"]
    # 停用失败的计划保持部署失败，第二天再试；订阅没建成的计划不处理
    expired_task_apis["objects"].filter.assert_called_once_with(Q(is_enabled=True) | Q(deployment_status="failed"))
    expired_task_apis["objects"].filter.return_value.exclude.assert_called_once_with(subscription_id=0)
    # 同一业务只设置一次租户、构造一次 handler
    expired_task_apis["set_tenant"].assert_called_once_with("system")
    expired_task_apis["event_group"].assert_called_once()


def test_stop_expired_tasks_skips_biz_that_cannot_init(expired_task_apis):
    expired_task_apis["event_group"].side_effect = lambda bk_biz_id, event_group_name: (
        [] if bk_biz_id == 2 else [{"bk_data_id": 555, "token": "event-token"}]
    )
    not_enabled_biz_task = once_at_task(1, STOP_NOW_MS - 2 * ONE_DAY_MS)
    other_biz_task = once_at_task(2, STOP_NOW_MS - 2 * ONE_DAY_MS)
    other_biz_task.bk_biz_id = 3
    expired_task_apis["tasks"].extend([not_enabled_biz_task, other_biz_task])

    stop_expired_active_profiling_tasks()

    assert (not_enabled_biz_task.is_enabled, other_biz_task.is_enabled) == (True, False)
    assert [call.kwargs["subscription_id"] for call in expired_task_apis["run"].call_args_list] == [8002]


HOST_QUERY_NOW = 1788411900000
RETENTION_DAYS = 7
EXPIRE_BEFORE = HOST_QUERY_NOW - RETENTION_DAYS * 24 * 3600 * 1000
# 采集时长上限 300 秒 + unknown 判定的 300 秒
UNKNOWN_WINDOW_MS = 600 * 1000


def active_event(
    event_name, content, status, bk_host_id=456, target="127.0.0.1", scheduled_at=1788411800000, task_id=None
):
    """按 ES 返回形态构造一条 Event，dimension 都是字符串"""
    dimensions = {
        "bk_tenant_id": "system",
        "bk_biz_id": "2",
        "task_name": "native-cpu" if task_id is None else "java-cpu-daily",
        "creator": "admin",
        "bk_host_id": str(bk_host_id),
        "schedule_type": "immediate" if task_id is None else "cron",
        "scheduled_at": str(scheduled_at),
        "collection_method": "perf",
        "collection_type": "native_cpu",
        "status": status,
    }
    if task_id is not None:
        dimensions["task_id"] = str(task_id)
    return {
        "event_name": event_name,
        "target": target,
        "dimensions": dimensions,
        "event": {"content": json.dumps({"schema_version": 1, **content})},
    }


def host_config(bk_host_id=456, collector_config=None, process_selector=TASK_SUBMIT_REQUEST["process_selector"]):
    """Event 里的配置快照只含当机，Golang 不带 process_selector"""
    config = {
        "schedule": IMMEDIATE_SCHEDULE,
        "target_config": {"node_type": "INSTANCE", "nodes": [{"bk_host_id": bk_host_id}]},
        "collector_config": collector_config or {"duration_sec": 30},
        "resource_guard_config": RESOURCE_GUARD_CONFIG,
    }
    if process_selector:
        config["process_selector"] = process_selector
    return config


def started_event(started_at, config=None, **kwargs):
    content = {"started_at": started_at, "config": config or host_config(kwargs.get("bk_host_id", 456))}
    return active_event("active_profiling_started", content, "running", **kwargs)


def finished_event(status, started_at, finished_at, processes=(), config=None, message="", **kwargs):
    content = {
        "started_at": started_at,
        "finished_at": finished_at,
        "execution_duration_ms": finished_at - started_at,
        "config": config or host_config(kwargs.get("bk_host_id", 456)),
        "processes": list(processes),
        "message": message,
    }
    return active_event("active_profiling_finished", content, status, **kwargs)


def with_filters(**filters):
    return {**EVENT_LIST_REQUEST, "filters": {**EVENT_LIST_REQUEST["filters"], **filters}}


@pytest.fixture
def host_query_apis(mocker):
    mocker.patch("apm_web.profile.active_collection.handlers.get_request_tenant_id", return_value="system")
    mocker.patch("apm_web.profile.active_collection.handlers.time").time.return_value = HOST_QUERY_NOW / 1000
    profile_datasource = mocker.patch("apm_web.profile.active_collection.handlers.ProfileDataSource")
    profile_datasource.objects.filter.return_value.first.return_value = SimpleNamespace(
        bk_data_id=777, retention=RETENTION_DAYS
    )
    # 按 ES 排序后的结果，查询按 offset/limit 切片返回
    events = []

    def query(table_id, query_body):
        return events[query_body["offset"] : query_body["offset"] + query_body["limit"]]

    return {
        "events": events,
        "query": mocker.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", side_effect=query),
        "event_group": mocker.patch(
            "core.drf_resource.api.metadata.single_query_event_group",
            return_value=[{"table_id": "2_bkmonitor_event_555"}],
        ),
        "profile_datasource": profile_datasource,
    }


def sent_query_bodies(query):
    return [call.kwargs["query_body"] for call in query.call_args_list]


def test_query_hosts_pairs_events_into_host_execution_rows(host_query_apis):
    host_query_apis["events"].extend(
        [
            started_event(1788411801000, bk_host_id=458, target="127.0.0.3"),
            finished_event(
                "succeed",
                1788310801000,
                1788310832000,
                processes=[{"pid": 1234, "process_name": "java"}],
                task_id=123,
                scheduled_at=1788310800000,
            ),
            started_event(1788310801000, task_id=123, scheduled_at=1788310800000),
            started_event(1788210801000, bk_host_id=457, target="127.0.0.2", scheduled_at=1788210800000),
            finished_event(
                "partial_succeed", EXPIRE_BEFORE - 999, EXPIRE_BEFORE - 500, scheduled_at=EXPIRE_BEFORE - 1000
            ),
        ]
    )

    result = QueryHostsResource().request(EVENT_LIST_REQUEST)

    assert result["columns"] == HOST_QUERY_COLUMNS
    assert result["data"][:2] == [
        {
            "bk_host_id": 458,
            "ip": "127.0.0.3",
            "processes": [],
            "task": {"name": "native-cpu", "schedule_type": "immediate"},
            "collection_method": "perf",
            "collection_type": "native_cpu",
            "creator": "admin",
            "scheduled_at": 1788411800000,
            "started_at": 1788411801000,
            "finished_at": None,
            "duration_ms": None,
            "status": "running",
        },
        {
            "bk_host_id": 456,
            "ip": "127.0.0.1",
            "processes": [{"pid": 1234, "process_name": "java"}],
            "task": {"task_id": 123, "name": "java-cpu-daily", "schedule_type": "cron"},
            "collection_method": "perf",
            "collection_type": "native_cpu",
            "creator": "admin",
            "scheduled_at": 1788310800000,
            "started_at": 1788310801000,
            "finished_at": 1788310832000,
            "duration_ms": 31000,
            "status": "succeed",
        },
    ]
    # 只有 started 且超过“采集时长 + 300 秒”为 unknown；成功结果按 scheduled_at 超过保留期为 outdate
    assert [row["status"] for row in result["data"][2:]] == ["unknown", "outdate"]
    assert result["data"][3]["finished_at"] == EXPIRE_BEFORE - 500


def test_query_hosts_uses_latest_duplicated_event(host_query_apis):
    host_query_apis["events"].extend(
        [
            finished_event("failed", 1788411801000, 1788411802000),
            finished_event("succeed", 1788411801000, 1788411832000),
        ]
    )

    assert [row["status"] for row in QueryHostsResource().request(EVENT_LIST_REQUEST)["data"]] == ["failed"]


def test_query_hosts_treats_omitted_processes_as_empty(host_query_apis):
    event = finished_event("failed", 1788411801000, 1788411801100)
    content = json.loads(event["event"]["content"])
    # 旧版采集端没拿到进程时省略 processes 字段
    del content["processes"]
    event["event"]["content"] = json.dumps(content)
    host_query_apis["events"].append(event)

    assert QueryHostsResource().request(EVENT_LIST_REQUEST)["data"][0]["processes"] == []


@pytest.mark.parametrize(("elapsed_ms", "status"), [(300 * 1000, "running"), (300 * 1000 + 1, "unknown")])
def test_query_hosts_counts_go_heap_duration_as_zero(host_query_apis, elapsed_ms, status):
    host_query_apis["events"].append(
        started_event(
            HOST_QUERY_NOW - elapsed_ms, config=host_config(collector_config={"ip_address": "127.0.0.1", "port": 6060})
        )
    )

    assert QueryHostsResource().request(EVENT_LIST_REQUEST)["data"][0]["status"] == status


def test_query_hosts_pushes_filters_down_to_es(host_query_apis):
    QueryHostsResource().request(
        with_filters(
            ips=["127.0.0.1"],
            task_name="cpu",
            process_names=["my,app", "java"],
            process_pids=["1234"],
            schedule_types=["cron"],
            collection_methods=["perf"],
            collection_types=["native_cpu"],
            status="failed",
        )
    )

    (query_body,) = sent_query_bodies(host_query_apis["query"])
    query_config = query_body["query_configs"][0]
    assert query_config["table"] == "2_bkmonitor_event_555"
    assert query_config["filter_dict"] == {
        "bk_tenant_id": "system",
        "bk_biz_id": 2,
        "event_name": ["active_profiling_started", "active_profiling_finished"],
        "target__include": ["127.0.0.1"],
        # 同一筛选项的多个值命中任一即可，查询词里的逗号按采集端归一化为 _
        "process_names__include": ["my_app", "java"],
        "process_pids__include": ["1234"],
        "task_name__include": "cpu",
        "schedule_type": ["cron"],
        "collection_method": ["perf"],
        "collection_type": ["native_cpu"],
        "status": "failed",
        "scheduled_at__gte": EVENT_LIST_REQUEST["start_time"],
        "scheduled_at__lte": EVENT_LIST_REQUEST["end_time"],
    }
    assert query_config["where"] == []
    assert query_body["order_by"] == [
        "-dimensions.scheduled_at",
        "dimensions.schedule_type",
        "dimensions.task_id",
        "dimensions.bk_host_id",
        "event_name",
        "-time",
    ]
    # 行按 scheduled_at 选取，窗口末尾执行的 finished 可能晚于 end_time 上报
    assert (query_body["start_time"], query_body["end_time"]) == (
        EVENT_LIST_REQUEST["start_time"],
        EVENT_LIST_REQUEST["end_time"] + UNKNOWN_WINDOW_MS,
    )


def test_query_hosts_skips_empty_filters(host_query_apis):
    QueryHostsResource().request(EVENT_LIST_REQUEST)

    (query_body,) = sent_query_bodies(host_query_apis["query"])
    assert set(query_body["query_configs"][0]["filter_dict"]) == {
        "bk_tenant_id",
        "bk_biz_id",
        "event_name",
        "scheduled_at__gte",
        "scheduled_at__lte",
    }
    assert query_body["query_configs"][0]["where"] == []


@pytest.mark.parametrize(
    ("status", "status_filter", "scheduled_at_range"),
    [
        ("succeed", "succeed", (EXPIRE_BEFORE, EVENT_LIST_REQUEST["end_time"])),
        ("partial_succeed", "partial_succeed", (EXPIRE_BEFORE, EVENT_LIST_REQUEST["end_time"])),
        ("outdate", ["succeed", "partial_succeed"], (EVENT_LIST_REQUEST["start_time"], EXPIRE_BEFORE - 1)),
        ("running", None, (HOST_QUERY_NOW - UNKNOWN_WINDOW_MS, EVENT_LIST_REQUEST["end_time"])),
    ],
)
def test_query_hosts_narrows_scheduled_at_for_derived_status(
    host_query_apis, status, status_filter, scheduled_at_range
):
    QueryHostsResource().request(with_filters(status=status))

    filter_dict = sent_query_bodies(host_query_apis["query"])[0]["query_configs"][0]["filter_dict"]
    assert filter_dict.get("status") == status_filter
    assert (filter_dict["scheduled_at__gte"], filter_dict["scheduled_at__lte"]) == scheduled_at_range


def test_query_hosts_running_filter_skips_finished_rows(host_query_apis):
    host_query_apis["events"].extend(
        [
            finished_event("succeed", 1788411801000, 1788411832000, bk_host_id=457),
            started_event(1788411801000, bk_host_id=457),
            started_event(1788411801000, bk_host_id=458),
        ]
    )

    result = QueryHostsResource().request(with_filters(status="running"))

    assert [(row["bk_host_id"], row["status"]) for row in result["data"]] == [(458, "running")]


def test_query_hosts_rejects_unknown_status_filter(host_query_apis):
    with pytest.raises(ValueError):
        QueryHostsResource().request(with_filters(status="unknown"))

    host_query_apis["query"].assert_not_called()


def test_query_hosts_paginates_by_rows(host_query_apis):
    host_query_apis["events"].extend(
        started_event(1788411801000, bk_host_id=bk_host_id) for bk_host_id in range(456, 461)
    )

    result = QueryHostsResource().request({**EVENT_LIST_REQUEST, "offset": 1, "limit": 2})

    assert [row["bk_host_id"] for row in result["data"]] == [457, 458]
    # 首批按每行最多两条事件估算：2 * (offset + limit) + 1
    assert [(body["offset"], body["limit"]) for body in sent_query_bodies(host_query_apis["query"])] == [(0, 7)]


def test_query_hosts_reads_next_batch_until_last_row_is_complete(host_query_apis, mocker):
    mocker.patch("apm_web.profile.active_collection.resources.EVENT_QUERY_BATCH_SIZE", 2)
    host_query_apis["events"].extend(
        [
            finished_event("succeed", 1788411801000, 1788411832000),
            finished_event("failed", 1788411801000, 1788411802000),
            started_event(1788411801000),
            started_event(1788411801000, bk_host_id=457),
        ]
    )

    result = QueryHostsResource().request({**EVENT_LIST_REQUEST, "limit": 1})

    assert [(row["bk_host_id"], row["status"]) for row in result["data"]] == [(456, "succeed")]
    # 首批 3 条都属于第一行，要读到下一行的事件才能确认第一行已完整
    assert [(body["offset"], body["limit"]) for body in sent_query_bodies(host_query_apis["query"])] == [
        (0, 3),
        (3, 2),
    ]


def test_query_hosts_rejects_when_scanned_events_exceed_limit(host_query_apis, mocker):
    mocker.patch("apm_web.profile.active_collection.handlers.EVENT_QUERY_MAX_SIZE", 4)
    host_query_apis["events"].extend(
        finished_event("succeed", 1788411801000, 1788411832000, bk_host_id=bk_host_id) for bk_host_id in range(456, 462)
    )

    with pytest.raises(ValueError):
        QueryHostsResource().request({**EVENT_LIST_REQUEST, "limit": 5})


def test_query_hosts_requires_enabled_event_group(host_query_apis):
    host_query_apis["event_group"].return_value = []

    with pytest.raises(ValueError):
        QueryHostsResource().request(EVENT_LIST_REQUEST)

    host_query_apis["query"].assert_not_called()


def test_query_hosts_requires_enabled_profile_datasource(host_query_apis):
    host_query_apis["profile_datasource"].objects.filter.return_value.first.return_value = None

    with pytest.raises(ValueError):
        QueryHostsResource().request(EVENT_LIST_REQUEST)

    host_query_apis["query"].assert_not_called()


def es_filtered_query(events):
    """按 IP、进程名、PID 的包含条件与 scheduled_at 过滤后再分页，任务历史两段查询只依赖这几项筛选"""

    def query(table_id, query_body):
        filter_dict = query_body["query_configs"][0]["filter_dict"]

        def contains(value, fragments):
            return not fragments or any(fragment in value for fragment in fragments)

        matched = [
            event
            for event in events
            if contains(event["target"], filter_dict.get("target__include"))
            and contains(event["dimensions"].get("process_names", ""), filter_dict.get("process_names__include"))
            and contains(event["dimensions"].get("process_pids", ""), filter_dict.get("process_pids__include"))
            and event["dimensions"]["scheduled_at"]
            in filter_dict.get("scheduled_at", [event["dimensions"]["scheduled_at"]])
        ]
        return matched[query_body["offset"] : query_body["offset"] + query_body["limit"]]

    return query


def test_list_executions_aggregates_all_hosts_into_execution_rows(host_query_apis):
    expired_scheduled_at = EXPIRE_BEFORE - 1000
    host_query_apis["events"].extend(
        [
            finished_event("succeed", 1788411801000, 1788411832000),
            started_event(1788411801000),
            started_event(1788411802000, bk_host_id=457, target="127.0.0.2"),
            finished_event("succeed", 1788310801000, 1788310832000, task_id=123, scheduled_at=1788310800000),
            finished_event(
                "failed",
                1788310801000,
                1788310840000,
                bk_host_id=457,
                target="127.0.0.2",
                task_id=123,
                scheduled_at=1788310800000,
            ),
            finished_event(
                "succeed",
                expired_scheduled_at + 1000,
                expired_scheduled_at + 31000,
                scheduled_at=expired_scheduled_at,
            ),
        ]
    )

    result = ListExecutionsResource().request(EVENT_LIST_REQUEST)

    assert result["task_columns"] == EXECUTION_LIST_TASK_COLUMNS
    # immediate 不返回 task_id；仍有主机运行时外层不结束
    assert result["data"][:2] == [
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
            "status_summary": {"succeed": 1, "running": 1},
            "target_count": 2,
            "hosts": [{"bk_host_id": 456, "ip": "127.0.0.1"}, {"bk_host_id": 457, "ip": "127.0.0.2"}],
        },
        {
            "task_id": 123,
            "task_name": "java-cpu-daily",
            "schedule_type": "cron",
            "scheduled_at": 1788310800000,
            "collection_method": "perf",
            "collection_type": "native_cpu",
            "creator": "admin",
            "started_at": 1788310801000,
            "finished_at": 1788310840000,
            "duration_ms": 39000,
            "execution_status": "partial_succeed",
            "status_summary": {"succeed": 1, "failed": 1},
            "target_count": 2,
            "hosts": [{"bk_host_id": 456, "ip": "127.0.0.1"}, {"bk_host_id": 457, "ip": "127.0.0.2"}],
        },
    ]
    assert (result["data"][2]["execution_status"], result["data"][2]["status_summary"]) == (
        "outdate",
        {"outdate": 1},
    )
    # 没有主机/进程筛选时一次扫描，首批至少读一整批
    (query_body,) = sent_query_bodies(host_query_apis["query"])
    assert (query_body["offset"], query_body["limit"]) == (0, 500)


def test_list_executions_pushes_execution_filters_down_to_es(host_query_apis):
    ListExecutionsResource().request(
        with_filters(
            task_name="cpu",
            schedule_types=["cron"],
            collection_methods=["perf"],
            collection_types=["native_cpu"],
            status="failed",
        )
    )

    (query_body,) = sent_query_bodies(host_query_apis["query"])
    query_config = query_body["query_configs"][0]
    # 执行状态由全部主机汇总，不能按主机的 status 维度筛
    assert query_config["filter_dict"] == {
        "bk_tenant_id": "system",
        "bk_biz_id": 2,
        "event_name": ["active_profiling_started", "active_profiling_finished"],
        "task_name__include": "cpu",
        "schedule_type": ["cron"],
        "collection_method": ["perf"],
        "collection_type": ["native_cpu"],
        "scheduled_at__gte": EVENT_LIST_REQUEST["start_time"],
        "scheduled_at__lte": EVENT_LIST_REQUEST["end_time"],
    }
    assert query_config["where"] == []
    assert (query_body["start_time"], query_body["end_time"]) == (
        EVENT_LIST_REQUEST["start_time"],
        EVENT_LIST_REQUEST["end_time"] + UNKNOWN_WINDOW_MS,
    )


@pytest.mark.parametrize(
    ("status", "scheduled_at_range"),
    [
        ("succeed", (EXPIRE_BEFORE, EVENT_LIST_REQUEST["end_time"])),
        ("partial_succeed", (EXPIRE_BEFORE, EVENT_LIST_REQUEST["end_time"])),
        ("outdate", (EVENT_LIST_REQUEST["start_time"], EXPIRE_BEFORE - 1)),
        ("running", (HOST_QUERY_NOW - UNKNOWN_WINDOW_MS, EVENT_LIST_REQUEST["end_time"])),
        ("failed", (EVENT_LIST_REQUEST["start_time"], EVENT_LIST_REQUEST["end_time"])),
    ],
)
def test_list_executions_narrows_scheduled_at_for_status(host_query_apis, status, scheduled_at_range):
    ListExecutionsResource().request(with_filters(status=status))

    filter_dict = sent_query_bodies(host_query_apis["query"])[0]["query_configs"][0]["filter_dict"]
    assert "status" not in filter_dict
    assert (filter_dict["scheduled_at__gte"], filter_dict["scheduled_at__lte"]) == scheduled_at_range


def test_list_executions_filters_aggregated_status_in_memory(host_query_apis):
    host_query_apis["events"].extend(
        [
            started_event(1788411801000),
            finished_event("succeed", 1788310801000, 1788310832000, task_id=123, scheduled_at=1788310800000),
            finished_event(
                "failed", 1788310801000, 1788310840000, bk_host_id=457, task_id=123, scheduled_at=1788310800000
            ),
            finished_event("succeed", 1788210801000, 1788210832000, scheduled_at=1788210800000),
        ]
    )

    result = ListExecutionsResource().request(with_filters(status="partial_succeed"))

    assert [(row["scheduled_at"], row["execution_status"]) for row in result["data"]] == [
        (1788310800000, "partial_succeed")
    ]


def test_list_executions_rejects_unknown_status_filter(host_query_apis):
    with pytest.raises(ValueError):
        ListExecutionsResource().request(with_filters(status="unknown"))

    host_query_apis["query"].assert_not_called()


def test_list_executions_paginates_by_execution_rows(host_query_apis):
    scheduled_ats = [1788411800000 - index * 1000 for index in range(5)]
    host_query_apis["events"].extend(
        started_event(scheduled_at + 1000, scheduled_at=scheduled_at) for scheduled_at in scheduled_ats
    )

    result = ListExecutionsResource().request({**EVENT_LIST_REQUEST, "offset": 1, "limit": 2})

    assert [row["scheduled_at"] for row in result["data"]] == scheduled_ats[1:3]
    assert [(body["offset"], body["limit"]) for body in sent_query_bodies(host_query_apis["query"])] == [(0, 500)]


def test_list_executions_reads_next_batch_until_last_execution_is_complete(host_query_apis, mocker):
    mocker.patch("apm_web.profile.active_collection.resources.EXECUTION_QUERY_BATCH_SIZE", 2)
    for bk_host_id in (456, 457, 458):
        host_query_apis["events"].extend(
            [
                finished_event("succeed", 1788411801000, 1788411832000, bk_host_id=bk_host_id),
                started_event(1788411801000, bk_host_id=bk_host_id),
            ]
        )
    host_query_apis["events"].append(started_event(1788310801000, scheduled_at=1788310800000))

    result = ListExecutionsResource().request({**EVENT_LIST_REQUEST, "limit": 1})

    assert [(row["scheduled_at"], row["target_count"]) for row in result["data"]] == [(1788411800000, 3)]
    # 首批按 2 * 行数 + 1 估算；要读到下一次执行的 Event 才能确认第一次执行的主机已经完整
    assert [(body["offset"], body["limit"]) for body in sent_query_bodies(host_query_apis["query"])] == [
        (0, 3),
        (3, 2),
        (5, 2),
    ]


@pytest.mark.parametrize("filters", [{"ips": ["127.0.0.2"]}, {"process_names": ["jav"]}, {"process_pids": ["81"]}])
def test_list_executions_selects_by_host_then_aggregates_all_hosts(host_query_apis, filters):
    matched_host = finished_event(
        "failed",
        1788411801000,
        1788411802000,
        processes=[{"pid": 812, "process_name": "java"}],
        bk_host_id=457,
        target="127.0.0.2",
    )
    matched_host["dimensions"].update(process_names="java", process_pids="812")
    events = [
        # 同一毫秒的另一次执行，回查时按执行键排除
        finished_event("succeed", 1788411801000, 1788411832000, bk_host_id=458, target="127.0.0.3", task_id=123),
        finished_event("succeed", 1788411801000, 1788411832000),
        matched_host,
        finished_event("succeed", 1788310801000, 1788310832000, scheduled_at=1788310800000),
    ]
    host_query_apis["query"].side_effect = es_filtered_query(events)

    result = ListExecutionsResource().request(with_filters(**filters))

    # 主机/进程只决定选中哪些执行，汇总仍基于该执行的全部主机
    assert [
        (row["scheduled_at"], row["execution_status"], row["status_summary"], row["target_count"])
        for row in result["data"]
    ] == [(1788411800000, "partial_succeed", {"succeed": 1, "failed": 1}, 2)]
    select_body, fetch_body = sent_query_bodies(host_query_apis["query"])
    assert (select_body["offset"], select_body["limit"]) == (0, 500)
    fetch_config = fetch_body["query_configs"][0]
    # 回查不带主机级筛选
    assert not {"target__include", "process_names__include", "process_pids__include"} & set(fetch_config["filter_dict"])
    assert fetch_config["filter_dict"]["scheduled_at"] == ["1788411800000"]
    assert (fetch_body["offset"], fetch_body["limit"]) == (0, 10000)


def test_list_executions_skips_fetch_when_no_execution_matches_host(host_query_apis):
    host_query_apis["query"].side_effect = es_filtered_query([finished_event("succeed", 1788411801000, 1788411832000)])

    assert ListExecutionsResource().request(with_filters(ips=["127.0.1.10"]))["data"] == []
    assert host_query_apis["query"].call_count == 1


def test_list_executions_fetches_only_current_page_when_selecting_by_host(host_query_apis):
    scheduled_ats = [1788411800000 - index * 1000 for index in range(3)]
    host_query_apis["query"].side_effect = es_filtered_query(
        [
            finished_event(
                "succeed", scheduled_at + 1000, scheduled_at + 31000, target="127.0.0.2", scheduled_at=scheduled_at
            )
            for scheduled_at in scheduled_ats
        ]
    )

    result = ListExecutionsResource().request({**with_filters(ips=["127.0.0.2"]), "offset": 1, "limit": 1})

    assert [row["scheduled_at"] for row in result["data"]] == [scheduled_ats[1]]
    # 不筛状态时每个命中的执行就是一行，offset 之前的执行不用回查
    fetch_body = sent_query_bodies(host_query_apis["query"])[1]
    assert fetch_body["query_configs"][0]["filter_dict"]["scheduled_at"] == [str(scheduled_ats[1])]


def test_list_executions_keeps_selecting_until_status_filter_fills_page(host_query_apis):
    host_query_apis["query"].side_effect = es_filtered_query(
        [
            finished_event("succeed", 1788411801000, 1788411832000, target="127.0.0.2"),
            finished_event("failed", 1788410801000, 1788410802000, target="127.0.0.2", scheduled_at=1788410800000),
            finished_event("failed", 1788409801000, 1788409802000, target="127.0.0.2", scheduled_at=1788409800000),
        ]
    )

    result = ListExecutionsResource().request({**with_filters(ips=["127.0.0.2"], status="failed"), "limit": 2})

    assert [row["scheduled_at"] for row in result["data"]] == [1788410800000, 1788409800000]
    # 回查后才知道执行状态，第一轮只命中一行，再接着找还缺的一个执行
    assert [
        body["query_configs"][0]["filter_dict"]["scheduled_at"]
        for body in sent_query_bodies(host_query_apis["query"])[1:]
    ] == [["1788411800000", "1788410800000"], ["1788409800000"]]
    # 多轮查询共用同一个事件表 ID
    host_query_apis["event_group"].assert_called_once()


def test_list_executions_rejects_when_fetched_events_exceed_limit(host_query_apis, mocker):
    mocker.patch("apm_web.profile.active_collection.resources.EVENT_QUERY_MAX_SIZE", 2)
    host_query_apis["query"].side_effect = es_filtered_query(
        [
            finished_event("succeed", 1788411801000, 1788411832000),
            finished_event("failed", 1788411801000, 1788411802000, bk_host_id=457, target="127.0.0.2"),
        ]
    )

    with pytest.raises(ValueError):
        ListExecutionsResource().request(with_filters(ips=["127.0.0.2"]))


TOPK_REQUEST = {
    "bk_biz_id": 2,
    "start_time": EVENT_LIST_REQUEST["start_time"],
    "end_time": EVENT_LIST_REQUEST["end_time"],
    "field": "task_name",
}


def test_topk_counts_field_values_with_event_topk_query(host_query_apis):
    # 按事件检索 TopK 的分组计数结果返回，已按事件数倒序
    host_query_apis["events"].extend(
        [
            {"task_name": "java-cpu-daily", "_result_": 4},
            {"task_name": "native-cpu", "_result_": 2},
            {"task_name": "", "_result_": 1},
        ]
    )

    result = QueryTopKResource().request({**TOPK_REQUEST, "limit": 3})

    # 空值不作为候选
    assert result == [
        {"value": "java-cpu-daily", "alias": "java-cpu-daily", "count": 4},
        {"value": "native-cpu", "alias": "native-cpu", "count": 2},
    ]
    (query_body,) = sent_query_bodies(host_query_apis["query"])
    query_config = query_body["query_configs"][0]
    assert (query_config["group_by"], query_config["metrics"]) == (
        ["task_name"],
        [{"field": "task_name", "method": "COUNT", "alias": "a"}],
    )
    # 与两个列表一样按 scheduled_at 选取
    assert query_config["filter_dict"] == {
        "bk_tenant_id": "system",
        "bk_biz_id": 2,
        "event_name": ["active_profiling_started", "active_profiling_finished"],
        "scheduled_at__gte": EVENT_LIST_REQUEST["start_time"],
        "scheduled_at__lte": EVENT_LIST_REQUEST["end_time"],
    }
    assert (query_body["start_time"], query_body["end_time"], query_body["limit"]) == (
        EVENT_LIST_REQUEST["start_time"],
        EVENT_LIST_REQUEST["end_time"] + UNKNOWN_WINDOW_MS,
        3,
    )


def test_topk_splits_process_names_and_counts_each_execution_once(host_query_apis):
    host_query_apis["events"].extend(
        [
            {"process_names": "java,java,nginx", "_result_": 3},
            {"process_names": "", "_result_": 5},
            {"process_names": "java", "_result_": 2},
        ]
    )

    result = QueryTopKResource().request({**TOPK_REQUEST, "field": "process_names"})

    assert result == [
        {"value": "java", "alias": "java", "count": 5},
        {"value": "nginx", "alias": "nginx", "count": 3},
    ]
    # 要取全时间范围的取值组合才能拆开计数
    (query_body,) = sent_query_bodies(host_query_apis["query"])
    assert (query_body["query_configs"][0]["group_by"], query_body["limit"]) == (["process_names"], 10000)


def test_topk_pairs_pids_with_process_names_by_position(host_query_apis):
    host_query_apis["events"].extend(
        [
            {"process_names": "java,nginx", "process_pids": "1234,812", "_result_": 2},
            {"process_names": "", "process_pids": "", "_result_": 4},
            {"process_names": "python", "process_pids": "1234", "_result_": 1},
        ]
    )

    result = QueryTopKResource().request({**TOPK_REQUEST, "field": "process_pids"})

    # 同一 PID 在不同主机上可能是不同进程，按进程名分开展示，点选后都按 PID 筛选
    assert result == [
        {"value": "1234", "alias": "java:1234", "count": 2},
        {"value": "812", "alias": "nginx:812", "count": 2},
        {"value": "1234", "alias": "python:1234", "count": 1},
    ]
    (query_body,) = sent_query_bodies(host_query_apis["query"])
    query_config = query_body["query_configs"][0]
    assert (query_config["group_by"], query_config["metrics"][0]["field"]) == (
        ["process_names", "process_pids"],
        "process_pids",
    )


def test_topk_rejects_when_process_groups_exceed_limit(host_query_apis, mocker):
    mocker.patch("apm_web.profile.active_collection.handlers.EVENT_QUERY_MAX_SIZE", 2)
    host_query_apis["events"].extend(
        [{"process_names": "java", "_result_": 2}, {"process_names": "nginx", "_result_": 1}]
    )

    with pytest.raises(ValueError):
        QueryTopKResource().request({**TOPK_REQUEST, "field": "process_names"})


IMMEDIATE_DETAIL_REQUEST = {"bk_biz_id": 2, "schedule_type": "immediate", "scheduled_at": 1788411800000}


def test_execution_detail_returns_all_hosts_of_execution(host_query_apis):
    host_query_apis["events"].extend(
        [
            finished_event("succeed", 1788411801000, 1788411832000, processes=[{"pid": 1234, "process_name": "java"}]),
            started_event(1788411802000, bk_host_id=457, target="127.0.0.2"),
        ]
    )

    result = ExecutionDetailResource().request(IMMEDIATE_DETAIL_REQUEST)

    # immediate 不返回 task_id；仍有主机运行时外层不结束
    assert result == {
        "host_columns": EXECUTION_DETAIL_HOST_COLUMNS,
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
        "status_summary": {"succeed": 1, "running": 1},
        "total_hosts": 2,
        "config": {
            **host_config(),
            "target_config": {"node_type": "INSTANCE", "nodes": [{"bk_host_id": 456}, {"bk_host_id": 457}]},
        },
        "hosts": [
            {
                "bk_host_id": 456,
                "ip": "127.0.0.1",
                "processes": [{"pid": 1234, "process_name": "java"}],
                "status": "succeed",
                "message": "",
                "started_at": 1788411801000,
                "finished_at": 1788411832000,
                "duration_ms": 31000,
            },
            {
                "bk_host_id": 457,
                "ip": "127.0.0.2",
                "processes": [],
                "status": "running",
                "message": "",
                "started_at": 1788411802000,
                "finished_at": None,
                "duration_ms": None,
            },
        ],
    }
    filter_dict = sent_query_bodies(host_query_apis["query"])[0]["query_configs"][0]["filter_dict"]
    assert (filter_dict["schedule_type"], "task_id" in filter_dict) == ("immediate", False)


def test_execution_detail_locates_planned_execution_by_task(host_query_apis):
    host_query_apis["events"].extend(
        [
            finished_event("succeed", 1788310801000, 1788310832000, task_id=123, scheduled_at=1788310800000),
            finished_event(
                "failed",
                1788310801000,
                1788310840000,
                message="Profiling 发送失败",
                bk_host_id=457,
                target="127.0.0.2",
                task_id=123,
                scheduled_at=1788310800000,
            ),
        ]
    )

    result = ExecutionDetailResource().request(EXECUTION_DETAIL_REQUEST)

    assert (result["task_id"], result["task_name"], result["schedule_type"]) == (123, "java-cpu-daily", "cron")
    assert (result["execution_status"], result["status_summary"]) == ("partial_succeed", {"succeed": 1, "failed": 1})
    # 外层从最早开始的主机算到最晚结束的主机
    assert (result["started_at"], result["finished_at"], result["duration_ms"]) == (
        1788310801000,
        1788310840000,
        39000,
    )
    assert result["hosts"][1]["message"] == "Profiling 发送失败"

    (query_body,) = sent_query_bodies(host_query_apis["query"])
    assert query_body["query_configs"][0]["filter_dict"] == {
        "bk_tenant_id": "system",
        "bk_biz_id": 2,
        "event_name": ["active_profiling_started", "active_profiling_finished"],
        "schedule_type": "cron",
        "scheduled_at": 1788310800000,
        "task_id": 123,
    }
    assert (query_body["offset"], query_body["limit"]) == (0, 10000)
    # 迟到的 finished 也要取到，窗口放到当前
    assert (query_body["start_time"], query_body["end_time"]) == (
        1788310800000 - UNKNOWN_WINDOW_MS,
        HOST_QUERY_NOW + UNKNOWN_WINDOW_MS,
    )


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["succeed", "running"], "running"),
        (["unknown", "running"], "running"),
        (["cancelled", "cancelled"], "cancelled"),
        (["unknown"], "unknown"),
        (["succeed", "partial_succeed"], "partial_succeed"),
        (["succeed", "failed"], "partial_succeed"),
        (["partial_succeed", "unknown"], "partial_succeed"),
        (["outdate", "failed"], "outdate"),
        (["failed", "timeout", "cancelled"], "failed"),
        (["unknown", "failed"], "failed"),
    ],
)
def test_execution_detail_aggregates_host_statuses(statuses, expected):
    assert ActiveProfilingEventQueryHandler._aggregate_status(statuses) == expected


def test_execution_detail_marks_expired_execution_outdate(host_query_apis):
    scheduled_at = EXPIRE_BEFORE - 1000
    host_query_apis["events"].extend(
        [
            finished_event("succeed", scheduled_at + 1000, scheduled_at + 31000, scheduled_at=scheduled_at),
            finished_event(
                "failed", scheduled_at + 1000, scheduled_at + 2000, bk_host_id=457, scheduled_at=scheduled_at
            ),
        ]
    )

    result = ExecutionDetailResource().request({**IMMEDIATE_DETAIL_REQUEST, "scheduled_at": scheduled_at})

    assert (result["execution_status"], result["status_summary"]) == ("outdate", {"outdate": 1, "failed": 1})


def test_execution_detail_returns_selector_as_submitted(host_query_apis):
    host_query_apis["events"].extend(
        [
            finished_event(
                "succeed", 1788411801000, 1788411832000, config=host_config(process_selector=STATIC_COMMAND_SELECTOR)
            ),
            finished_event(
                "succeed",
                1788411801000,
                1788411832000,
                config=host_config(457, process_selector=STATIC_COMMAND_SELECTOR),
                bk_host_id=457,
            ),
        ]
    )

    config = ExecutionDetailResource().request(IMMEDIATE_DETAIL_REQUEST)["config"]

    assert config["target_config"]["nodes"] == [{"bk_host_id": 456}, {"bk_host_id": 457}]
    assert config["process_selector"] == STATIC_COMMAND_SELECTOR


def test_execution_detail_keeps_golang_config_without_selector(host_query_apis):
    golang_config = host_config(
        collector_config={"ip_address": "127.0.0.1", "port": 6060, "duration_sec": 30}, process_selector=None
    )
    host_query_apis["events"].append(finished_event("succeed", 1788411801000, 1788411832000, config=golang_config))

    assert ExecutionDetailResource().request(IMMEDIATE_DETAIL_REQUEST)["config"] == golang_config


def test_execution_detail_requires_existing_execution(host_query_apis):
    with pytest.raises(ValueError):
        ExecutionDetailResource().request(IMMEDIATE_DETAIL_REQUEST)


def test_execution_detail_rejects_when_events_exceed_limit(host_query_apis, mocker):
    mocker.patch("apm_web.profile.active_collection.handlers.EVENT_QUERY_MAX_SIZE", 2)
    host_query_apis["events"].extend(
        finished_event("succeed", 1788411801000, 1788411832000, bk_host_id=bk_host_id) for bk_host_id in (456, 457)
    )

    with pytest.raises(ValueError):
        ExecutionDetailResource().request(IMMEDIATE_DETAIL_REQUEST)


# 取消只针对仍在运行的执行，计划时间放在查询当前时刻之前一分钟
CANCEL_SCHEDULED_AT = HOST_QUERY_NOW - 60 * 1000

CANCEL_REQUEST = {
    "bk_biz_id": 2,
    "schedule_type": "cron",
    "task_id": 123,
    "scheduled_at": CANCEL_SCHEDULED_AT,
    "hosts": [{"bk_host_id": 456, "ip": "127.0.0.1"}, {"bk_host_id": 457, "ip": "127.0.0.2"}],
}


@pytest.fixture
def cancel_apis(host_query_apis, mocker):
    mocker.patch("apm_web.profile.active_collection.resources.get_request_tenant_id", return_value="system")
    return {
        **host_query_apis,
        "job": mocker.patch(
            "core.drf_resource.api.job.fast_execute_script",
            return_value={"job_instance_id": 1000, "step_instance_id": 2000},
        ),
    }


def running_cancel_event(bk_host_id=456, target="127.0.0.1", task_id=123):
    return started_event(
        CANCEL_SCHEDULED_AT + 1000,
        bk_host_id=bk_host_id,
        target=target,
        task_id=task_id,
        scheduled_at=CANCEL_SCHEDULED_AT,
    )


def test_cancel_execution_dispatches_cli_per_running_host(cancel_apis):
    cancel_apis["events"].extend([running_cancel_event(), running_cancel_event(457, "127.0.0.2")])

    assert CancelExecutionResource().request(CANCEL_REQUEST) is None

    job_calls = cancel_apis["job"].call_args_list
    assert [call.kwargs["target_server"] for call in job_calls] == [{"host_id_list": [456]}, {"host_id_list": [457]}]
    kwargs = job_calls[0].kwargs
    assert (kwargs["bk_scope_type"], kwargs["bk_scope_id"], kwargs["account_alias"]) == ("biz", 2, "root")
    assert base64.b64decode(kwargs["script_content"]).decode() == (
        'echo "$1" | base64 -d | /usr/local/gse/plugins/bin/bkmonitorbeat '
        "-c /usr/local/gse/plugins/etc/bkmonitorbeat.conf -active-profile-cancel\n"
    )
    assert decode_cli_config(job_calls[0]) == {
        "bk_tenant_id": "system",
        "bk_biz_id": 2,
        "bk_host_id": 456,
        "task_id": 123,
        "schedule_type": "cron",
        "scheduled_at": CANCEL_SCHEDULED_AT,
    }
    assert decode_cli_config(job_calls[1])["bk_host_id"] == 457
    # 只查请求主机在该次执行中的 Event
    (query_body,) = sent_query_bodies(cancel_apis["query"])
    assert query_body["query_configs"][0]["filter_dict"] == {
        "bk_tenant_id": "system",
        "bk_biz_id": 2,
        "event_name": ["active_profiling_started", "active_profiling_finished"],
        "schedule_type": "cron",
        "scheduled_at": CANCEL_SCHEDULED_AT,
        "task_id": 123,
        "bk_host_id": [456, 457],
    }


def test_cancel_execution_skips_hosts_already_finished(cancel_apis):
    cancel_apis["events"].extend(
        [
            finished_event(
                "succeed",
                CANCEL_SCHEDULED_AT + 1000,
                CANCEL_SCHEDULED_AT + 31000,
                task_id=123,
                scheduled_at=CANCEL_SCHEDULED_AT,
            ),
            running_cancel_event(),
            running_cancel_event(457, "127.0.0.2"),
        ]
    )

    CancelExecutionResource().request(CANCEL_REQUEST)

    assert [call.kwargs["target_server"] for call in cancel_apis["job"].call_args_list] == [{"host_id_list": [457]}]


def test_cancel_execution_rejects_host_outside_execution(cancel_apis):
    cancel_apis["events"].append(running_cancel_event())

    with pytest.raises(ValueError, match="127.0.0.2"):
        CancelExecutionResource().request(CANCEL_REQUEST)

    cancel_apis["job"].assert_not_called()


def test_cancel_immediate_execution_omits_task_id(cancel_apis):
    cancel_apis["events"].append(running_cancel_event(task_id=None))

    CancelExecutionResource().request(
        {
            "bk_biz_id": 2,
            "schedule_type": "immediate",
            "scheduled_at": CANCEL_SCHEDULED_AT,
            "hosts": [{"bk_host_id": 456, "ip": "127.0.0.1"}],
        }
    )

    assert "task_id" not in decode_cli_config(cancel_apis["job"].call_args)
    (query_body,) = sent_query_bodies(cancel_apis["query"])
    assert "task_id" not in query_body["query_configs"][0]["filter_dict"]


def test_cancel_execution_reports_hosts_whose_job_failed(cancel_apis):
    cancel_apis["events"].extend([running_cancel_event(), running_cancel_event(457, "127.0.0.2")])

    def fail_first_host(**kwargs):
        if kwargs["target_server"] == {"host_id_list": [456]}:
            raise BKAPIError(system_name="bk-job", url="", result={"message": "agent not ready"})
        return {"job_instance_id": 1000, "step_instance_id": 2000}

    cancel_apis["job"].side_effect = fail_first_host

    with pytest.raises(ValueError, match="127.0.0.1"):
        CancelExecutionResource().request(CANCEL_REQUEST)

    assert cancel_apis["job"].call_count == 2


RESULT_STARTED_AT = 1788411801000
RESULT_FINISHED_AT = 1788411832000
PLANNED_RESULT_REQUEST = {
    "bk_biz_id": 2,
    "scheduled_at": 1788411800000,
    "bk_host_id": 456,
    "task_id": 123,
    "started_at": RESULT_STARTED_AT,
    "finished_at": RESULT_FINISHED_AT,
    "data_type": "cpu/nanoseconds",
    "diagram_types": ["flamegraph", "table"],
}
IMMEDIATE_RESULT_REQUEST = {key: value for key, value in PLANNED_RESULT_REQUEST.items() if key != "task_id"}
# 导出不需要 diagram_types
PLANNED_EXPORT_REQUEST = {key: value for key, value in PLANNED_RESULT_REQUEST.items() if key != "diagram_types"}
IMMEDIATE_EXPORT_REQUEST = {key: value for key, value in PLANNED_EXPORT_REQUEST.items() if key != "task_id"}
# 采样类型查询只需要定位单次采集
PLANNED_DATA_TYPES_REQUEST = {key: value for key, value in PLANNED_EXPORT_REQUEST.items() if key != "data_type"}
IMMEDIATE_DATA_TYPES_REQUEST = {key: value for key, value in PLANNED_DATA_TYPES_REQUEST.items() if key != "task_id"}


def profile_sample(value, *root_to_leaf):
    """Doris 样本行，调用栈按叶子到根存储"""
    return {
        "dtEventTimeStamp": str(RESULT_STARTED_AT + 4000),
        "sample_type": "cpu/nanoseconds",
        "value": str(value),
        "stacktrace": json.dumps(
            [
                {"lines": [{"line": 1, "function": {"name": name, "systemName": name, "fileName": "demo.c"}}]}
                for name in reversed(root_to_leaf)
            ]
        ),
    }


PROFILE_SAMPLES = [profile_sample(700, "main", "work"), profile_sample(100, "main")]


@pytest.fixture
def result_apis(host_query_apis, mocker):
    profile_datasource = host_query_apis["profile_datasource"].objects.filter.return_value.first.return_value
    profile_datasource.result_table_id = "2_profile_active_profiling_builtin_1"
    return {
        **host_query_apis,
        "bkdata": mocker.patch(
            "core.drf_resource.api.bkdata.query_profile_data", return_value={"list": list(PROFILE_SAMPLES)}
        ),
    }


def sent_profile_query(bkdata):
    (call,) = bkdata.call_args_list
    return json.loads(call.kwargs["sql"])


def expected_diagrams(diagram_types):
    converter = TreeConverter()
    converter.convert({"list": PROFILE_SAMPLES})
    expected = {}
    for diagram_type in diagram_types:
        expected.update(get_diagrammer(diagram_type).draw(converter, sort="-total"))
    return {**expected, "type": "cpu", "unit": "nanoseconds"}


def test_query_planned_results_locates_samples_by_task(result_apis):
    result = QueryResultsResource().request(PLANNED_RESULT_REQUEST)

    assert result == expected_diagrams(["flamegraph", "table"])
    assert [child["name"] for child in result["flame_data"]["children"]] == ["main"]
    # 定位键和起止时间都由请求传入，不回查执行 Event
    result_apis["query"].assert_not_called()
    profile_query = sent_profile_query(result_apis["bkdata"])
    assert profile_query["result_table_id"] == "2_profile_active_profiling_builtin_1"
    api_params = profile_query["api_params"]
    assert (api_params["biz_id"], api_params["app"], api_params["service_name"]) == (
        "2",
        "active_profiling_builtin_allocation_source",
        "active_allocation",
    )
    assert api_params["label_filter"] == {"scheduled_at": "1788411800000", "bk_host_id": "456", "task_id": "123"}
    assert api_params["general_filters"] == {"sample_type": "op_eq|cpu/nanoseconds"}
    assert (api_params["start"], api_params["end"]) == (
        RESULT_STARTED_AT - RUNNING_EXECUTION_WINDOW_MS,
        RESULT_FINISHED_AT + RUNNING_EXECUTION_WINDOW_MS,
    )
    assert api_params["limit"] == {"offset": 0, "rows": 10001}


def test_query_immediate_results_locates_samples_without_task(result_apis):
    QueryResultsResource().request({**IMMEDIATE_RESULT_REQUEST, "data_type": "inuse_space/bytes"})

    api_params = sent_profile_query(result_apis["bkdata"])["api_params"]
    assert api_params["label_filter"] == {"scheduled_at": "1788411800000", "bk_host_id": "456"}
    assert api_params["general_filters"] == {"sample_type": "op_eq|inuse_space/bytes"}


@pytest.mark.parametrize("diagram_types", [["flamegraph"], ["table"]])
def test_query_results_only_return_requested_diagrams(result_apis, diagram_types):
    result = QueryResultsResource().request({**IMMEDIATE_RESULT_REQUEST, "diagram_types": diagram_types})

    assert result == expected_diagrams(diagram_types)


def test_query_results_returns_empty_when_no_samples(result_apis):
    result_apis["bkdata"].return_value = {"list": []}

    assert QueryResultsResource().request(IMMEDIATE_RESULT_REQUEST) == {}


def test_query_results_rejects_samples_over_limit(result_apis, mocker):
    mocker.patch("apm_web.profile.active_collection.handlers.NORMAL_SERVICE_MAX_QUERY_SIZE", 1)

    with pytest.raises(ValueError):
        QueryResultsResource().request(IMMEDIATE_RESULT_REQUEST)

    assert sent_profile_query(result_apis["bkdata"])["api_params"]["limit"] == {"offset": 0, "rows": 2}


def test_query_results_requires_enabled_profile_datasource(result_apis):
    result_apis["profile_datasource"].objects.filter.return_value.first.return_value = None

    with pytest.raises(ValueError):
        QueryResultsResource().request(IMMEDIATE_RESULT_REQUEST)

    result_apis["bkdata"].assert_not_called()


def test_query_result_data_types_groups_single_collection_by_sample_type(result_apis):
    result_apis["bkdata"].return_value = {
        "list": [
            {"sample_type": sample_type, "count(*)": 3}
            for sample_type in ["inuse_space/bytes", "alloc_objects/count", "inuse_objects/count", "alloc_space/bytes"]
        ]
    }

    result = QueryResultDataTypesResource().request(PLANNED_DATA_TYPES_REQUEST)

    assert result == {
        "data_types": [
            {"key": "alloc_objects/count", "name": "ALLOC_OBJECTS"},
            {"key": "alloc_space/bytes", "name": "ALLOC_SPACE"},
            {"key": "inuse_objects/count", "name": "INUSE_OBJECTS"},
            {"key": "inuse_space/bytes", "name": "INUSE_SPACE"},
        ]
    }
    profile_query = sent_profile_query(result_apis["bkdata"])
    assert profile_query["api_type"] == "select_aggregate"
    api_params = profile_query["api_params"]
    assert (api_params["dimension_fields"], api_params["metric_fields"]) == ("sample_type", "count(*)")
    assert api_params["label_filter"] == {"scheduled_at": "1788411800000", "bk_host_id": "456", "task_id": "123"}
    assert "general_filters" not in api_params
    assert (api_params["start"], api_params["end"]) == (
        RESULT_STARTED_AT - RUNNING_EXECUTION_WINDOW_MS,
        RESULT_FINISHED_AT + RUNNING_EXECUTION_WINDOW_MS,
    )


def test_query_result_data_types_reuses_profiling_count_filter(result_apis):
    result_apis["bkdata"].return_value = {
        "list": [{"sample_type": "samples/count", "count(*)": 2}, {"sample_type": "cpu/nanoseconds", "count(*)": 2}]
    }

    result = QueryResultDataTypesResource().request(IMMEDIATE_DATA_TYPES_REQUEST)

    assert result == {"data_types": [{"key": "cpu/nanoseconds", "name": "CPU"}]}
    assert sent_profile_query(result_apis["bkdata"])["api_params"]["label_filter"] == {
        "scheduled_at": "1788411800000",
        "bk_host_id": "456",
    }


def test_query_result_data_types_returns_empty_when_no_samples(result_apis):
    result_apis["bkdata"].return_value = {"list": []}

    assert QueryResultDataTypesResource().request(IMMEDIATE_DATA_TYPES_REQUEST) == {"data_types": []}


def export_profile_sample(value, *root_to_leaf):
    """带齐 pprof 转换字段的 Doris 样本行"""
    return {
        "dtEventTimeStamp": str(RESULT_STARTED_AT + 4000),
        "sample_type": "cpu/nanoseconds",
        "period_type": "cpu/nanoseconds",
        "period": 10000000,
        "value": str(value),
        "stacktrace": json.dumps(
            [
                {
                    "mapping": None,
                    "address": 1,
                    "isFolded": False,
                    "lines": [
                        {
                            "line": 1,
                            "function": {
                                "name": name,
                                "systemName": name,
                                "fileName": "demo.c",
                                "startLine": 1,
                            },
                        }
                    ],
                }
                for name in reversed(root_to_leaf)
            ]
        ),
    }


def test_export_returns_gzip_pprof(result_apis):
    samples = [export_profile_sample(700, "main", "work"), export_profile_sample(100, "main")]
    result_apis["bkdata"].return_value = {"list": samples}

    response = ExportResultsResource().request(PLANNED_EXPORT_REQUEST)

    assert isinstance(response, HttpResponse)
    assert response["Content-Type"] == "application/octet-stream"
    assert response["Content-Encoding"] == "gzip"
    disposition = response["Content-Disposition"]
    assert disposition.startswith('attachment; filename="active_profiling_builtin_allocation_source-cpu/nanoseconds-')
    assert disposition.endswith('.pprof"')
    converter = DorisProfileConverter()
    converter.convert(
        {"list": samples},
        agg_interval=ProfileQueryViewSet.get_agg_interval(
            RESULT_STARTED_AT - RUNNING_EXECUTION_WINDOW_MS,
            RESULT_FINISHED_AT + RUNNING_EXECUTION_WINDOW_MS,
        ),
    )
    assert gzip.decompress(response.content) == converter.profile.SerializeToString()
    result_apis["query"].assert_not_called()
    api_params = sent_profile_query(result_apis["bkdata"])["api_params"]
    assert api_params["label_filter"] == {"scheduled_at": "1788411800000", "bk_host_id": "456", "task_id": "123"}
    assert (api_params["biz_id"], api_params["app"], api_params["service_name"]) == (
        "2",
        "active_profiling_builtin_allocation_source",
        "active_allocation",
    )
    assert (api_params["start"], api_params["end"]) == (
        RESULT_STARTED_AT - RUNNING_EXECUTION_WINDOW_MS,
        RESULT_FINISHED_AT + RUNNING_EXECUTION_WINDOW_MS,
    )
    assert api_params["limit"] == {"offset": 0, "rows": 10001}


def test_export_rejects_empty_samples(result_apis):
    result_apis["bkdata"].return_value = {"list": []}

    with pytest.raises(ValueError, match="无法导出"):
        ExportResultsResource().request(IMMEDIATE_EXPORT_REQUEST)


def test_export_rejects_samples_over_limit(result_apis, mocker):
    mocker.patch("apm_web.profile.active_collection.handlers.NORMAL_SERVICE_MAX_QUERY_SIZE", 1)

    with pytest.raises(ValueError, match="无法完整查看或导出"):
        ExportResultsResource().request(IMMEDIATE_EXPORT_REQUEST)


@pytest.mark.parametrize(
    "viewset_cls",
    [
        ActiveProfilingMetaConfigViewSet,
        EnableViewSet,
        ProcessesViewSet,
        TasksViewSet,
        HostsViewSet,
        ExecutionsListViewSet,
        TopKViewSet,
        ExecutionsViewSet,
        ResultsViewSet,
    ],
)
def test_viewsets_require_business_permission(viewset_cls):
    viewset = viewset_cls()
    viewset.request = APIRequestFactory().get("/")
    viewset.action = "list"

    assert [type(permission) for permission in viewset.get_permissions()] == [ViewBusinessPermission]


def test_active_collection_routes_are_registered():
    assert reverse("apm_web:active_profiling_meta_config-list") == (
        "/apm/profile_api/active_collection/active_profiling_meta_config/"
    )
    assert reverse("apm_web:enable-list") == "/apm/profile_api/active_collection/enable/"
    assert reverse("apm_web:tasks-list") == "/apm/profile_api/active_collection/tasks/"
    assert reverse("apm_web:tasks-edit") == "/apm/profile_api/active_collection/tasks/edit/"
    assert reverse("apm_web:tasks-delete") == "/apm/profile_api/active_collection/tasks/delete/"
    assert reverse("apm_web:tasks-switch") == "/apm/profile_api/active_collection/tasks/switch/"
    assert reverse("apm_web:processes-preview") == "/apm/profile_api/active_collection/processes/preview/"
    assert reverse("apm_web:hosts-query") == "/apm/profile_api/active_collection/hosts/query/"
    assert reverse("apm_web:executions_list-list") == "/apm/profile_api/active_collection/executions/list/"
    assert reverse("apm_web:topk-list") == "/apm/profile_api/active_collection/topk/"
    assert reverse("apm_web:executions-detail") == "/apm/profile_api/active_collection/executions/detail/"
    assert reverse("apm_web:executions-cancel") == "/apm/profile_api/active_collection/executions/cancel/"
    assert reverse("apm_web:results-query") == "/apm/profile_api/active_collection/results/query/"
    assert reverse("apm_web:results-data-types") == "/apm/profile_api/active_collection/results/data_types/"
    assert reverse("apm_web:results-export") == "/apm/profile_api/active_collection/results/export/"


@pytest.mark.parametrize(
    ("serializer_cls", "params"),
    [
        (EnableRequestSerializer, {"bk_biz_id": 2}),
        (ProcessPreviewRequestSerializer, PROCESS_PREVIEW_REQUEST),
        (
            ProcessPreviewRequestSerializer,
            {
                **PROCESS_PREVIEW_REQUEST,
                "process_selector": {"type": "pid_file", "config": {"pid_path": "/var/run/demo.pid"}},
            },
        ),
        (
            ProcessPreviewRequestSerializer,
            {
                **PROCESS_PREVIEW_REQUEST,
                "process_selector": {"type": "pid", "config": {"pids": "2341"}},
            },
        ),
        (TaskSubmitRequestSerializer, TASK_SUBMIT_REQUEST),
        (
            TaskSubmitRequestSerializer,
            {
                **TASK_SUBMIT_REQUEST,
                "process_selector": {"type": "pid", "config": {"pids": " 2341; 2342;"}},
            },
        ),
        (TaskSubmitRequestSerializer, {**TASK_SUBMIT_REQUEST, "process_selector": DYNAMIC_COMMAND_SELECTOR}),
        (TaskSubmitRequestSerializer, {**TASK_SUBMIT_REQUEST, "process_selector": STATIC_COMMAND_SELECTOR}),
        (
            TaskSubmitRequestSerializer,
            {
                **TASK_SUBMIT_REQUEST,
                "process_selector": {"type": "pid_file", "config": {"pid_path": "/var/run/a.pid; /var/run/b.pid"}},
            },
        ),
        (TaskSubmitRequestSerializer, GOLANG_TASK_SUBMIT_REQUEST),
        (PlannedTaskSubmitRequestSerializer, TASK_SUBMIT_REQUEST),
        (TaskEditRequestSerializer, {**TASK_SUBMIT_REQUEST, "task_id": 123}),
        (EventListRequestSerializer, EVENT_LIST_REQUEST),
        (TopKRequestSerializer, TOPK_REQUEST),
        (TopKRequestSerializer, {**TOPK_REQUEST, "field": "process_pids", "limit": 5}),
        (ExecutionDetailRequestSerializer, EXECUTION_DETAIL_REQUEST),
        (
            ExecutionDetailRequestSerializer,
            {"bk_biz_id": 2, "schedule_type": "immediate", "scheduled_at": 1788310800000},
        ),
        (ExecutionCancelRequestSerializer, CANCEL_REQUEST),
        (
            ExecutionCancelRequestSerializer,
            {
                "bk_biz_id": 2,
                "schedule_type": "immediate",
                "scheduled_at": 1788310800000,
                "hosts": [{"bk_host_id": 456, "ip": "127.0.0.1"}],
            },
        ),
        (ResultQueryRequestSerializer, RESULT_QUERY_REQUEST),
        (ResultQueryRequestSerializer, {**PLANNED_RESULT_REQUEST, "data_type": "inuse_space/bytes"}),
        (ResultExportRequestSerializer, PLANNED_EXPORT_REQUEST),
        (ResultExportRequestSerializer, IMMEDIATE_EXPORT_REQUEST),
        (ResultDataTypesRequestSerializer, PLANNED_DATA_TYPES_REQUEST),
        (ResultDataTypesRequestSerializer, IMMEDIATE_DATA_TYPES_REQUEST),
    ],
)
def test_request_serializers_accept_doc_payload(serializer_cls, params):
    serializer = serializer_cls(data=params)
    assert serializer.is_valid(), serializer.errors


@pytest.mark.parametrize(
    ("serializer_cls", "params"),
    [
        (
            ProcessPreviewRequestSerializer,
            {**PROCESS_PREVIEW_REQUEST, "process_selector": {"type": "pid", "config": {"pids": " ; "}}},
        ),
        # pid 是分号分隔的字符串，不接受列表、逐主机结构、非正整数与全角数字
        (
            ProcessPreviewRequestSerializer,
            {**PROCESS_PREVIEW_REQUEST, "process_selector": {"type": "pid", "config": {"pids": [2341]}}},
        ),
        (
            TaskSubmitRequestSerializer,
            {
                **TASK_SUBMIT_REQUEST,
                "process_selector": {"type": "pid", "config": {"host_pids": [{"bk_host_id": 456, "pid": 2341}]}},
            },
        ),
        (
            TaskSubmitRequestSerializer,
            {**TASK_SUBMIT_REQUEST, "process_selector": {"type": "pid", "config": {"pids": "2341;0"}}},
        ),
        (
            TaskSubmitRequestSerializer,
            {**TASK_SUBMIT_REQUEST, "process_selector": {"type": "pid", "config": {"pids": "2341;abc"}}},
        ),
        (
            TaskSubmitRequestSerializer,
            {**TASK_SUBMIT_REQUEST, "process_selector": {"type": "pid", "config": {"pids": "２３４１"}}},
        ),
        (
            TaskSubmitRequestSerializer,
            {**TASK_SUBMIT_REQUEST, "resource_guard_config": {"auto_stop_on_resource_pressure": True}},
        ),
        (
            TaskSubmitRequestSerializer,
            {**TASK_SUBMIT_REQUEST, "collection_type": "native_cpu"},
        ),
        (
            TaskSubmitRequestSerializer,
            {k: v for k, v in TASK_SUBMIT_REQUEST.items() if k != "process_selector"},
        ),
        (
            TaskSubmitRequestSerializer,
            {
                **GOLANG_TASK_SUBMIT_REQUEST,
                "process_selector": TASK_SUBMIT_REQUEST["process_selector"],
            },
        ),
        (
            TaskSubmitRequestSerializer,
            {
                **TASK_SUBMIT_REQUEST,
                "collection_method": "perf",
                "collection_type": "native_cpu",
                "collector_config": {"duration_sec": 30},
            },
        ),
        (PlannedTaskSubmitRequestSerializer, GOLANG_TASK_SUBMIT_REQUEST),
        (
            TaskEditRequestSerializer,
            {**GOLANG_TASK_SUBMIT_REQUEST, "task_id": 123},
        ),
        (
            ExecutionDetailRequestSerializer,
            {**EXECUTION_DETAIL_REQUEST, "schedule_type": "immediate"},
        ),
        (
            ExecutionDetailRequestSerializer,
            {"bk_biz_id": 2, "schedule_type": "cron", "scheduled_at": 1788310800000},
        ),
        (ExecutionCancelRequestSerializer, {**CANCEL_REQUEST, "hosts": []}),
        (ExecutionCancelRequestSerializer, {**CANCEL_REQUEST, "schedule_type": "immediate"}),
        (ResultQueryRequestSerializer, {**RESULT_QUERY_REQUEST, "diagram_types": []}),
        (ResultQueryRequestSerializer, {**RESULT_QUERY_REQUEST, "diagram_types": ["callgraph"]}),
        (ResultQueryRequestSerializer, {**RESULT_QUERY_REQUEST, "finished_at": None}),
        (ResultQueryRequestSerializer, {**RESULT_QUERY_REQUEST, "finished_at": RESULT_QUERY_REQUEST["started_at"] - 1}),
        # 查看仍要求 diagram_types，导出不需要
        (ResultQueryRequestSerializer, PLANNED_EXPORT_REQUEST),
        (ResultExportRequestSerializer, {**PLANNED_EXPORT_REQUEST, "finished_at": RESULT_STARTED_AT - 1}),
        # 查看与导出都要求前端按 results/data_types 的返回指定 data_type
        (ResultQueryRequestSerializer, {**PLANNED_DATA_TYPES_REQUEST, "diagram_types": ["table"]}),
        (ResultExportRequestSerializer, PLANNED_DATA_TYPES_REQUEST),
        (ResultDataTypesRequestSerializer, {**PLANNED_DATA_TYPES_REQUEST, "finished_at": RESULT_STARTED_AT - 1}),
        (
            ExecutionCancelRequestSerializer,
            {
                "bk_biz_id": 2,
                "schedule_type": "cron",
                "scheduled_at": 1788310800000,
                "hosts": [{"bk_host_id": 456, "ip": "127.0.0.1"}],
            },
        ),
    ],
)
def test_request_serializers_reject_invalid_nested_config(serializer_cls, params):
    assert not serializer_cls(data=params).is_valid()


@pytest.mark.parametrize(
    ("serializer_cls", "params"),
    [
        (TaskListRequestSerializer, {"bk_biz_id": 2, "page": 0}),
        (EventListRequestSerializer, {**EVENT_LIST_REQUEST, "start_time": 2, "end_time": 1}),
        (EventListRequestSerializer, {**EVENT_LIST_REQUEST, "offset": -1}),
        (EventListRequestSerializer, {**EVENT_LIST_REQUEST, "limit": 0}),
        # 状态是固定枚举，不提供候选值
        (TopKRequestSerializer, {**TOPK_REQUEST, "field": "status"}),
        (TopKRequestSerializer, {**TOPK_REQUEST, "limit": 0}),
        (TopKRequestSerializer, {**TOPK_REQUEST, "start_time": 2, "end_time": 1}),
        (
            TaskSubmitRequestSerializer,
            {**TASK_SUBMIT_REQUEST, "collector_config": {"duration_sec": 0}},
        ),
        (
            TaskSubmitRequestSerializer,
            {**TASK_SUBMIT_REQUEST, "collector_config": {"duration_sec": 301}},
        ),
        (
            TaskSubmitRequestSerializer,
            {
                **TASK_SUBMIT_REQUEST,
                "process_selector": {
                    "type": "command",
                    "config": {**STATIC_COMMAND_SELECTOR["config"], "host_pids": [{"bk_host_id": 999, "pid": 2341}]},
                },
            },
        ),
        # 动态采集与 host_pids 互斥：开启时不能传，关闭时必须传
        (
            TaskSubmitRequestSerializer,
            {
                **TASK_SUBMIT_REQUEST,
                "process_selector": {
                    "type": "command",
                    "config": {
                        **DYNAMIC_COMMAND_SELECTOR["config"],
                        "host_pids": [{"bk_host_id": 456, "pid": 2341}],
                    },
                },
            },
        ),
        (
            TaskSubmitRequestSerializer,
            {
                **TASK_SUBMIT_REQUEST,
                "process_selector": {
                    "type": "command",
                    "config": {**DYNAMIC_COMMAND_SELECTOR["config"], "enable_dynamic_collection": False},
                },
            },
        ),
        (
            TaskSubmitRequestSerializer,
            {
                **TASK_SUBMIT_REQUEST,
                "process_selector": {
                    "type": "command",
                    "config": {
                        k: v for k, v in DYNAMIC_COMMAND_SELECTOR["config"].items() if k != "enable_dynamic_collection"
                    },
                },
            },
        ),
        (
            TaskSubmitRequestSerializer,
            {
                **TASK_SUBMIT_REQUEST,
                "process_selector": {"type": "pid_file", "config": {"pid_path": " ; "}},
            },
        ),
        (
            TaskSubmitRequestSerializer,
            {
                **GOLANG_TASK_SUBMIT_REQUEST,
                "collector_config": {"ip_address": "127.0.0.1", "port": 0, "duration_sec": 30},
            },
        ),
        (
            TaskSubmitRequestSerializer,
            {
                **TASK_SUBMIT_REQUEST,
                "collection_method": "perf",
                "collection_type": "native_cpu",
                "collector_config": {"duration_sec": 30, "frequency_hz": 0, "stack_unwind": "fp"},
            },
        ),
        (
            TaskSubmitRequestSerializer,
            {**TASK_SUBMIT_REQUEST, "schedule": {**TASK_SUBMIT_REQUEST["schedule"], "timezone": "Mars/Olympus"}},
        ),
    ],
)
def test_request_serializers_reject_invalid_boundaries(serializer_cls, params):
    assert not serializer_cls(data=params).is_valid()


def test_task_submit_accepts_max_duration():
    serializer = TaskSubmitRequestSerializer(data={**TASK_SUBMIT_REQUEST, "collector_config": {"duration_sec": 300}})

    assert serializer.is_valid(), serializer.errors


MAX_TEXT = PROCESS_SELECTOR_MAX_TEXT_LENGTH


def command_selector(**config):
    return {"type": "command", "config": {**DYNAMIC_COMMAND_SELECTOR["config"], **config}}


def pid_file_selector(pid_paths):
    return {"type": "pid_file", "config": {"pid_path": ";".join(pid_paths)}}


def pid_selector(pids):
    return {"type": "pid", "config": {"pids": ";".join(str(pid) for pid in pids)}}


def static_command_selector(count):
    return command_selector(
        enable_dynamic_collection=False, host_pids=[{"bk_host_id": 456, "pid": pid} for pid in range(1, count + 1)]
    )


@pytest.mark.parametrize(
    ("process_selector", "valid"),
    [
        (command_selector(match_pattern="a" * MAX_TEXT, exclude_pattern="b" * MAX_TEXT), True),
        (command_selector(match_pattern="a" * (MAX_TEXT + 1)), False),
        (command_selector(exclude_pattern="b" * (MAX_TEXT + 1)), False),
        (pid_file_selector(["/" + "a" * (MAX_TEXT - 1)]), True),
        (pid_file_selector(["/" + "a" * MAX_TEXT]), False),
        (pid_file_selector([f"/{index}" for index in range(PROCESS_SELECTOR_MAX_PID_PATHS)]), True),
        (pid_file_selector([f"/{index}" for index in range(PROCESS_SELECTOR_MAX_PID_PATHS + 1)]), False),
        # 整串不超过 4096 个字符，分号也计入
        (pid_file_selector(["/" + "a" * 1022] * 4), True),
        (pid_file_selector(["/" + "a" * 1023] * 4), False),
        (pid_selector(list(range(1, PROCESS_SELECTOR_MAX_PIDS + 1))), True),
        (pid_selector(list(range(1, PROCESS_SELECTOR_MAX_PIDS + 2))), False),
        (static_command_selector(PROCESS_SELECTOR_MAX_HOST_PIDS), True),
        (static_command_selector(PROCESS_SELECTOR_MAX_HOST_PIDS + 1), False),
    ],
)
def test_task_submit_bounds_process_selector_size(process_selector, valid):
    """选择器会进入每条 Event 的配置快照，大小受采集端 event.content 上限约束"""
    serializer = TaskSubmitRequestSerializer(data={**TASK_SUBMIT_REQUEST, "process_selector": process_selector})

    assert serializer.is_valid() is valid, serializer.errors


def test_preview_bounds_pid_count():
    serializer = ProcessPreviewRequestSerializer(
        data={
            **PROCESS_PREVIEW_REQUEST,
            "process_selector": pid_selector(list(range(1, PROCESS_SELECTOR_MAX_PIDS + 2))),
        }
    )

    assert not serializer.is_valid()


@pytest.mark.parametrize(
    "process_selector",
    [
        STATIC_COMMAND_SELECTOR,
        {"type": "pid", "config": {"pids": "2341"}},
        {"type": "pid_file", "config": {"pid_path": "/var/run/demo.pid"}},
    ],
)
def test_task_submit_keeps_all_target_hosts(process_selector):
    """选择器下发到用户选择的全部主机，没有勾选进程的主机也照常下发"""
    serializer = TaskSubmitRequestSerializer(
        data={**TASK_SUBMIT_REQUEST, "target_config": TWO_HOSTS_TARGET_CONFIG, "process_selector": process_selector}
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["target_config"]["nodes"] == TWO_HOSTS_TARGET_CONFIG["nodes"]


def test_is_mock_returns_fixtures_and_skips_write_side_effects():
    hosts = QueryHostsResource().perform_request({"is_mock": True})
    assert [column["name"] for column in hosts["columns"] if column["field"] in ("ip", "task")] == [
        "目标 IP",
        "采集历史",
    ]
    assert hosts["data"][-1]["status"] == "outdate"

    tasks = ListTasksResource().perform_request({"is_mock": True})
    assert tasks["data"][1]["deployment_status"] == "outdate"
    meta = ActiveProfilingMetaConfigResource().perform_request({"is_mock": True})
    assert meta["enabled"] is True
    assert "outdate" in meta["execution_statuses"]
    assert "outdate" in meta["deployment_statuses"]

    assert EnableActiveCollectionResource().perform_request({"is_mock": True, "bk_biz_id": 2}) is None
    assert "task_id" not in ExecutionDetailResource().perform_request({"is_mock": True, "schedule_type": "immediate"})
    assert QueryTopKResource().perform_request({"is_mock": True, "field": "process_pids"})[0]["alias"] == "java:1234"
    result = QueryResultsResource().perform_request({"is_mock": True, "diagram_types": ["table"]})
    assert set(result) == {"table_data", "type", "unit"}
    data_types = QueryResultDataTypesResource().perform_request({"is_mock": True})["data_types"]
    assert data_types[1] == {"key": "alloc_space/bytes", "name": "ALLOC_SPACE"}
    response = ExportResultsResource().perform_request({"is_mock": True})
    assert gzip.decompress(response.content) == b"mock-active-profiling-pprof"


@pytest.mark.parametrize(
    "cron_expression",
    [
        "not cron",
        "0 0 * *",
        "0 0 * * * *",
        "0 25 * * *",
        "0 0 * * 7",
    ],
)
def test_task_submit_rejects_invalid_cron_expression(cron_expression):
    serializer = TaskSubmitRequestSerializer(
        data={
            **TASK_SUBMIT_REQUEST,
            "schedule": {**TASK_SUBMIT_REQUEST["schedule"], "cron_expression": cron_expression},
        }
    )

    assert not serializer.is_valid()
