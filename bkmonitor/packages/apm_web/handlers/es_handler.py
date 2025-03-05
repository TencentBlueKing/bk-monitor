# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2022 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from apm_web.constants import OPERATORS


class ESMappingHandler:
    def __init__(self, es_mapping: dict):
        self._mapping = es_mapping

    @staticmethod
    def flatten_mapping_properties(mapping_properties: dict, parent_path: str = None) -> dict[str, dict]:
        """
        将嵌套的 Elasticsearch mapping properties 结构展开为扁平化的字段字典
        参数 mapping_properties 请传入 mapping[table_name]["mappings"]["properties"]
        """
        result_dict = {}
        for k, v in mapping_properties.items():
            current_path = f"{parent_path}.{k}" if parent_path else k
            if "properties" in v:
                child_result = ESMappingHandler.flatten_mapping_properties(v["properties"], current_path)
                result_dict.update(child_result)
            else:
                result_dict[current_path] = v
        return result_dict

    def flatten_all_index_mapping_properties(self) -> dict[str, dict]:
        """将所有表嵌套的 Elasticsearch mapping properties 结构展开为扁平化的字段字典"""
        field_info_dict = {}
        for table_name, table_mapping in self._mapping.items():
            mapping_properties = table_mapping.get("mappings", {}).get("properties", {})
            field_info_dict.update(ESMappingHandler.flatten_mapping_properties(mapping_properties))
        return field_info_dict

    def get_queryable_fields(self) -> list[dict]:
        """获取可用于查询的字段信息（包含字段类型对应的操作符）"""
        field_info_dict = self.flatten_all_index_mapping_properties()

        # 排序，排序规则：顶层字段在前面，其他字段顺序随意
        sorted_field_names = sorted(field_info_dict.keys(), key=lambda x: ("." in x, x))

        fields = []
        for field_name in sorted_field_names:
            fields.append(
                {"field_name": field_name, "field_operator": OPERATORS.get(field_info_dict[field_name]["type"], [])}
            )
        return fields
