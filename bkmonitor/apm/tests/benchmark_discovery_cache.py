"""Opt-in, fixed-input discovery benchmark using real discovery code and ORM.

Run with pytest -s and APM_DISCOVERY_BASE_REF set to the pre-change Git revision.
APM_DISCOVERY_BENCHMARK_PAGES=742 and APM_DISCOVERY_BENCHMARK_REPEATS=3 select
the large comparison. ES responses and Redis transport are local fixtures; JSON,
discovery, and SQL execute normally. Results are not production latency forecasts.
"""

import ast
import copy
import hashlib
import importlib
import json
import logging
import os
import statistics
import subprocess
import time
from collections import Counter
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest import mock

import fakeredis
import pytest
from django.db import connections
from django.db.models.query import QuerySet

from apm.constants import ApmCacheType
from apm.core.discover.base import DiscoverContainer, TopoHandler
from apm.core.discover.cached_mixin import CachedDiscoverMixin
from apm.core.discover.endpoint import EndpointDiscover
from apm.core.discover.host import HostDiscover
from apm.core.discover.instance import InstanceDiscover
from apm.core.discover.relation import RelationDiscover
from apm.core.discover.remote_service_relation import RemoteServiceRelationDiscover
from apm.core.discover.root_endpoint import RootEndpointDiscover
from apm.core.handlers.apm_cache_handler import ApmCacheHandler
from apm.models import Endpoint, TopoNode
from apm.tests.test_discovery_group_query import build_trace_span, trace_discovery  # noqa: F401
from constants.apm import SpanKind, TelemetryDataType

pytestmark = pytest.mark.django_db(databases="__all__")

CACHED_DISCOVERERS = (
    EndpointDiscover,
    HostDiscover,
    InstanceDiscover,
    RelationDiscover,
    RemoteServiceRelationDiscover,
    RootEndpointDiscover,
)
MODELS = (TopoNode, *(discoverer.model for discoverer in CACHED_DISCOVERERS))


class CountingRedis(fakeredis.FakeRedis):
    """Count actual transport operations while retaining real JSON round trips."""

    def __init__(self):
        super().__init__(decode_responses=True)
        self.operations = Counter()

    def get(self, name):
        value = super().get(name)
        self.operations["get"] += 1
        self.operations["get_bytes"] += len(value.encode()) if value else 0
        return value

    def set(self, name, value, *args, **kwargs):
        self.operations["set"] += 1
        self.operations["set_bytes"] += len(str(value).encode())
        return super().set(name, value, *args, **kwargs)


def spans_for_trace(identifier):
    """100 traces contain 162 spans: singletons, sync chains, and async pairs."""
    page, index = map(int, identifier.split("-"))
    offset = (page * 100 + index) * 1_000_000

    def span(service, suffix, parent, endpoint, start, end, kind=SpanKind.SPAN_KIND_SERVER):
        return build_trace_span(
            service, identifier, f"{identifier}:{suffix}", parent, endpoint, offset + start, offset + end, kind
        )

    if index < 62:
        return [span("front", "root", "", f"GET /entry/{index}", 0, 900_000)]
    if index < 86:
        root = span("front", "root", "", "GET /chain", 0, 900_000)
        client = span("front", "client", root["span_id"], "GET /catalog", 100_000, 800_000, SpanKind.SPAN_KIND_CLIENT)
        client["attributes"]["peer.service"] = "catalog"
        server = span("back", "server", client["span_id"], "GET /catalog", 200_000, 700_000)
        return [root, client, server]
    producer = span("publisher", "producer", "", "publish", 0, 900_000, SpanKind.SPAN_KIND_PRODUCER)
    consumer = span(
        "subscriber", "consumer", producer["span_id"], "consume", 100_000, 800_000, SpanKind.SPAN_KIND_CONSUMER
    )
    return [producer, consumer]


def coverage_snapshot():
    """Compare every entity/relation identity, not only aggregate row counts."""
    result = {"TopoNode": {json.dumps(key) for key in TopoNode.objects.values_list("topo_key", flat=True)}}
    row_counts = {"TopoNode": TopoNode.objects.count()}
    for discoverer in CACHED_DISCOVERERS:
        rows = list(discoverer.model.objects.all())
        result[discoverer.model.__name__] = {
            json.dumps(discoverer._to_found_key(discoverer.build_instance_data(row))) for row in rows
        }
        row_counts[discoverer.model.__name__] = len(rows)
    return result, row_counts


