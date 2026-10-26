"""Exercise the real publishers and RedisTools against an in-memory Redis.

Only imports of project services/models are replaced; no database, Celery
worker or deployment Redis is used. Run with pytest --noconftest -c /dev/null.
"""

import ast
import json
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
    RELATION_MULTI_RESOURCE_PATH,
    RELATION_MULTI_RESOURCE_V1BETA3_PATH,
    resolve_relation_query_path,
)
from bkmonitor.utils.graph_relation import get_relation_v1beta3_biz_ids


METADATA_ROOT = Path(__file__).parents[2]


def load_source(path, dependencies):
    tree = ast.parse(path.read_text())
    tree.body = [node for node in tree.body if not isinstance(node, ast.ImportFrom) or node.module == "typing"]
    namespace = {"__name__": __name__, **dependencies}
    exec(compile(tree, str(path), "exec"), namespace)
    return SimpleNamespace(**namespace)


@pytest.fixture
def publication():
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
    space = Mock()
    rollout_module = load_source(
        METADATA_ROOT / "utils" / "relation_rollout.py",
        {"Space": space, "NAMESPACE_ALL": "__all__", "get_relation_v1beta3_biz_ids": get_relation_v1beta3_biz_ids},
    )
    dependencies = {
        "RedisTools": redis_module.RedisTools,
        "NAMESPACE_ALL": "__all__",
        "should_publish_relation_definition": rollout_module.should_publish_relation_definition,
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
        space=space,
        should_publish=rollout_module.should_publish_relation_definition,
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
@pytest.mark.parametrize("namespace", ["__all__", "bkcc__2", "bkcc__3"])
@pytest.mark.parametrize("query_biz_ids", [[], [2]])
def test_apply_and_delete_follow_query_rollout(publication, kind, namespace, query_biz_ids):
    model = publication.resources if kind == "ResourceDefinition" else publication.relations
    entity = definition(namespace, kind)
    model.objects.get_or_create.return_value = (entity, True)
    model.objects.get.return_value = entity
    model.objects.filter.return_value = [entity]
    model.get_serializer_class.return_value.return_value.validated_data = {}
    handler = publication.handler(model)
    key = f"bkmonitorv3:entity:{kind}"

    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=query_biz_ids):
        result = handler.apply({"namespace": namespace, "name": "pod"}, {})
        assert result["metadata"]["name"] == "pod"
        enabled = namespace == "__all__" or (namespace == "bkcc__2" and 2 in query_biz_ids)
        cached = publication.redis.hget(key, namespace)
        assert (cached is not None) == enabled
        if cached:
            assert json.loads(cached)["pod"]["generation"] == 1
        model.objects.get_or_create.assert_called_once()

        entity.to_redis_json.return_value = {"name": "pod", "generation": 2}
        with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[]):
            handler.apply({"namespace": namespace, "name": "pod"}, {})
            cached = publication.redis.hget(key, namespace)
            if namespace == "__all__":
                assert json.loads(cached)["pod"]["generation"] == 2
            else:
                assert cached is None
            model.objects.filter.return_value = []
            handler.delete(namespace, "pod")
        entity.delete.assert_called_once()
        assert publication.redis.hget(key, namespace) is None

        expected_path = RELATION_MULTI_RESOURCE_V1BETA3_PATH if 2 in query_biz_ids else RELATION_MULTI_RESOURCE_PATH
        assert (
            resolve_relation_query_path(RELATION_MULTI_RESOURCE_PATH, RELATION_MULTI_RESOURCE_V1BETA3_PATH, 2)
            == expected_path
        )


@pytest.mark.parametrize("query_biz_ids", [[], [2]])
@pytest.mark.parametrize("legacy_biz_ids", [[], [2]])
def test_periodic_refresh_follows_query_rollout_and_notifies_deletions(
    publication, monkeypatch, query_biz_ids, legacy_biz_ids
):
    for model in (publication.resources, publication.relations):
        kind = model.get_kind()
        key = f"bkmonitorv3:entity:{kind}"
        model.objects.all.return_value = [definition(ns, kind) for ns in ("__all__", "bkcc__2", "bkcc__3")]
        for namespace in ("__all__", "bkcc__2", "bkcc__3", "bkcc__4", "bkcc__5"):
            publication.redis.hset(key, namespace, "previous-version")

    delete_spy = Mock(wraps=publication.tools.hdel)
    monkeypatch.setattr(publication.tools, "hdel", delete_spy)
    with publication.redis.pubsub() as subscriber:
        channels = [
            f"bkmonitorv3:entity:{model.get_kind()}:channel" for model in (publication.resources, publication.relations)
        ]
        subscriber.subscribe(*channels)
        for _ in channels:
            subscriber.get_message()
        with override_settings(
            RELATION_V1BETA3_BIZ_ID_WHITE_LIST=query_biz_ids,
            GRAPH_RELATION_V4_BIZ_ID_WHITE_LIST=legacy_biz_ids,
        ):
            publication.refresh()
        messages = []
        while message := subscriber.get_message(ignore_subscribe_messages=True):
            messages.append(json.loads(message["data"]))

    expected_namespaces = {"__all__"}
    if 2 in query_biz_ids:
        expected_namespaces.add("bkcc__2")
    stale_namespaces = {"__all__", "bkcc__2", "bkcc__3", "bkcc__4", "bkcc__5"} - expected_namespaces

    # Byte-valued Redis fields must not make enabled DB namespaces appear stale.
    assert delete_spy.call_count == 2
    for call in delete_spy.call_args_list:
        assert set(call.args[1]) == stale_namespaces
    for model in (publication.resources, publication.relations):
        kind = model.get_kind()
        key = f"bkmonitorv3:entity:{kind}"
        assert set(publication.tools.hkeys(key)) == {namespace.encode() for namespace in expected_namespaces}
        for namespace in expected_namespaces:
            assert json.loads(publication.redis.hget(key, namespace))["pod"]["generation"] == 1
        assert {message["namespace"] for message in messages if message["kind"] == kind} == {
            "__all__",
            "bkcc__2",
            "bkcc__3",
            "bkcc__4",
            "bkcc__5",
        }


@pytest.mark.parametrize("biz_ids", [[], [2]])
def test_empty_redis_restores_only_enabled_definitions(publication, biz_ids):
    publication.resources.objects.all.return_value = [definition("__all__"), definition("bkcc__2")]
    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=biz_ids):
        publication.refresh()
    expected = {b"__all__", b"bkcc__2"} if biz_ids else {b"__all__"}
    assert set(publication.tools.hkeys("bkmonitorv3:entity:ResourceDefinition")) == expected


def test_non_bkcc_space_uses_its_business_id(publication):
    publication.space.objects.get_biz_id_by_space.return_value = -7
    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[-7]):
        assert publication.should_publish("bkci__pipeline") is True
    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[]):
        assert publication.should_publish("bkci__pipeline") is False
    publication.space.objects.get_biz_id_by_space.assert_called_with("bkci", "pipeline")
