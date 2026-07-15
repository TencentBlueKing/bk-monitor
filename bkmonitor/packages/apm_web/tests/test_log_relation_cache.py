"""APM 服务关联 K8S 日志索引缓存测试。"""

from types import SimpleNamespace
from typing import Any

import pytest

from apm_web import tasks
from apm_web.constants import ApmCacheKey
from apm_web.handlers import log_handler, task_handler
from apm_web.handlers.log_handler import ServiceLogHandler
from apm_web.handlers.task_handler import ServiceLogTaskHandler
from apm_web.log import resources as log_resources
from apm_web.log.resources import process_metric_relations
from bkmonitor.utils.common_utils import compress_and_serialize, deserialize_and_decompress


BK_BIZ_ID = 2
APP_NAME = "demo"
WORKLOAD = {
    "bcs_cluster_id": "BCS-K8S-00000",
    "namespace": "default",
    "kind": "Deployment",
    "name": "demo-api",
}


class FakeEntitySet:
    """提供应用服务与 workload 的最小 EntitySet 测试替身。"""

    def __init__(self, workloads_by_service: dict[str, list[dict[str, str]]]) -> None:
        self.service_names: list[str] = list(workloads_by_service)
        self._workloads_by_service: dict[str, list[dict[str, str]]] = workloads_by_service

    def get_workloads(self, service_name: str) -> list[dict[str, str]]:
        return self._workloads_by_service[service_name]


class FakeRedisCache:
    """记录 Redis 缓存读写和过期时间。"""

    def __init__(self, data: dict[str, bytes] | None = None) -> None:
        self.data: dict[str, bytes] = data or {}
        self.expirations: dict[str, int] = {}

    def get(self, key: str) -> bytes | None:
        return self.data.get(key)

    def set(self, key: str, value: bytes, timeout: int | None = None) -> None:
        self.data[key] = value
        if timeout is not None:
            self.expirations[key] = timeout


class FailingRedisCache(FakeRedisCache):
    """模拟 Redis 读取异常。"""

    def get(self, key: str) -> bytes | None:
        raise ConnectionError(key)


def test_get_k8s_related_log_indexes_empty_workloads(monkeypatch: pytest.MonkeyPatch) -> None:
    entity_set = FakeEntitySet({"service-a": []})
    monkeypatch.setattr(task_handler, "EntitySet", lambda *_args, **_kwargs: entity_set)
    monkeypatch.setattr(
        task_handler.RelationQ,
        "query",
        lambda *_args, **_kwargs: pytest.fail("无 workload 时不应查询 UQ"),
    )

    assert ServiceLogTaskHandler.get_k8s_related_log_indexes(BK_BIZ_ID, APP_NAME) == {}


