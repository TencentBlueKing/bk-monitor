"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import hashlib
import json
import logging

from django.conf import settings
from redis.exceptions import WatchError

from metadata import config
from metadata.utils import consul_tools
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


class FeatureFlagSourceMissingError(RuntimeError):
    """Consul 中没有可迁移的 Feature Flag 快照。"""


class FeatureFlagRedisSync:
    """将 Consul 中的 Feature Flag 快照一次性迁移给 Unify Query 的 Redis Provider。"""

    CONSUL_SOURCE_PATH = f"{config.MIGRATION_CONSUL_PATH}/unify-query/data/feature_flag"
    REDIS_TARGET_KEY = f"{settings.BACKEND_APP_CODE}:unify-query:data:feature_flag"
    REDIS_CHANNEL = f"{REDIS_TARGET_KEY}:feature_flag_channel"
    REDIS_MIGRATION_MARKER_KEY = f"{REDIS_TARGET_KEY}:consul_migration_done"

    @classmethod
    def sync_from_consul(cls):
        """读取 Consul 全量快照并一次性写入 UQ Redis Key。

        Consul key 缺失不是一个空快照：迁移期间必须保留 Redis 中已有的
        快照，避免误删后让 unify-query 回退到代码默认开关值。
        """
        _, consul_data = consul_tools.HashConsul().get(cls.CONSUL_SOURCE_PATH)
        snapshot = cls._load_snapshot(consul_data)
        redis_client = RedisTools().client
        payload = json.dumps(snapshot, sort_keys=True)
        payload_digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        migrated = cls._migrate_once(redis_client, payload, payload_digest)

        logger.info(
            "feature flag config %s, consul_key=%s, redis_key=%s, flag_count=%s",
            "migrated from consul to redis" if migrated else "migration already completed; skip",
            cls.CONSUL_SOURCE_PATH,
            cls.REDIS_TARGET_KEY,
            len(snapshot),
        )
        return snapshot

    @classmethod
    def _migrate_once(cls, redis_client, payload: str, payload_digest: str) -> bool:
        """在 Redis 中原子地完成一次迁移；重复调用不再写入或发布。"""
        with redis_client.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(cls.REDIS_MIGRATION_MARKER_KEY, cls.REDIS_TARGET_KEY)
                    marker = cls._decode_redis_value(pipe.get(cls.REDIS_MIGRATION_MARKER_KEY))
                    current_value = cls._decode_redis_value(pipe.get(cls.REDIS_TARGET_KEY))

                    if marker is not None:
                        pipe.unwatch()
                        if marker != payload_digest:
                            raise RuntimeError("feature flag migration already completed with a different snapshot")
                        if not cls._same_snapshot(current_value, payload):
                            raise RuntimeError("feature flag migration marker exists but Redis snapshot does not match")
                        return False

                    # 目标值可能已经由人工迁移写入；只补一次性标记，避免重复 SET/PUBLISH。
                    if cls._same_snapshot(current_value, payload):
                        pipe.multi()
                        pipe.set(cls.REDIS_MIGRATION_MARKER_KEY, payload_digest)
                        results = pipe.execute()
                        if not results or not results[0]:
                            raise RuntimeError("set feature flag migration marker failed")
                        return False

                    pipe.multi()
                    pipe.set(cls.REDIS_TARGET_KEY, payload)
                    pipe.publish(cls.REDIS_CHANNEL, payload)
                    pipe.set(cls.REDIS_MIGRATION_MARKER_KEY, payload_digest)
                    results = pipe.execute()
                    if not results or not results[0]:
                        raise RuntimeError("set feature flag config to redis failed")
                    if len(results) < 3 or not results[2]:
                        raise RuntimeError("set feature flag migration marker failed")
                    return True
                except WatchError:
                    # 另一个 metadata 实例完成迁移后，重新读取标记并跳过。
                    continue

    @staticmethod
    def _decode_redis_value(value):
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value

    @staticmethod
    def _same_snapshot(current_value, payload: str) -> bool:
        if not isinstance(current_value, str):
            return False
        try:
            return json.dumps(json.loads(current_value), sort_keys=True) == payload
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _load_snapshot(consul_data):
        """校验 Consul 快照；缺失快照直接失败且不修改 Redis。"""
        if not consul_data or consul_data.get("Value") in (None, "", b""):
            raise FeatureFlagSourceMissingError(
                f"feature flag consul snapshot is missing: {FeatureFlagRedisSync.CONSUL_SOURCE_PATH}"
            )

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
