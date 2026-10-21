"""Consumer contracts, running production method bodies with external services replaced.

The isolated loader avoids initializing unrelated Django apps and infrastructure.
It does not replace the relation parsing, completeness checks or cache merge logic.
"""

import ast
import copy
import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field, fields
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.conf import settings

if not settings.configured:
    settings.configure(USE_I18N=False)

from api.unify_query.relation_result import (  # noqa: E402
    IncompleteRelationError,
    ensure_complete_relation,
    is_incomplete_relation,
)
from core.errors.api import BKAPIError  # noqa: E402

ROOT = Path(__file__).parents[3]
RELATION = "packages/apm_web/topo/handle/relation/"


def load_definitions(path, names, namespace, methods=None):
    """Execute actual definitions; only imports/decorators for unrelated infrastructure are omitted."""
    tree = ast.parse((ROOT / path).read_text())
    body = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef | ast.FunctionDef) or node.name not in names:
            continue
        if isinstance(node, ast.ClassDef) and methods is not None:
            node.bases = []
            node.body = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name in methods]
        if isinstance(node, ast.FunctionDef):
            node.decorator_list = []
        body.append(node)
    assert {node.name for node in body} == set(names)
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *body],
        type_ignores=[],
    )
    exec(compile(ast.fix_missing_locations(module), str(ROOT / path), "exec"), namespace)
    return namespace


def result(*, targets=(), **quality):
    return {
        "code": 200,
        "source_info": {"apm_application_name": "demo", "apm_service_name": "api"},
        "source_type": "apm_service",
        "path": ["apm_service", "datasource"],
        "target_list": [{"timestamp": 100, "items": list(targets)}] if targets else [],
        **quality,
    }


@pytest.fixture
def consumer():
    ns = {
        "__name__": __name__,
        "dataclass": dataclass,
        "field": field,
        "fields": fields,
        "hashlib": hashlib,
        "SourceType": SimpleNamespace(DATA_SOURCE=SimpleNamespace(value="datasource")),
        "logger": logging.getLogger("apm"),
        "is_incomplete_relation": is_incomplete_relation,
        "IncompleteRelationError": IncompleteRelationError,
        "ensure_complete_relation": ensure_complete_relation,
        "api": SimpleNamespace(unify_query=SimpleNamespace(query_multi_resource_range=Mock())),
        "time": time,
    }
    load_definitions(RELATION + "define.py", ["SourceProvider", "Source", "SourceDatasource", "Node", "Relation"], ns)
    load_definitions(RELATION + "query.py", ["RelationQ"], ns)
    return SimpleNamespace(**ns)


@pytest.mark.parametrize("quality", [{}, {"partial": False, "truncated": False}])
def test_complete_empty_remains_empty(consumer, quality):
    consumer.api.unify_query.query_multi_resource_range.return_value = {"data": [result(**quality)]}
    relations = consumer.RelationQ.query([{}])
    assert len(relations) == 1
    assert relations[0].nodes == []


@pytest.mark.parametrize("quality", [{"partial": True}, {"truncated": True}, {"partial": True, "truncated": True}])
@pytest.mark.parametrize("targets", [[], [{"bk_data_id": "1001"}]])
def test_pages_reject_incomplete_before_path_filter(consumer, quality, targets):
    consumer.api.unify_query.query_multi_resource_range.return_value = {"data": [result(targets=targets, **quality)]}
    with pytest.raises(IncompleteRelationError) as exc:
        consumer.RelationQ.query([{}], expect_paths=["a-different-path"], fill_with_empty=True)
    assert isinstance(exc.value, BKAPIError)
    assert exc.value.error_details["popup_message"] == "warning"


def test_cache_skips_incomplete_with_alignment_and_keeps_complete_nodes(consumer):
    consumer.api.unify_query.query_multi_resource_range.return_value = {
        "data": [
            result(partial=True, targets=[{"bk_data_id": "9999"}]),
            result(targets=[{"bk_data_id": "1001"}, {"bk_data_id": "1001"}]),
            result(truncated=True),
            result(),
            {"code": 500},
        ]
    }
    rows = consumer.RelationQ.query([{}] * 5, fill_with_empty=True, skip_incomplete=True)
    assert [r is None for r in rows] == [True, False, True, False, True]
    assert [n.source_info.bk_data_id for n in rows[1].nodes] == ["1001"]
    assert rows[3].nodes == []


