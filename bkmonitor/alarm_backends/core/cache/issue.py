"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from alarm_backends.core.cache.base import CacheManager
from bkmonitor.utils import extended_json

logger = logging.getLogger("fta_action.issue")

STRATEGY_ISSUE_CONFIG_CACHE_TTL = 300


class StrategyIssueConfigCache(CacheManager):
    """StrategyIssueConfig 按 strategy_id 缓存，TTL 5min"""

    CACHE_TIMEOUT = STRATEGY_ISSUE_CONFIG_CACHE_TTL
    CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".issue.strategy_config_{strategy_id}"

    @classmethod
    def _serialize(cls, config) -> dict:
        return {
            "strategy_id": config.strategy_id,
            "bk_biz_id": config.bk_biz_id,
            "is_enabled": config.is_enabled,
            "aggregate_dimensions": config.aggregate_dimensions,
            "conditions": config.conditions,
            "alert_levels": config.alert_levels,
        }

    @classmethod
    def upsert(cls, config):
        cache_key = cls.CACHE_KEY_TEMPLATE.format(strategy_id=config.strategy_id)
        data = cls._serialize(config)
        cls.cache.set(cache_key, extended_json.dumps(data), cls.CACHE_TIMEOUT)
        return data

    @classmethod
    def refresh(cls):
        """全量同步 StrategyIssueConfig 到缓存，并清理已删除配置。"""
        from bkmonitor.models.issue import StrategyIssueConfig

        pipeline = cls.cache.pipeline()

        configs = StrategyIssueConfig.origin_objects.filter(is_deleted=False).values(
            "strategy_id",
            "bk_biz_id",
            "is_enabled",
            "aggregate_dimensions",
            "conditions",
            "alert_levels",
        )
        for config in configs:
            cache_key = cls.CACHE_KEY_TEMPLATE.format(strategy_id=config["strategy_id"])
            pipeline.set(cache_key, extended_json.dumps(config), cls.CACHE_TIMEOUT)

        deleted_strategy_ids = StrategyIssueConfig.origin_objects.filter(is_deleted=True).values_list(
            "strategy_id", flat=True
        )
        for strategy_id in deleted_strategy_ids:
            cache_key = cls.CACHE_KEY_TEMPLATE.format(strategy_id=strategy_id)
            pipeline.delete(cache_key)

        pipeline.execute()

    @classmethod
    def get(cls, strategy_id: int):
        """仅从 Redis 获取配置。"""
        cache_key = cls.CACHE_KEY_TEMPLATE.format(strategy_id=strategy_id)

        cached = cls.cache.get(cache_key)
        if cached:
            try:
                return extended_json.loads(cached)
            except (TypeError, ValueError):
                logger.warning("StrategyIssueConfigCache.get decode failed, strategy_id=%s", strategy_id)
        return None

    @classmethod
    def invalidate(cls, strategy_id: int):
        """配置变更时主动删除缓存"""
        try:
            cache_key = cls.CACHE_KEY_TEMPLATE.format(strategy_id=strategy_id)
            cls.cache.delete(cache_key)
        except Exception:
            logger.warning("StrategyIssueConfigCache.invalidate failed, strategy_id=%s", strategy_id)


def main():
    StrategyIssueConfigCache.refresh()
