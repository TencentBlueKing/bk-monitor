"""Exercise the real publishers and RedisTools against an in-memory Redis.

Only imports of project services/models are replaced; no database, Celery
worker or deployment Redis is used. Run with pytest --noconftest -c /dev/null.
"""

import ast
import json
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import fakeredis
import pytest
from django.conf import settings
from django.test import override_settings
from rest_framework import serializers

if not settings.configured:
    settings.configure(REST_FRAMEWORK={})

from api.unify_query.relation_routing import (
    resolve_relation_query_path,
)
from bkmonitor.utils import graph_relation
from bkmonitor.utils.graph_relation import RELATION_SCHEMA_READY_KEY, get_relation_v1beta3_biz_ids


METADATA_ROOT = Path(__file__).parents[2]


def load_source(path, dependencies):
    tree = ast.parse(path.read_text())
    tree.body = [node for node in tree.body if not isinstance(node, ast.ImportFrom) or node.module == "typing"]
    namespace = {"__name__": __name__, **dependencies}
    exec(compile(tree, str(path), "exec"), namespace)
    return SimpleNamespace(**namespace)


@pytest.fixture
def publication(monkeypatch):
    redis = fakeredis.FakeRedis(decode_responses=False)
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
    dependencies = {"RedisTools": redis_module.RedisTools, "NAMESPACE_ALL": "__all__"}
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
            "RELATION_SCHEMA_READY_KEY": RELATION_SCHEMA_READY_KEY,
            "TASK_FINISHED_FAILURE": "failure",
            "TASK_STARTED": "started",
            "TASK_FINISHED_SUCCESS": "success",
            "get_relation_v1beta3_biz_ids": get_relation_v1beta3_biz_ids,
        },
    )
    yield SimpleNamespace(
        redis=redis,
        tools=redis_module.RedisTools,
        resources=resources,
        relations=relations,
        handler=handler_module.EntityHandler,
        refresh=task_module.refresh_entity_definition_to_redis,
    )
    redis.close()


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


def test_activation_waits_for_complete_publication_and_rollback_retains_legacy(publication):
    populate(publication)
    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[]):
        assert publication.refresh() is True
    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[2]):
        assert (
            resolve_relation_query_path("legacy", "v1beta3", graph_relation.get_relation_schema_version(2)) == "legacy"
        )
        assert publication.refresh() is True
        assert (
            resolve_relation_query_path("legacy", "v1beta3", graph_relation.get_relation_schema_version(2)) == "v1beta3"
        )
        assert (
            resolve_relation_query_path("legacy", "v1beta3", graph_relation.get_relation_schema_version(3)) == "legacy"
        )
    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[]):
        assert (
            resolve_relation_query_path("legacy", "v1beta3", graph_relation.get_relation_schema_version(2)) == "legacy"
        )
        assert publication.refresh() is True
    for kind in ("ResourceDefinition", "RelationDefinition"):
        assert set(publication.redis.hkeys(f"bkmonitorv3:entity:{kind}")) == {b"__all__", b"bkcc__2", b"bkcc__3"}


def test_missing_shared_definitions_do_not_enable_rollout(publication):
    populate(publication)
    publication.relations.objects.all.return_value = []
    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[2]):
        assert publication.refresh() is True
        assert (
            resolve_relation_query_path("legacy", "v1beta3", graph_relation.get_relation_schema_version(2)) == "legacy"
        )


def test_preparation_failure_leaves_last_snapshot_and_cannot_enable_new_list(publication):
    populate(publication)
    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[]):
        assert publication.refresh() is True
    previous = publication.redis.hgetall("bkmonitorv3:entity:ResourceDefinition")
    publication.relations.objects.all.side_effect = RuntimeError("DB unavailable")
    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[2]):
        assert publication.refresh() is False
        assert (
            resolve_relation_query_path("legacy", "v1beta3", graph_relation.get_relation_schema_version(2)) == "legacy"
        )
    assert publication.redis.hgetall("bkmonitorv3:entity:ResourceDefinition") == previous


def test_redis_write_failure_never_publishes_ready(publication, monkeypatch):
    populate(publication)
    original_pipeline = publication.redis.pipeline

    # Force a WRONGTYPE after the preflight HKEYS reads but before EXEC. Redis
    # continues executing later commands even when an earlier command fails.
    def pipeline(**kwargs):
        pipe = original_pipeline(**kwargs)
        execute = pipe.execute

        def execute_with_failure():
            publication.redis.delete("bkmonitorv3:entity:RelationDefinition")
            publication.redis.set("bkmonitorv3:entity:RelationDefinition", "wrong-type")
            return execute()

        pipe.execute = execute_with_failure
        return pipe

    monkeypatch.setattr(publication.redis, "pipeline", pipeline)
    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[2]):
        assert publication.refresh() is False
        assert publication.redis.get(RELATION_SCHEMA_READY_KEY) is None
        assert (
            resolve_relation_query_path("legacy", "v1beta3", graph_relation.get_relation_schema_version(2)) == "legacy"
        )


def test_actual_db_deletions_are_removed_and_notified(publication):
    populate(publication)
    for kind in ("ResourceDefinition", "RelationDefinition"):
        publication.redis.hset(f"bkmonitorv3:entity:{kind}", "bkcc__deleted", "{}")
    with publication.redis.pubsub() as subscription:
        channel = "bkmonitorv3:entity:ResourceDefinition:channel"
        subscription.subscribe(channel)
        subscription.get_message()
        with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[]):
            assert publication.refresh() is True
        messages = []
        while message := subscription.get_message(ignore_subscribe_messages=True):
            messages.append(json.loads(message["data"]))
        assert {message["namespace"] for message in messages} == {"__all__", "bkcc__2", "bkcc__3", "bkcc__deleted"}
    assert publication.redis.hget("bkmonitorv3:entity:ResourceDefinition", "bkcc__deleted") is None
