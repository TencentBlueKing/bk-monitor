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
from api.cmdb.define import Set
from core.drf_resource import api


class SetManager(RefreshByBizMixin, CMDBCacheManager):
    """
    CMDB 集群缓存
    """

    ObjectClass = Set
    type = "set"
    CACHE_KEY = f"{CMDBCacheManager.CACHE_KEY_PREFIX}.cmdb.set"

    @classmethod
    def key_to_internal_value(cls, bk_set_id):
        return str(bk_set_id)

    @classmethod
    def key_to_representation(cls, origin_key):
        """
        取出key时进行转化
        """
        return int(origin_key)

    @classmethod
    def get(cls, bk_set_id):
        """
        :param bk_set_id: 集群ID
        :rtype: Set
        """
        return super().get(bk_set_id)

    @classmethod
    def refresh_by_biz(cls, bk_biz_id):
        """
        按业务ID刷新缓存
        """
        biz_sets = api.cmdb.get_set(bk_biz_id=bk_biz_id)  # type: list[Set]
        return {cls.key_to_internal_value(biz_set.bk_set_id): biz_set for biz_set in biz_sets}
