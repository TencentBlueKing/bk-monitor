"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Dict, Optional

from alarm_backends.core.cache.base import CacheManager
from bkmonitor.utils import extended_json


class StrategyIssueConfigCacheManager(CacheManager):
    """策略 Issue 聚合配置缓存

    按 strategy_id 缓存 StrategyIssueConfig 序列化结果。
    - 读路径：get_config_by_strategy_id()，缓存未命中返回空 dict
    - 写路径：refresh() 全量刷新；invalidate() 单条主动失效
    - 缓存后端：cache-strategy（与 ActionConfigCacheManager 一致）
    """

    CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".strategy_issue_config.{strategy_id}"

    @classmethod
    def get_config_by_strategy_id(cls, strategy_id: int) -> Optional[Dict]:
        """从缓存获取策略 Issue 配置，未命中返回 None"""
        raw = cls.cache.get(cls.CACHE_KEY_TEMPLATE.format(strategy_id=strategy_id))
        if not raw:
            return None
        return extended_json.loads(raw)

    @classmethod
    def invalidate(cls, strategy_id: int) -> None:
        """主动失效单条缓存（由 StrategyIssueConfig post_save/post_delete 信号调用）"""
        cls.cache.delete(cls.CACHE_KEY_TEMPLATE.format(strategy_id=strategy_id))
        cls.logger.debug("StrategyIssueConfigCacheManager: invalidated strategy_id=%s", strategy_id)

    @classmethod
    def refresh(cls, minutes=None):
        """全量（或增量）刷新缓存

        :param minutes: 若提供，则仅刷新最近 N 分钟内更新的记录；否则全量刷新。
        """
        import datetime

        import pytz

        from bkmonitor.models.issue import StrategyIssueConfig

        pipeline = cls.cache.pipeline()

        if minutes:
            updated_configs = StrategyIssueConfig.origin_objects.filter(
                update_time__gte=datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(minutes=minutes)
            )
        else:
            updated_configs = StrategyIssueConfig.objects.filter(is_deleted=False)

        updated_strategy_ids = set()
        for config in updated_configs:
            if config.is_deleted:
                pipeline.delete(cls.CACHE_KEY_TEMPLATE.format(strategy_id=config.strategy_id))
                continue
            data = {
                "id": config.id,
                "strategy_id": config.strategy_id,
                "bk_biz_id": config.bk_biz_id,
                "is_enabled": config.is_enabled,
                "aggregate_dimensions": config.aggregate_dimensions,
                "conditions": config.conditions,
                "alert_levels": config.alert_levels,
            }
            pipeline.set(
                cls.CACHE_KEY_TEMPLATE.format(strategy_id=config.strategy_id),
                extended_json.dumps(data),
                cls.CACHE_TIMEOUT,
            )
            updated_strategy_ids.add(config.strategy_id)

        pipeline.execute()
        cls.logger.info(
            "StrategyIssueConfigCacheManager.refresh: updated %d configs (minutes=%s)",
            len(updated_strategy_ids),
            minutes,
        )


def refresh_total():
    """全量刷新（供 celery beat 调用）"""
    StrategyIssueConfigCacheManager.refresh()


def refresh_latest_5_minutes():
    """增量刷新最近 5 分钟（供 celery beat 高频调用）"""
    StrategyIssueConfigCacheManager.refresh(minutes=5)