def baseline_method(revision, cls, name):
    """Compile the unmodified old method, without maintaining a second algorithm."""
    module = importlib.import_module(cls.__module__)
    root = Path(__file__).resolve().parents[3]
    relative = Path(module.__file__).resolve().relative_to(root)
    source = subprocess.check_output(["git", "show", f"{revision}:{relative.as_posix()}"], cwd=root, text=True)
    definition = next(
        node for node in ast.parse(source).body if isinstance(node, ast.ClassDef) and node.name == cls.__name__
    )
    method = copy.deepcopy(
        next(node for node in definition.body if isinstance(node, ast.FunctionDef) and node.name == name)
    )
    tree = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    namespace = vars(module).copy()
    exec(compile(tree, f"baseline:{relative}:{name}", "exec"), namespace)
    return namespace[name]


@contextmanager
def original_implementation(revision):
    methods = {
        name: baseline_method(revision, TopoHandler, name)
        for name in ("discover", "_discover_spans", "_discover_handle")
    }
    original_refresh = baseline_method(revision, CachedDiscoverMixin, "handle_cache_refresh_after_create")

    def refresh(self, *args, **kwargs):
        # The new call sites pass the shared mapping; the old method did not use it.
        kwargs.pop("remain_data", None)
        return original_refresh(self, *args, **kwargs)

    with ExitStack() as stack:
        for name, method in methods.items():
            stack.enter_context(mock.patch.object(TopoHandler, name, method))
        stack.enter_context(mock.patch.object(CachedDiscoverMixin, "handle_cache_refresh_after_create", refresh))
        yield


def seed_application(redis, endpoint_count):
    for model in MODELS:
        model.objects.all().delete()
    redis.flushdb()
    # Keep two endpoint identities new in the timed run to expose cross-page duplication.
    seed_spans = [span for index in range(1, 100) for span in spans_for_trace(f"0-{index}")]
    for cls in DiscoverContainer.list_discovers(TelemetryDataType.TRACE.value):
        discoverer = cls(2, "app")
        selected = (
            seed_spans if cls.DISCOVERY_ALL_SPANS else [s for s in seed_spans if s["kind"] in TopoHandler.FILTER_KIND]
        )
        discoverer.discover(selected, discoverer.get_remain_data())
    sample = Endpoint.objects.first()
    fields = {
        field.name: getattr(sample, field.name)
        for field in Endpoint._meta.fields
        if field.name not in {"id", "created_at", "updated_at"}
    }
    Endpoint.objects.bulk_create(
        [Endpoint(**(fields | {"endpoint_name": f"GET /seed/{index}"})) for index in range(endpoint_count)]
    )
    endpoint_cache = {
        EndpointDiscover.to_cache_key(EndpointDiscover.build_instance_data(row)): int(time.time())
        for row in Endpoint.objects.all()
    }
    key = ApmCacheHandler.get_cache_key(ApmCacheType.ENDPOINT, 2, "app")
    redis.set(key, json.dumps(endpoint_cache))
    redis.operations.clear()


