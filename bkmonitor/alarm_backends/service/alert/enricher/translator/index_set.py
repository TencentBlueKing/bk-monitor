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


from alarm_backends.core.cache.result_table import ResultTableCacheManager
from alarm_backends.service.alert.enricher.translator.base import BaseTranslator
from constants.data_source import DataSourceLabel


class IndexSetTranslator(BaseTranslator):
    """
    索引集字段名翻译
    """

    def is_enabled(self):
        return self.data_source_label == DataSourceLabel.BK_LOG_SEARCH

    def translate(self, data):
        index_set_id = self.item["query_configs"][0].get("index_set_id")
        if not index_set_id:
            return data
        rt_info = ResultTableCacheManager.get_result_table_by_id(self.data_source_label, index_set_id)
        if not rt_info:
            return data
        field_alias_mapping = {field["field_name"]: field["field_alias"] for field in rt_info["fields"]}
        for name, field in data.items():
            translated_name = field_alias_mapping.get(name) or name
            if field.display_name == field.name:
                # 如果没有翻译过，才使用字段别名
                field.display_name = translated_name
        return data
