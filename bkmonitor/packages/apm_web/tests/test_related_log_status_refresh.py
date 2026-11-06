"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import Counter
from types import SimpleNamespace
from typing import Any

import pytest
from django.core.cache.backends.locmem import LocMemCache
from django.test import override_settings
from pytest_mock import MockerFixture

from api.log_search.default import SearchIndexSetResource
from apm_web import tasks
from apm_web.constants import ApmCacheKey
from apm_web.handlers import log_handler
from apm_web.handlers.log_handler import ServiceLogHandler
from apm_web.models import Application, LogServiceRelation
from bkmonitor.utils import cache as cache_utils
from bkmonitor.utils.common_utils import compress_and_serialize
from bkmonitor.utils.local import local
from bkmonitor.utils.tenant import get_local_tenant_id, set_local_tenant_id


NOW = 1_800_000_000


@pytest.fixture
def refresh_context(monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> SimpleNamespace:
    state = SimpleNamespace(
        applications=[Application(bk_biz_id=2, app_name="demo", bk_tenant_id="tenant-a", is_enabled=True)],
        relations={},
        metadata={},
        queried_targets=[],
        queried_applications=[],
        cache_data={},
        writes=[],
    )

    def filter_applications(**kwargs: Any) -> SimpleNamespace:
        def exclude_applications(**exclude_kwargs: Any) -> list[Application]:
            prefix = exclude_kwargs["app_name__startswith"]
            return [
                app
                for app in state.applications
                if app.is_enabled == kwargs["is_enabled"] and not app.app_name.startswith(prefix)
            ]

        return SimpleNamespace(exclude=exclude_applications)

    def get_relations(_bk_biz_id: int, app_name: str, _names: Any, **_kwargs: Any) -> list[LogServiceRelation]:
        state.queried_applications.append((get_local_tenant_id(), app_name))
        result = state.relations.get(app_name, [])
        if isinstance(result, Exception):
            raise result
        return result

    def get_metadata(*, bk_biz_id: int) -> list[dict[str, Any]]:
        target = (get_local_tenant_id(), bk_biz_id)
        state.queried_targets.append(target)
        result = state.metadata[target]
        if isinstance(result, Exception):
            raise result
        return result

    def write_cache(key: str, value: dict[str, Any], timeout: int) -> None:
        state.cache_data[key] = value
        state.writes.append((key, value, timeout))

    state.cache = SimpleNamespace(get=state.cache_data.get, set=write_cache)
    state.application_filter = mocker.patch.object(Application.objects, "filter", side_effect=filter_applications)
    monkeypatch.setattr(ServiceLogHandler, "get_log_relations", get_relations)
    monkeypatch.setattr(tasks, "caches", {"redis": state.cache})
    monkeypatch.setattr(log_handler, "caches", {"redis": state.cache})
    monkeypatch.setattr(tasks, "get_biz_index_sets_with_cache", get_metadata)
    monkeypatch.setattr(tasks.time, "time", lambda: NOW)
    monkeypatch.setattr(local, "bk_tenant_id", "previous-tenant", raising=False)
    return state


def test_related_log_status_refresh_collects_all_sources_and_deduplicates_targets(
    refresh_context: SimpleNamespace,
) -> None:
    state = refresh_context
    state.applications.extend(
        [
            Application(bk_biz_id=2, app_name="second", bk_tenant_id="tenant-a", is_enabled=True),
            Application(bk_biz_id=20, app_name="cross-tenant", bk_tenant_id="tenant-b", is_enabled=True),
            Application(bk_biz_id=2, app_name="no-relations", bk_tenant_id="tenant-a", is_enabled=True),
            Application(bk_biz_id=2, app_name="disabled", bk_tenant_id="tenant-a", is_enabled=False),
            Application(bk_biz_id=2, app_name="bkapp_ai0us0_agent", bk_tenant_id="tenant-a", is_enabled=True),
        ]
    )
    state.relations = {
        "demo": [
            LogServiceRelation(service_name="service-a", related_bk_biz_id=3, value_list=[100]),
            LogServiceRelation(service_name="", related_bk_biz_id=5, value_list=[500], is_global=True),
        ],
        "second": [LogServiceRelation(service_name="service-b", related_bk_biz_id=3, value_list=[101])],
        "cross-tenant": [LogServiceRelation(service_name="service-c", related_bk_biz_id=3, value_list=[100])],
        "disabled": [LogServiceRelation(service_name="service-d", related_bk_biz_id=99, value_list=[999])],
        "bkapp_ai0us0_agent": [LogServiceRelation(service_name="agent", related_bk_biz_id=98, value_list=[998])],
    }
    k8s_key = ApmCacheKey.APP_SERVICE_K8S_RELATED_LOG_INDEXES_KEY.format(bk_biz_id=2, app_name="demo")
    state.cache_data[k8s_key] = compress_and_serialize(
        {"service-a": [{"index_set_id": 100, "bk_biz_id": 3}, {"index_set_id": 400, "bk_biz_id": 4}]}
    )
    state.metadata = {
        ("tenant-a", 3): [
            {"index_set_id": 100, "tags": [{"name": "trace"}]},
            {"index_set_id": 999, "tags": [{"name": "无数据"}]},
        ],
        ("tenant-a", 4): [{"index_set_id": 400, "tags": [{"name": "trace"}]}],
        ("tenant-a", 5): [{"index_set_id": 500, "tags": []}],
        ("tenant-b", 3): [{"index_set_id": 100, "tags": [{"name": "No Data"}]}],
    }

    tasks.refresh_related_log_index_status()

    state.application_filter.assert_called_once_with(is_enabled=True)
    assert Counter(state.queried_targets) == Counter({target: 1 for target in state.metadata})
    assert state.queried_applications == [
        ("tenant-a", "demo"),
        ("tenant-a", "second"),
        ("tenant-b", "cross-tenant"),
        ("tenant-a", "no-relations"),
    ]
    assert len(state.writes) == 4
    tenant_a_key = ApmCacheKey.APM_RELATED_LOG_INDEX_STATUS_KEY.format(bk_tenant_id="tenant-a", bk_biz_id=3)
    tenant_b_key = ApmCacheKey.APM_RELATED_LOG_INDEX_STATUS_KEY.format(bk_tenant_id="tenant-b", bk_biz_id=3)
    assert state.cache_data[tenant_a_key] == {
        "checked_at": NOW,
        "indexes": [{"index_set_id": 100, "available": True}, {"index_set_id": 999, "available": False}],
    }
    assert state.cache_data[tenant_b_key] == {
        "checked_at": NOW,
        "indexes": [{"index_set_id": 100, "available": False}],
    }
    assert all(timeout == 900 for _, _, timeout in state.writes)
    assert get_local_tenant_id() == "previous-tenant"


@override_settings(APM_RELATED_LOG_INDEX_STATUS_CACHE_TTL=120)
def test_related_log_status_refresh_preserves_failed_snapshot_and_replaces_successful_empty(
    refresh_context: SimpleNamespace,
) -> None:
    state = refresh_context
    state.relations["demo"] = [
        LogServiceRelation(related_bk_biz_id=bk_biz_id, value_list=[100]) for bk_biz_id in (3, 4, 5)
    ]
    old_snapshot = {"checked_at": NOW - 100, "indexes": [{"index_set_id": 100, "available": True}]}
    for bk_biz_id in (3, 4):
        key = ApmCacheKey.APM_RELATED_LOG_INDEX_STATUS_KEY.format(bk_tenant_id="tenant-a", bk_biz_id=bk_biz_id)
        state.cache_data[key] = old_snapshot
    state.metadata = {
        ("tenant-a", 3): RuntimeError("log platform unavailable"),
        ("tenant-a", 4): [],
        ("tenant-a", 5): [{"index_set_id": 500, "tags": [{"name": "trace"}]}],
    }

    tasks.refresh_related_log_index_status()

    failed_key = ApmCacheKey.APM_RELATED_LOG_INDEX_STATUS_KEY.format(bk_tenant_id="tenant-a", bk_biz_id=3)
    empty_key = ApmCacheKey.APM_RELATED_LOG_INDEX_STATUS_KEY.format(bk_tenant_id="tenant-a", bk_biz_id=4)
    assert state.cache_data[failed_key] == old_snapshot
    assert failed_key not in {key for key, _, _ in state.writes}
    assert state.cache_data[empty_key] == {"checked_at": NOW, "indexes": []}
    assert len(state.writes) == 2
    assert all(timeout == 120 for _, _, timeout in state.writes)
    assert set(state.queried_targets) == set(state.metadata)
    assert get_local_tenant_id() == "previous-tenant"


def test_related_log_status_refresh_all_failures_do_not_write_or_renew(refresh_context: SimpleNamespace) -> None:
    state = refresh_context
    state.relations["demo"] = [LogServiceRelation(related_bk_biz_id=3, value_list=[100])]
    key = ApmCacheKey.APM_RELATED_LOG_INDEX_STATUS_KEY.format(bk_tenant_id="tenant-a", bk_biz_id=3)
    old_snapshot = {"checked_at": NOW - 100, "indexes": [{"index_set_id": 100, "available": True}]}
    state.cache_data[key] = old_snapshot
    state.metadata[("tenant-a", 3)] = RuntimeError("log platform unavailable")

    tasks.refresh_related_log_index_status()

    assert state.cache_data[key] == old_snapshot
    assert state.writes == []
    assert get_local_tenant_id() == "previous-tenant"


def test_related_log_status_refresh_continues_after_application_relation_failure(
    refresh_context: SimpleNamespace,
) -> None:
    state = refresh_context
    state.relations["demo"] = RuntimeError("relation unavailable")
    state.applications.append(Application(bk_biz_id=2, app_name="second", bk_tenant_id="tenant-a", is_enabled=True))
    state.relations["second"] = [LogServiceRelation(related_bk_biz_id=3, value_list=[100])]
    state.metadata[("tenant-a", 3)] = [{"index_set_id": 100, "tags": [{"name": "trace"}]}]

    tasks.refresh_related_log_index_status()

    assert state.queried_targets == [("tenant-a", 3)]
    assert len(state.writes) == 1
    assert get_local_tenant_id() == "previous-tenant"


@pytest.mark.parametrize(
    ("tags", "is_available"),
    [
        ([], False),
        (None, False),
        ([{"name": "无数据", "tag_id": 91}], False),
        ([{"name": "No Data", "tag_id": 91}], False),
        ([{"name": "trace"}, {"name": "无数据", "tag_type": "inner"}], False),
        ([{"name": "无数据", "tag_type": "user"}], True),
        ([{"name": "trace", "tag_id": 4}], True),
    ],
)
def test_related_log_status_refresh_preserves_tag_rules(
    refresh_context: SimpleNamespace, tags: list[dict[str, Any]] | None, is_available: bool
) -> None:
    state = refresh_context
    state.relations["demo"] = [LogServiceRelation(related_bk_biz_id=3, value_list=[100])]
    state.metadata[("tenant-a", 3)] = [{"index_set_id": 100, "tags": tags}]

    tasks.refresh_related_log_index_status()

    key = ApmCacheKey.APM_RELATED_LOG_INDEX_STATUS_KEY.format(bk_tenant_id="tenant-a", bk_biz_id=3)
    assert state.cache_data[key] == {
        "checked_at": NOW,
        "indexes": [{"index_set_id": 100, "available": is_available}],
    }


@override_settings(ENVIRONMENT="production", ENABLE_MULTI_TENANT_MODE=True, ENABLE_RESOURCE_DATA_COLLECT=False)
def test_related_log_metadata_cache_is_tenant_isolated(monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    cache_backend = LocMemCache("related-log-tenant-metadata", {})
    cache_backend.clear()
    monkeypatch.setattr(cache_utils, "cache", cache_backend)
    monkeypatch.setattr(cache_utils, "mem_cache", cache_backend)
    monkeypatch.setattr(local, "bk_tenant_id", "tenant-a", raising=False)
    lookup = mocker.patch.object(
        SearchIndexSetResource,
        "perform_request",
        autospec=True,
        side_effect=lambda resource, _params: [{"index_set_id": 100, "tenant": resource.bk_tenant_id}],
    )
    monkeypatch.setattr(log_handler.api.log_search, "search_index_set", SearchIndexSetResource())

    first = log_handler.get_biz_index_sets_with_cache(bk_biz_id=3)
    set_local_tenant_id("tenant-b")
    second = log_handler.get_biz_index_sets_with_cache(bk_biz_id=3)
    set_local_tenant_id("tenant-a")
    repeated = log_handler.get_biz_index_sets_with_cache(bk_biz_id=3)

    assert first == repeated == [{"index_set_id": 100, "tenant": "tenant-a"}]
    assert second == [{"index_set_id": 100, "tenant": "tenant-b"}]
    assert log_handler.get_biz_index_sets_with_cache.cacheless(bk_biz_id=3) == first
    set_local_tenant_id("tenant-b")
    assert log_handler.get_biz_index_sets_with_cache.cacheless(bk_biz_id=3) == second
    assert lookup.call_count == 2
