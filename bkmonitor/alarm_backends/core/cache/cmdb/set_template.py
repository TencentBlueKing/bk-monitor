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
from collections import defaultdict


from alarm_backends.core.cache.cmdb.base import CMDBCacheManager, RefreshByBizMixin
from core.drf_resource import api


class SetTemplateManager(RefreshByBizMixin, CMDBCacheManager):
    """
    CMDB 集群模板缓存
    """

    type = "set_template"
    CACHE_KEY = f"{CMDBCacheManager.CACHE_KEY_PREFIX}.cmdb.set_template"
    SET_TEMPLATE_TO_SETS = f"{CMDBCacheManager.CACHE_KEY_PREFIX}.cmdb.set_template_to_sets"

    @classmethod
    def key_to_internal_value(cls, set_template_id):
        return str(set_template_id)

    @classmethod
    def key_to_representation(cls, origin_key):
        return int(origin_key)

    @classmethod
    def serialize(cls, obj):
        return json.dumps(obj)

    @classmethod
    def get(cls, set_template_id):
        """
        :param set_template_id: 集群模板ID
        """
        return super().get(set_template_id)

    @classmethod
    def deserialize(cls, string):
        """
        反序列化数据
        """
        return json.loads(string) if string else []

    @classmethod
    def refresh_by_biz(cls, bk_biz_id):
        """
        按业务ID刷新缓存
        """
        sets = api.cmdb.get_set(bk_biz_id=bk_biz_id)
        set_template_to_set = defaultdict(list)

        for _set in sets:
            set_template_to_set[str(_set.set_template_id)].append(_set.bk_set_id)

        return set_template_to_set
