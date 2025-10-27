"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from alarm_backends.core.cache.cmdb.base import CMDBCacheManager, RefreshByBizMixin
from api.cmdb.define import Module
from core.drf_resource import api


class ModuleManager(RefreshByBizMixin, CMDBCacheManager):
    """
    CMDB 模块缓存
    """

    type = "module"
    CACHE_KEY = f"{CMDBCacheManager.CACHE_KEY_PREFIX}.cmdb.module"
    ObjectClass = Module

    @classmethod
    def key_to_internal_value(cls, bk_module_id):
        return str(bk_module_id)

    @classmethod
    def key_to_representation(cls, origin_key):
        """
        取出key时进行转化
        """
        return int(origin_key)

    @classmethod
    def get(cls, bk_module_id):
        """
        :param bk_module_id: 模块ID
        :rtype: Module
        """
        return super().get(bk_module_id)

    @classmethod
    def refresh_by_biz(cls, bk_biz_id):
        """
        按业务ID刷新缓存
        """
        modules = api.cmdb.get_module(bk_biz_id=bk_biz_id)  # type: list[Module]
        return {cls.key_to_internal_value(module.bk_module_id): module for module in modules}
