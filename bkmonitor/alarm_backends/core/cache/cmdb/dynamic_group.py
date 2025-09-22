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

from django.conf import settings

from alarm_backends.core.cache.cmdb.base import CMDBCacheManager, RefreshByBizMixin
from api.cmdb.define import Module
from core.drf_resource import api


class DynamicGroupManager(CMDBCacheManager):
    """
    CMDB 模块缓存
    """

    type = "dynamic_group"
    CACHE_KEY = "{prefix}.cmdb.dynamic_group".format(prefix=CMDBCacheManager.CACHE_KEY_PREFIX)

    @classmethod
    def key_to_internal_value(cls, dynamic_group_id: str):
        return dynamic_group_id

    @classmethod
    def key_to_representation(cls, dynamic_group_id: str):
        """
        取出key时进行转化
        """
        return dynamic_group_id

    @classmethod
    def deserialize(cls, string):
        if not string:
            return None

        return json.loads(string)
