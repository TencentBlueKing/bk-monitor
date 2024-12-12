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

from django.utils.translation import gettext as _

from alarm_backends.core.cache.result_table import ResultTableCacheManager
from alarm_backends.service.alert.enricher.translator.base import BaseTranslator


class ResultTableTranslator(BaseTranslator):
    """
    结果表字段名翻译
    """

    def is_enabled(self):
        return True

    def translate(self, data):
        rt_info = ResultTableCacheManager.get_result_table_by_id(self.data_source_label, self.result_table_id)
        if not rt_info:
            return data
        field_alias_mapping = {field["field_name"]: field["field_alias"] for field in rt_info["fields"]}
        for name, field in list(data.items()):
            translated_name = field_alias_mapping.get(name) or name
            if field.display_name == field.name:
                # 如果没有翻译过，才使用字段别名
                field.display_name = _(translated_name)
        return data
