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
import itertools
import json
from types import SimpleNamespace
from typing import Any

import pytest
from django.db.models import Q

from apm.constants import ACTIVE_PROFILING_PARSING_MS
from apm.core.handlers.profile.active_profiling import (
    CONSUL_PATH_PREFIX,
    ActiveProfilingConsulHandler,
    ActiveProfilingExecutionQueryHandler,
    ActiveProfilingExecutionWriter,
    ActiveProfilingNodeManHandler,
)
from apm.core.handlers.profile.active_profiling_es import ActiveProfilingEventQueryHandler
from apm.models import ActiveProfilingExecution, ActiveProfilingHostExecution, ActiveProfilingTask, ProfileDataSource
from apm.resources import (
    ACTIVE_PROFILING_QUERY_HANDLERS,
    CancelActiveProfilingExecutionResource,
    DeleteActiveProfilingTaskResource,
    EditActiveProfilingTaskResource,
    EnableActiveProfilingResource,
    ListActiveProfilingExecutionsResource,
    ListActiveProfilingTasksResource,
    QueryActiveProfilingExecutionDetailResource,
    QueryActiveProfilingHostsResource,
    QueryActiveProfilingTopKResource,
    RenameActiveProfilingExecutionResource,
    SubmitActiveProfilingTaskResource,
    SwitchActiveProfilingTaskResource,
)
from apm.task.tasks import stop_expired_active_profiling_tasks
from constants.apm import BUILTIN_EVENT_GROUP_LABEL, BUILTIN_EVENT_GROUP_NAME, BUILTIN_PROFILING_APP_NAME
from core.drf_resource.exceptions import CustomException
from core.errors.api import BKAPIError
from metadata.models import DataSource

HANDLER_MODULE = "apm.core.handlers.profile.active_profiling"
ES_HANDLER_MODULE = "apm.core.handlers.profile.active_profiling_es"


@pytest.fixture
def enable_apis(mocker):
    mocker.patch("apm.resources.get_request_username", return_value="admin")
    mocks = {
        name: mocker.patch(f"core.drf_resource.resource.metadata.{name}", return_value=return_value)
        for name, return_value in [
            ("query_event_group", []),
            ("query_data_source", {"bk_data_id": 1001}),
            ("create_data_id", {"bk_data_id": 1002}),
            ("create_event_group", {"event_group_id": 555}),
        ]
    }
    mocks["apply_datasource"] = mocker.patch.object(ProfileDataSource, "apply_datasource")
    mocks["refresh_consul"] = mocker.patch("apm.resources.refresh_active_profiling_consul_config.delay")
    return mocks


def test_enable_creates_builtin_profiling_datasource_and_event_group(enable_apis):
    enable_apis["query_data_source"].side_effect = DataSource.DoesNotExist

    assert EnableActiveProfilingResource().request({"bk_biz_id": 2}) is None

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
    enable_apis["refresh_consul"].assert_called_once_with(2)


def test_enable_skips_existing_event_group(enable_apis):
    enable_apis["query_event_group"].return_value = [{"event_group_id": 555}]

    assert EnableActiveProfilingResource().request({"bk_biz_id": 2}) is None

    enable_apis["query_data_source"].assert_not_called()
    enable_apis["create_data_id"].assert_not_called()
    enable_apis["create_event_group"].assert_not_called()
    enable_apis["refresh_consul"].assert_called_once_with(2)


def test_enable_reuses_existing_event_data_id(enable_apis):
    EnableActiveProfilingResource().request({"bk_biz_id": 2})

    enable_apis["create_data_id"].assert_not_called()
    assert enable_apis["create_event_group"].call_args.kwargs["bk_data_id"] == 1001


class FakeQuerySet(list):
    def values(self, *fields: str) -> "FakeQuerySet":
        return FakeQuerySet({field: row[field] for field in fields} for row in self)

    def values_list(self, *fields: str, flat: bool = False) -> "FakeQuerySet":
        if flat:
            return FakeQuerySet(row[fields[0]] for row in self)
        return FakeQuerySet(tuple(row[field] for field in fields) for row in self)


@pytest.fixture
def consul_rows(mocker):
    """业务 2 已开通且 DataID 启用；业务 3 的事件分组 DataID 已停用"""
    rows: dict[str, list[Any]] = {
        "profiles": [{"bk_biz_id": 2}, {"bk_biz_id": 3}],
        "event_groups": [
            {"bk_tenant_id": "system", "bk_biz_id": 2, "bk_data_id": 1001},
            {"bk_tenant_id": "system", "bk_biz_id": 3, "bk_data_id": 1002},
        ],
        "data_sources": [{"bk_data_id": 1001, "mq_cluster_id": 9}],
        "topics": [{"bk_data_id": 1001, "topic": "topic_1001"}],
        "clusters": [SimpleNamespace(cluster_id=9, domain_name="kafka.local", port=9092, username="u", password="p")],
    }
    filters = {
        "profiles": mocker.patch.object(ProfileDataSource.objects, "filter"),
        "event_groups": mocker.patch(f"{HANDLER_MODULE}.EventGroup.objects.filter"),
        "data_sources": mocker.patch(f"{HANDLER_MODULE}.DataSource.objects.filter"),
        "topics": mocker.patch(f"{HANDLER_MODULE}.KafkaTopicInfo.objects.filter"),
        "clusters": mocker.patch(f"{HANDLER_MODULE}.ClusterInfo.objects.filter"),
    }
    for name, patched in filters.items():
        patched.side_effect = lambda *args, _name=name, **kwargs: FakeQuerySet(rows[_name])

    hash_consul = mocker.patch(f"{HANDLER_MODULE}.consul_tools.HashConsul").return_value
    hash_consul.list_keys.return_value = (1, [])
    return SimpleNamespace(rows=rows, filters=filters, consul=hash_consul)


def test_check_update_puts_enabled_data_ids_and_deletes_stale_keys(consul_rows):
    consul_rows.consul.list_keys.return_value = (
        1,
        [f"{CONSUL_PATH_PREFIX}1001", f"{CONSUL_PATH_PREFIX}1002", f"{CONSUL_PATH_PREFIX}1003"],
    )

    ActiveProfilingConsulHandler.check_update()

    consul_rows.filters["profiles"].assert_called_once_with(app_name=BUILTIN_PROFILING_APP_NAME)
    consul_rows.filters["event_groups"].assert_called_once_with(
        bk_biz_id__in=[2, 3], event_group_name=BUILTIN_EVENT_GROUP_NAME, is_delete=False, is_enable=True
    )
    consul_rows.filters["data_sources"].assert_called_once_with(bk_data_id__in=[1001, 1002], is_enable=True)
    consul_rows.consul.put.assert_called_once_with(
        key=f"{CONSUL_PATH_PREFIX}1001",
        value={
            "bk_tenant_id": "system",
            "bk_biz_id": 2,
            "bk_data_id": 1001,
            "kafka_info": {"host": "kafka.local:9092", "username": "u", "password": "p", "topic": "topic_1001"},
        },
        bk_data_id=1001,
    )
    deleted = [call.args[0] for call in consul_rows.consul.delete.call_args_list]
    assert deleted == [f"{CONSUL_PATH_PREFIX}1002", f"{CONSUL_PATH_PREFIX}1003"]


def test_check_update_keeps_old_value_when_kafka_info_incomplete(consul_rows):
    consul_rows.rows["topics"] = []
    consul_rows.consul.list_keys.return_value = (1, [f"{CONSUL_PATH_PREFIX}1001"])

    ActiveProfilingConsulHandler.check_update()

    consul_rows.consul.put.assert_not_called()
    consul_rows.consul.delete.assert_not_called()


def test_check_update_isolates_consul_put_failure(consul_rows):
    consul_rows.rows["data_sources"].append({"bk_data_id": 1002, "mq_cluster_id": 9})
    consul_rows.rows["topics"].append({"bk_data_id": 1002, "topic": "topic_1002"})
    consul_rows.consul.put.side_effect = [RuntimeError("consul unavailable"), True]

    ActiveProfilingConsulHandler.check_update()

    assert consul_rows.consul.put.call_count == 2
    consul_rows.consul.delete.assert_not_called()


def test_refresh_only_puts_target_biz(consul_rows):
    ActiveProfilingConsulHandler.refresh(2)

    consul_rows.filters["event_groups"].assert_called_once_with(
        bk_biz_id__in=[2], event_group_name=BUILTIN_EVENT_GROUP_NAME, is_delete=False, is_enable=True
    )
    consul_rows.consul.put.assert_called_once()
    consul_rows.consul.list_keys.assert_not_called()
    consul_rows.consul.delete.assert_not_called()


NOW_MS = 1788400000000
DAY_MS = 24 * 3600 * 1000
# 保留期 7 天：RECENT、MID 未过期，OLD 已过期
RECENT_AT = NOW_MS - 3600 * 1000
MID_AT = NOW_MS - 2 * 3600 * 1000
OLD_AT = NOW_MS - 8 * DAY_MS
TIME_RANGE = {"bk_biz_id": 2, "start_time": NOW_MS - 9 * DAY_MS, "end_time": NOW_MS}


def create_execution(hosts, collector_config=None, **fields):
    execution = ActiveProfilingExecution.objects.create(
        bk_biz_id=2,
        creator="admin",
        target_count=len(hosts),
        config={
            "target_config": {"node_type": "INSTANCE", "nodes": [{"bk_host_id": host["bk_host_id"]} for host in hosts]},
            "collector_config": collector_config or {"duration_sec": 30},
        },
        **fields,
    )
    for host in hosts:
        ActiveProfilingHostExecution.objects.create(
            execution_id=execution.id,
            bk_biz_id=2,
            scheduled_at=execution.scheduled_at,
            event_time=host.get("started_at") or 0,
            **host,
        )
    return execution


