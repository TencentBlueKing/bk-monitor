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

from apm_web.constants import ApmCacheKey, ServiceRelationLogTypeChoices
from apm_web.handlers import log_handler
from apm_web.handlers.log_handler import ServiceLogHandler
from apm_web.models import Application, LogServiceRelation
from bkmonitor.utils.common_utils import compress_and_serialize


@pytest.fixture
def related_logs(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    state = SimpleNamespace(
        app=Application(bk_biz_id=2, app_name="demo"),
        relations=[],
        cached_indexes={},
        metadata={},
        queried_businesses=[],
        relation_queries=[],
        cache_reads=[],
    )

    def get_relation_qs(*args: Any, **kwargs: Any) -> list[LogServiceRelation]:
        state.relation_queries.append((args, kwargs))
        return state.relations

    def read_cache(cache_key: str) -> bytes:
        state.cache_reads.append(cache_key)
        return compress_and_serialize(state.cached_indexes)

    def get_metadata(*, bk_biz_id: int) -> list[dict[str, Any]]:
        state.queried_businesses.append(bk_biz_id)
        return state.metadata[bk_biz_id]

    def reject_storage_query(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("关联日志状态不应探测日志数据")

    monkeypatch.setattr(LogServiceRelation, "get_relation_qs", get_relation_qs)
    monkeypatch.setattr(log_handler, "caches", {"redis": SimpleNamespace(get=read_cache)})
    monkeypatch.setattr(log_handler, "get_biz_index_sets_with_cache", get_metadata)
    monkeypatch.setattr(ServiceLogHandler, "get_log_datasource", reject_storage_query)
    monkeypatch.setattr(log_handler.api.log_search, "es_query_dsl", reject_storage_query)
    return state


def test_available_related_services_checks_all_indexes(related_logs: SimpleNamespace) -> None:
    related_logs.relations = [
        LogServiceRelation(
            service_name="service-a", related_bk_biz_id=3, value_list=[100, 101], value="102", is_global=False
        ),
        LogServiceRelation(service_name="service-b", related_bk_biz_id=3, value_list=[102], is_global=False),
    ]
    related_logs.metadata = {
        3: [
            {"index_set_id": 100, "tags": [{"name": "无数据", "tag_id": 91, "tag_type": "inner"}]},
            {"index_set_id": "101", "tags": [{"name": "trace", "tag_id": 4}]},
            {"index_set_id": 102, "tags": [{"name": "trace"}]},
        ]
    }

    assert ServiceLogHandler.list_available_related_services(related_logs.app, ["service-a", "service-b"]) == {
        "service-a",
        "service-b",
    }
    assert related_logs.queried_businesses == [3]
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
    related_logs.metadata = {3: [{"index_set_id": 100, "tags": [{"name": "trace"}]}]}

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
    related_logs.metadata = {
        3: [{"index_set_id": 100, "tags": [{"name": "trace"}]}],
        4: [{"index_set_id": 100, "tags": [{"name": "No Data", "tag_id": 91}]}],
    }

    assert ServiceLogHandler.list_available_related_services(related_logs.app, ["service-a", "service-b"]) == {
        "service-a"
    }
    assert sorted(related_logs.queried_businesses) == [3, 4]
    assert related_logs.cache_reads == [
        ApmCacheKey.APP_SERVICE_K8S_RELATED_LOG_INDEXES_KEY.format(bk_biz_id=2, app_name="demo")
    ]


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
def test_related_index_available_tags(
    related_logs: SimpleNamespace, tags: list[dict[str, Any]] | None, is_available: bool
) -> None:
    related_logs.relations = [
        LogServiceRelation(service_name="service-a", related_bk_biz_id=3, value_list=[100], is_global=False)
    ]
    related_logs.metadata = {3: [{"index_set_id": 100, "tags": tags}]}

    assert ServiceLogHandler.list_available_related_services(related_logs.app, ["service-a"]) == (
        {"service-a"} if is_available else set()
    )


@pytest.mark.parametrize("cached_data", [None, b"invalid-cache-data", compress_and_serialize([])])
def test_available_related_services_cache_failure_preserves_manual_relations(
    related_logs: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, cached_data: bytes | None
) -> None:
    related_logs.relations = [
        LogServiceRelation(service_name="service-a", related_bk_biz_id=3, value_list=[100], is_global=False)
    ]
    related_logs.metadata = {3: [{"index_set_id": 100, "tags": [{"name": "trace"}]}]}
    monkeypatch.setattr(log_handler, "caches", {"redis": SimpleNamespace(get=lambda _key: cached_data)})

    assert ServiceLogHandler.list_available_related_services(related_logs.app, ["service-a"]) == {"service-a"}


def test_available_related_services_empty_service_list_skips_reads(related_logs: SimpleNamespace) -> None:
    assert ServiceLogHandler.list_available_related_services(related_logs.app, []) == set()
    assert related_logs.queried_businesses == []
    assert related_logs.relation_queries == []
    assert related_logs.cache_reads == []
