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
import copy
from typing import List

from luqum.tree import FieldGroup, OrOperation, SearchField, Word
from luqum.visitor import TreeTransformer


class BaseTreeTransformer(TreeTransformer):
    VALUE_TRANSLATE_FIELDS = {}

    def visit_word(self, node, context):
        if context.get("ignore_word"):
            yield from self.generic_visit(node, context)

        else:
            # 获取搜索字段的名字
            search_field_name = context.get("search_field_name")
            if search_field_name:
                if search_field_name in self.VALUE_TRANSLATE_FIELDS:
                    for value, display in self.VALUE_TRANSLATE_FIELDS[search_field_name]:
                        # 尝试将匹配翻译值，并转换回原值
                        if display == node.value:
                            node.value = str(value)
                else:
                    node.value = self.transform_value_with_search_field(node.value)
            else:
                for key, choices in self.VALUE_TRANSLATE_FIELDS.items():
                    origin_value = None
                    for value, display in choices:
                        # 尝试将匹配翻译值，并转换回原值。例如: severity: 致命 => severity: 1
                        if display == node.value:
                            origin_value = str(value)

                    if origin_value is not None:
                        # 例如:  致命 =>  致命 OR (severity: 1)
                        node = FieldGroup(OrOperation(node, SearchField(key, Word(origin_value))))
                        context = {"ignore_search_field": True, "ignore_word": True}
                        break
                else:
                    node.value = self.transform_value_without_search_field(node.value)

            yield from self.generic_visit(node, context)

    @classmethod
    def transform_value_with_search_field(cls, value: str) -> str:
        return value

    @classmethod
    def transform_value_without_search_field(cls, value: str) -> str:
        return f'"{value}"'

    @classmethod
    def transform_condition_fields(cls, conditions: List):
        if not conditions:
            return []
        new_conditions = copy.deepcopy(conditions)
        if new_conditions:
            for condition in new_conditions:
                condition["key"] = cls.transform_field_to_es_field(condition["key"])
        return new_conditions

    @classmethod
    def transform_ordering_fields(cls, ordering: List):
        if not ordering:
            return []
        new_ordering = []
        for field in ordering:
            if field.startswith("-"):
                # 处理倒序的特殊情况
                es_field = field[0] + cls.transform_field_to_es_field(field[1:], for_agg=True)
            else:
                es_field = cls.transform_field_to_es_field(field, for_agg=True)
            new_ordering.append(es_field)
        return new_ordering

    @classmethod
    def transform_field_to_es_field(cls, field: str, for_agg=False):
        """
        将字段名转换为ES可查询的真实字段名
        """
        raise NotImplementedError