@pytest.fixture
def query_rows(mocker):
    """一次 cron 执行（一台成功、一台占位）、一次已过期的立即执行、一次改造前没有 task_id 的立即执行"""
    mocker.patch(f"{HANDLER_MODULE}.time").time.return_value = NOW_MS / 1000
    mocker.patch.object(ActiveProfilingExecutionQueryHandler, "_get_retention_ms", return_value=7 * DAY_MS)
    cron = create_execution(
        [
            {
                "bk_host_id": 456,
                "ip": "127.0.0.1",
                "status": "succeed",
                "started_at": RECENT_AT + 100,
                "finished_at": RECENT_AT + 31100,
                "process_names": "order_api",
                "process_pids": "2341",
                "processes": [{"pid": 2341, "process_name": "order,api"}],
            },
            {"bk_host_id": 457, "ip": "127.0.0.2", "status": "running"},
        ],
        schedule_type="cron",
        task_id=12,
        scheduled_at=RECENT_AT,
        task_name="order-api-cpu",
        collection_method="perf",
        collection_type="native_cpu",
        execution_status="running",
        status_summary={"succeed": 1, "running": 1},
        started_at=RECENT_AT + 100,
    )
    expired = create_execution(
        [
            {
                "bk_host_id": 456,
                "ip": "127.0.0.1",
                "status": "succeed",
                "started_at": OLD_AT + 100,
                "finished_at": OLD_AT + 1100,
                "process_names": "java",
                "process_pids": "3000",
                "processes": [{"pid": 3000, "process_name": "java"}],
            },
            {
                "bk_host_id": 458,
                "ip": "127.0.0.3",
                "status": "failed",
                "started_at": OLD_AT + 200,
                "finished_at": OLD_AT + 200,
                "error_type": "dispatch_failed",
                "message": "agent not ready",
            },
        ],
        schedule_type="immediate",
        task_id=30521,
        scheduled_at=OLD_AT,
        task_name="order-api-cpu-adhoc",
        collection_method="java",
        collection_type="java_cpu",
        execution_status="partial_succeed",
        status_summary={"succeed": 1, "failed": 1},
        started_at=OLD_AT + 100,
        finished_at=OLD_AT + 1100,
    )
    legacy = create_execution(
        [{"bk_host_id": 459, "ip": "127.0.1.10", "status": "unknown", "started_at": MID_AT + 100}],
        schedule_type="immediate",
        scheduled_at=MID_AT,
        task_name="go-cpu-legacy",
        collection_method="golang",
        collection_type="go_cpu",
        execution_status="unknown",
        status_summary={"unknown": 1},
        started_at=MID_AT + 100,
    )
    return SimpleNamespace(cron=cron, expired=expired, legacy=legacy)


def query_hosts(**filters):
    return QueryActiveProfilingHostsResource().request({**TIME_RANGE, "filters": filters})


def host_keys(rows):
    return [(row["scheduled_at"], row["bk_host_id"]) for row in rows]


@pytest.mark.django_db(databases="__all__")
def test_query_hosts_orders_by_scheduled_at_and_derives_outdate(query_rows):
    rows = query_hosts()

    # 同一毫秒内按执行、主机同向倒序
    assert host_keys(rows) == [(RECENT_AT, 457), (RECENT_AT, 456), (MID_AT, 459), (OLD_AT, 458), (OLD_AT, 456)]
    assert rows[1] == {
        "bk_host_id": 456,
        "ip": "127.0.0.1",
        "processes": [{"pid": 2341, "process_name": "order,api"}],
        "status": "succeed",
        "started_at": RECENT_AT + 100,
        "finished_at": RECENT_AT + 31100,
        # 采集时长取执行配置的 duration_sec
        "duration_ms": 30000,
        "task": {"task_id": 12, "name": "order-api-cpu", "schedule_type": "cron"},
        "collection_method": "perf",
        "collection_type": "native_cpu",
        "creator": "admin",
        "scheduled_at": RECENT_AT,
    }
    # 占位行没有开始时间；历史立即执行不返回 task_id；过保留期的成功结果展示为 outdate
    assert rows[0]["started_at"] is None
    assert rows[2]["task"] == {"name": "go-cpu-legacy", "schedule_type": "immediate"}
    assert [row["status"] for row in rows[3:]] == ["failed", "outdate"]

    page = QueryActiveProfilingHostsResource().request({**TIME_RANGE, "offset": 1, "limit": 2})
    assert host_keys(page) == [(RECENT_AT, 456), (MID_AT, 459)]


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        ({"ips": ["0.0.2"]}, [(RECENT_AT, 457)]),
        # 进程名里的逗号已由采集端归一化为 _，查询词同样归一化
        ({"process_names": ["order,api"]}, [(RECENT_AT, 456)]),
        ({"process_pids": ["3000", "2341"]}, [(RECENT_AT, 456), (OLD_AT, 456)]),
        # PID 候选的 进程名:PID 按 processes 中同一进程的原始进程名与 PID 精确匹配，多选命中任一
        ({"process_pids": ["java:3000", "order,api:2341"]}, [(RECENT_AT, 456), (OLD_AT, 456)]),
        ({"process_pids": ["java:2341"]}, []),
        ({"process_pids": ["java:300"]}, []),
        ({"schedule_types": ["immediate"]}, [(MID_AT, 459), (OLD_AT, 458), (OLD_AT, 456)]),
        # 任务名可以改，按计划查历史用任务 ID 精确匹配
        ({"task_id": 12}, [(RECENT_AT, 457), (RECENT_AT, 456)]),
        ({"task_name": "adhoc", "ips": ["127.0.0.1"]}, [(OLD_AT, 456)]),
        ({"status": "unknown"}, [(MID_AT, 459)]),
        ({"status": "succeed"}, [(RECENT_AT, 456)]),
        ({"status": "outdate"}, [(OLD_AT, 456)]),
    ],
)
@pytest.mark.django_db(databases="__all__")
def test_query_hosts_filters(query_rows, filters, expected):
    assert host_keys(query_hosts(**filters)) == expected


@pytest.mark.django_db(databases="__all__")
def test_hosts_display_parsing_until_result_stored(query_rows):
    # 刚结束 1 秒的成功主机还在解析入库，结束 30 秒的已可查看
    scheduled_at = NOW_MS - 60 * 1000
    create_execution(
        [
            {"bk_host_id": 460, "ip": "127.0.1.11", "status": "succeed", "finished_at": NOW_MS - 1000},
            {"bk_host_id": 461, "ip": "127.0.1.12", "status": "succeed", "finished_at": NOW_MS - 30 * 1000},
        ],
        schedule_type="cron",
        task_id=14,
        scheduled_at=scheduled_at,
        task_name="fresh-cpu",
        collection_method="perf",
        collection_type="native_cpu",
        execution_status="succeed",
        status_summary={"succeed": 2},
    )

    assert [row["status"] for row in query_hosts()[:2]] == ["succeed", "parsing"]
    # 按成功筛选时排除还在解析中的行
    assert host_keys(query_hosts(status="succeed")) == [(scheduled_at, 461), (RECENT_AT, 456)]

    detail = QueryActiveProfilingExecutionDetailResource().request(
        {"bk_biz_id": 2, "task_id": 14, "scheduled_at": scheduled_at}
    )
    assert [host["status"] for host in detail["hosts"]] == ["parsing", "succeed"]
    assert (detail["execution_status"], detail["status_summary"]) == ("succeed", {"succeed": 2})


@pytest.mark.django_db(databases="__all__")
def test_go_heap_has_no_duration(query_rows):
    # Go Heap 是即时快照，配置里没有 duration_sec
    create_execution(
        [{"bk_host_id": 460, "ip": "127.0.1.11", "status": "failed", "finished_at": NOW_MS - 60 * 1000}],
        collector_config={"ip_address": "127.0.0.1", "port": 6060},
        schedule_type="cron",
        task_id=15,
        scheduled_at=NOW_MS - 2 * 60 * 1000,
        task_name="go-heap",
        collection_method="golang",
        collection_type="go_heap",
        execution_status="failed",
        status_summary={"failed": 1},
    )

    assert query_hosts()[0]["duration_ms"] is None
    assert ListActiveProfilingExecutionsResource().request({**TIME_RANGE, "limit": 1})[0]["duration_ms"] is None


@pytest.mark.django_db(databases="__all__")
def test_list_executions_selects_by_host_but_keeps_all_hosts(query_rows):
    rows = ListActiveProfilingExecutionsResource().request({**TIME_RANGE, "filters": {"ips": ["127.0.0.3"]}})

    # 立即执行不返回 task_id，与一期协议一致
    assert rows == [
        {
            "task_name": "order-api-cpu-adhoc",
            "schedule_type": "immediate",
            "scheduled_at": OLD_AT,
            "collection_method": "java",
            "collection_type": "java_cpu",
            "creator": "admin",
            "started_at": OLD_AT + 100,
            "finished_at": OLD_AT + 1100,
            "duration_ms": 30000,
            # 过保留期后执行状态与状态计数里的成功类都展示为 outdate
            "execution_status": "outdate",
            "status_summary": {"failed": 1, "outdate": 1},
            "target_count": 2,
            "hosts": [{"bk_host_id": 456, "ip": "127.0.0.1"}, {"bk_host_id": 458, "ip": "127.0.0.3"}],
        }
    ]


@pytest.mark.django_db(databases="__all__")
def test_list_executions_orders_and_filters_by_execution_status(query_rows):
    def scheduled_ats(**filters):
        rows = ListActiveProfilingExecutionsResource().request({**TIME_RANGE, "filters": filters})
        return [row["scheduled_at"] for row in rows]

    assert scheduled_ats() == [RECENT_AT, MID_AT, OLD_AT]
    assert scheduled_ats(status="running") == [RECENT_AT]
    assert scheduled_ats(status="outdate") == [OLD_AT]
    assert scheduled_ats(status="partial_succeed") == []
    assert scheduled_ats(collection_methods=["golang"]) == [MID_AT]

    legacy = ListActiveProfilingExecutionsResource().request({**TIME_RANGE, "offset": 1, "limit": 1})[0]
    assert "task_id" not in legacy


@pytest.mark.django_db(databases="__all__")
def test_list_executions_orders_same_millisecond_by_task_id_desc(query_rows):
    # 整点触发的多个计划落在同一毫秒，按 task_id 倒序保证翻页稳定
    create_execution(
        [{"bk_host_id": 460, "ip": "127.0.1.11", "status": "running"}],
        schedule_type="cron",
        task_id=99,
        scheduled_at=RECENT_AT,
        task_name="other-cron",
        collection_method="perf",
        collection_type="native_cpu",
        execution_status="running",
        status_summary={"running": 1},
    )

    rows = ListActiveProfilingExecutionsResource().request({**TIME_RANGE, "limit": 2})

    assert [(row["scheduled_at"], row["task_id"]) for row in rows] == [(RECENT_AT, 99), (RECENT_AT, 12)]


