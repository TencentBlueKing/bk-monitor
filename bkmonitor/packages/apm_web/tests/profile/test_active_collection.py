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
import json
import string
from types import SimpleNamespace

import pytest
from django.http import HttpResponse
from django.urls import reverse
from rest_framework.test import APIRequestFactory

from apm.models import ProfileDataSource
from apm_web.profile.active_collection import fixtures
from apm_web.profile.active_collection.constants import META_CONFIG
from apm_web.profile.active_collection.constants import (
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
    RenameExecutionResource,
    SubmitTaskResource,
    SwitchTaskResource,
)
from apm_web.profile.active_collection.serializers import (
    EnableRequestSerializer,
    EventListRequestSerializer,
    ExecutionCancelRequestSerializer,
    ExecutionDetailRequestSerializer,
    ExecutionRenameRequestSerializer,
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
from bkmonitor.iam.drf import ViewBusinessPermission

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

CANCEL_REQUEST = {
    **EXECUTION_DETAIL_REQUEST,
    "hosts": [{"bk_host_id": 456, "ip": "127.0.0.1"}, {"bk_host_id": 457, "ip": "127.0.0.2"}],
}

RENAME_REQUEST = {**EXECUTION_DETAIL_REQUEST, "task_name": "java-cpu-renamed"}

TOPK_REQUEST = {
    "bk_biz_id": 2,
    "start_time": EVENT_LIST_REQUEST["start_time"],
    "end_time": EVENT_LIST_REQUEST["end_time"],
    "field": "task_name",
}

IMMEDIATE_TASK_SUBMIT_REQUEST = {
    **TASK_SUBMIT_REQUEST,
    "schedule": {"type": "immediate", "execute_at": 1788310800000, "timezone": "Asia/Shanghai"},
}

TWO_HOSTS_TARGET_CONFIG = {"node_type": "INSTANCE", "nodes": [{"bk_host_id": 456}, {"bk_host_id": 457}]}


def with_filters(**filters):
    return {**EVENT_LIST_REQUEST, "filters": {**EVENT_LIST_REQUEST["filters"], **filters}}


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


def test_enable_delegates_to_backend_apm(mocker):
    enable = mocker.patch("core.drf_resource.api.apm_api.enable_active_profiling")

    assert EnableActiveCollectionResource().request({"bk_biz_id": 2}) is None

    enable.assert_called_once_with(bk_biz_id=2)


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


@pytest.mark.parametrize(
    ("errmsg", "exit_code", "failure"),
    [
        # 采集端失败时 stdout 是带 error_type 的 JSON
        (
            json.dumps({"error_type": "collect_failed", "message": "list host processes: permission denied"}),
            1,
            {"error_type": "collect_failed", "err_msg": "list host processes: permission denied"},
        ),
        # 旧版采集端只输出错误文本
        (
            "flag provided but not defined: -active-profile-match",
            2,
            {"error_type": "config_invalid", "err_msg": "flag provided but not defined: -active-profile-match"},
        ),
        # 退出码为 0 是作业平台没有执行成功
        ("任务执行超时", 0, {"error_type": "dispatch_failed", "err_msg": "任务执行超时"}),
    ],
)
def test_preview_processes_reports_failed_hosts_with_error_type(fast_execute_script, errmsg, exit_code, failure):
    fast_execute_script.return_value["failed"] = [
        {"bk_host_id": 457, "ip": "127.0.0.2", "errmsg": errmsg, "exit_code": exit_code}
    ]

    assert PreviewProcessesResource().request(PROCESS_PREVIEW_REQUEST)["data"] == [
        {"bk_host_id": 456, "ip": "127.0.0.1", **MATCHED_PROCESS},
        {"bk_host_id": 457, "ip": "127.0.0.2", **failure},
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
def result_apis(mocker):
    profile_datasource = mocker.patch("apm_web.profile.active_collection.handlers.ProfileDataSource")
    profile_datasource.objects.filter.return_value.first.return_value = SimpleNamespace(
        bk_data_id=777, result_table_id="2_profile_active_profiling_builtin_1"
    )
    return {
        "profile_datasource": profile_datasource,
        "query": mocker.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query"),
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


@pytest.mark.parametrize("diagram_types", [["flamegraph"], ["table"], ["callgraph"]])
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
    assert reverse("apm_web:executions-rename") == "/apm/profile_api/active_collection/executions/rename/"
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
        (TopKRequestSerializer, {**TOPK_REQUEST, "field": "process_names", "limit": 5}),
        (TopKRequestSerializer, {**TOPK_REQUEST, "field": "process_pids"}),
        (TopKRequestSerializer, {**TOPK_REQUEST, "keyword": "java"}),
        (TopKRequestSerializer, {**TOPK_REQUEST, "keyword": ""}),
        (ExecutionRenameRequestSerializer, RENAME_REQUEST),
        (
            ExecutionRenameRequestSerializer,
            {"bk_biz_id": 2, "schedule_type": "immediate", "scheduled_at": 1788310800000, "task_name": "adhoc"},
        ),
        (EventListRequestSerializer, with_filters(task_id=123)),
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
        (ResultQueryRequestSerializer, {**RESULT_QUERY_REQUEST, "diagram_types": ["tendency"]}),
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
        (EventListRequestSerializer, {**EVENT_LIST_REQUEST, "source": "kafka"}),
        (ExecutionRenameRequestSerializer, {**RENAME_REQUEST, "task_name": ""}),
        (ExecutionRenameRequestSerializer, {**RENAME_REQUEST, "task_name": "a" * 129}),
        # 计划执行必须带 task_id 定位
        (ExecutionRenameRequestSerializer, {key: value for key, value in RENAME_REQUEST.items() if key != "task_id"}),
        (EventListRequestSerializer, with_filters(task_id=0)),
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
    # parsing 只用于展示主机行，不提供筛选；后台 MySQL 能按 unknown 筛选
    assert set(meta["execution_statuses"]) - set(meta["execution_status_filters"]) == {"parsing"}
    assert "unknown" in meta["execution_status_filters"]
    assert "outdate" in meta["deployment_statuses"]
    assert meta["diagram_types"] == ["flamegraph", "table", "callgraph"]

    assert EnableActiveCollectionResource().perform_request({"is_mock": True, "bk_biz_id": 2}) is None
    assert "task_id" not in ExecutionDetailResource().perform_request({"is_mock": True, "schedule_type": "immediate"})
    assert QueryTopKResource().perform_request({"is_mock": True, "field": "process_names"})[0]["alias"] == "java"
    assert QueryTopKResource().perform_request({"is_mock": True, "field": "process_pids"})[0]["alias"] == "java:1234"
    result = QueryResultsResource().perform_request({"is_mock": True, "diagram_types": ["table"]})
    assert set(result) == {"table_data", "type", "unit"}
    result = QueryResultsResource().perform_request({"is_mock": True, "diagram_types": ["callgraph"]})
    assert set(result) == {"call_graph_data", "call_graph_all", "type", "unit"}
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


@pytest.mark.parametrize(
    ("resource_cls", "api_name", "request_data", "backend_result", "expected"),
    [
        (
            ListTasksResource,
            "list_active_profiling_tasks",
            {"bk_biz_id": 2, "page": 1, "page_size": 20},
            {"data": [], "page": 1, "page_size": 20, "total": 0},
            {"columns": TASK_LIST_COLUMNS, "data": [], "page": 1, "page_size": 20, "total": 0},
        ),
        (
            QueryHostsResource,
            "query_active_profiling_hosts",
            with_filters(status="unknown"),
            [{"bk_host_id": 456}],
            {"columns": HOST_QUERY_COLUMNS, "data": [{"bk_host_id": 456}]},
        ),
        (
            ListExecutionsResource,
            "list_active_profiling_executions",
            EVENT_LIST_REQUEST,
            [{"task_name": "native-cpu"}],
            {"task_columns": EXECUTION_LIST_TASK_COLUMNS, "data": [{"task_name": "native-cpu"}]},
        ),
        (
            QueryTopKResource,
            "query_active_profiling_top_k",
            {"bk_biz_id": 2, "start_time": 1, "end_time": 2, "field": "target", "keyword": "127"},
            [{"value": "127.0.0.1", "alias": "127.0.0.1", "count": 1}],
            [{"value": "127.0.0.1", "alias": "127.0.0.1", "count": 1}],
        ),
        (
            ExecutionDetailResource,
            "query_active_profiling_execution_detail",
            EXECUTION_DETAIL_REQUEST,
            {"task_id": 123, "hosts": []},
            {"host_columns": EXECUTION_DETAIL_HOST_COLUMNS, "task_id": 123, "hosts": []},
        ),
    ],
)
def test_backend_queries_forward_request_and_add_columns(
    mocker, resource_cls, api_name, request_data, backend_result, expected
):
    backend_api = mocker.patch(f"core.drf_resource.api.apm_api.{api_name}", return_value=backend_result)

    assert resource_cls().request(request_data) == expected

    # is_mock 只在 SaaS 侧生效，其余参数原样转给后台
    sent = backend_api.call_args.kwargs
    assert "is_mock" not in sent
    assert {key: sent[key] for key in request_data} == request_data


@pytest.mark.parametrize(
    ("resource_cls", "api_name", "request_data"),
    [
        (QueryHostsResource, "query_active_profiling_hosts", EVENT_LIST_REQUEST),
        (ListExecutionsResource, "list_active_profiling_executions", EVENT_LIST_REQUEST),
        (QueryTopKResource, "query_active_profiling_top_k", TOPK_REQUEST),
        (ExecutionDetailResource, "query_active_profiling_execution_detail", EXECUTION_DETAIL_REQUEST),
    ],
)
@pytest.mark.parametrize(("source", "expected_source"), [(None, "mysql"), ("mysql", "mysql"), ("es", "es")])
def test_backend_queries_forward_query_source(mocker, resource_cls, api_name, request_data, source, expected_source):
    backend_api = mocker.patch(f"core.drf_resource.api.apm_api.{api_name}", return_value={})
    if source:
        request_data = {**request_data, "source": source}

    resource_cls().request(request_data)

    assert backend_api.call_args.kwargs["source"] == expected_source


@pytest.mark.parametrize(
    ("resource_cls", "api_name", "request_data"),
    [
        (SubmitTaskResource, "submit_active_profiling_task", IMMEDIATE_TASK_SUBMIT_REQUEST),
        (EditTaskResource, "edit_active_profiling_task", {**TASK_SUBMIT_REQUEST, "task_id": 123}),
        (DeleteTaskResource, "delete_active_profiling_task", {"bk_biz_id": 2, "task_id": 123}),
        (SwitchTaskResource, "switch_active_profiling_task", {"bk_biz_id": 2, "task_id": 123, "enabled": False}),
        (
            CancelExecutionResource,
            "cancel_active_profiling_execution",
            {**EXECUTION_DETAIL_REQUEST, "hosts": [{"bk_host_id": 456, "ip": "127.0.0.1"}]},
        ),
        (RenameExecutionResource, "rename_active_profiling_execution", RENAME_REQUEST),
    ],
)
def test_backend_operations_forward_request_and_return_nothing(mocker, resource_cls, api_name, request_data):
    backend_api = mocker.patch(f"core.drf_resource.api.apm_api.{api_name}")

    assert resource_cls().request(request_data) is None

    sent = backend_api.call_args.kwargs
    assert "is_mock" not in sent
    assert sent["bk_biz_id"] == 2


def test_backend_resources_return_fixtures_without_calling_backend(mocker):
    backend_apis = [
        mocker.patch(f"core.drf_resource.api.apm_api.{api_name}")
        for api_name in (
            "query_active_profiling_hosts",
            "list_active_profiling_tasks",
            "submit_active_profiling_task",
            "cancel_active_profiling_execution",
            "rename_active_profiling_execution",
        )
    ]

    assert QueryHostsResource().perform_request({"is_mock": True}) == fixtures.HOST_QUERY
    assert ListTasksResource().perform_request({"is_mock": True}) == fixtures.TASK_LIST
    assert SubmitTaskResource().perform_request({"is_mock": True}) is None
    assert CancelExecutionResource().perform_request({"is_mock": True}) is None
    assert RenameExecutionResource().perform_request({"is_mock": True}) is None

    for backend_api in backend_apis:
        backend_api.assert_not_called()