def test_get_k8s_related_log_indexes_dedup(monkeypatch: pytest.MonkeyPatch) -> None:
    entity_set = FakeEntitySet(
        {
            "service-a": [WORKLOAD.copy()],
            "service-b": [WORKLOAD.copy()],
        }
    )
    query_lists: list[list[dict[str, Any]]] = []

    def query_relations(query_list: list[dict[str, Any]], **_kwargs: Any) -> list[SimpleNamespace]:
        query_lists.append(query_list)
        source_info: dict[str, Any] = query_list[0]["source_info"]
        datasource_node = SimpleNamespace(source_info=SimpleNamespace(to_source_info=lambda: {"bk_data_id": "1001"}))
        return [SimpleNamespace(source_info=source_info, nodes=[datasource_node])]

    monkeypatch.setattr(task_handler, "EntitySet", lambda *_args, **_kwargs: entity_set)
    monkeypatch.setattr(task_handler.RelationQ, "query", query_relations)
    monkeypatch.setattr(
        ServiceLogTaskHandler,
        "_query_service_related_indexes",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(ServiceLogHandler, "list_tables_by_data_ids", lambda *_args: ["2_bklog.demo"])
    monkeypatch.setattr(
        task_handler,
        "get_biz_index_sets_with_cache",
        lambda **_kwargs: [{"index_set_id": 100, "indices": [{"result_table_id": "2_bklog.demo"}]}],
    )

    result = ServiceLogTaskHandler.get_k8s_related_log_indexes(BK_BIZ_ID, APP_NAME)

    expected_indexes = [{"index_set_id": 100, "bk_biz_id": BK_BIZ_ID}]
    assert result == {"service-a": expected_indexes, "service-b": expected_indexes}
    assert len(query_lists) == 1
    assert len(query_lists[0]) == 1


def test_get_k8s_related_log_indexes_deduplicates_query_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    entity_set = FakeEntitySet({"service-a": [WORKLOAD.copy()]})

    def query_relations(query_list: list[dict[str, Any]], **_kwargs: Any) -> list[SimpleNamespace]:
        datasource_node = SimpleNamespace(source_info=SimpleNamespace(to_source_info=lambda: {"bk_data_id": "1001"}))
        return [SimpleNamespace(source_info=query_list[0]["source_info"], nodes=[datasource_node])]

    monkeypatch.setattr(task_handler, "EntitySet", lambda *_args, **_kwargs: entity_set)
    monkeypatch.setattr(task_handler.RelationQ, "query", query_relations)
    monkeypatch.setattr(ServiceLogHandler, "list_tables_by_data_ids", lambda *_args: ["2_bklog.demo"])
    monkeypatch.setattr(
        task_handler,
        "get_biz_index_sets_with_cache",
        lambda **_kwargs: [{"index_set_id": 100, "indices": [{"result_table_id": "2_bklog.demo"}]}],
    )

    assert ServiceLogTaskHandler.get_k8s_related_log_indexes(BK_BIZ_ID, APP_NAME) == {
        "service-a": [{"index_set_id": 100, "bk_biz_id": BK_BIZ_ID}]
    }


def test_get_k8s_related_log_indexes_custom_workload_uses_service_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    custom_workload = {**WORKLOAD, "kind": "CustomWorkload"}
    entity_set = FakeEntitySet({"service-a": [custom_workload]})
    query_lists: list[list[dict[str, Any]]] = []

    def query_relations(query_list: list[dict[str, Any]], **_kwargs: Any) -> list[SimpleNamespace]:
        query_lists.append(query_list)
        source_info: dict[str, Any] = query_list[0]["source_info"]
        datasource_node = SimpleNamespace(source_info=SimpleNamespace(to_source_info=lambda: {"bk_data_id": "1001"}))
        return [SimpleNamespace(source_info=source_info, nodes=[datasource_node])]

    monkeypatch.setattr(task_handler, "EntitySet", lambda *_args, **_kwargs: entity_set)
    monkeypatch.setattr(task_handler.RelationQ, "query", query_relations)
    monkeypatch.setattr(ServiceLogHandler, "list_tables_by_data_ids", lambda *_args: ["2_bklog.demo"])
    monkeypatch.setattr(
        task_handler,
        "get_biz_index_sets_with_cache",
        lambda **_kwargs: [{"index_set_id": 100, "indices": [{"result_table_id": "2_bklog.demo"}]}],
    )

    assert ServiceLogTaskHandler.get_k8s_related_log_indexes(BK_BIZ_ID, APP_NAME) == {
        "service-a": [{"index_set_id": 100, "bk_biz_id": BK_BIZ_ID}]
    }
    assert len(query_lists) == 1
    assert query_lists[0][0]["source_info"]["apm_service_name"] == "service-a"


@pytest.mark.parametrize(
    "partial_workload",
    [
        {"bcs_cluster_id": WORKLOAD["bcs_cluster_id"]},
        {
            "bcs_cluster_id": WORKLOAD["bcs_cluster_id"],
            "namespace": WORKLOAD["namespace"],
        },
        {
            "bcs_cluster_id": WORKLOAD["bcs_cluster_id"],
            "namespace": WORKLOAD["namespace"],
            "kind": WORKLOAD["kind"],
        },
    ],
)
def test_get_k8s_related_log_indexes_partial_relation_uses_service_path(
    monkeypatch: pytest.MonkeyPatch,
    partial_workload: dict[str, str],
) -> None:
    entity_set = FakeEntitySet({"service-a": [partial_workload]})
    query_lists: list[list[dict[str, Any]]] = []

    def query_relations(query_list: list[dict[str, Any]], **_kwargs: Any) -> list[SimpleNamespace]:
        query_lists.append(query_list)
        source_info: dict[str, Any] = query_list[0]["source_info"]
        datasource_node = SimpleNamespace(source_info=SimpleNamespace(to_source_info=lambda: {"bk_data_id": "1001"}))
        return [SimpleNamespace(source_info=source_info, nodes=[datasource_node])]

    monkeypatch.setattr(task_handler, "EntitySet", lambda *_args, **_kwargs: entity_set)
    monkeypatch.setattr(task_handler.RelationQ, "query", query_relations)
    monkeypatch.setattr(ServiceLogHandler, "list_tables_by_data_ids", lambda *_args: ["2_bklog.demo"])
    monkeypatch.setattr(
        task_handler,
        "get_biz_index_sets_with_cache",
        lambda **_kwargs: [{"index_set_id": 100, "indices": [{"result_table_id": "2_bklog.demo"}]}],
    )

    assert ServiceLogTaskHandler.get_k8s_related_log_indexes(BK_BIZ_ID, APP_NAME) == {
        "service-a": [{"index_set_id": 100, "bk_biz_id": BK_BIZ_ID}]
    }
    assert len(query_lists) == 1
    assert query_lists[0][0]["source_info"]["apm_service_name"] == "service-a"


def test_cache_merge_append_only(monkeypatch: pytest.MonkeyPatch) -> None:
    cache_key = ApmCacheKey.APP_SERVICE_K8S_RELATED_LOG_INDEXES_KEY.format(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME)
    old_cache = {
        "service-a": [
            {"index_set_id": 100, "bk_biz_id": BK_BIZ_ID, "updated_at": 1},
            {"index_set_id": 200, "bk_biz_id": BK_BIZ_ID, "updated_at": 2},
        ],
        "service-old": [{"index_set_id": 400, "bk_biz_id": BK_BIZ_ID, "updated_at": 4}],
    }
    redis_cache = FakeRedisCache({cache_key: compress_and_serialize(old_cache)})
    application = SimpleNamespace(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME, bk_tenant_id="tenant-a")
    application_filters: list[dict[str, Any]] = []

    def filter_applications(**kwargs: Any) -> list[SimpleNamespace]:
        application_filters.append(kwargs)
        return [application]

    application_model = SimpleNamespace(objects=SimpleNamespace(filter=filter_applications))
    tenant_ids: list[str] = []

    monkeypatch.setattr(tasks, "Application", application_model)
    monkeypatch.setattr(tasks, "caches", {"redis": redis_cache})
    monkeypatch.setattr(tasks, "set_local_tenant_id", tenant_ids.append)
    monkeypatch.setattr(tasks.time, "time", lambda: 123)
    monkeypatch.setattr(
        tasks.ServiceLogTaskHandler,
        "get_k8s_related_log_indexes",
        lambda *_args, **_kwargs: {
            "service-a": [
                {"index_set_id": "100", "bk_biz_id": BK_BIZ_ID},
                {"index_set_id": 300, "bk_biz_id": BK_BIZ_ID},
            ]
        },
    )

    tasks.cache_application_k8s_related_indexes()

    serialized_data = redis_cache.data[cache_key]
    assert isinstance(serialized_data, bytes)
    cached_data = deserialize_and_decompress(serialized_data)
    assert cached_data == {
        "service-a": [
            {"index_set_id": "100", "bk_biz_id": BK_BIZ_ID, "updated_at": 123},
            {"index_set_id": 200, "bk_biz_id": BK_BIZ_ID, "updated_at": 2},
            {"index_set_id": 300, "bk_biz_id": BK_BIZ_ID, "updated_at": 123},
        ],
        "service-old": [{"index_set_id": 400, "bk_biz_id": BK_BIZ_ID, "updated_at": 4}],
    }
    assert tenant_ids == ["tenant-a"]
    assert application_filters == [{"is_enabled": True}]
    assert redis_cache.expirations[cache_key] == 24 * 60 * 60


@pytest.mark.parametrize(
    "invalid_cache_data",
    [
        b"invalid-cache-data",
        compress_and_serialize([]),
        compress_and_serialize({"service-a": None}),
        compress_and_serialize({"service-a": [{}]}),
    ],
)
def test_cache_invalid_data_replaced(monkeypatch: pytest.MonkeyPatch, invalid_cache_data: bytes) -> None:
    cache_key = ApmCacheKey.APP_SERVICE_K8S_RELATED_LOG_INDEXES_KEY.format(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME)
    redis_cache = FakeRedisCache({cache_key: invalid_cache_data})
    application = SimpleNamespace(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME, bk_tenant_id="tenant-a")
    application_model = SimpleNamespace(objects=SimpleNamespace(filter=lambda **_kwargs: [application]))

    monkeypatch.setattr(tasks, "Application", application_model)
    monkeypatch.setattr(tasks, "caches", {"redis": redis_cache})
    monkeypatch.setattr(tasks, "set_local_tenant_id", lambda _tenant_id: None)
    monkeypatch.setattr(tasks.time, "time", lambda: 123)
    monkeypatch.setattr(
        tasks.ServiceLogTaskHandler,
        "get_k8s_related_log_indexes",
        lambda *_args, **_kwargs: {"service-a": [{"index_set_id": 100, "bk_biz_id": BK_BIZ_ID}]},
    )

    tasks.cache_application_k8s_related_indexes()

    assert deserialize_and_decompress(redis_cache.data[cache_key]) == {
        "service-a": [{"index_set_id": 100, "bk_biz_id": BK_BIZ_ID, "updated_at": 123}]
    }
    assert redis_cache.expirations[cache_key] == 24 * 60 * 60


def test_list_indexes_by_relation_cache_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    cache_key = ApmCacheKey.APP_SERVICE_K8S_RELATED_LOG_INDEXES_KEY.format(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME)
    expected = [{"index_set_id": 100, "bk_biz_id": BK_BIZ_ID, "updated_at": 123}]
    redis_cache = FakeRedisCache({cache_key: compress_and_serialize({"service-a": expected})})
    monkeypatch.setattr(log_handler, "caches", {"redis": redis_cache})
    monkeypatch.setattr(
        task_handler.RelationQ,
        "query",
        lambda *_args, **_kwargs: pytest.fail("缓存命中时不应查询 UQ"),
    )

    assert ServiceLogHandler.list_indexes_by_relation(BK_BIZ_ID, APP_NAME, "service-a") == expected


def test_list_indexes_by_relation_cache_miss_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(log_handler, "caches", {"redis": FakeRedisCache()})
    monkeypatch.setattr(
        task_handler.RelationQ,
        "query",
        lambda *_args, **_kwargs: pytest.fail("缓存未命中时不应回退 UQ"),
    )

    assert ServiceLogHandler.list_indexes_by_relation(BK_BIZ_ID, APP_NAME, "service-a") == []


@pytest.mark.parametrize(
    "redis_cache",
    [
        FailingRedisCache(),
        FakeRedisCache(
            {
                ApmCacheKey.APP_SERVICE_K8S_RELATED_LOG_INDEXES_KEY.format(
                    bk_biz_id=BK_BIZ_ID, app_name=APP_NAME
                ): b"invalid-cache-data"
            }
        ),
        FakeRedisCache(
            {
                ApmCacheKey.APP_SERVICE_K8S_RELATED_LOG_INDEXES_KEY.format(
                    bk_biz_id=BK_BIZ_ID, app_name=APP_NAME
                ): compress_and_serialize([])
            }
        ),
        FakeRedisCache(
            {
                ApmCacheKey.APP_SERVICE_K8S_RELATED_LOG_INDEXES_KEY.format(
                    bk_biz_id=BK_BIZ_ID, app_name=APP_NAME
                ): compress_and_serialize({"service-a": None})
            }
        ),
        FakeRedisCache(
            {
                ApmCacheKey.APP_SERVICE_K8S_RELATED_LOG_INDEXES_KEY.format(
                    bk_biz_id=BK_BIZ_ID, app_name=APP_NAME
                ): compress_and_serialize({"service-a": [{}]})
            }
        ),
    ],
)
def test_list_indexes_by_relation_cache_error_empty(
    monkeypatch: pytest.MonkeyPatch,
    redis_cache: FakeRedisCache,
) -> None:
    monkeypatch.setattr(log_handler, "caches", {"redis": redis_cache})

    assert ServiceLogHandler.list_indexes_by_relation(BK_BIZ_ID, APP_NAME, "service-a") == []


def test_process_metric_relations_accepts_cached_indexes_without_addition(monkeypatch: pytest.MonkeyPatch) -> None:
    entity_set = FakeEntitySet({"service-a": [WORKLOAD.copy()]})
    monkeypatch.setattr(log_resources, "EntitySet", lambda *_args, **_kwargs: entity_set)
    monkeypatch.setattr(
        ServiceLogHandler,
        "list_indexes_by_relation",
        lambda *_args, **_kwargs: [
            {"index_set_id": "100", "bk_biz_id": BK_BIZ_ID},
            {"index_set_id": 200, "bk_biz_id": BK_BIZ_ID},
        ],
    )
    indexes_mapping = {
        BK_BIZ_ID: [
            {"index_set_id": 100, "index_set_name": "demo"},
            {"index_set_id": "200", "index_set_name": "api"},
        ]
    }

    assert process_metric_relations(
        BK_BIZ_ID,
        APP_NAME,
        "service-a",
        indexes_mapping,
    ) == [
        {"index_set_id": 100, "index_set_name": "demo", "addition": []},
        {"index_set_id": "200", "index_set_name": "api", "addition": []},
    ]


def test_process_metric_relations_skips_cache_for_service_without_workload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entity_set = FakeEntitySet({"service-a": [], "service-b": [WORKLOAD.copy()]})
    monkeypatch.setattr(log_resources, "EntitySet", lambda *_args, **_kwargs: entity_set)
    monkeypatch.setattr(
        ServiceLogHandler,
        "list_indexes_by_relation",
        lambda *_args, **_kwargs: pytest.fail("无 workload 的服务不应读取关联索引缓存"),
    )

    assert (
        process_metric_relations(
            BK_BIZ_ID,
            APP_NAME,
            "service-a",
            {BK_BIZ_ID: []},
        )
        == []
    )
