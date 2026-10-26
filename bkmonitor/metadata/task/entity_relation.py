"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import time
import uuid

from alarm_backends.core.lock.service_lock import share_lock
from bkmonitor.utils.graph_relation import RELATION_SCHEMA_READY_KEY, get_relation_v1beta3_biz_ids
from core.prometheus import metrics
from metadata.models.entity_relation import NAMESPACE_ALL, RelationDefinition, ResourceDefinition
from metadata.resources.entity_relation import ENTITY_REDIS_KEY_PREFIX, ENTITY_REDIS_CHANNEL_SUFFIX
from metadata.tools.constants import TASK_FINISHED_FAILURE, TASK_FINISHED_SUCCESS, TASK_STARTED
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


@share_lock(ttl=3600, identify="metadata_refresh_entity_definition_to_redis")
def refresh_entity_definition_to_redis():
    """Publish both definition kinds atomically, then announce their rollout version.

    All business definitions remain available to the legacy query service.
    Only namespaces removed from DB are deleted. A failed snapshot preparation
    leaves the last published data intact, and cannot enable a new rollout list.
    """
    started = time.time()
    task_name = "refresh_entity_definition_to_redis"
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(task_name=task_name, status=TASK_STARTED, process_target=None).inc()
    succeeded = False
    try:
        enabled_biz_ids = get_relation_v1beta3_biz_ids()
        snapshots = {}
        for model in (ResourceDefinition, RelationDefinition):
            namespaces = {}
            for entity in model.objects.all():
                namespace = entity.namespace or NAMESPACE_ALL
                namespaces.setdefault(namespace, {})[entity.name] = entity.to_redis_json()
            snapshots[model.get_kind()] = namespaces

        client = RedisTools().client
        with client.pipeline(transaction=True) as pipeline:
            pipeline.delete(RELATION_SCHEMA_READY_KEY)
            for kind, namespaces in snapshots.items():
                key = f"{ENTITY_REDIS_KEY_PREFIX}:{kind}"
                channel = f"{key}{ENTITY_REDIS_CHANNEL_SUFFIX}"
                previous = {field.decode() if isinstance(field, bytes) else field for field in client.hkeys(key)}
                stale = previous - namespaces.keys()
                if stale:
                    pipeline.hdel(key, *sorted(stale))
                for namespace, entities in namespaces.items():
                    pipeline.hset(key, namespace, json.dumps(entities))
                for namespace in sorted(previous | namespaces.keys()):
                    pipeline.publish(channel, json.dumps({"namespace": namespace, "kind": kind}))

            pipeline.execute()
        # Announce readiness only after every write succeeds: Redis EXEC does
        # not roll back other commands when one command fails (e.g. WRONGTYPE).
        if all(namespaces.get(NAMESPACE_ALL) for namespaces in snapshots.values()):
            ready = {"biz_ids": sorted(enabled_biz_ids), "version": uuid.uuid4().hex}
            client.set(RELATION_SCHEMA_READY_KEY, json.dumps(ready))
        succeeded = True
    except Exception:  # pylint: disable=broad-except
        logger.exception("refresh_entity_definition_to_redis: publication failed")
    finally:
        metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
            task_name=task_name,
            status=TASK_FINISHED_SUCCESS if succeeded else TASK_FINISHED_FAILURE,
            process_target=None,
        ).inc()
        metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name=task_name, process_target=None).observe(
            time.time() - started
        )
        metrics.report_all()
    return succeeded
