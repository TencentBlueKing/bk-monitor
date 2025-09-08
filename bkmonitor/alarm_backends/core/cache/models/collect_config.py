# -*- coding: utf-8 -*-
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

from alarm_backends.core.cache.base import CacheManager
from core.drf_resource import api


class CollectConfigCacheManager(CacheManager):
    """
    采集配置缓存
    """

    # 缓存key
    CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".collect_config_{config_id}"

    @classmethod
    def format_key(cls, config_id):
        return cls.CACHE_KEY_TEMPLATE.format(config_id=config_id)

    @classmethod
    def get(cls, config_id):
        """
        根据配置ID获取采集配置
        :param config_id:
        :return: dict
        {
            "name": "Mysql配置"
        }
        """
        config = cls.cache.get(cls.format_key(config_id))
        if not config:
            return None
        return json.loads(config)

    @classmethod
    def _get_configs(cls):
        return api.monitor.collect_config_list()

    @classmethod
    def refresh(cls):
        configs = cls._get_configs()
        pipeline = cls.cache.pipeline()
        for config in configs:
            pipeline.set(cls.format_key(config["id"]), json.dumps(config), cls.CACHE_TIMEOUT)
        pipeline.execute()

        cls.logger.info("refresh collect config data finished, amount:{}".format(len(configs)))


def main():
    CollectConfigCacheManager.refresh()
