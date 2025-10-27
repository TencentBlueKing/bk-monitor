"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy

from luqum.tree import FieldGroup, OrOperation, SearchField, Word
from luqum.visitor import TreeTransformer

from constants.elasticsearch import QueryStringCharacters, QueryStringLogicOperators, QueryStringOperators
from constants.apm import OperatorGroupRelation


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
    def transform_condition_fields(cls, conditions: list):
        if not conditions:
            return []
        new_conditions = copy.deepcopy(conditions)
        if new_conditions:
            for condition in new_conditions:
                condition["origin_key"] = condition["key"]
                condition["key"] = cls.transform_field_to_es_field(condition["key"])
        return new_conditions

    @classmethod
    def transform_ordering_fields(cls, ordering: list):
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


class QueryStringGenerator:
    """根据 UI 模式过滤条件生成query string"""

    def __init__(self, operator_mapping: dict[str, str]):
        self.filters = []
        # 操作符到 query string 操作符模板的映射
        self.operator_mapping = operator_mapping
        self.query_string_list = []

    @staticmethod
    def _process_values_by_wildcard(values: list, is_wildcard: bool) -> list:
        """根据是否使用通配符预处理值"""

        result_values = []
        for v in values:
            c_list = []
            for c in v:
                # 如果使用通配符，* 和 ? 不转义
                if c in QueryStringCharacters.SUPPORTED_WILDCARDS_CHARACTERS and is_wildcard:
                    c_list.append(c)
                elif c in QueryStringCharacters.ES_RESERVED_CHARACTERS:
                    c_list.append(f"\\{c}")
                else:
                    c_list.append(c)
            result_values.append(f"*{''.join(c_list)}*")
        return result_values

    @staticmethod
    def _process_values_by_add_double_quotation(values: list) -> list:
        """将值两端添加双引号"""

        result_values = []
        for v in values:
            if isinstance(v, str):
                v = v.replace('"', '\\"')
                result_values.append(f'"{v}"')
            else:
                result_values.append(v)
        return result_values

    def _process_values(self, query_string_operator: str, values: list, is_wildcard: bool) -> list:
        """根据操作符预处理值"""
        if query_string_operator in QueryStringOperators.NEED_WILDCARD_OPERATORS:
            values = self._process_values_by_wildcard(values, is_wildcard)
        elif query_string_operator in QueryStringOperators.NEED_ADD_DOUBLE_QUOTATION_OPERATORS:
            values = self._process_values_by_add_double_quotation(values)
        return values

    def add_filter(
        self,
        key: str,
        operator: str,
        values: list,
        is_wildcard: bool = False,
        group_relation: OperatorGroupRelation = OperatorGroupRelation.OR,
    ):
        query_string_operator = self.operator_mapping.get(operator, QueryStringOperators.EQUAL)
        self.filters.append(
            {
                "key": key,
                "query_string_operator": query_string_operator,
                "values": values,
                "options": {"is_wildcard": is_wildcard, "group_relation": group_relation},
            }
        )

    @staticmethod
    def _get_query_string(
        field: str,
        query_string_operator: str,
        values: list,
        group_relation: OperatorGroupRelation = OperatorGroupRelation.OR,
    ):
        template = QueryStringOperators.OPERATOR_TEMPLATE_MAPPING.get(query_string_operator)
        if query_string_operator == QueryStringOperators.BETWEEN:
            start_value, end_value = values
            result_str = template.format(field=field, start_value=start_value, end_value=end_value)
        elif query_string_operator in [QueryStringOperators.EXISTS, QueryStringOperators.NOT_EXISTS]:
            result_str = template.format(field=field)
        else:
            if group_relation == OperatorGroupRelation.OR:
                logic_operator = QueryStringLogicOperators.OR
            else:
                logic_operator = QueryStringLogicOperators.AND
            result_str = f" {logic_operator} ".join(map(str, values))
            if len(values) > 1:
                result_str = f"({result_str})"
            result_str = template.format(field=field, value=result_str)
        return result_str

    def to_query_string(self) -> str:
        for f in self.filters:
            query_string_operator = f["query_string_operator"]
            values = f["values"]
            values = self._process_values(query_string_operator, values, f["options"]["is_wildcard"])
            query_string = self._get_query_string(
                f["key"], query_string_operator, values, f["options"]["group_relation"]
            )
            self.query_string_list.append(query_string)
        return f" {QueryStringLogicOperators.AND} ".join(self.query_string_list)
