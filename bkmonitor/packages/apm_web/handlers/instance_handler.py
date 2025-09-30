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
from apm_web.constants import InstanceDiscoverKeys

from constants.apm import OtlpKey
from core.drf_resource import api


class InstanceHandler:

    BK_INSTANCE_ID_FIELD_NAME = OtlpKey.get_resource_key(OtlpKey.BK_INSTANCE_ID)

    @classmethod
    def get_span_fields(cls, app):
        """获取所有es字段"""
        res = set()
        response = api.apm_api.query_es_mapping(bk_biz_id=app.bk_biz_id, app_name=app.app_name)
        for index_name, item in response.items():

            item_properties = item.get("mappings", {}).get("properties", {})
            if not item_properties:
                # properties 可能位于不同结构中
                item_properties = item.get("mappings", {}).get(app.trace_result_table_id, {}).get("properties", {})

            # 只获取resource字段
            resource_properties = item_properties.get(OtlpKey.RESOURCE, {})
            properties_fields = set()
            cls._extract_properties(resource_properties, properties_fields, OtlpKey.RESOURCE)

            res |= properties_fields

        # 去除自身的实例字段
        try:
            res.remove(cls.BK_INSTANCE_ID_FIELD_NAME)
        except KeyError:
            pass

        return [{"id": i, "name": i, "alias": InstanceDiscoverKeys.get_label_by_key(i)} for i in res]

    @classmethod
    def _extract_properties(cls, properties, res, prefix):
        if "properties" not in properties:
            return prefix

        for p_prefix, p_properties in properties["properties"].items():
            r = cls._extract_properties(p_properties, res, ".".join([prefix, p_prefix]))
            if r:
                res.add(r)
