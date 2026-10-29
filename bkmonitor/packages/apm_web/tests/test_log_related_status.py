"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace
from typing import Any

import pytest
from django.test import override_settings

from apm_web.constants import ApmCacheKey, DataStatus, ServiceRelationLogTypeChoices
from apm_web.handlers import log_handler
from apm_web.handlers.log_handler import ServiceLogHandler
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.metric.resources import ServiceListAsyncResource
from apm_web.models import Application, LogServiceRelation
from bkmonitor.utils.common_utils import compress_and_serialize


NOW = 1_800_000_000


@pytest.fixture
def related_logs(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    state = SimpleNamespace(
        app=Application(bk_biz_id=2, app_name="demo", bk_tenant_id="tenant-a", is_enabled_log=True),
        relations=[],
        cached_indexes={},
        snapshots={},
        relation_queries=[],
        cache_reads=[],
    )

    def get_relation_qs(*args: Any, **kwargs: Any) -> list[LogServiceRelation]:
        state.relation_queries.append((args, kwargs))
        return state.relations

    def read_cache(cache_key: str) -> bytes | dict[str, Any] | None:
        state.cache_reads.append(cache_key)
        k8s_key = ApmCacheKey.APP_SERVICE_K8S_RELATED_LOG_INDEXES_KEY.format(bk_biz_id=2, app_name="demo")
        if cache_key == k8s_key:
            return compress_and_serialize(state.cached_indexes)
        return state.snapshots.get(cache_key)

    def reject_remote_query(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("关联日志状态请求不应访问日志平台")

    monkeypatch.setattr(LogServiceRelation, "get_relation_qs", get_relation_qs)
    monkeypatch.setattr(log_handler, "caches", {"redis": SimpleNamespace(get=read_cache)})
    monkeypatch.setattr(log_handler.time, "time", lambda: NOW)
    monkeypatch.setattr(log_handler, "get_biz_index_sets_with_cache", reject_remote_query)
    monkeypatch.setattr(ServiceLogHandler, "get_log_datasource", reject_remote_query)
    monkeypatch.setattr(log_handler.api.log_search, "search_index_set", reject_remote_query)
    monkeypatch.setattr(log_handler.api.log_search, "es_query_dsl", reject_remote_query)
    return state


def test_available_related_services_checks_all_indexes(related_logs: SimpleNamespace) -> None:
    related_logs.relations = [
        LogServiceRelation(
            service_name="service-a", related_bk_biz_id=3, value_list=[100, 101], value="102", is_global=False
        ),
        LogServiceRelation(service_name="service-b", related_bk_biz_id=3, value_list=[102], is_global=False),
    ]
    key = ApmCacheKey.APM_RELATED_LOG_INDEX_STATUS_KEY.format(bk_tenant_id="tenant-a", bk_biz_id=3)
    related_logs.snapshots[key] = {
        "checked_at": NOW,
        "indexes": [
            {"index_set_id": 100, "available": False},
            {"index_set_id": "101", "available": True},
            {"index_set_id": 102, "available": True},
        ],
    }

    assert ServiceLogHandler.list_available_related_services(related_logs.app, ["service-a", "service-b"]) == {
        "service-a",
        "service-b",
    }
    assert related_logs.cache_reads.count(key) == 1
    assert related_logs.relation_queries == [
        (
            (2, "demo", ["service-a", "service-b"]),
            {"include_global": True, "log_type": ServiceRelationLogTypeChoices.BK_LOG},
        )
    ]


def test_available_related_services_global_applies_to_all_services(related_logs: SimpleNamespace) -> None:
    related_logs.relations = [
        LogServiceRelation(service_name="", related_bk_biz_id=3, value_list=[100], is_global=True)
    ]
    key = ApmCacheKey.APM_RELATED_LOG_INDEX_STATUS_KEY.format(bk_tenant_id="tenant-a", bk_biz_id=3)
    related_logs.snapshots[key] = {"checked_at": NOW, "indexes": [{"index_set_id": 100, "available": True}]}

    assert ServiceLogHandler.list_available_related_services(related_logs.app, ["service-a", "service-b"]) == {
        "service-a",
        "service-b",
    }


def test_available_related_services_k8s_respects_index_business(related_logs: SimpleNamespace) -> None:
    related_logs.cached_indexes = {
        "service-a": [{"index_set_id": 100, "bk_biz_id": 3, "updated_at": 123}],
        "service-b": [{"index_set_id": 100, "bk_biz_id": 4, "updated_at": 456}],
        "other-service": [{"index_set_id": 999, "bk_biz_id": 5, "updated_at": 789}],
    }
    for bk_biz_id, available in ((3, True), (4, False)):
        key = ApmCacheKey.APM_RELATED_LOG_INDEX_STATUS_KEY.format(bk_tenant_id="tenant-a", bk_biz_id=bk_biz_id)
        related_logs.snapshots[key] = {
            "checked_at": NOW,
            "indexes": [{"index_set_id": 100, "available": available}],
        }

    assert ServiceLogHandler.list_available_related_services(related_logs.app, ["service-a", "service-b"]) == {
        "service-a"
    }
    other_key = ApmCacheKey.APM_RELATED_LOG_INDEX_STATUS_KEY.format(bk_tenant_id="tenant-a", bk_biz_id=5)
    assert other_key not in related_logs.cache_reads


@override_settings(APM_RELATED_LOG_INDEX_STATUS_CACHE_TTL=60)
@pytest.mark.parametrize("snapshot_age", [None, 0, 59, 60, 61])
def test_related_log_status_snapshot_only(related_logs: SimpleNamespace, snapshot_age: int | None) -> None:
    related_logs.relations = [
        LogServiceRelation(service_name="service-a", related_bk_biz_id=3, value_list=[100], is_global=False)
    ]
    if snapshot_age is not None:
        key = ApmCacheKey.APM_RELATED_LOG_INDEX_STATUS_KEY.format(bk_tenant_id="tenant-a", bk_biz_id=3)
        related_logs.snapshots[key] = {
            "checked_at": NOW - snapshot_age,
            "indexes": [{"index_set_id": 100, "available": True}],
        }

    expected = {"service-a"} if snapshot_age is not None and snapshot_age < 60 else set()
    assert ServiceLogHandler.list_available_related_services(related_logs.app, ["service-a"]) == expected


def test_related_log_snapshot_is_tenant_isolated(related_logs: SimpleNamespace) -> None:
    related_logs.relations = [
        LogServiceRelation(service_name="service-a", related_bk_biz_id=3, value_list=[100], is_global=False)
    ]
    key = ApmCacheKey.APM_RELATED_LOG_INDEX_STATUS_KEY.format(bk_tenant_id="tenant-a", bk_biz_id=3)
    related_logs.snapshots[key] = {"checked_at": NOW, "indexes": [{"index_set_id": 100, "available": True}]}

    assert ServiceLogHandler.list_available_related_services(related_logs.app, ["service-a"]) == {"service-a"}
    related_logs.app.bk_tenant_id = "tenant-b"
    assert ServiceLogHandler.list_available_related_services(related_logs.app, ["service-a"]) == set()


def test_related_log_relation_removal_takes_effect_with_fresh_snapshot(related_logs: SimpleNamespace) -> None:
    related_logs.relations = [
        LogServiceRelation(service_name="service-a", related_bk_biz_id=3, value_list=[100], is_global=False)
    ]
    key = ApmCacheKey.APM_RELATED_LOG_INDEX_STATUS_KEY.format(bk_tenant_id="tenant-a", bk_biz_id=3)
    related_logs.snapshots[key] = {"checked_at": NOW, "indexes": [{"index_set_id": 100, "available": True}]}
    assert ServiceLogHandler.list_available_related_services(related_logs.app, ["service-a"]) == {"service-a"}

    related_logs.relations = []
    assert ServiceLogHandler.list_available_related_services(related_logs.app, ["service-a"]) == set()
    assert key in related_logs.snapshots


@pytest.mark.parametrize("cached_data", [None, b"invalid-cache-data", compress_and_serialize([])])
def test_available_related_services_k8s_failure_preserves_manual_relations(
    related_logs: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, cached_data: bytes | None
) -> None:
    related_logs.relations = [
        LogServiceRelation(service_name="service-a", related_bk_biz_id=3, value_list=[100], is_global=False)
    ]
    key = ApmCacheKey.APM_RELATED_LOG_INDEX_STATUS_KEY.format(bk_tenant_id="tenant-a", bk_biz_id=3)
    snapshot = {"checked_at": NOW, "indexes": [{"index_set_id": 100, "available": True}]}
    monkeypatch.setattr(
        log_handler,
        "caches",
        {"redis": SimpleNamespace(get=lambda cache_key: snapshot if cache_key == key else cached_data)},
    )

    assert ServiceLogHandler.list_available_related_services(related_logs.app, ["service-a"]) == {"service-a"}


def test_related_log_snapshot_failure_keeps_heartbeat_status(
    related_logs: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    related_logs.relations = [
        LogServiceRelation(service_name="related", related_bk_biz_id=3, value_list=[100], is_global=False)
    ]
    nodes = [
        {"topo_key": "reported", "heartbeat": {"log": {"last_data_at": NOW}}},
        {"topo_key": "related", "heartbeat": {}},
    ]
    status = ServiceHandler.build_service_data_status(related_logs.app, nodes, data_type="log")
    assert status == {"reported": {"log": DataStatus.NORMAL}, "related": {"log": DataStatus.NO_DATA}}

    def read_cache(_key: str) -> None:
        raise RuntimeError("cache unavailable")

    monkeypatch.setattr(log_handler, "caches", {"redis": SimpleNamespace(get=read_cache)})
    assert ServiceHandler.build_service_data_status(related_logs.app, nodes, data_type="log") == status


@pytest.mark.parametrize("snapshot_is_fresh", [True, False])
def test_related_log_column_and_full_filter_counts_agree(
    related_logs: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, snapshot_is_fresh: bool
) -> None:
    related_logs.relations = [
        LogServiceRelation(service_name="related", related_bk_biz_id=3, value_list=[100], is_global=False)
    ]
    key = ApmCacheKey.APM_RELATED_LOG_INDEX_STATUS_KEY.format(bk_tenant_id="tenant-a", bk_biz_id=3)
    related_logs.snapshots[key] = {
        "checked_at": NOW if snapshot_is_fresh else NOW - 900,
        "indexes": [{"index_set_id": 100, "available": True}],
    }
    nodes = [
        {"topo_key": "reported", "heartbeat": {"log": {"last_data_at": NOW}}},
        {"topo_key": "related", "heartbeat": {}},
        {"topo_key": "empty", "heartbeat": {}},
    ]
    monkeypatch.setattr(ServiceHandler, "list_services", lambda _app: nodes)

    column, _ = ServiceListAsyncResource._get_data_status_mapping(related_logs.app, ["related"], data_status_type="log")
    counted_column, fields = ServiceListAsyncResource._get_data_status_mapping(
        related_logs.app, ["related"], data_status_type="log", filter_keys=["have_data", "apply_module"]
    )
    filters = {field["id"]: {item["id"]: item["count"] for item in field["data"]} for field in fields}
    assert column == counted_column == {"related": DataStatus.NORMAL if snapshot_is_fresh else DataStatus.NO_DATA}
    assert filters["have_data"] == {"true": 2 if snapshot_is_fresh else 1, "false": 1 if snapshot_is_fresh else 2}
    assert filters["apply_module"]["log"] == 3


def test_available_related_services_empty_service_list_skips_reads(related_logs: SimpleNamespace) -> None:
    assert ServiceLogHandler.list_available_related_services(related_logs.app, []) == set()
    assert related_logs.relation_queries == []
    assert related_logs.cache_reads == []
