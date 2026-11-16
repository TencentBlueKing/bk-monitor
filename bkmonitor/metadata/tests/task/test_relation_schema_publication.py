"""Exercise publishers and RedisTools against fakeredis and a real redis-server.

Only imports of project services/models are replaced; no database, Celery
worker or deployment Redis is used. Real Redis is started on a temporary Unix socket. Run with pytest --noconftest -c /dev/null.
"""

import ast
import json
import shutil
import subprocess
import time
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import fakeredis
import pytest
from redis import Redis
from django.conf import settings
from django.test import override_settings
from redis.exceptions import ConnectionError
from rest_framework import serializers

if not settings.configured:
    settings.configure(REST_FRAMEWORK={})

METADATA_ROOT = Path(__file__).parents[2]


def load_source(path, dependencies):
    tree = ast.parse(path.read_text())
    tree.body = [node for node in tree.body if not isinstance(node, ast.ImportFrom) or node.module == "typing"]
    namespace = {"__name__": __name__, **dependencies}
    exec(compile(tree, str(path), "exec"), namespace)
    return SimpleNamespace(**namespace)


@pytest.fixture(scope="session")
def redis_server(tmp_path_factory):
    binary = shutil.which("redis-server")
    if binary is None:
        pytest.skip("real Redis tests require redis-server")
    socket = str(tmp_path_factory.mktemp("relation-redis") / "redis.sock")
    process = subprocess.Popen(
        [binary, "--port", "0", "--unixsocket", socket, "--save", "", "--appendonly", "no"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    client = Redis(unix_socket_path=socket)
    try:
        deadline = time.monotonic() + 5
        while True:
            try:
                client.ping()
                break
            except ConnectionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.01)
        yield client
    finally:
        client.close()
        process.terminate()
        process.wait(timeout=5)


@pytest.fixture(params=["fake", "real"])
def redis_client(request):
    if request.param == "real":
        client = request.getfixturevalue("redis_server")
        client.flushdb()
        yield client
        client.flushdb()
    else:
        with fakeredis.FakeRedis(decode_responses=False) as client:
            yield client


@pytest.fixture
def publication(monkeypatch, redis_client):
    redis = redis_client
    redis_module = load_source(
        METADATA_ROOT / "utils" / "redis_tools.py",
        {"settings": settings, "RedisClient": SimpleNamespace(from_envs=lambda **kwargs: redis)},
    )
    resources = Mock()
    resources.get_kind.return_value = "ResourceDefinition"
    resources.objects.all.return_value = []
    relations = Mock()
    relations.get_kind.return_value = "RelationDefinition"
    relations.objects.all.return_value = []
    monkeypatch.setitem(sys.modules, "metadata.utils.redis_tools", redis_module)
    dependencies = {
        "RedisTools": redis_module.RedisTools,
        "NAMESPACE_ALL": "__all__",
    }
    handler_module = load_source(
        METADATA_ROOT / "resources" / "entity_relation.py",
        {
            **dependencies,
            "apps": Mock(),
            "transaction": SimpleNamespace(atomic=nullcontext),
            "_": lambda value: value,
            "serializers": serializers,
            "Resource": object,
            "EntityMeta": object,
            "EntityNotFoundError": Exception,
            "UnsupportedKindError": Exception,
        },
    )
    task_module = load_source(
        METADATA_ROOT / "task" / "entity_relation.py",
        {
            **dependencies,
            "share_lock": lambda **kwargs: lambda function: function,
            "metrics": Mock(),
            "ResourceDefinition": resources,
            "RelationDefinition": relations,
            "ENTITY_REDIS_KEY_PREFIX": handler_module.ENTITY_REDIS_KEY_PREFIX,
            "ENTITY_REDIS_CHANNEL_SUFFIX": handler_module.ENTITY_REDIS_CHANNEL_SUFFIX,
            "TASK_FINISHED_FAILURE": "failure",
            "TASK_STARTED": "started",
            "TASK_FINISHED_SUCCESS": "success",
        },
    )
    yield SimpleNamespace(
        redis=redis,
        tools=redis_module.RedisTools,
        resources=resources,
        relations=relations,
        handler=handler_module.EntityHandler,
        refresh=task_module.refresh_entity_definition_to_redis,
        task=task_module,
    )


def definition(namespace, kind="ResourceDefinition", name="pod"):
    entity = Mock(namespace=namespace, labels={}, generation=1)
    entity.name = name
    entity.get_kind.return_value = kind
    entity.to_redis_json.return_value = {"name": name, "generation": 1}
    entity.get_spec.return_value = {}
    entity.to_json.return_value = {"metadata": {"namespace": namespace, "name": name}}
    return entity


@pytest.mark.parametrize("kind", ["ResourceDefinition", "RelationDefinition"])
@pytest.mark.parametrize("namespace", ["__all__", "bkcc__2", "bkcc__3", "bkci__pipeline"])
def test_crud_keeps_definitions_outside_rollout(publication, kind, namespace):
    model = publication.resources if kind == "ResourceDefinition" else publication.relations
    entity = definition(namespace, kind)
    model.objects.get_or_create.return_value = (entity, True)
    model.objects.get.return_value = entity
    model.objects.filter.return_value = [entity]
    model.get_serializer_class.return_value.return_value.validated_data = {}
    handler = publication.handler(model)
    key = f"bkmonitorv3:entity:{kind}"
    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[]):
        handler.apply({"namespace": namespace, "name": "pod"}, {})
        assert json.loads(publication.redis.hget(key, namespace))["pod"]["generation"] == 1
        model.objects.filter.return_value = []
        handler.delete(namespace, "pod")
        assert publication.redis.hget(key, namespace) is None