@pytest.mark.parametrize(
    ("field", "limit", "expected"),
    [
        ("target", 1, [("127.0.0.1", "127.0.0.1", 2)]),
        # 执行级字段按执行的主机数累加
        ("task_name", 2, [("order-api-cpu", "order-api-cpu", 2), ("order-api-cpu-adhoc", "order-api-cpu-adhoc", 2)]),
    ],
)
@pytest.mark.django_db(databases="__all__")
def test_topk_counts_host_executions(query_rows, field, limit, expected):
    candidates = QueryActiveProfilingTopKResource().request({**TIME_RANGE, "field": field, "limit": limit})

    assert sorted((item["value"], item["alias"], item["count"]) for item in candidates) == sorted(expected)


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        # 点选后按进程名筛选，所以按进程名去重；计数是含有该进程的主机执行数
        ("process_names", [("order_api", 1), ("java", 2)]),
        # 同名进程的每个 PID 各是一个候选，取 processes 中的原始进程名，点选后按同一进程精确匹配
        ("process_pids", [("order,api:2341", 1), ("java:4000", 1), ("java:4001", 1), ("java:3000", 1)]),
    ],
)
@pytest.mark.django_db(databases="__all__")
def test_topk_lists_recent_processes(query_rows, field, expected):
    # 同名进程在另一次采集里换了 PID，同一次采集里也有两个同名进程
    create_execution(
        [
            {
                "bk_host_id": 460,
                "ip": "127.0.1.11",
                "status": "succeed",
                "started_at": MID_AT + 100,
                "process_names": "java,java",
                "process_pids": "4000,4001",
                "processes": [{"pid": 4000, "process_name": "java"}, {"pid": 4001, "process_name": "java"}],
            }
        ],
        schedule_type="cron",
        task_id=13,
        scheduled_at=MID_AT,
        task_name="java-cpu",
        collection_method="java",
        collection_type="java_cpu",
        execution_status="succeed",
        status_summary={"succeed": 1},
    )

    candidates = QueryActiveProfilingTopKResource().request({**TIME_RANGE, "field": field})

    # 按最近出现排序，显示与取值相同
    assert [(item["value"], item["count"]) for item in candidates] == expected
    assert all(item["alias"] == item["value"] for item in candidates)


@pytest.mark.parametrize(
    ("field", "expected"), [("process_names", ["order_api"]), ("process_pids", ["order,api:2341"])]
)
@pytest.mark.django_db(databases="__all__")
def test_topk_reads_limited_recent_rows_for_processes(query_rows, mocker, field, expected):
    mocker.patch(f"{HANDLER_MODULE}.ACTIVE_PROFILING_PROCESS_TOPK_RECENT_ROWS", 1)

    candidates = QueryActiveProfilingTopKResource().request({**TIME_RANGE, "field": field})

    assert [item["value"] for item in candidates] == expected


@pytest.mark.parametrize(
    ("field", "keyword", "expected"),
    [
        ("target", "0.0.3", [("127.0.0.3", 1)]),
        ("task_name", "adhoc", [("order-api-cpu-adhoc", 2)]),
        # 进程名里的逗号已由采集端归一化为 _，关键字同样归一化
        ("process_names", "order,api", [("order_api", 1)]),
        # PID 候选按进程名或 PID 片段命中
        ("process_pids", "300", [("java:3000", 1)]),
        ("process_pids", "order", [("order,api:2341", 1)]),
        # 空关键字等同不传
        ("process_names", "", [("order_api", 1), ("java", 1)]),
    ],
)
@pytest.mark.django_db(databases="__all__")
def test_topk_filters_candidates_by_keyword(query_rows, field, keyword, expected):
    candidates = QueryActiveProfilingTopKResource().request({**TIME_RANGE, "field": field, "keyword": keyword})

    assert [(item["value"], item["count"]) for item in candidates] == expected


@pytest.mark.django_db(databases="__all__")
def test_topk_keyword_reads_matching_rows_beyond_recent_rows(query_rows, mocker):
    mocker.patch(f"{HANDLER_MODULE}.ACTIVE_PROFILING_PROCESS_TOPK_RECENT_ROWS", 1)
    create_execution(
        [
            {
                "bk_host_id": 460,
                "ip": "127.0.0.12",
                "status": "succeed",
                "started_at": MID_AT + 100,
                "process_names": "java,nginx",
                "process_pids": "4000,812",
                "processes": [{"pid": 4000, "process_name": "java"}, {"pid": 812, "process_name": "nginx"}],
            }
        ],
        schedule_type="cron",
        task_id=13,
        scheduled_at=MID_AT,
        task_name="java-cpu",
        collection_method="java",
        collection_type="java_cpu",
        execution_status="succeed",
        status_summary={"succeed": 1},
    )

    candidates = QueryActiveProfilingTopKResource().request({**TIME_RANGE, "field": "process_pids", "keyword": "java"})

    # 只读包含关键字的行，最近一行之外的进程也能搜到；同一行里不包含关键字的 nginx 不作为候选
    assert [item["value"] for item in candidates] == ["java:4000"]


@pytest.mark.django_db(databases="__all__")
def test_rename_immediate_execution_allows_duplicated_name(query_rows, mocker):
    mocker.patch("apm.resources.get_request_tenant_id", return_value="system")

    for scheduled_at in (MID_AT, OLD_AT):
        request = {"bk_biz_id": 2, "scheduled_at": scheduled_at, "task_name": "renamed"}
        assert RenameActiveProfilingExecutionResource().request(request) is None

    # 任务名只存在执行行，任务历史、已采数据与详情都读它
    rows = ListActiveProfilingExecutionsResource().request({**TIME_RANGE, "filters": {"task_name": "renamed"}})
    assert [row["scheduled_at"] for row in rows] == [MID_AT, OLD_AT]
    assert {row["task"]["name"] for row in query_hosts(task_name="renamed")} == {"renamed"}


@pytest.mark.django_db(databases="__all__")
def test_rename_planned_execution_by_task_id(query_rows, mocker):
    mocker.patch("apm.resources.get_request_tenant_id", return_value="system")
    request = {"bk_biz_id": 2, "scheduled_at": RECENT_AT, "task_name": "renamed"}

    # 不带 task_id 只按立即执行定位
    with pytest.raises(ValueError):
        RenameActiveProfilingExecutionResource().request(request)
    with pytest.raises(CustomException):
        RenameActiveProfilingExecutionResource().request({**request, "task_id": 12, "task_name": ""})

    assert RenameActiveProfilingExecutionResource().request({**request, "task_id": 12}) is None

    # 只改这一次执行的任务名，计划的历史按任务 ID 筛选，不受改名影响
    rows = ListActiveProfilingExecutionsResource().request({**TIME_RANGE, "filters": {"task_id": 12}})
    assert [(row["scheduled_at"], row["task_name"]) for row in rows] == [(RECENT_AT, "renamed")]


@pytest.mark.django_db(databases="__all__")
def test_execution_detail_returns_all_hosts(query_rows):
    # 前端不给立即执行传 task_id，按立即执行与计划时间定位，响应也不返回 task_id
    detail = QueryActiveProfilingExecutionDetailResource().request({"bk_biz_id": 2, "scheduled_at": OLD_AT})

    assert "task_id" not in detail
    assert (detail["execution_status"], detail["total_hosts"]) == ("outdate", 2)
    assert detail["config"] == query_rows.expired.config
    # 成功的不带原因，过期后仍显示采集成功
    assert (detail["hosts"][0]["status"], detail["hosts"][0]["message"]) == ("outdate", "采集成功")
    assert detail["hosts"][1] == {
        "bk_host_id": 458,
        "ip": "127.0.0.3",
        "processes": [],
        "status": "failed",
        "error_type": "dispatch_failed",
        "message": "agent not ready",
        "started_at": OLD_AT + 200,
        "finished_at": OLD_AT + 200,
        "duration_ms": 30000,
    }
    assert "target_count" not in detail


@pytest.mark.django_db(databases="__all__")
def test_execution_detail_locates_legacy_immediate_without_task_id(query_rows):
    detail = QueryActiveProfilingExecutionDetailResource().request({"bk_biz_id": 2, "scheduled_at": MID_AT})

    assert "task_id" not in detail
    assert [(host["bk_host_id"], host["message"]) for host in detail["hosts"]] == [
        (459, "请检查agent状态及版本信息，若持续异常请联系管理员")
    ]

    with pytest.raises(ValueError):
        QueryActiveProfilingExecutionDetailResource().request({"bk_biz_id": 2, "task_id": 12, "scheduled_at": MID_AT})


@pytest.mark.django_db(databases="__all__")
def test_queries_require_enabled_biz():
    with pytest.raises(ValueError):
        QueryActiveProfilingHostsResource().request(TIME_RANGE)


@pytest.mark.parametrize(
    ("resource_cls", "request_data", "method"),
    [
        (QueryActiveProfilingHostsResource, TIME_RANGE, "query_hosts"),
        (ListActiveProfilingExecutionsResource, TIME_RANGE, "list_executions"),
        (QueryActiveProfilingTopKResource, {**TIME_RANGE, "field": "task_name"}, "query_topk"),
        (
            QueryActiveProfilingExecutionDetailResource,
            {"bk_biz_id": 2, "scheduled_at": RECENT_AT},
            "query_execution_detail",
        ),
    ],
)
@pytest.mark.parametrize(("source", "expected"), [(None, "mysql"), ("mysql", "mysql"), ("es", "es")])
def test_queries_default_to_mysql_and_route_es_by_source(mocker, resource_cls, request_data, method, source, expected):
    handlers = {name: mocker.MagicMock() for name in ACTIVE_PROFILING_QUERY_HANDLERS}
    mocker.patch.dict(ACTIVE_PROFILING_QUERY_HANDLERS, handlers)
    if source:
        request_data = {**request_data, "source": source}

    resource_cls().request(request_data)

    handlers[expected].assert_called_once_with(2)
    getattr(handlers[expected].return_value, method).assert_called_once()
    for name, handler in handlers.items():
        if name != expected:
            handler.assert_not_called()


