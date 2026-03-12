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

from alarm_backends.core.lock.service_lock import share_lock
from core.prometheus import metrics
from metadata.models.entity_relation import NAMESPACE_ALL, RelationDefinition, ResourceDefinition
from metadata.resources.entity_relation import ENTITY_REDIS_KEY_PREFIX, ENTITY_REDIS_CHANNEL_SUFFIX
from metadata.tools.constants import TASK_FINISHED_SUCCESS, TASK_STARTED
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


@share_lock(ttl=3600, identify="metadata_refresh_entity_definition_to_redis")
def refresh_entity_definition_to_redis():
    """
    全量刷新 ResourceDefinition 和 RelationDefinition 到 Redis 的兜底任务。

    当 Redis 数据丢失（Redis 重启、数据过期等）时，定时从 DB 全量重建缓存，
    保证 bmw SchemaProvider 始终能读到最新的资源/关联定义。

    Redis 数据契约（与 EntityHandler._rebuild_redis_cache 保持一致）:
    - Key:     bkmonitorv3:entity:{Kind}
    - Field:   namespace（空 namespace 映射为 __all__）
    - Value:   JSON string of {name: redisJsonData, ...}
    - Channel: {Key}:channel
    - Message: JSON string of {namespace, kind}
    """
    logger.info("refresh_entity_definition_to_redis started")
    start_time = time.time()
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="refresh_entity_definition_to_redis", status=TASK_STARTED, process_target=None
    ).inc()

    for model_class in (ResourceDefinition, RelationDefinition):
        kind = model_class.get_kind()
        redis_key = f"{ENTITY_REDIS_KEY_PREFIX}:{kind}"
        channel = f"{redis_key}{ENTITY_REDIS_CHANNEL_SUFFIX}"

        try:
            # 按 namespace 分组，全量重建每个 namespace 的缓存
            namespace_entities: dict[str, dict] = {}
            for entity in model_class.objects.all():
                ns = entity.namespace or NAMESPACE_ALL
                if ns not in namespace_entities:
                    namespace_entities[ns] = {}
                namespace_entities[ns][entity.name] = entity.to_redis_json()

            if not namespace_entities:
                logger.info("refresh_entity_definition_to_redis: no entities found for kind=%s, skip", kind)
                continue

            for ns, entities in namespace_entities.items():
                RedisTools.hset_to_redis(redis_key, ns, json.dumps(entities))
                msg = json.dumps({"namespace": ns, "kind": kind})
                RedisTools.publish(channel, [msg])

            logger.info(
                "refresh_entity_definition_to_redis: kind=%s, namespace_count=%d, total_entities=%d",
                kind,
                len(namespace_entities),
                sum(len(v) for v in namespace_entities.values()),
            )

        except Exception:  # pylint: disable=broad-except
            logger.exception("refresh_entity_definition_to_redis: failed to refresh kind=%s", kind)

    cost_time = time.time() - start_time
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="refresh_entity_definition_to_redis", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(
        task_name="refresh_entity_definition_to_redis", process_target=None
    ).observe(cost_time)
    metrics.report_all()
    logger.info("refresh_entity_definition_to_redis finished, cost=[%s] seconds", cost_time)