def populate(publication):
    for model in (publication.resources, publication.relations):
        kind = model.get_kind()
        model.objects.all.return_value = [definition(ns, kind) for ns in ("__all__", "bkcc__2", "bkcc__3")]


@pytest.mark.parametrize("query_biz_ids", [[], [2]])
def test_periodic_publication_keeps_all_definitions_independent_of_query_list(publication, query_biz_ids):
    populate(publication)
    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=query_biz_ids):
        assert publication.refresh() is True

    for kind in ("ResourceDefinition", "RelationDefinition"):
        values = publication.redis.hgetall(f"bkmonitorv3:entity:{kind}")
        assert set(values) == {b"__all__", b"bkcc__2", b"bkcc__3"}
        assert all(json.loads(value)["pod"]["generation"] == 1 for value in values.values())
    counter = publication.task.metrics.METADATA_CRON_TASK_STATUS_TOTAL
    assert [call.kwargs["status"] for call in counter.labels.call_args_list] == ["started", "success"]


def test_periodic_publication_restores_lost_cache(publication):
    populate(publication)
    assert publication.refresh() is True
    expected = publication.redis.hgetall("bkmonitorv3:entity:ResourceDefinition")
    publication.redis.flushdb()

    assert publication.refresh() is True

    assert publication.redis.hgetall("bkmonitorv3:entity:ResourceDefinition") == expected
    assert publication.redis.hgetall("bkmonitorv3:entity:RelationDefinition") == expected


@pytest.mark.parametrize("failure", ["db", "hkeys", "hset", "hdel", "publish"])
def test_failed_kind_is_reported_and_other_kind_still_refreshes(publication, monkeypatch, failure):
    populate(publication)
    resource_key = "bkmonitorv3:entity:ResourceDefinition"
    publication.redis.hset(resource_key, "deleted", "{}")
    if failure == "db":
        publication.resources.objects.all.side_effect = RuntimeError("database unavailable")
    else:
        original = getattr(publication.redis, failure)

        def fail_resource(key, *args, **kwargs):
            if key.startswith(resource_key):
                raise ConnectionError("Redis unavailable")
            return original(key, *args, **kwargs)

        monkeypatch.setattr(publication.redis, failure, fail_resource)

    assert publication.refresh() is False

    assert set(publication.redis.hgetall("bkmonitorv3:entity:RelationDefinition")) == {
        b"__all__",
        b"bkcc__2",
        b"bkcc__3",
    }
    counter = publication.task.metrics.METADATA_CRON_TASK_STATUS_TOTAL
    assert [call.kwargs["status"] for call in counter.labels.call_args_list] == ["started", "failure"]
    publication.task.metrics.METADATA_CRON_TASK_COST_SECONDS.labels.return_value.observe.assert_called_once()
    publication.task.metrics.report_all.assert_called_once()


@pytest.mark.parametrize("kind", ["ResourceDefinition", "RelationDefinition"])
@pytest.mark.parametrize("delete_all", [False, True])
def test_deleted_namespaces_are_removed_and_notified(publication, kind, delete_all):
    populate(publication)
    model = publication.resources if kind == "ResourceDefinition" else publication.relations
    if delete_all:
        model.objects.all.return_value = []
    key = f"bkmonitorv3:entity:{kind}"
    publication.redis.hset(key, "bkcc__deleted", "{}")
    expected = {"bkcc__deleted"} if delete_all else {"__all__", "bkcc__2", "bkcc__3", "bkcc__deleted"}
    with publication.redis.pubsub() as subscription:
        subscription.subscribe(f"{key}:channel")
        assert subscription.get_message(timeout=5)["type"] == "subscribe"

        assert publication.refresh() is True

        messages = []
        deadline = time.monotonic() + 5
        while len(messages) < len(expected) and time.monotonic() < deadline:
            message = subscription.get_message(ignore_subscribe_messages=True, timeout=0.05)
            if message is not None:
                messages.append(json.loads(message["data"]))
        assert {message["namespace"] for message in messages} == expected
        assert all(message["kind"] == kind for message in messages)
    assert publication.redis.hget(key, "bkcc__deleted") is None
    if delete_all:
        assert publication.redis.hgetall(key) == {}