DISPATCH_NOW_MS = 1788310801000
RESOURCE_GUARD_CONFIG = {"auto_stop_on_resource_pressure": True, "max_disk_usage": 1024, "min_mem_level": 100}
PROCESS_SELECTOR = {"type": "pid_file", "config": {"pid_path": "/var/run/demo.pid"}}
TWO_HOSTS_TARGET_CONFIG = {"node_type": "INSTANCE", "nodes": [{"bk_host_id": 456}, {"bk_host_id": 457}]}
TASK_SUBMIT_REQUEST = {
    "bk_biz_id": 2,
    "name": "java-cpu-daily",
    "collection_method": "java",
    "collection_type": "java_cpu",
    "target_config": {"node_type": "INSTANCE", "nodes": [{"bk_host_id": 456}]},
    "process_selector": PROCESS_SELECTOR,
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
IMMEDIATE_SCHEDULE = {"type": "immediate", "execute_at": 1788310800000, "timezone": "Asia/Shanghai"}
IMMEDIATE_REQUEST = {**TASK_SUBMIT_REQUEST, "schedule": IMMEDIATE_SCHEDULE, "target_config": TWO_HOSTS_TARGET_CONFIG}


@pytest.fixture
def deploy_apis(mocker):
    """作业平台、节点管理与 CMDB 都替换掉；业务已开通，新建的订阅 ID 从 9001 递增"""
    mocker.patch(f"{HANDLER_MODULE}.get_request_tenant_id", return_value="system")
    mocker.patch(f"{HANDLER_MODULE}.get_request_username", return_value="admin")
    mocker.patch(f"{HANDLER_MODULE}.time").time.return_value = DISPATCH_NOW_MS / 1000
    profile_datasource = mocker.patch(f"{HANDLER_MODULE}.ProfileDataSource")
    profile_datasource.objects.filter.return_value.first.return_value = SimpleNamespace(bk_data_id=777)
    event_group = mocker.patch(f"{HANDLER_MODULE}.EventGroup")
    event_group.objects.filter.return_value.first.return_value = SimpleNamespace(bk_data_id=555)
    subscription_ids = itertools.count(9001)

    def submit_job(**kwargs):
        bk_host_id = kwargs["target_server"]["host_id_list"][0]
        return {"job_instance_id": 1000 + bk_host_id, "step_instance_id": 2000 + bk_host_id}

    return {
        "job": mocker.patch("core.drf_resource.api.job.fast_execute_script", side_effect=submit_job),
        "hosts": mocker.patch(
            "core.drf_resource.api.cmdb.get_host_by_id",
            return_value=[
                SimpleNamespace(bk_host_id=456, bk_host_innerip="127.0.0.1", bk_host_innerip_v6=""),
                SimpleNamespace(bk_host_id=457, bk_host_innerip="", bk_host_innerip_v6="fd00::9"),
            ],
        ),
        "create": mocker.patch(
            "core.drf_resource.api.node_man.create_subscription",
            side_effect=lambda **kwargs: {"subscription_id": next(subscription_ids)},
        ),
        "update": mocker.patch("core.drf_resource.api.node_man.update_subscription"),
        "switch": mocker.patch("core.drf_resource.api.node_man.switch_subscription"),
        "run": mocker.patch("core.drf_resource.api.node_man.run_subscription"),
        "profile_datasource": profile_datasource,
        "event_group": event_group,
    }


def decode_cli_config(call):
    """作业平台传输层 base64 之内还有一层 base64，才是脚本读到的 $1"""
    return json.loads(base64.b64decode(base64.b64decode(call.kwargs["script_param"])))


def host_states(execution, *fields):
    return list(
        ActiveProfilingHostExecution.objects.filter(execution_id=execution.id)
        .order_by("bk_host_id")
        .values_list("bk_host_id", *fields)
    )


def beat_task(task_id, bk_host_id=456, **overrides):
    """下发给 Beat 的单机 task，三类执行都带 task_id"""
    return {
        "schedule": TASK_SUBMIT_REQUEST["schedule"],
        "collector_config": TASK_SUBMIT_REQUEST["collector_config"],
        "resource_guard_config": RESOURCE_GUARD_CONFIG,
        "task_id": task_id,
        "bk_tenant_id": "system",
        "bk_biz_id": 2,
        "name": TASK_SUBMIT_REQUEST["name"],
        "creator": "admin",
        "collection_method": "java",
        "collection_type": "java_cpu",
        "event_data_id": 555,
        "profile_data_id": 777,
        "profile_app_name": BUILTIN_PROFILING_APP_NAME,
        "profile_service_name": "active_allocation",
        "bk_host_id": bk_host_id,
        "process_selector": {"type": "pid_file", "pid_path": "/var/run/demo.pid"},
        **overrides,
    }


@pytest.mark.django_db(databases="__all__")
def test_immediate_creates_rows_then_dispatches_with_execution_id_as_task_id(deploy_apis):
    assert SubmitActiveProfilingTaskResource().request(IMMEDIATE_REQUEST) is None

    execution = ActiveProfilingExecution.objects.get(bk_biz_id=2, schedule_type="immediate")
    assert execution.task_id == execution.id
    assert (execution.scheduled_at, execution.task_name, execution.creator) == (
        1788310800000,
        "java-cpu-daily",
        "admin",
    )
    # 执行配置是提交的完整配置，target_config 含全部目标主机
    assert execution.config == {
        "schedule": IMMEDIATE_SCHEDULE,
        "collector_config": {"duration_sec": 30},
        "resource_guard_config": RESOURCE_GUARD_CONFIG,
        "target_config": TWO_HOSTS_TARGET_CONFIG,
        "process_selector": PROCESS_SELECTOR,
    }

    job_calls = deploy_apis["job"].call_args_list
    assert [call.kwargs["target_server"] for call in job_calls] == [{"host_id_list": [456]}, {"host_id_list": [457]}]
    assert base64.b64decode(job_calls[0].kwargs["script_content"]).decode() == (
        'echo "$1" | base64 -d | /usr/local/gse/plugins/bin/bkmonitorbeat '
        "-c /usr/local/gse/plugins/etc/bkmonitorbeat.conf -active-profile-run\n"
    )
    assert decode_cli_config(job_calls[0]) == beat_task(execution.id, schedule=IMMEDIATE_SCHEDULE)

    # 作业受理后主机行由占位行直接更新为 started，不再上报 Event，执行行随之重算
    assert host_states(execution, "ip", "status", "started_at", "event_time") == [
        (456, "127.0.0.1", "running", DISPATCH_NOW_MS, DISPATCH_NOW_MS),
        (457, "fd00::9", "running", DISPATCH_NOW_MS, DISPATCH_NOW_MS),
    ]
    execution.refresh_from_db()
    assert (execution.execution_status, execution.status_summary, execution.target_count, execution.started_at) == (
        "running",
        {"running": 2},
        2,
        DISPATCH_NOW_MS,
    )


@pytest.mark.django_db(databases="__all__")
def test_immediate_job_failure_writes_failed_host_and_continues(deploy_apis):
    submit_job = deploy_apis["job"].side_effect

    def fail_first_host(**kwargs):
        if kwargs["target_server"]["host_id_list"] == [456]:
            raise BKAPIError(system_name="bk-job", url="", result={"message": "agent not ready"})
        return submit_job(**kwargs)

    deploy_apis["job"].side_effect = fail_first_host

    SubmitActiveProfilingTaskResource().request(IMMEDIATE_REQUEST)

    # 下发失败的主机不会再有采集端的 finished，直接写失败终态
    execution = ActiveProfilingExecution.objects.get(bk_biz_id=2, schedule_type="immediate")
    (failed_host, running_host) = host_states(execution, "status", "error_type", "started_at", "finished_at", "message")
    assert failed_host[:5] == (456, "failed", "dispatch_failed", DISPATCH_NOW_MS, DISPATCH_NOW_MS)
    assert "agent not ready" in failed_host[5]
    assert running_host[:2] == (457, "running")
    execution.refresh_from_db()
    assert (execution.execution_status, execution.status_summary) == ("running", {"failed": 1, "running": 1})


@pytest.mark.django_db(databases="__all__")
def test_immediate_keeps_dispatching_when_host_write_fails(deploy_apis, mocker):
    mocker.patch.object(
        ActiveProfilingExecutionWriter, "write_started", autospec=True, side_effect=RuntimeError("db gone")
    )

    assert SubmitActiveProfilingTaskResource().request(IMMEDIATE_REQUEST) is None

    # 写库失败只记日志，其余主机照常下发；主机保留占位行，终态由采集端的 finished 经 BMW 补上
    assert deploy_apis["job"].call_count == 2
    execution = ActiveProfilingExecution.objects.get(bk_biz_id=2, schedule_type="immediate")
    assert host_states(execution, "status", "started_at", "event_time", "unknown_at") == [
        (456, "running", None, 0, 1788310800000 + 330 * 1000),
        (457, "running", None, 0, 1788310800000 + 330 * 1000),
    ]


@pytest.mark.django_db(databases="__all__")
def test_immediate_requires_enabled_biz_before_creating_rows(deploy_apis):
    deploy_apis["profile_datasource"].objects.filter.return_value.first.return_value = None

    with pytest.raises(ValueError):
        SubmitActiveProfilingTaskResource().request(IMMEDIATE_REQUEST)

    assert not ActiveProfilingExecution.objects.exists()
    deploy_apis["job"].assert_not_called()


def create_running_execution(hosts, schedule_type="cron", task_id=123, scheduled_at=DISPATCH_NOW_MS - 60 * 1000):
    execution = ActiveProfilingExecution.objects.create(
        bk_biz_id=2,
        schedule_type=schedule_type,
        task_id=task_id,
        scheduled_at=scheduled_at,
        task_name="java-cpu-daily",
        creator="admin",
        collection_method="java",
        collection_type="java_cpu",
        execution_status="running",
        target_count=len(hosts),
        config={"collector_config": {"duration_sec": 30}},
    )
    for host in hosts:
        ActiveProfilingHostExecution.objects.create(
            execution_id=execution.id, bk_biz_id=2, scheduled_at=scheduled_at, **host
        )
    return execution


# 456 已开始采集，457 还没有任何 Event 的占位行，458 已成功结束
CANCEL_HOSTS = [
    {
        "bk_host_id": 456,
        "ip": "127.0.0.1",
        "status": "running",
        "started_at": DISPATCH_NOW_MS - 50000,
        "event_time": DISPATCH_NOW_MS,
    },
    {"bk_host_id": 457, "ip": "127.0.0.2", "status": "running", "event_time": 0},
    {
        "bk_host_id": 458,
        "ip": "127.0.0.3",
        "status": "succeed",
        "started_at": DISPATCH_NOW_MS - 50000,
        "finished_at": DISPATCH_NOW_MS - 20000,
        "event_time": DISPATCH_NOW_MS - 20000,
    },
]


def cancel_request(execution, *bk_host_ids, **overrides):
    ips = {host["bk_host_id"]: host["ip"] for host in CANCEL_HOSTS}
    return {
        "bk_biz_id": 2,
        "task_id": execution.task_id,
        "scheduled_at": execution.scheduled_at,
        "hosts": [{"bk_host_id": bk_host_id, "ip": ips.get(bk_host_id, "127.0.1.10")} for bk_host_id in bk_host_ids],
        **overrides,
    }


@pytest.mark.django_db(databases="__all__")
def test_cancel_dispatches_running_hosts_and_writes_cancelled(deploy_apis):
    execution = create_running_execution(CANCEL_HOSTS)

    assert CancelActiveProfilingExecutionResource().request(cancel_request(execution, 456, 457, 458)) is None

    job_calls = deploy_apis["job"].call_args_list
    assert [call.kwargs["target_server"] for call in job_calls] == [{"host_id_list": [456]}, {"host_id_list": [457]}]
    assert decode_cli_config(job_calls[0]) == {
        "bk_tenant_id": "system",
        "bk_biz_id": 2,
        "task_id": 123,
        "schedule_type": "cron",
        "scheduled_at": execution.scheduled_at,
        "bk_host_id": 456,
    }
    # 只改仍为 running 的主机行，event_time 不变，之后真实的 finished 会覆盖
    assert host_states(execution, "status", "finished_at", "event_time") == [
        (456, "cancelled", DISPATCH_NOW_MS, DISPATCH_NOW_MS),
        (457, "cancelled", DISPATCH_NOW_MS, 0),
        (458, "succeed", DISPATCH_NOW_MS - 20000, DISPATCH_NOW_MS - 20000),
    ]
    execution.refresh_from_db()
    assert (execution.execution_status, execution.status_summary, execution.finished_at) == (
        "partial_succeed",
        {"cancelled": 2, "succeed": 1},
        DISPATCH_NOW_MS,
    )


@pytest.mark.django_db(databases="__all__")
def test_cancel_writes_placeholder_even_if_dispatch_fails(deploy_apis):
    execution = create_running_execution(CANCEL_HOSTS)
    deploy_apis["job"].side_effect = BKAPIError(system_name="bk-job", url="", result={})

    # 上报过 Event 的主机下发失败要报错重试；占位行没有证据表明在采集，仍写 cancelled
    with pytest.raises(ValueError, match="127.0.0.1"):
        CancelActiveProfilingExecutionResource().request(cancel_request(execution, 456, 457))

    assert host_states(execution, "status") == [(456, "running"), (457, "cancelled"), (458, "succeed")]


@pytest.mark.django_db(databases="__all__")
def test_cancel_rejects_host_outside_execution(deploy_apis):
    execution = create_running_execution(CANCEL_HOSTS)

    with pytest.raises(ValueError, match="127.0.1.10"):
        CancelActiveProfilingExecutionResource().request(cancel_request(execution, 456, 999))

    deploy_apis["job"].assert_not_called()


@pytest.mark.django_db(databases="__all__")
def test_cancel_locates_immediate_without_task_id(deploy_apis):
    execution = create_running_execution(CANCEL_HOSTS[:1], schedule_type="immediate", task_id=30521)
    request = cancel_request(execution, 456)
    del request["task_id"]

    CancelActiveProfilingExecutionResource().request(request)

    payload = decode_cli_config(deploy_apis["job"].call_args)
    assert (payload["schedule_type"], payload["task_id"]) == ("immediate", 30521)


@pytest.mark.django_db(databases="__all__")
def test_saas_writes_never_regress_finished_host(deploy_apis):
    """BMW 已写入更新的终态时，SaaS 的受理与下发失败写入都跳过"""
    execution = create_running_execution([{**CANCEL_HOSTS[2], "bk_host_id": 456, "event_time": DISPATCH_NOW_MS + 1000}])
    writer = ActiveProfilingExecutionWriter(execution)

    writer.write_started(456, DISPATCH_NOW_MS)
    writer.write_dispatch_failed(456, DISPATCH_NOW_MS, "agent not ready")

    assert host_states(execution, "status", "event_time") == [(456, "succeed", DISPATCH_NOW_MS + 1000)]


def create_planned_task(**overrides):
    request = {**TASK_SUBMIT_REQUEST, **overrides}
    SubmitActiveProfilingTaskResource().request(request)
    return ActiveProfilingTask.objects.get(bk_biz_id=request["bk_biz_id"], name=request["name"])


def sent_host_tasks(call):
    return call.kwargs["steps"][0]["params"]["context"]["host_tasks"]


@pytest.mark.django_db(databases="__all__")
def test_submit_planned_task_persists_and_deploys_with_task_id(deploy_apis):
    task = create_planned_task()

    assert (task.collection_type, task.schedule, task.process_selector) == (
        "java_cpu",
        TASK_SUBMIT_REQUEST["schedule"],
        PROCESS_SELECTOR,
    )
    assert (task.deployment_status, task.subscription_id, task.is_enabled) == ("success", 9001, True)
    kwargs = deploy_apis["create"].call_args.kwargs
    assert kwargs["bk_tenant_id"] == "system"
    step = kwargs["steps"][0]
    assert step["config"] == {
        "plugin_name": "bkmonitorbeat",
        "plugin_version": "0.0.5",
        "config_templates": [{"name": "bkmonitorbeat_active_profile.conf", "version": "latest"}],
    }
    assert step["params"]["context"] == {
        "host_tasks": {"456": [beat_task(task.id, creator=task.create_user)]},
        "target_hosts": [{"bk_host_id": 456, "ip": "127.0.0.1"}],
    }
    deploy_apis["switch"].assert_called_once_with(bk_tenant_id="system", subscription_id=9001, action="enable")


@pytest.mark.django_db(databases="__all__")
def test_submit_rejects_duplicated_name_in_same_biz(deploy_apis):
    create_planned_task()

    with pytest.raises(ValueError):
        SubmitActiveProfilingTaskResource().request(TASK_SUBMIT_REQUEST)


@pytest.mark.django_db(databases="__all__")
def test_list_tasks_returns_tasks_and_paginates(deploy_apis, mocker):
    mocker.patch("apm.resources.time.time", return_value=1788310800)
    task = create_planned_task()
    create_planned_task(name="java-cpu-hourly")
    create_planned_task(bk_biz_id=3, name="other-biz")

    result = ListActiveProfilingTasksResource().request({"bk_biz_id": 2, "page": 2, "page_size": 1})

    assert (result["page"], result["page_size"], result["total"]) == (2, 1, 2)
    assert result["data"] == [
        {
            "task_id": task.id,
            "task_status": "enabled",
            "deployment_status": "success",
            "creator": task.create_user,
            "updated_at": int(ActiveProfilingTask.objects.get(id=task.id).update_time.timestamp() * 1000),
            **{field: TASK_SUBMIT_REQUEST[field] for field in ActiveProfilingTask.CONFIG_FIELDS},
        }
    ]


@pytest.mark.parametrize(
    ("deployment_status", "schedule", "now_sec", "expected"),
    [
        ("success", TASK_SUBMIT_REQUEST["schedule"], 1788915600 + 1, "outdate"),
        ("success", {"type": "once_at", "execute_at": 1788310800000}, 1788310800 + 1, "outdate"),
        ("success", {"type": "cron", "cron_expression": "0 */2 * * *"}, 1788915600 + 1, "success"),
        ("failed", TASK_SUBMIT_REQUEST["schedule"], 1788915600 + 1, "failed"),
    ],
)
def test_list_tasks_displays_expired_only_for_finished_successful_schedules(
    mocker, deployment_status, schedule, now_sec, expected
):
    mocker.patch("apm.resources.time.time", return_value=now_sec)
    task = SimpleNamespace(deployment_status=deployment_status, schedule=schedule)

    assert ListActiveProfilingTasksResource._display_deployment_status(task) == expected


@pytest.mark.django_db(databases="__all__")
def test_edit_task_updates_in_place_and_redeploys(deploy_apis):
    task = create_planned_task()

    EditActiveProfilingTaskResource().request(
        {**TASK_SUBMIT_REQUEST, "task_id": task.id, "name": "java-cpu-hourly", "target_config": TWO_HOSTS_TARGET_CONFIG}
    )

    task.refresh_from_db()
    assert (task.name, task.deployment_status) == ("java-cpu-hourly", "success")
    kwargs = deploy_apis["update"].call_args.kwargs
    assert (kwargs["subscription_id"], kwargs["scope"]["nodes"]) == (9001, TWO_HOSTS_TARGET_CONFIG["nodes"])
    assert set(sent_host_tasks(deploy_apis["update"].call_args)) == {"456", "457"}


@pytest.mark.django_db(databases="__all__")
@pytest.mark.filterwarnings("ignore:DateTimeField.*received a naive datetime:RuntimeWarning")
def test_switch_then_delete_task(deploy_apis):
    task = create_planned_task()

    with pytest.raises(ValueError):
        DeleteActiveProfilingTaskResource().request({"bk_biz_id": 2, "task_id": task.id})

    SwitchActiveProfilingTaskResource().request({"bk_biz_id": 2, "task_id": task.id, "enabled": False})
    task.refresh_from_db()
    assert (task.is_enabled, task.deployment_status) == (False, "success")
    assert deploy_apis["run"].call_args.kwargs["actions"] == {"bkmonitorbeat_active_profile": "STOP"}

    DeleteActiveProfilingTaskResource().request({"bk_biz_id": 2, "task_id": task.id})
    assert deploy_apis["run"].call_args.kwargs["actions"] == {"bkmonitorbeat_active_profile": "UNINSTALL_AND_DELETE"}
    assert ActiveProfilingTask.origin_objects.filter(id=task.id, is_deleted=True).exists()
    # 软删后名称可复用
    create_planned_task()


@pytest.mark.django_db(databases="__all__")
def test_task_operations_reject_other_biz_task(deploy_apis):
    task = create_planned_task()

    with pytest.raises(ValueError):
        SwitchActiveProfilingTaskResource().request({"bk_biz_id": 3, "task_id": task.id, "enabled": False})


def planned_task(task_id, is_enabled=True, subscription_id=0, **overrides):
    """不落库的计划，id 即下发给 Beat 的 task_id"""
    config = {**TASK_SUBMIT_REQUEST, **overrides}
    return ActiveProfilingTask(
        id=task_id,
        bk_biz_id=2,
        is_enabled=is_enabled,
        subscription_id=subscription_id,
        create_user="admin",
        **{field: config.get(field, {}) for field in ActiveProfilingTask.CONFIG_FIELDS},
    )


def test_nodeman_deploy_failure_marks_task_failed(deploy_apis, mocker):
    mocker.patch.object(ActiveProfilingTask, "save")
    task = planned_task(1)
    deploy_apis["create"].side_effect = BKAPIError(system_name="bk-nodeman", url="", result={"message": "failed"})

    assert ActiveProfilingNodeManHandler(2).deploy(task) is False

    assert (task.subscription_id, task.deployment_status) == (0, "failed")
    deploy_apis["switch"].assert_not_called()


STOP_NOW_MS = 1788411900000
ONE_DAY_MS = 24 * 3600 * 1000


def test_stop_expired_tasks_disables_tasks_one_day_after_last_run(deploy_apis, mocker):
    mocker.patch.object(ActiveProfilingTask, "save")
    mocker.patch(f"{HANDLER_MODULE}.time").time.return_value = STOP_NOW_MS / 1000
    mocker.patch(f"{HANDLER_MODULE}.bk_biz_id_to_bk_tenant_id", return_value="system")
    set_tenant = mocker.patch(f"{HANDLER_MODULE}.set_local_tenant_id")
    objects = mocker.patch.object(ActiveProfilingTask, "objects")
    endless_schedule = {k: v for k, v in TASK_SUBMIT_REQUEST["schedule"].items() if k != "effective_end_at"}
    tasks = [
        planned_task(1, subscription_id=8001, schedule={"type": "once_at", "execute_at": STOP_NOW_MS - ONE_DAY_MS - 1}),
        planned_task(
            2, subscription_id=8002, schedule={**endless_schedule, "effective_end_at": STOP_NOW_MS - ONE_DAY_MS - 1}
        ),
        planned_task(3, subscription_id=8003, schedule={"type": "once_at", "execute_at": STOP_NOW_MS - ONE_DAY_MS + 1}),
        planned_task(4, subscription_id=8004, schedule=endless_schedule),
    ]
    objects.filter.return_value.exclude.return_value = tasks

    stop_expired_active_profiling_tasks()

    # 最后一次执行过去 1 天的计划走手动停用的同一流程；没设生效结束时间的 cron 一直有效
    assert [task.is_enabled for task in tasks] == [False, False, True, True]
    assert [call.kwargs["subscription_id"] for call in deploy_apis["run"].call_args_list] == [8001, 8002]
    assert [task.deployment_status for task in tasks[:2]] == ["outdate", "outdate"]
    # 停用失败的计划保持部署失败，第二天再试；订阅没建成的计划不处理
    objects.filter.assert_called_once_with(Q(is_enabled=True) | Q(deployment_status="failed"))
    objects.filter.return_value.exclude.assert_called_once_with(subscription_id=0)
    set_tenant.assert_called_once_with("system")


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
EXECUTION_DETAIL_REQUEST = {"bk_biz_id": 2, "scheduled_at": 1788310800000, "task_id": 123}
STATIC_COMMAND_SELECTOR = {
    "type": "command",
    "config": {
        "match_pattern": "/data/order-api",
        "exclude_pattern": "",
        "enable_dynamic_collection": False,
        "host_pids": [{"bk_host_id": 456, "pid": 2341}, {"bk_host_id": 456, "pid": 2342}],
    },
}


def query_es_hosts(request):
    return QueryActiveProfilingHostsResource().request({**request, "source": "es"})


def list_es_executions(request):
    return ListActiveProfilingExecutionsResource().request({**request, "source": "es"})


def query_es_topk(request):
    return QueryActiveProfilingTopKResource().request({**request, "source": "es"})


def query_es_detail(request):
    return QueryActiveProfilingExecutionDetailResource().request({**request, "source": "es"})


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


def finished_event(status, started_at, finished_at, processes=(), config=None, message="", error_type="", **kwargs):
    content = {
        "started_at": started_at,
        "finished_at": finished_at,
        "execution_duration_ms": finished_at - started_at,
        "config": config or host_config(kwargs.get("bk_host_id", 456)),
        "processes": list(processes),
        "error_type": error_type,
        "message": message,
    }
    return active_event("active_profiling_finished", content, status, **kwargs)


def with_filters(**filters):
    return {**EVENT_LIST_REQUEST, "filters": {**EVENT_LIST_REQUEST["filters"], **filters}}


@pytest.fixture
def host_query_apis(mocker):
    mocker.patch(f"{ES_HANDLER_MODULE}.get_request_tenant_id", return_value="system")
    mocker.patch(f"{ES_HANDLER_MODULE}.time").time.return_value = HOST_QUERY_NOW / 1000
    profile_datasource = mocker.patch(f"{ES_HANDLER_MODULE}.ProfileDataSource")
    profile_datasource.objects.filter.return_value.first.return_value = SimpleNamespace(
        bk_data_id=777, retention=RETENTION_DAYS
    )
    event_group = mocker.patch(f"{ES_HANDLER_MODULE}.EventGroup")
    event_group.objects.filter.return_value.first.return_value = SimpleNamespace(table_id="2_bkmonitor_event_555")
    # 按 ES 排序后的结果，查询按 offset/limit 切片返回
    events = []

    def query(table_id, query_body):
        return events[query_body["offset"] : query_body["offset"] + query_body["limit"]]

    return {
        "events": events,
        "query": mocker.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", side_effect=query),
        "event_group": event_group,
        "profile_datasource": profile_datasource,
    }


def sent_query_bodies(query):
    return [call.kwargs["query_body"] for call in query.call_args_list]


def test_es_query_hosts_pairs_events_into_host_execution_rows(host_query_apis):
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

    result = query_es_hosts(EVENT_LIST_REQUEST)

    assert result[:2] == [
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
            # 采集时长取配置的 duration_sec，采集中的主机同样返回
            "duration_ms": 30000,
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
            "duration_ms": 30000,
            "status": "succeed",
        },
    ]
    # 只有 started 且超过“采集时长 + 300 秒”为 unknown；成功结果按 scheduled_at 超过保留期为 outdate
    assert [row["status"] for row in result[2:]] == ["unknown", "outdate"]
    assert result[3]["finished_at"] == EXPIRE_BEFORE - 500


