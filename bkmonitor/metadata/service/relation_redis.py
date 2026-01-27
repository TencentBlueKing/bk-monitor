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

from opentelemetry import trace

from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")
tracer = trace.get_tracer(__name__)

# Redis Key 前缀
REDIS_KEY_PREFIX = "bkmonitorv3:relation"


def get_redis_key(kind: str) -> str:
    """获取 Redis Key"""
    return f"{REDIS_KEY_PREFIX}:{kind}"


def get_redis_channel(kind: str) -> str:
    """获取 Redis Pub/Sub Channel"""
    return f"{REDIS_KEY_PREFIX}:{kind}:channel"


def push_and_publish_entity(kind: str, namespace: str, name: str, data: dict):
    """
    推送并发布实体数据到 Redis

    Args:
        kind: 实体类型 (如 CustomRelationStatus, ResourceDefinition 等)
        namespace: 命名空间
        name: 资源名称
        data: 实体数据 (to_json() 的结果)
    """
    with tracer.start_as_current_span("push_and_publish_entity") as span:
        span.set_attribute("entity.kind", kind)
        span.set_attribute("entity.namespace", namespace)
        span.set_attribute("entity.name", name)

        redis_key = get_redis_key(kind)
        redis_channel = get_redis_channel(kind)
        field = f"{namespace}:{name}"

        # 1. 组装数据
        redis_value = {field: json.dumps(data)}
        span.set_attribute("redis.key", redis_key)
        span.set_attribute("redis.field", field)

        # 2. 写入 Redis
        RedisTools.hmset_to_redis(redis_key, redis_value)

        # 3. 发布变更通知
        RedisTools.publish(redis_channel, [field])
        span.set_attribute("redis.channel", redis_channel)

        logger.info("push and publish entity, kind: %s, namespace: %s, name: %s", kind, namespace, name)
