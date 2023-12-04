# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import datetime
from typing import Dict

import pytz

from alarm_backends.core.cache.base import CacheManager
from bkmonitor.action.serializers import ActionConfigDetailSlz, ActionPluginSlz
from bkmonitor.models import ActionConfig, ActionPlugin
from bkmonitor.utils import extended_json
from constants.action import DEFAULT_NOTICE_ID, DEFAULT_NOTICE_INTERVAL


class ActionConfigCacheManager(CacheManager):
    """
    处理套餐缓存
    """

    # 处理套餐的缓存key
    CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".action_config.{cache_type}_{cache_id}"

    PLUGIN_CACHE_KEY = CacheManager.CACHE_KEY_PREFIX + ".action_plugin_{cache_id}"

    class CacheType:
        CONFIG_ID = "config_id"
        BK_BIZ_ID = "bk_biz_id"

    @staticmethod
    def get_default_notice_config():
        """
        默认的告警通知配置
        :return:
        """
        return {
            "execute_config": {
                "template_detail": {
                    "interval_notify_mode": "standard",  # 间隔模式
                    "notify_interval": DEFAULT_NOTICE_INTERVAL,  # 通知间隔
                }
            },
            "plugin_id": 1,
            "plugin_type": "notice",
            "is_enabled": True,
            "bk_biz_id": 0,
            "name": "默认告警通知",
            "id": DEFAULT_NOTICE_ID,
        }

    @classmethod
    def get_action_plugin_by_id(cls, plugin_id: int) -> Dict:
        """
        从缓存中获取策略详情
        """
        return extended_json.loads(cls.cache.get(cls.PLUGIN_CACHE_KEY.format(cache_id=plugin_id)) or "{}")

    @classmethod
    def get_action_config_by_id(cls, config_id: int) -> Dict:
        """
        从缓存中获取策略详情
        """
        if config_id == DEFAULT_NOTICE_ID:
            return cls.get_default_notice_config()

        return extended_json.loads(
            cls.cache.get(cls.CACHE_KEY_TEMPLATE.format(cache_type=cls.CacheType.CONFIG_ID, cache_id=config_id)) or "{}"
        )

    @classmethod
    def refresh(cls, minutes=None):
        pipeline = cls.cache.pipeline()
        action_plugins = ActionPluginSlz(instance=ActionPlugin.objects.all(), many=True).data
        for action_plugin in action_plugins:
            # 插件信息缓存
            pipeline.set(
                cls.PLUGIN_CACHE_KEY.format(cache_id=action_plugin["id"]),
                extended_json.dumps(action_plugin),
                cls.CACHE_TIMEOUT,
            )
        deleted_plugins = set(ActionPlugin.origin_objects.filter(is_deleted=True).values_list("id", flat=True))
        for deleted_plugin_id in deleted_plugins:
            pipeline.delete(cls.PLUGIN_CACHE_KEY.format(cache_id=deleted_plugin_id))

        deleted_configs = []
        updated_configs = []
        if minutes:
            # 如果有带时间，通过原生manager查找出来
            all_configs = ActionConfig.origin_objects.filter(
                update_time__gte=datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(minutes=minutes)
            )
            for config in all_configs:
                if config.is_deleted:
                    # 如果被删除的，加入到删除列表中
                    deleted_configs.append(config.id)
                    continue
                else:
                    updated_configs.append(config)
        else:
            updated_configs = ActionConfig.objects.all()

        action_configs = ActionConfigDetailSlz(instance=updated_configs, many=True).data

        for action_config in action_configs:
            pipeline.set(
                cls.CACHE_KEY_TEMPLATE.format(cache_type=cls.CacheType.CONFIG_ID, cache_id=action_config["id"]),
                extended_json.dumps(action_config),
                cls.CACHE_TIMEOUT,
            )

        for deleted_config_id in deleted_configs:
            pipeline.delete(
                cls.CACHE_KEY_TEMPLATE.format(cache_type=cls.CacheType.CONFIG_ID, cache_id=deleted_config_id)
            )
        pipeline.execute()


def refresh_total():
    """
    刷新全部
    """
    ActionConfigCacheManager.refresh()


def refresh_latest_5_minutes():
    """
    刷新全部
    """
    ActionConfigCacheManager.refresh(minutes=5)