def test_es_query_hosts_uses_latest_duplicated_event(host_query_apis):
    host_query_apis["events"].extend(
        [
            finished_event("failed", 1788411801000, 1788411802000),
            finished_event("succeed", 1788411801000, 1788411832000),
        ]
    )

    assert [row["status"] for row in query_es_hosts(EVENT_LIST_REQUEST)] == ["failed"]


def test_es_query_hosts_treats_omitted_processes_as_empty(host_query_apis):
    event = finished_event("failed", 1788411801000, 1788411801100)
    content = json.loads(event["event"]["content"])
    # 旧版采集端没拿到进程时省略 processes 字段
    del content["processes"]
    event["event"]["content"] = json.dumps(content)
    host_query_apis["events"].append(event)

    assert query_es_hosts(EVENT_LIST_REQUEST)[0]["processes"] == []


@pytest.mark.parametrize(("elapsed_ms", "status"), [(300 * 1000, "running"), (300 * 1000 + 1, "unknown")])
def test_es_query_hosts_counts_go_heap_duration_as_zero(host_query_apis, elapsed_ms, status):
    host_query_apis["events"].append(
        started_event(
            HOST_QUERY_NOW - elapsed_ms, config=host_config(collector_config={"ip_address": "127.0.0.1", "port": 6060})
        )
    )

    row = query_es_hosts(EVENT_LIST_REQUEST)[0]
    # Go Heap 是即时快照，没有采集时长
    assert (row["status"], row["duration_ms"]) == (status, None)


