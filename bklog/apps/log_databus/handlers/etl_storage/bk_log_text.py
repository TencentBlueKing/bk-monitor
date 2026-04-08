# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
import copy

from apps.log_databus.constants import EtlConfig
from apps.log_databus.handlers.etl_storage import EtlStorage


class BkLogTextEtlStorage(EtlStorage):
    """
    直接入库
    """

    etl_config = EtlConfig.BK_LOG_TEXT

    def etl_preview(self, data, etl_params) -> list:
        """
        字段提取预览
        :param data: 日志原文
        :param etl_params: 字段提取参数
        :return: 字段列表 list
        """
        return data

    def etl_preview_v4(self, data, etl_params) -> list:
        """
        字段提取预览v4
        :param data: 日志原文
        :param etl_params: 字段提取参数
        :return: 字段列表 list
        """
        return data

    def get_result_table_config(self, fields, etl_params, built_in_config, es_version="5.X", enable_v4=False):
        """
        配置清洗入库策略，需兼容新增、编辑
        """
        built_in_fields = built_in_config.get("fields", [])

        etl_params = etl_params or {}
        es_analyzer = self.generate_field_analyzer_name(
            field_name="log",
            field_alias="data",
            is_case_sensitive=etl_params.get("original_text_is_case_sensitive", False),
            tokenize_on_chars=etl_params.get("original_text_tokenize_on_chars", ""),
        )
        original_text_field = {
            "field_name": "log",
            "field_type": "string",
            "tag": "metric",
            "alias_name": "data",
            "description": "original_text",
            "option": {"es_type": "text", "es_include_in_all": True}
            if es_version.startswith("5.")
            else {"es_type": "text"},
        }
        if es_analyzer:
            original_text_field["option"]["es_analyzer"] = es_analyzer

        result_table_config = {
            "option": built_in_config.get("option", {}),
            "field_list": built_in_fields + (fields or []) + [built_in_config["time_field"]] + [original_text_field],
            "time_alias_name": built_in_config["time_field"]["alias_name"],
            "time_option": built_in_config["time_field"]["option"],
        }
        
        # 检查是否启用V4数据链路
        if enable_v4:
            result_table_config["option"]["enable_log_v4_data_link"] = True
            result_table_config["option"]["log_v4_data_link"] = self.build_log_v4_data_link(fields, etl_params, built_in_config)
        
        return result_table_config

    def build_log_v4_data_link(self, fields: list, etl_params: dict, built_in_config: dict) -> dict:
        """
        构建直接入库类型的V4 clean_rules配置
        包含完整的数据流转规则：原始数据 -> JSON解析 -> 内置字段提取 -> 原文提取
        """
        rules = []

        # 1. JSON解析阶段（原始数据 -> json_data）
        rules.append({
            "input_id": "__raw_data",
            "output_id": "json_data",
            "operator": {
                "type": "json_de",
                "error_strategy": "drop"
            }
        })

        # 2. 提取内置字段（从json_data提取内置字段）
        built_in_rules = self._build_built_in_fields_v4(built_in_config)
        rules.extend(built_in_rules)

        # 3. 提取items数组并迭代
        rules.extend([
            {
                "input_id": "json_data",
                "output_id": "items",
                "operator": {
                    "type": "get",
                    "key_index": [{"type": "key", "value": "items"}],
                    "missing_strategy": None
                }
            },
            {
                "input_id": "items",
                "output_id": "iter_item",
                "operator": {"type": "iter"}
            }
        ])

        # 4. 从iter_item提取data字段作为原文（直接入库，不需要额外处理）
        rules.append({
            "input_id": "iter_item",
            "output_id": "log",
            "operator": {
                "type": "assign",
                "key_index": "data",
                "alias": "log",
                "output_type": "string"
            }
        })

        # 4.1. 提取iterationIndex字段（从iter_item提取，参考v3的flat_field处理）
        iteration_index_rules = self._build_iteration_index_field_v4(built_in_config)
        rules.extend(iteration_index_rules)

        # 5. Path字段处理（根据separator_configs配置）
        separator_configs = built_in_config.get("option", {}).get("separator_configs", [])
        if separator_configs:
            separator_config = separator_configs[0]
            path_regexp = separator_config.get("separator_regexp", "")
            if path_regexp:
                # 从json_data提取path字段
                rules.append({
                    "input_id": "json_data",
                    "output_id": "path",
                    "operator": {
                        "type": "get",
                        "key_index": [
                            {
                                "type": "key",
                                "value": "filename"
                            }
                        ],
                        "missing_strategy": None
                    }
                })
                
                # 从path字段提取路径信息
                rules.append({
                    "input_id": "path",
                    "output_id": "bk_separator_object_path",
                    "operator": {
                        "type": "regex",
                        "regex": path_regexp
                    }
                })
                
                # 提取路径字段
                import re
                pattern = re.compile(path_regexp)
                match_fields = list(pattern.groupindex.keys())
                for field_name in match_fields:
                    rules.append({
                        "input_id": "bk_separator_object_path",
                        "output_id": field_name,
                        "operator": {
                            "type": "assign",
                            "key_index": field_name,
                            "alias": field_name,
                            "output_type": "string"
                        }
                    })

        return {
            "clean_rules": rules,
            "es_storage_config": {
                "unique_field_list": built_in_config["option"]["es_unique_field_list"],
                "timezone": 8
            },
            "doris_storage_config": None
        }

    def get_bkdata_etl_config(self, fields, etl_params, built_in_config):
        built_in_fields = built_in_config.get("fields", [])
        (
            built_in_fields_type_object,
            built_in_fields_no_type_object,
            access_built_in_fields_type_object,
        ) = self._get_built_in_fields_type_fields(built_in_fields)

        result_table_fields = self.get_result_table_fields(fields, etl_params, copy.deepcopy(built_in_config))
        time_field = result_table_fields.get("time_field")

        return {
            "extract": {
                "method": "from_json",
                "next": {
                    "next": [
                        {
                            "default_type": "null",
                            "default_value": "",
                            "next": {
                                "method": "iterate",
                                "next": {
                                    "next": None,
                                    "subtype": "assign_obj",
                                    "label": "labelb140f1",
                                    "assign": [
                                        {"key": "data", "assign_to": "data", "type": "text"},
                                    ]
                                    + [
                                        self._to_bkdata_assign(built_in_field)
                                        for built_in_field in built_in_fields_no_type_object
                                        if built_in_field.get("flat_field", False)
                                    ],
                                    "type": "assign",
                                },
                                "label": "label21ca91",
                                "result": "iter_item",
                                "args": [],
                                "type": "fun",
                            },
                            "label": "label36c8ad",
                            "key": "items",
                            "result": "item_data",
                            "subtype": "access_obj",
                            "type": "access",
                        },
                        {
                            "next": None,
                            "subtype": "assign_obj",
                            "label": "labelf676c9",
                            "assign": self._get_bkdata_default_fields(built_in_fields_no_type_object, time_field),
                            "type": "assign",
                        },
                    ]
                    + access_built_in_fields_type_object,
                    "name": "",
                    "label": None,
                    "type": "branch",
                },
                "result": "json_data",
                "label": "label04a222",
                "args": [],
                "type": "fun",
            },
            "conf": self._to_bkdata_conf(time_field),
        }
