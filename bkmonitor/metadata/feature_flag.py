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

from django.conf import settings

from metadata import config
from metadata.utils import consul_tools
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


class FeatureFlagRedisSync:
    """将 Consul 中的 Feature Flag 快照同步给 Unify Query 的 Redis Provider。"""

    CONSUL_SOURCE_PATH = f"{config.MIGRATION_CONSUL_PATH}/unify-query/data/feature_flag"
    REDIS_TARGET_KEY = f"{settings.BACKEND_APP_CODE}:unify-query:data:feature_flag"
    REDIS_CHANNEL = f"{REDIS_TARGET_KEY}:feature_flag_channel"

    @classmethod
    def sync_from_consul(cls):
        """读取 Consul 全量快照并更新 UQ Redis Key。"""
        _, consul_data = consul_tools.HashConsul().get(cls.CONSUL_SOURCE_PATH)
        snapshot = cls._load_snapshot(consul_data)
        redis_client = RedisTools().client

        if snapshot:
            if not redis_client.set(cls.REDIS_TARGET_KEY, json.dumps(snapshot)):
                raise RuntimeError("set feature flag config to redis failed")
        else:
            redis_client.delete(cls.REDIS_TARGET_KEY)
        redis_client.publish(cls.REDIS_CHANNEL, json.dumps(snapshot))

        logger.info(
            "feature flag config synced from consul to redis, consul_key=%s, redis_key=%s, flag_count=%s",
            cls.CONSUL_SOURCE_PATH,
            cls.REDIS_TARGET_KEY,
            len(snapshot),
        )

    @staticmethod
    def _load_snapshot(consul_data):
        """校验 Consul 快照；缺失快照以空对象清理 Redis，避免 UQ 保留旧配置。"""
        if consul_data is None:
            return {}

        raw_snapshot = consul_data.get("Value")
        if isinstance(raw_snapshot, bytes):
            raw_snapshot = raw_snapshot.decode("utf-8")
        if not isinstance(raw_snapshot, str):
            raise ValueError("feature flag consul snapshot must be a JSON object")

        try:
            snapshot = json.loads(raw_snapshot)
        except (TypeError, ValueError) as error:
            raise ValueError("feature flag consul snapshot must be valid JSON") from error

        if not isinstance(snapshot, dict):
            raise ValueError("feature flag consul snapshot must be a JSON object")

        return snapshot