def test_es_query_hosts_pushes_filters_down_to_es(host_query_apis):
    query_es_hosts(
        with_filters(
            ips=["127.0.0.1"],
            task_id=123,
            task_name="cpu",
            process_names=["my,app", "java"],
            process_pids=["1234", "postgres: writer:812"],
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
        # 维度无法按同一进程配对，PID 候选的 进程名:PID 只取最后一个冒号后的 PID
        "process_pids__include": ["1234", "812"],
        "task_id": "123",
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


def test_es_query_hosts_skips_empty_filters(host_query_apis):
    query_es_hosts(EVENT_LIST_REQUEST)

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
def test_es_query_hosts_narrows_scheduled_at_for_derived_status(
    host_query_apis, status, status_filter, scheduled_at_range
):
    query_es_hosts(with_filters(status=status))

    filter_dict = sent_query_bodies(host_query_apis["query"])[0]["query_configs"][0]["filter_dict"]
    assert filter_dict.get("status") == status_filter
    assert (filter_dict["scheduled_at__gte"], filter_dict["scheduled_at__lte"]) == scheduled_at_range


def test_es_query_hosts_running_filter_skips_finished_rows(host_query_apis):
    host_query_apis["events"].extend(
        [
            finished_event("succeed", 1788411801000, 1788411832000, bk_host_id=457),
            started_event(1788411801000, bk_host_id=457),
            started_event(1788411801000, bk_host_id=458),
        ]
    )

    result = query_es_hosts(with_filters(status="running"))

    assert [(row["bk_host_id"], row["status"]) for row in result] == [(458, "running")]


@pytest.mark.parametrize(
    ("status", "finished_at", "expected"),
    [
        ("succeed", HOST_QUERY_NOW - ACTIVE_PROFILING_PARSING_MS + 1, "parsing"),
        ("partial_succeed", HOST_QUERY_NOW - ACTIVE_PROFILING_PARSING_MS + 1, "parsing"),
        ("succeed", HOST_QUERY_NOW - ACTIVE_PROFILING_PARSING_MS, "succeed"),
        ("failed", HOST_QUERY_NOW - 1, "failed"),
    ],
)
def test_es_query_hosts_displays_parsing_until_result_stored(host_query_apis, status, finished_at, expected):
    host_query_apis["events"].append(finished_event(status, finished_at - 1000, finished_at))

    assert query_es_hosts(EVENT_LIST_REQUEST)[0]["status"] == expected


def test_es_query_hosts_succeed_filter_skips_parsing_rows(host_query_apis):
    host_query_apis["events"].extend(
        [
            finished_event("succeed", HOST_QUERY_NOW - 2000, HOST_QUERY_NOW - 1000, bk_host_id=457),
            finished_event("succeed", 1788411801000, 1788411832000, bk_host_id=458),
        ]
    )

    result = query_es_hosts(with_filters(status="succeed"))

    assert [(row["bk_host_id"], row["status"]) for row in result] == [(458, "succeed")]


def test_es_query_hosts_rejects_unknown_status_filter(host_query_apis):
    with pytest.raises(ValueError):
        query_es_hosts(with_filters(status="unknown"))

    host_query_apis["query"].assert_not_called()


def test_es_query_hosts_paginates_by_rows(host_query_apis):
    host_query_apis["events"].extend(
        started_event(1788411801000, bk_host_id=bk_host_id) for bk_host_id in range(456, 461)
    )

    result = query_es_hosts({**EVENT_LIST_REQUEST, "offset": 1, "limit": 2})

    assert [row["bk_host_id"] for row in result] == [457, 458]
    # 首批按每行最多两条事件估算：2 * (offset + limit) + 1
    assert [(body["offset"], body["limit"]) for body in sent_query_bodies(host_query_apis["query"])] == [(0, 7)]


def test_es_query_hosts_reads_next_batch_until_last_row_is_complete(host_query_apis, mocker):
    mocker.patch(f"{ES_HANDLER_MODULE}.ACTIVE_PROFILING_ES_QUERY_BATCH_SIZE", 2)
    host_query_apis["events"].extend(
        [
            finished_event("succeed", 1788411801000, 1788411832000),
            finished_event("failed", 1788411801000, 1788411802000),
            started_event(1788411801000),
            started_event(1788411801000, bk_host_id=457),
        ]
    )

    result = query_es_hosts({**EVENT_LIST_REQUEST, "limit": 1})

    assert [(row["bk_host_id"], row["status"]) for row in result] == [(456, "succeed")]
    # 首批 3 条都属于第一行，要读到下一行的事件才能确认第一行已完整
    assert [(body["offset"], body["limit"]) for body in sent_query_bodies(host_query_apis["query"])] == [
        (0, 3),
        (3, 2),
    ]


def test_es_query_hosts_rejects_when_scanned_events_exceed_limit(host_query_apis, mocker):
    mocker.patch(f"{ES_HANDLER_MODULE}.ACTIVE_PROFILING_ES_QUERY_MAX_SIZE", 4)
    host_query_apis["events"].extend(
        finished_event("succeed", 1788411801000, 1788411832000, bk_host_id=bk_host_id) for bk_host_id in range(456, 462)
    )

    with pytest.raises(ValueError):
        query_es_hosts({**EVENT_LIST_REQUEST, "limit": 5})


def test_es_query_hosts_requires_enabled_event_group(host_query_apis):
    host_query_apis["event_group"].objects.filter.return_value.first.return_value = None

    with pytest.raises(ValueError):
        query_es_hosts(EVENT_LIST_REQUEST)

    host_query_apis["query"].assert_not_called()


def test_es_query_hosts_requires_enabled_profile_datasource(host_query_apis):
    host_query_apis["profile_datasource"].objects.filter.return_value.first.return_value = None

    with pytest.raises(ValueError):
        query_es_hosts(EVENT_LIST_REQUEST)

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


def test_es_list_executions_aggregates_all_hosts_into_execution_rows(host_query_apis):
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

    result = list_es_executions(EVENT_LIST_REQUEST)

    # immediate 不返回 task_id；仍有主机运行时外层不结束
    assert result[:2] == [
        {
            "task_name": "native-cpu",
            "schedule_type": "immediate",
            "scheduled_at": 1788411800000,
            "collection_method": "perf",
            "collection_type": "native_cpu",
            "creator": "admin",
            "started_at": 1788411801000,
            "finished_at": None,
            "duration_ms": 30000,
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
            "duration_ms": 30000,
            "execution_status": "partial_succeed",
            "status_summary": {"succeed": 1, "failed": 1},
            "target_count": 2,
            "hosts": [{"bk_host_id": 456, "ip": "127.0.0.1"}, {"bk_host_id": 457, "ip": "127.0.0.2"}],
        },
    ]
    assert (result[2]["execution_status"], result[2]["status_summary"]) == (
        "outdate",
        {"outdate": 1},
    )
    # 没有主机/进程筛选时一次扫描，首批至少读一整批
    (query_body,) = sent_query_bodies(host_query_apis["query"])
    assert (query_body["offset"], query_body["limit"]) == (0, 500)


def test_es_list_executions_pushes_execution_filters_down_to_es(host_query_apis):
    list_es_executions(
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
def test_es_list_executions_narrows_scheduled_at_for_status(host_query_apis, status, scheduled_at_range):
    list_es_executions(with_filters(status=status))

    filter_dict = sent_query_bodies(host_query_apis["query"])[0]["query_configs"][0]["filter_dict"]
    assert "status" not in filter_dict
    assert (filter_dict["scheduled_at__gte"], filter_dict["scheduled_at__lte"]) == scheduled_at_range


def test_es_list_executions_filters_aggregated_status_in_memory(host_query_apis):
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

    result = list_es_executions(with_filters(status="partial_succeed"))

    assert [(row["scheduled_at"], row["execution_status"]) for row in result] == [(1788310800000, "partial_succeed")]


def test_es_list_executions_rejects_unknown_status_filter(host_query_apis):
    with pytest.raises(ValueError):
        list_es_executions(with_filters(status="unknown"))

    host_query_apis["query"].assert_not_called()


def test_es_list_executions_paginates_by_execution_rows(host_query_apis):
    scheduled_ats = [1788411800000 - index * 1000 for index in range(5)]
    host_query_apis["events"].extend(
        started_event(scheduled_at + 1000, scheduled_at=scheduled_at) for scheduled_at in scheduled_ats
    )

    result = list_es_executions({**EVENT_LIST_REQUEST, "offset": 1, "limit": 2})

    assert [row["scheduled_at"] for row in result] == scheduled_ats[1:3]
    assert [(body["offset"], body["limit"]) for body in sent_query_bodies(host_query_apis["query"])] == [(0, 500)]


def test_es_list_executions_reads_next_batch_until_last_execution_is_complete(host_query_apis, mocker):
    mocker.patch(f"{ES_HANDLER_MODULE}.ACTIVE_PROFILING_ES_EXECUTION_BATCH_SIZE", 2)
    for bk_host_id in (456, 457, 458):
        host_query_apis["events"].extend(
            [
                finished_event("succeed", 1788411801000, 1788411832000, bk_host_id=bk_host_id),
                started_event(1788411801000, bk_host_id=bk_host_id),
            ]
        )
    host_query_apis["events"].append(started_event(1788310801000, scheduled_at=1788310800000))

    result = list_es_executions({**EVENT_LIST_REQUEST, "limit": 1})

    assert [(row["scheduled_at"], row["target_count"]) for row in result] == [(1788411800000, 3)]
    # 首批按 2 * 行数 + 1 估算；要读到下一次执行的 Event 才能确认第一次执行的主机已经完整
    assert [(body["offset"], body["limit"]) for body in sent_query_bodies(host_query_apis["query"])] == [
        (0, 3),
        (3, 2),
        (5, 2),
    ]


@pytest.mark.parametrize("filters", [{"ips": ["127.0.0.2"]}, {"process_names": ["jav"]}, {"process_pids": ["81"]}])
def test_es_list_executions_selects_by_host_then_aggregates_all_hosts(host_query_apis, filters):
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

    result = list_es_executions(with_filters(**filters))

    # 主机/进程只决定选中哪些执行，汇总仍基于该执行的全部主机
    assert [
        (row["scheduled_at"], row["execution_status"], row["status_summary"], row["target_count"]) for row in result
    ] == [(1788411800000, "partial_succeed", {"succeed": 1, "failed": 1}, 2)]
    select_body, fetch_body = sent_query_bodies(host_query_apis["query"])
    assert (select_body["offset"], select_body["limit"]) == (0, 500)
    fetch_config = fetch_body["query_configs"][0]
    # 回查不带主机级筛选
    assert not {"target__include", "process_names__include", "process_pids__include"} & set(fetch_config["filter_dict"])
    assert fetch_config["filter_dict"]["scheduled_at"] == ["1788411800000"]
    assert (fetch_body["offset"], fetch_body["limit"]) == (0, 10000)


def test_es_list_executions_skips_fetch_when_no_execution_matches_host(host_query_apis):
    host_query_apis["query"].side_effect = es_filtered_query([finished_event("succeed", 1788411801000, 1788411832000)])

    assert list_es_executions(with_filters(ips=["127.0.1.10"])) == []
    assert host_query_apis["query"].call_count == 1


def test_es_list_executions_fetches_only_current_page_when_selecting_by_host(host_query_apis):
    scheduled_ats = [1788411800000 - index * 1000 for index in range(3)]
    host_query_apis["query"].side_effect = es_filtered_query(
        [
            finished_event(
                "succeed", scheduled_at + 1000, scheduled_at + 31000, target="127.0.0.2", scheduled_at=scheduled_at
            )
            for scheduled_at in scheduled_ats
        ]
    )

    result = list_es_executions({**with_filters(ips=["127.0.0.2"]), "offset": 1, "limit": 1})

    assert [row["scheduled_at"] for row in result] == [scheduled_ats[1]]
    # 不筛状态时每个命中的执行就是一行，offset 之前的执行不用回查
    fetch_body = sent_query_bodies(host_query_apis["query"])[1]
    assert fetch_body["query_configs"][0]["filter_dict"]["scheduled_at"] == [str(scheduled_ats[1])]


def test_es_list_executions_keeps_selecting_until_status_filter_fills_page(host_query_apis):
    host_query_apis["query"].side_effect = es_filtered_query(
        [
            finished_event("succeed", 1788411801000, 1788411832000, target="127.0.0.2"),
            finished_event("failed", 1788410801000, 1788410802000, target="127.0.0.2", scheduled_at=1788410800000),
            finished_event("failed", 1788409801000, 1788409802000, target="127.0.0.2", scheduled_at=1788409800000),
        ]
    )

    result = list_es_executions({**with_filters(ips=["127.0.0.2"], status="failed"), "limit": 2})

    assert [row["scheduled_at"] for row in result] == [1788410800000, 1788409800000]
    # 回查后才知道执行状态，第一轮只命中一行，再接着找还缺的一个执行
    assert [
        body["query_configs"][0]["filter_dict"]["scheduled_at"]
        for body in sent_query_bodies(host_query_apis["query"])[1:]
    ] == [["1788411800000", "1788410800000"], ["1788409800000"]]
    # 多轮查询共用同一个事件表 ID
    host_query_apis["event_group"].objects.filter.assert_called_once()


def test_es_list_executions_rejects_when_fetched_events_exceed_limit(host_query_apis, mocker):
    mocker.patch(f"{ES_HANDLER_MODULE}.ACTIVE_PROFILING_ES_QUERY_MAX_SIZE", 2)
    host_query_apis["query"].side_effect = es_filtered_query(
        [
            finished_event("succeed", 1788411801000, 1788411832000),
            finished_event("failed", 1788411801000, 1788411802000, bk_host_id=457, target="127.0.0.2"),
        ]
    )

    with pytest.raises(ValueError):
        list_es_executions(with_filters(ips=["127.0.0.2"]))


TOPK_REQUEST = {
    "bk_biz_id": 2,
    "start_time": EVENT_LIST_REQUEST["start_time"],
    "end_time": EVENT_LIST_REQUEST["end_time"],
    "field": "task_name",
}


def test_es_topk_counts_field_values_with_event_topk_query(host_query_apis):
    # 按事件检索 TopK 的分组计数结果返回，已按事件数倒序
    host_query_apis["events"].extend(
        [
            {"task_name": "java-cpu-daily", "_result_": 4},
            {"task_name": "native-cpu", "_result_": 2},
            {"task_name": "", "_result_": 1},
        ]
    )

    result = query_es_topk({**TOPK_REQUEST, "limit": 3})

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


def with_processes(event, process_names, process_pids):
    event["dimensions"].update(process_names=process_names, process_pids=process_pids)
    return event


@pytest.mark.parametrize(
    ("field", "limit", "expected"),
    [
        # 点选后按进程名筛选，所以按进程名去重；同一次采集的同名进程只计一次
        ("process_names", 2, [("java", 2), ("nginx", 1)]),
        # PID 按位置配上进程名，显示与取值都是 进程名:PID；PID 被别的进程复用时是另一个候选
        ("process_pids", 4, [("java:1234", 2), ("nginx:812", 1), ("java:1235", 1), ("python:1234", 1)]),
    ],
)
def test_es_topk_lists_recent_processes(host_query_apis, field, limit, expected):
    # 按 ES 排序后的最近 Event：started 与下发失败补发的 finished 没有进程维度
    host_query_apis["events"].extend(
        [
            started_event(1788411801000, bk_host_id=458),
            with_processes(finished_event("succeed", 1788411801000, 1788411832000), "java,nginx,java", "1234,812,1235"),
            finished_event("failed", 1788311801000, 1788311801000, bk_host_id=457, scheduled_at=1788311800000),
            with_processes(
                finished_event("succeed", 1788211801000, 1788211832000, scheduled_at=1788211800000), "java", "1234"
            ),
            with_processes(
                finished_event("succeed", 1788111801000, 1788111832000, scheduled_at=1788111800000), "python", "1234"
            ),
        ]
    )

    result = query_es_topk({**TOPK_REQUEST, "field": field, "limit": limit})

    # 按最近出现排序
    assert [(item["value"], item["count"]) for item in result] == expected
    assert all(item["alias"] == item["value"] for item in result)
    # 不做分组计数，只按两个列表的排序读最近的有限条 Event
    (query_body,) = sent_query_bodies(host_query_apis["query"])
    assert (query_body["query_configs"][0].get("group_by"), query_body["limit"]) == ([], 1000)


def test_es_topk_reads_limited_recent_events_for_processes(host_query_apis, mocker):
    mocker.patch(f"{ES_HANDLER_MODULE}.ACTIVE_PROFILING_PROCESS_TOPK_RECENT_ROWS", 1)
    host_query_apis["events"].extend(
        [
            with_processes(finished_event("succeed", 1788411801000, 1788411832000), "java", "1234"),
            with_processes(
                finished_event("succeed", 1788211801000, 1788211832000, scheduled_at=1788211800000), "nginx", "812"
            ),
        ]
    )

    result = query_es_topk({**TOPK_REQUEST, "field": "process_names"})

    assert result == [{"value": "java", "alias": "java", "count": 1}]


def test_es_topk_rejects_keyword(host_query_apis):
    with pytest.raises(ValueError):
        query_es_topk({**TOPK_REQUEST, "field": "process_names", "keyword": "java"})

    host_query_apis["query"].assert_not_called()


IMMEDIATE_DETAIL_REQUEST = {"bk_biz_id": 2, "schedule_type": "immediate", "scheduled_at": 1788411800000}


def test_es_execution_detail_returns_all_hosts_of_execution(host_query_apis):
    host_query_apis["events"].extend(
        [
            finished_event("succeed", 1788411801000, 1788411832000, processes=[{"pid": 1234, "process_name": "java"}]),
            started_event(1788411802000, bk_host_id=457, target="127.0.0.2"),
        ]
    )

    result = query_es_detail(IMMEDIATE_DETAIL_REQUEST)

    # immediate 不返回 task_id；仍有主机运行时外层不结束
    assert result == {
        "task_name": "native-cpu",
        "schedule_type": "immediate",
        "scheduled_at": 1788411800000,
        "collection_method": "perf",
        "collection_type": "native_cpu",
        "creator": "admin",
        "started_at": 1788411801000,
        "finished_at": None,
        "duration_ms": 30000,
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
                "error_type": "",
                "message": "采集成功",
                "started_at": 1788411801000,
                "finished_at": 1788411832000,
                "duration_ms": 30000,
            },
            {
                "bk_host_id": 457,
                "ip": "127.0.0.2",
                "processes": [],
                "status": "running",
                "error_type": "",
                "message": "",
                "started_at": 1788411802000,
                "finished_at": None,
                "duration_ms": 30000,
            },
        ],
    }
    filter_dict = sent_query_bodies(host_query_apis["query"])[0]["query_configs"][0]["filter_dict"]
    assert (filter_dict["schedule_type"], "task_id" in filter_dict) == ("immediate", False)


def test_es_execution_detail_locates_planned_execution_by_task(host_query_apis):
    host_query_apis["events"].extend(
        [
            finished_event("succeed", 1788310801000, 1788310832000, task_id=123, scheduled_at=1788310800000),
            finished_event(
                "failed",
                1788310801000,
                1788310840000,
                message="Profiling 发送失败",
                error_type="report_failed",
                bk_host_id=457,
                target="127.0.0.2",
                task_id=123,
                scheduled_at=1788310800000,
            ),
        ]
    )

    result = query_es_detail(EXECUTION_DETAIL_REQUEST)

    assert (result["task_id"], result["task_name"], result["schedule_type"]) == (123, "java-cpu-daily", "cron")
    assert (result["execution_status"], result["status_summary"]) == ("partial_succeed", {"succeed": 1, "failed": 1})
    # 外层从最早开始的主机算到最晚结束的主机；采集时长取配置
    assert (result["started_at"], result["finished_at"], result["duration_ms"]) == (
        1788310801000,
        1788310840000,
        30000,
    )
    # error_type 供前端给出展示文案，message 保留原始错误
    assert (result["hosts"][1]["error_type"], result["hosts"][1]["message"]) == ("report_failed", "Profiling 发送失败")

    # 计划执行按 task_id + scheduled_at 定位，执行方式取自 Event 维度
    (query_body,) = sent_query_bodies(host_query_apis["query"])
    assert query_body["query_configs"][0]["filter_dict"] == {
        "bk_tenant_id": "system",
        "bk_biz_id": 2,
        "event_name": ["active_profiling_started", "active_profiling_finished"],
        "scheduled_at": 1788310800000,
        "task_id": 123,
    }
    assert result["schedule_type"] == "cron"
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
def test_es_execution_detail_aggregates_host_statuses(statuses, expected):
    assert ActiveProfilingEventQueryHandler._aggregate_status(statuses) == expected


def test_es_execution_detail_marks_expired_execution_outdate(host_query_apis):
    scheduled_at = EXPIRE_BEFORE - 1000
    host_query_apis["events"].extend(
        [
            finished_event("succeed", scheduled_at + 1000, scheduled_at + 31000, scheduled_at=scheduled_at),
            finished_event(
                "failed", scheduled_at + 1000, scheduled_at + 2000, bk_host_id=457, scheduled_at=scheduled_at
            ),
        ]
    )

    result = query_es_detail({**IMMEDIATE_DETAIL_REQUEST, "scheduled_at": scheduled_at})

    assert (result["execution_status"], result["status_summary"]) == ("outdate", {"outdate": 1, "failed": 1})


def test_es_execution_detail_displays_parsing_only_on_hosts(host_query_apis):
    host_query_apis["events"].extend(
        [
            finished_event("succeed", HOST_QUERY_NOW - 2000, HOST_QUERY_NOW - 1000),
            finished_event("succeed", 1788411801000, 1788411832000, bk_host_id=457, target="127.0.0.2"),
        ]
    )

    result = query_es_detail(IMMEDIATE_DETAIL_REQUEST)

    assert [(host["bk_host_id"], host["status"]) for host in result["hosts"]] == [(456, "parsing"), (457, "succeed")]
    assert (result["execution_status"], result["status_summary"]) == ("succeed", {"succeed": 2})


def test_es_execution_detail_keeps_error_type_empty_for_legacy_events(host_query_apis):
    event = finished_event("failed", 1788411801000, 1788411802000, message="perf unsuccessful")
    content = json.loads(event["event"]["content"])
    # 旧版采集端不上报 error_type
    del content["error_type"]
    event["event"]["content"] = json.dumps(content)
    host_query_apis["events"].append(event)

    (host,) = query_es_detail(IMMEDIATE_DETAIL_REQUEST)["hosts"]

    assert (host["error_type"], host["message"]) == ("", "perf unsuccessful")


def test_es_execution_detail_explains_unknown_host(host_query_apis):
    host_query_apis["events"].extend(
        [
            finished_event("failed", 1788411801000, 1788411802000, message="Profiling 发送失败"),
            started_event(HOST_QUERY_NOW - UNKNOWN_WINDOW_MS, bk_host_id=457, target="127.0.0.2"),
        ]
    )

    result = query_es_detail(IMMEDIATE_DETAIL_REQUEST)

    assert [(host["status"], host["message"]) for host in result["hosts"]] == [
        ("failed", "Profiling 发送失败"),
        ("unknown", "请检查agent状态及版本信息，若持续异常请联系管理员"),
    ]


def test_es_execution_detail_returns_selector_as_submitted(host_query_apis):
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

    config = query_es_detail(IMMEDIATE_DETAIL_REQUEST)["config"]

    assert config["target_config"]["nodes"] == [{"bk_host_id": 456}, {"bk_host_id": 457}]
    assert config["process_selector"] == STATIC_COMMAND_SELECTOR


def test_es_execution_detail_keeps_golang_config_without_selector(host_query_apis):
    golang_config = host_config(
        collector_config={"ip_address": "127.0.0.1", "port": 6060, "duration_sec": 30}, process_selector=None
    )
    host_query_apis["events"].append(finished_event("succeed", 1788411801000, 1788411832000, config=golang_config))

    assert query_es_detail(IMMEDIATE_DETAIL_REQUEST)["config"] == golang_config


def test_es_execution_detail_requires_existing_execution(host_query_apis):
    with pytest.raises(ValueError):
        query_es_detail(IMMEDIATE_DETAIL_REQUEST)


def test_es_execution_detail_rejects_when_events_exceed_limit(host_query_apis, mocker):
    mocker.patch(f"{ES_HANDLER_MODULE}.ACTIVE_PROFILING_ES_QUERY_MAX_SIZE", 2)
    host_query_apis["events"].extend(
        finished_event("succeed", 1788411801000, 1788411832000, bk_host_id=bk_host_id) for bk_host_id in (456, 457)
    )

    with pytest.raises(ValueError):
        query_es_detail(IMMEDIATE_DETAIL_REQUEST)