@pytest.mark.parametrize("quality", [{"partial": True}, {"truncated": True}])
def test_direct_instance_consumer_rejects_incomplete(consumer, quality):
    ns = vars(consumer)
    load_definitions(RELATION + "relation_metric.py", ["RelationMetricHandler"], ns)
    consumer.api.unify_query.query_multi_resource_range.return_value = {"data": [result(**quality)]}
    with pytest.raises(IncompleteRelationError):
        ns["RelationMetricHandler"].list_instances(2, "demo", 1, 100, service_name="api")


def test_direct_instance_consumer_accepts_complete_nonempty(consumer):
    ns = vars(consumer)
    load_definitions(RELATION + "relation_metric.py", ["RelationMetricHandler"], ns)
    consumer.api.unify_query.query_multi_resource_range.return_value = {
        "data": [result(targets=[{"apm_service_instance_name": "instance-a"}])]
    }
    assert ns["RelationMetricHandler"].list_instances(2, "demo", 1, 100, service_name="api") == [
        {"apm_service_instance_name": "instance-a"}
    ]


def test_log_to_apm_checks_whole_batch_before_returning_first_match(consumer):
    ns = vars(consumer)
    empty_qs = Mock()
    empty_qs.exists.return_value = False
    bindings = SimpleNamespace(filter_by_index_set_id=Mock())
    bindings.filter_by_index_set_id.return_value.order_by.return_value.first.return_value = None
    # The only local import in this production method is the explicit-binding model.
    import sys
    from types import ModuleType
    from unittest.mock import patch

    models = ModuleType("apm_web.models")
    models.LogServiceRelation = bindings
    ns.update(
        LogDataSource=SimpleNamespace(objects=SimpleNamespace(filter=lambda **_: empty_qs)),
        TraceDataSource=SimpleNamespace(objects=SimpleNamespace(filter=lambda **_: empty_qs)),
        ApmApplication=Mock(),
    )
    load_definitions("apm/resources.py", ["QueryLogRelationByIndexSetIdResource"], ns, ["perform_request"])
    consumer.api.unify_query.query_multi_resource_range.return_value = {
        "data": [result(targets=[{"apm_application_name": "demo"}]), result(partial=True)]
    }
    with patch.dict(sys.modules, {"apm_web.models": models}):
        with pytest.raises(IncompleteRelationError):
            ns["QueryLogRelationByIndexSetIdResource"]().perform_request({"index_set_id": 1, "bk_data_id": 1001})
    ns["ApmApplication"].objects.filter.assert_not_called()


def test_host_list_does_not_swallow_incomplete_or_write_cache(consumer):
    ns = vars(consumer)
    cache = Mock()
    cache.get_value.return_value = None
    failed = Mock()
    failed.get.side_effect = IncompleteRelationError()
    healthy = Mock()
    healthy.get.return_value = [{"bk_host_id": 1}]
    pool = Mock()
    pool.apply_async.side_effect = [healthy, healthy, failed]
    ns.update(using_cache=lambda _: cache, CacheType=SimpleNamespace(APM=lambda value: value), ThreadPool=lambda: pool)
    load_definitions("packages/apm_web/handlers/host_handler.py", ["HostHandler"], ns, ["list_application_hosts"])
    cls = ns["HostHandler"]
    cls.get_hosts_from_trace_relation = cls.get_hosts_from_service_relation = cls.get_hosts_from_auto_relation = Mock()
    with pytest.raises(IncompleteRelationError):
        cls.list_application_hosts(2, "demo", "api", 1, 100)
    cache.set_value.assert_not_called()


@pytest.mark.parametrize("quality", [{"partial": True}, {"truncated": True}])
def test_alarm_keeps_known_positive_and_skips_incomplete_empty(consumer, quality, caplog):
    ns = vars(consumer)
    ns.update(defaultdict=defaultdict, bk_biz_id_to_bk_tenant_id=lambda _: "tenant-example")
    load_definitions(
        "alarm_backends/service/alert/enricher/kubernetes_cmdb.py", ["KubernetesCMDBEnricher"], ns, ["get_node_ips"]
    )
    obj = ns["KubernetesCMDBEnricher"]()
    obj.biz_resource_info = {
        2: [
            {"code": 200, "target_list": [], **quality},
            {"code": 200, "target_list": [{"bk_target_ip": "192.0.2.1"}], **quality},
            {"code": 200, "target_list": [{"bk_target_ip": "192.0.2.2"}]},
        ]
    }
    obj.kubernetes_alerts = {2: [SimpleNamespace(id="a"), SimpleNamespace(id="b"), SimpleNamespace(id="c")]}
    obj.alert_relations = {}
    with caplog.at_level(logging.WARNING, logger="apm"):
        assert obj.get_node_ips() == {"tenant-example": {"192.0.2.1", "192.0.2.2"}}
    assert set(obj.alert_relations) == {"b", "c"}
    assert "incomplete host relation" in caplog.text


