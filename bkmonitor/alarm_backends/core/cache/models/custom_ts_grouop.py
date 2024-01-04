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


from alarm_backends.core.cache.base import CacheManager


class CustomTSGroupCacheManager(CacheManager):
    """
    自定义指标分组缓存[无过期时间]
    """

    # 缓存key
    CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".ts_group{bk_data_id}"

    @classmethod
    def format_key(cls, bk_data_id):
        return cls.CACHE_KEY_TEMPLATE.format(bk_data_id=bk_data_id)

    @classmethod
    def get(cls, bk_data_id):
        """
        根据配置ID获取采集配置
        :param config_id:
        :return: dict
        {
            "name": "Mysql配置"
        }
        """
        protocol = cls.cache.get(cls.format_key(bk_data_id))
        if not protocol:
            return None
        return protocol

    @classmethod
    def refresh_all(cls, protocol_dict):
        data = {}
        for bk_data_id, protocol in protocol_dict.items():
            data[cls.format_key(bk_data_id)] = protocol
        cls.cache.mset(data)
