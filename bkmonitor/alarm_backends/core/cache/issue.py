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
from typing import Optional

from alarm_backends.core.storage.redis import Cache

logger = logging.getLogger("alarm_backends")

_CACHE_CLIENT = None


def _get_cache_client():
    global _CACHE_CLIENT
    if _CACHE_CLIENT is None:
        _CACHE_CLIENT = Cache("service")
    return _CACHE_CLIENT


class StrategyIssueConfigCache:
    """StrategyIssueConfig 按 strategy_id 缓存，TTL 5min

    读路径：Redis 命中 → 反序列化返回；未命中 → MySQL 查询 → 写缓存 → 返回。
    写路径：StrategyIssueConfig 的 post_save / post_delete 信号触发 invalidate()。
    """

    CACHE_KEY_TPL = "issue.strategy.config.{strategy_id}"
    TTL = 300  # 5min

    @classmethod
    def _make_key(cls, strategy_id: int) -> str:
        from alarm_backends.core.cache.key import KEY_PREFIX

        return f"{KEY_PREFIX}.{cls.CACHE_KEY_TPL.format(strategy_id=strategy_id)}"

    @classmethod
    def get(cls, strategy_id: int) -> Optional["StrategyIssueConfig"]:  # noqa: F821
        """获取配置，优先走缓存，缺失则降级到 MySQL"""
        from bkmonitor.models.issue import StrategyIssueConfig

        client = _get_cache_client()
        key = cls._make_key(strategy_id)
        cached = client.get(key)
        if cached:
            try:
                data = json.loads(cached)
                # 用缓存数据构造临时对象（不触发 DB 查询）
                config = StrategyIssueConfig.__new__(StrategyIssueConfig)
                for field_name, value in data.items():
                    setattr(config, field_name, value)
                return config
            except Exception as e:
                logger.warning("StrategyIssueConfigCache: deserialize failed, key=%s, err=%s", key, e)

        # 缓存未命中，降级到 MySQL
        try:
            config = StrategyIssueConfig.objects.get(strategy_id=strategy_id)
            cls._write(strategy_id, config)
            return config
        except StrategyIssueConfig.DoesNotExist:
            # 写空值标记，防止缓存穿透（TTL 较短）
            client.set(key, json.dumps(None), ex=60)
            return None
        except Exception as e:
            logger.warning(
                "StrategyIssueConfigCache: mysql query failed, strategy_id=%s, err=%s",
                strategy_id,
                e,
            )
            return None

    @classmethod
    def _write(cls, strategy_id: int, config: "StrategyIssueConfig") -> None:  # noqa: F821
        """将配置对象序列化写入 Redis"""
        client = _get_cache_client()
        key = cls._make_key(strategy_id)
        data = {
            "id": config.id,
            "strategy_id": config.strategy_id,
            "bk_biz_id": config.bk_biz_id,
            "is_enabled": config.is_enabled,
            "aggregate_dimensions": config.aggregate_dimensions,
            "conditions": config.conditions,
            "alert_levels": config.alert_levels,
        }
        client.set(key, json.dumps(data), ex=cls.TTL)

    @classmethod
    def invalidate(cls, strategy_id: int) -> None:
        """主动失效指定 strategy_id 的缓存"""
        client = _get_cache_client()
        key = cls._make_key(strategy_id)
        client.delete(key)
        logger.debug("StrategyIssueConfigCache: invalidated key=%s", key)
