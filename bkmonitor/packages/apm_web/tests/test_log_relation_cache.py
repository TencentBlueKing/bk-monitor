"""APM 服务关联 K8S 日志索引缓存测试。"""

from types import SimpleNamespace
from typing import Any, cast

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


class FakeLogRelationCache:
    """记录日志关联列表结果缓存的读写。"""

    def __init__(self) -> None:
        self.data: dict[str, list[dict[str, Any]]] = {}
        self.read_keys: list[str] = []

    def get_value(self, key: str) -> list[dict[str, Any]] | None:
        self.read_keys.append(key)
        return self.data.get(key)

    def set_value(self, key: str, value: list[dict[str, Any]]) -> None:
        self.data[key] = value


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
    workload_query_lists: list[list[dict[str, Any]]] = []

    def query_relations(query_list: list[dict[str, Any]], **_kwargs: Any) -> list[SimpleNamespace]:
        if "apm_service_name" in query_list[0]["source_info"]:
            return [SimpleNamespace(source_info=query["source_info"], nodes=[]) for query in query_list]

        workload_query_lists.append(query_list)
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

    result = ServiceLogTaskHandler.get_k8s_related_log_indexes(BK_BIZ_ID, APP_NAME)

    expected_indexes = [{"index_set_id": 100, "bk_biz_id": BK_BIZ_ID}]
    assert result == {"service-a": expected_indexes, "service-b": expected_indexes}
    assert len(workload_query_lists) == 1
    assert len(workload_query_lists[0]) == 1


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


