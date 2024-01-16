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
from core.drf_resource import api
from core.errors.api import BKAPIError
from metadata.models import TimeSeriesGroup


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
        """
        protocol = cls.cache.get(cls.format_key(bk_data_id))
        if not protocol:
            try:
                ts_group = TimeSeriesGroup.objects.get(bk_data_id=bk_data_id)
            except TimeSeriesGroup.DoesNotExist:
                return None
            try:
                ts_info = api.metadata.custom_time_series_detail(
                    time_series_group_id=ts_group.time_series_group_id, bk_biz_id=ts_group.bk_biz_id, model_only=True
                )
                protocol = ts_info["protocol"]
                cls.set(bk_data_id, protocol)
            except BKAPIError:
                protocol = "json"

        return protocol

    @classmethod
    def set(cls, bk_data_id, protocol):
        cls.cache.set(cls.format_key(bk_data_id), protocol)
