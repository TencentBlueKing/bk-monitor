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

from alarm_backends.core.storage.redis_cluster import RedisProxy

logger = logging.getLogger("fta_action.issue")

STRATEGY_ISSUE_CONFIG_CACHE_TTL = 300
STRATEGY_ISSUE_CONFIG_KEY_TPL = "issue.strategy.config.{strategy_id}"


class StrategyIssueConfigCache:
    """StrategyIssueConfig 按 strategy_id 缓存，TTL 5min"""

    _backend = "service"

    @classmethod
    def _get_client(cls):
        return RedisProxy(cls._backend)

    @classmethod
    def _cache_key(cls, strategy_id: int) -> str:
        return STRATEGY_ISSUE_CONFIG_KEY_TPL.format(strategy_id=strategy_id)

    @classmethod
    def get(cls, strategy_id: int):
        """Redis → MySQL 降级 → 写缓存"""
        client = cls._get_client()
        cache_key = cls._cache_key(strategy_id)

        cached = client.get(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except (json.JSONDecodeError, TypeError):
                pass

        try:
            from bkmonitor.models.issue import StrategyIssueConfig

            config = StrategyIssueConfig.objects.get(strategy_id=strategy_id)
        except Exception:
            return None

        data = {
            "strategy_id": config.strategy_id,
            "bk_biz_id": config.bk_biz_id,
            "is_enabled": config.is_enabled,
            "aggregate_dimensions": config.aggregate_dimensions,
            "conditions": config.conditions,
            "alert_levels": config.alert_levels,
        }
        client.set(cache_key, json.dumps(data), ex=STRATEGY_ISSUE_CONFIG_CACHE_TTL)
        return data

    @classmethod
    def invalidate(cls, strategy_id: int):
        """配置变更时主动删除缓存"""
        try:
            client = cls._get_client()
            client.delete(cls._cache_key(strategy_id))
        except Exception:
            logger.warning("StrategyIssueConfigCache.invalidate failed, strategy_id=%s", strategy_id)