def test_get_k8s_related_log_indexes_keeps_partial_results_and_logs_failures(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    entity_set = FakeEntitySet({"service-a": [WORKLOAD.copy()]})

    def query_relations(query_list: list[dict[str, Any]], **_kwargs: Any) -> list[SimpleNamespace | None]:
        source_info: dict[str, Any] = query_list[0]["source_info"]
        if "apm_service_name" not in source_info:
            return [None]

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

    with caplog.at_level("WARNING", logger="apm"):
        result = ServiceLogTaskHandler.get_k8s_related_log_indexes(BK_BIZ_ID, APP_NAME)

    assert result == {"service-a": [{"index_set_id": 100, "bk_biz_id": BK_BIZ_ID}]}
    assert "relation query partially failed" in caplog.text
    assert "failed=1, total=2" in caplog.text


@pytest.mark.parametrize("query_result", [[None], []])
def test_get_k8s_related_log_indexes_raises_when_all_queries_fail(
    monkeypatch: pytest.MonkeyPatch,
    query_result: list[None],
) -> None:
    entity_set = FakeEntitySet({"service-a": [WORKLOAD.copy()]})
    monkeypatch.setattr(task_handler, "EntitySet", lambda *_args, **_kwargs: entity_set)
    monkeypatch.setattr(task_handler.RelationQ, "query", lambda *_args, **_kwargs: query_result)

    with pytest.raises(RuntimeError, match="all relation queries failed"):
        ServiceLogTaskHandler.get_k8s_related_log_indexes(BK_BIZ_ID, APP_NAME)


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


def test_cache_query_failure_keeps_existing_cache_and_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    failed_app_name = "failed-app"
    succeeded_app_name = "succeeded-app"
    failed_cache_key = ApmCacheKey.APP_SERVICE_K8S_RELATED_LOG_INDEXES_KEY.format(
        bk_biz_id=BK_BIZ_ID, app_name=failed_app_name
    )
    succeeded_cache_key = ApmCacheKey.APP_SERVICE_K8S_RELATED_LOG_INDEXES_KEY.format(
        bk_biz_id=BK_BIZ_ID, app_name=succeeded_app_name
    )
    old_cache = {"service-old": [{"index_set_id": 100, "bk_biz_id": BK_BIZ_ID, "updated_at": 1}]}
    redis_cache = FakeRedisCache({failed_cache_key: compress_and_serialize(old_cache)})
    applications = [
        SimpleNamespace(bk_biz_id=BK_BIZ_ID, app_name=failed_app_name, bk_tenant_id="tenant-a"),
        SimpleNamespace(bk_biz_id=BK_BIZ_ID, app_name=succeeded_app_name, bk_tenant_id="tenant-b"),
    ]
    tenant_ids: list[str] = []

    def get_related_indexes(_bk_biz_id: int, app_name: str) -> dict[str, list[dict[str, Any]]]:
        if app_name == failed_app_name:
            raise RuntimeError("all relation queries failed")

        return {"service-a": [{"index_set_id": 200, "bk_biz_id": BK_BIZ_ID}]}

    monkeypatch.setattr(
        tasks,
        "Application",
        SimpleNamespace(objects=SimpleNamespace(filter=lambda **_kwargs: applications)),
    )
    monkeypatch.setattr(tasks, "caches", {"redis": redis_cache})
    monkeypatch.setattr(tasks, "set_local_tenant_id", tenant_ids.append)
    monkeypatch.setattr(tasks.time, "time", lambda: 123)
    monkeypatch.setattr(tasks.ServiceLogTaskHandler, "get_k8s_related_log_indexes", get_related_indexes)

    tasks.cache_application_k8s_related_indexes()

    assert deserialize_and_decompress(redis_cache.data[failed_cache_key]) == old_cache
    assert failed_cache_key not in redis_cache.expirations
    assert deserialize_and_decompress(redis_cache.data[succeeded_cache_key]) == {
        "service-a": [{"index_set_id": 200, "bk_biz_id": BK_BIZ_ID, "updated_at": 123}]
    }
    assert redis_cache.expirations[succeeded_cache_key] == 24 * 60 * 60
    assert tenant_ids == ["tenant-a", "tenant-b"]


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


def test_log_relation_list_reuses_cache_across_time_ranges(monkeypatch: pytest.MonkeyPatch) -> None:
    result = [{"index_set_id": 100}]
    relation_calls: list[tuple[Any, ...]] = []
    result_cache = FakeLogRelationCache()

    def process_relation(*args: Any) -> list[dict[str, Any]]:
        relation_calls.append(args)
        return result

    monkeypatch.setattr(log_resources, "using_cache", lambda *_args, **_kwargs: result_cache)
    monkeypatch.setattr(log_resources, "get_biz_index_sets_with_cache", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(log_resources, "process_relation", process_relation)
    monkeypatch.setattr(log_resources, "process_datasource", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(log_resources, "process_metric_relations", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(log_resources, "process_span_host", lambda *_args, **_kwargs: [])

    first_result = log_resources.log_relation_list(BK_BIZ_ID, APP_NAME, "service-a", start_time=1, end_time=2)
    second_result = log_resources.log_relation_list(BK_BIZ_ID, APP_NAME, "service-a", start_time=3, end_time=4)

    assert first_result == result
    assert second_result == result
    assert len(relation_calls) == 1
    assert result_cache.read_keys[0] == result_cache.read_keys[1]


def test_log_info_accepts_but_does_not_forward_time_range(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, str, str | None]] = []
    entity_set = FakeEntitySet({"service-a": [WORKLOAD.copy()]})

    def list_indexes_by_relation(
        bk_biz_id: int,
        app_name: str,
        service_name: str | None,
    ) -> list[dict[str, Any]]:
        calls.append((bk_biz_id, app_name, service_name))
        return [{"index_set_id": 100, "bk_biz_id": bk_biz_id}]

    monkeypatch.setattr(ServiceLogHandler, "get_log_datasource", lambda **_kwargs: None)
    monkeypatch.setattr(ServiceLogHandler, "get_log_relations", lambda **_kwargs: [])
    monkeypatch.setattr(ServiceLogHandler, "list_indexes_by_relation", list_indexes_by_relation)
    monkeypatch.setattr(log_resources, "EntitySet", lambda *_args, **_kwargs: entity_set)
    serializer = log_resources.LogInfoResource.RequestSerializer(
        data={
            "bk_biz_id": BK_BIZ_ID,
            "app_name": APP_NAME,
            "service_name": "service-a",
            "start_time": 1,
            "end_time": 2,
        }
    )

    assert serializer.is_valid(), serializer.errors
    validated_request_data = cast(dict[str, Any], serializer.validated_data)
    assert log_resources.LogInfoResource().perform_request(validated_request_data) is True
    assert calls == [(BK_BIZ_ID, APP_NAME, "service-a")]


def test_log_info_skips_stale_cache_for_service_without_workload(monkeypatch: pytest.MonkeyPatch) -> None:
    entity_set = FakeEntitySet({"service-a": []})
    monkeypatch.setattr(ServiceLogHandler, "get_log_datasource", lambda **_kwargs: None)
    monkeypatch.setattr(ServiceLogHandler, "get_log_relations", lambda **_kwargs: [])
    monkeypatch.setattr(
        ServiceLogHandler,
        "list_indexes_by_relation",
        lambda *_args, **_kwargs: pytest.fail("无 workload 的服务不应读取历史关联索引缓存"),
    )
    monkeypatch.setattr(log_resources, "EntitySet", lambda *_args, **_kwargs: entity_set)

    assert (
        log_resources.LogInfoResource().perform_request(
            {"bk_biz_id": BK_BIZ_ID, "app_name": APP_NAME, "service_name": "service-a"}
        )
        is False
    )


def test_log_info_workload_query_error_returns_false(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def raise_topology_query_error(*_args: Any, **_kwargs: Any) -> None:
        raise ValueError("topology query failed")

    monkeypatch.setattr(ServiceLogHandler, "get_log_datasource", lambda **_kwargs: None)
    monkeypatch.setattr(ServiceLogHandler, "get_log_relations", lambda **_kwargs: [])
    monkeypatch.setattr(
        ServiceLogHandler,
        "list_indexes_by_relation",
        lambda *_args, **_kwargs: pytest.fail("workload 查询失败后不应继续读取关联索引缓存"),
    )
    monkeypatch.setattr(
        log_resources,
        "EntitySet",
        raise_topology_query_error,
    )

    with caplog.at_level("ERROR", logger="apm"):
        result = log_resources.LogInfoResource().perform_request(
            {"bk_biz_id": BK_BIZ_ID, "app_name": APP_NAME, "service_name": "service-a"}
        )

    assert result is False
    assert "[LOG_INFO] workload query failed" in caplog.text
