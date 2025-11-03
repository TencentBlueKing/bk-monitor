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


class ServiceTemplateManager(RefreshByBizMixin, CMDBCacheManager):
    """
    CMDB 服务模板缓存
    """

    type = "service_template"
    CACHE_KEY = f"{CMDBCacheManager.CACHE_KEY_PREFIX}.cmdb.service_template"

    @classmethod
    def key_to_internal_value(cls, service_template_id):
        return str(service_template_id)

    @classmethod
    def key_to_representation(cls, origin_key):
        return int(origin_key)

    @classmethod
    def get(cls, service_template_id):
        """
        :param service_template_id: 服务模板ID
        """
        return super().get(service_template_id)

    @classmethod
    def deserialize(cls, string):
        """
        反序列化数据
        """
        return json.loads(string) if string else []

    @classmethod
    def serialize(cls, obj):
        return json.dumps(obj)

    @classmethod
    def refresh_by_biz(cls, bk_biz_id):
        """
        按业务ID刷新缓存
        """
        modules = api.cmdb.get_module(bk_biz_id=bk_biz_id)
        service_template_to_module = defaultdict(list)

        for module in modules:
            service_template_to_module[str(module.service_template_id)].append(module.bk_module_id)

        return service_template_to_module
