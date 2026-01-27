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

from metadata.models import RelationDefinition, ResourceDefinition
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")
tracer = trace.get_tracer(__name__)

# Redis Key 和 Channel 常量
RESOURCE_DEFINITION_KEY = "bkmonitorv3:relation:resource_definition"
RESOURCE_DEFINITION_CHANNEL = "bkmonitorv3:relation:resource_definition:channel"
RELATION_DEFINITION_KEY = "bkmonitorv3:relation:relation_definition"
RELATION_DEFINITION_CHANNEL = "bkmonitorv3:relation:relation_definition:channel"


def push_and_publish_resource_definition(name: str):
    """推送并发布资源定义"""
    with tracer.start_as_current_span("push_and_publish_resource_definition") as span:
        span.set_attribute("resource_definition.name", name)

        try:
            resource_def = ResourceDefinition.objects.get(name=name)
        except ResourceDefinition.DoesNotExist:
            logger.error("resource definition not found: %s", name)
            span.set_attribute("error", True)
            span.set_attribute("error.message", f"resource definition not found: {name}")
            return

        # 1. 组装数据
        redis_value = {name: json.dumps(resource_def.to_json())}
        span.set_attribute("redis.key", RESOURCE_DEFINITION_KEY)
        span.set_attribute("redis.field", name)

        # 2. 写入 Redis
        RedisTools.hmset_to_redis(RESOURCE_DEFINITION_KEY, redis_value)

        # 3. 发布变更通知
        RedisTools.publish(RESOURCE_DEFINITION_CHANNEL, [name])
        span.set_attribute("redis.channel", RESOURCE_DEFINITION_CHANNEL)

        logger.info("push and publish resource definition, name: %s", name)


def push_and_publish_relation_definition(namespace: str, name: str):
    """推送并发布关联定义"""
    with tracer.start_as_current_span("push_and_publish_relation_definition") as span:
        span.set_attribute("relation_definition.namespace", namespace)
        span.set_attribute("relation_definition.name", name)

        try:
            relation_def = RelationDefinition.objects.get(namespace=namespace, name=name)
        except RelationDefinition.DoesNotExist:
            logger.error("relation definition not found: namespace=%s, name=%s", namespace, name)
            span.set_attribute("error", True)
            span.set_attribute("error.message", f"relation definition not found: namespace={namespace}, name={name}")
            return

        # 1. 组装数据
        field = f"{namespace}:{name}"
        redis_value = {field: json.dumps(relation_def.to_json())}
        span.set_attribute("redis.key", RELATION_DEFINITION_KEY)
        span.set_attribute("redis.field", field)

        # 2. 写入 Redis
        RedisTools.hmset_to_redis(RELATION_DEFINITION_KEY, redis_value)

        # 3. 发布变更通知
        RedisTools.publish(RELATION_DEFINITION_CHANNEL, [field])
        span.set_attribute("redis.channel", RELATION_DEFINITION_CHANNEL)

        logger.info("push and publish relation definition, namespace: %s, name: %s", namespace, name)