def load_cache_handler(consumer, workload_result, service_result):
    ns = vars(consumer)
    workload = {"kind": "Deployment", "name": "demo", "namespace": "default", "bcs_cluster_id": "example"}
    ns.update(EntitySet=lambda **_: SimpleNamespace(service_names=["api"]), ThreadPool=lambda _: SimplePool())
    load_definitions(
        "packages/apm_web/handlers/task_handler.py",
        ["ServiceLogTaskHandler"],
        ns,
        ["get_k8s_related_log_indexes", "_query_relations"],
    )
    cls = ns["ServiceLogTaskHandler"]
    cls._fetch_app_workloads = Mock(return_value={"api": [workload]})
    cls._normalize_and_deduplicate_workloads = Mock(return_value=[workload])
    cls._query_workload_related_indexes = Mock(return_value=workload_result)
    cls._query_service_related_indexes = Mock(return_value=service_result)
    cls._merge_by_service = lambda _, w, s: {**w, **s}
    return cls


class SimplePool:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def apply_async(self, fn, args):
        return SimpleNamespace(get=lambda: fn(*args))


@pytest.mark.parametrize("counts", [(1, 0), (0, 1)])
def test_cache_failed_plus_complete_empty_is_not_a_successful_refresh(consumer, counts):
    handler = load_cache_handler(consumer, ({}, counts[0]), ({}, counts[1]))
    with pytest.raises(IncompleteRelationError):
        handler.get_k8s_related_log_indexes(2, "demo")


def test_cache_all_complete_empty_preserves_legacy_semantics(consumer):
    handler = load_cache_handler(consumer, ({}, 0), ({}, 0))
    assert handler.get_k8s_related_log_indexes(2, "demo") == {}


def test_cache_consumes_healthy_subitems_and_counts_incomplete(consumer):
    consumer.api.unify_query.query_multi_resource_range.return_value = {
        "data": [result(partial=True), result(targets=[{"bk_data_id": "1001"}]), result(truncated=True)]
    }
    handler = load_cache_handler(consumer, ({}, 1), ({"api": [{"index_set_id": 1}]}, 0))
    rows, failures = handler._query_relations([{}] * 3)
    assert failures == 2 and len(rows) == 1
    assert rows[0].nodes[0].source_info.bk_data_id == "1001"
    assert handler.get_k8s_related_log_indexes(2, "demo") == {"api": [{"index_set_id": 1}]}


@pytest.mark.parametrize("has_healthy", [False, True])
def test_real_cache_task_keeps_failed_data_freshness_and_only_writes_on_positive_refresh(consumer, has_healthy):
    ns = vars(consumer)
    old = {"failed": [{"index_set_id": 9, "updated_at": 1}]}
    cache = Mock()
    cache.get.return_value = copy.deepcopy(old)
    handler = load_cache_handler(consumer, ({}, 1), ({"healthy": [{"index_set_id": 1}]} if has_healthy else {}, 0))
    ns.update(
        caches={"redis": cache},
        ServiceLogTaskHandler=handler,
        Application=Mock(),
        set_local_tenant_id=Mock(),
        ApmCacheKey=SimpleNamespace(APP_SERVICE_K8S_RELATED_LOG_INDEXES_KEY="{bk_biz_id}:{app_name}"),
        deserialize_service_related_log_indexes=lambda x: x,
        compress_and_serialize=lambda x: x,
    )
    ns["Application"].objects.filter.return_value.exclude.return_value = [
        SimpleNamespace(bk_biz_id=2, app_name="demo", bk_tenant_id="tenant-example")
    ]
    load_definitions("packages/apm_web/tasks.py", ["cache_application_k8s_related_indexes"], ns)
    ns["cache_application_k8s_related_indexes"]()
    if not has_healthy:
        cache.get.assert_not_called()
        cache.set.assert_not_called()
    else:
        value = cache.set.call_args.args[1]
        assert value["failed"] == old["failed"]
        assert value["healthy"][0]["updated_at"] > 1
        assert cache.set.call_args.kwargs == {"timeout": 24 * 60 * 60}