def measured_run(handler, redis, pages):
    consumed = Counter()
    sql = Counter()
    created = Counter()

    def list_pages(_index, _stats=None):
        for page in range(pages):
            consumed["pages"] += 1
            consumed["traces"] += 100
            yield [f"{page}-{index}" for index in range(100)]

    def fetch_spans(identifiers, *_args):
        spans = [span for identifier in identifiers for span in spans_for_trace(identifier)]
        consumed["spans"] += len(spans)
        return spans

    def execute(executor, statement, params, many, context):
        sql[statement.lstrip().split(None, 1)[0].upper()] += 1
        return executor(statement, params, many, context)

    original_create = QuerySet.bulk_create

    def bulk_create(queryset, objects, *args, **kwargs):
        objects = list(objects)
        if queryset.model in MODELS:
            created[queryset.model.__name__] += len(objects)
        return original_create(queryset, objects, *args, **kwargs)

    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(handler, "list_trace_ids", side_effect=list_pages))
        stack.enter_context(mock.patch.object(handler, "list_span_by_trace_ids", side_effect=fetch_spans))
        stack.enter_context(mock.patch.object(QuerySet, "bulk_create", bulk_create))
        for connection in connections.all():
            stack.enter_context(connection.execute_wrapper(execute))
        started = time.perf_counter()
        success = handler.discover()
        duration = time.perf_counter() - started
    assert success is True
    assert consumed == {"pages": pages, "traces": pages * 100, "spans": pages * 162}
    coverage, rows = coverage_snapshot()
    assert all(coverage.values())
    assert '"sparse"' in coverage["TopoNode"]
    assert not any('"sparse"' in item for item in coverage["RootEndpoint"])
    return {
        "seconds": duration,
        "consumed": dict(consumed),
        "redis": dict(redis.operations),
        "sql": dict(sql),
        "created_rows": dict(created),
        "final_rows": rows,
        "coverage_counts": {name: len(keys) for name, keys in coverage.items()},
        "coverage_sha256": hashlib.sha256(
            json.dumps({name: sorted(keys) for name, keys in coverage.items()}, sort_keys=True).encode()
        ).hexdigest(),
    }, coverage


def test_fixed_workload_discovery_cache(request, mocker):
    revision = os.environ.get("APM_DISCOVERY_BASE_REF")
    if not revision:
        pytest.skip("Set APM_DISCOVERY_BASE_REF to the pre-change revision for this opt-in benchmark")
    pages = int(os.environ.get("APM_DISCOVERY_BENCHMARK_PAGES", "8"))
    repeats = int(os.environ.get("APM_DISCOVERY_BENCHMARK_REPEATS", "1"))
    endpoint_count = int(os.environ.get("APM_DISCOVERY_BENCHMARK_ENDPOINTS", "5000"))
    assert pages > 0 and repeats > 0 and endpoint_count >= 0
    handler, query = request.getfixturevalue("trace_discovery")
    redis = CountingRedis()
    mocker.patch.object(ApmCacheHandler, "get_redis_client", return_value=redis)
    sparse = build_trace_span(
        "sparse", "fallback", "sparse-child", "unavailable-parent", "GET /rare", 100_000_000, 110_000_000
    )
    query.query_group_list.return_value = [spans_for_trace("0-62")[-1], sparse]
    results = {"baseline": [], "optimized": []}
    expected_coverage = None
    old_logging_disable = logging.root.manager.disable
    try:
        logging.disable(logging.CRITICAL)
        for repeat in range(repeats):
            # Alternate ordering so interpreter/database warm-up does not always favor one side.
            for mode in ("baseline", "optimized") if repeat % 2 == 0 else ("optimized", "baseline"):
                seed_application(redis, endpoint_count)
                with ExitStack() as stack:
                    if mode == "baseline":
                        stack.enter_context(original_implementation(revision))
                    result, coverage = measured_run(handler, redis, pages)
                if expected_coverage is None:
                    expected_coverage = coverage
                assert coverage == expected_coverage, f"Discovery coverage changed in {mode} repeat {repeat}"
                results[mode].append(result)
    finally:
        logging.disable(old_logging_disable)
    medians = {mode: statistics.median(run["seconds"] for run in runs) for mode, runs in results.items()}
    report = {
        "baseline_ref": revision,
        "pages": pages,
        "seeded_endpoints": endpoint_count,
        "repeats": repeats,
        "median_seconds": medians,
        "median_reduction_percent": 100 * (1 - medians["optimized"] / medians["baseline"]),
        "all_seven_model_identity_sets_equal": True,
        "limitations": "Synthetic fixed input; serial local query execution; real ORM and JSON; FakeRedis and mocked ES; expiry isolation matches fixture; no production latency claim.",
        "runs": results,
    }
    output = os.environ.get("APM_DISCOVERY_BENCHMARK_OUTPUT")
    if output:
        Path(output).write_text(json.dumps(report, indent=2) + "\n")
    print("DISCOVERY_CACHE_BENCHMARK=" + json.dumps(report, sort_keys=True))
