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
import re

from django.utils.translation import gettext_lazy as _

from apps.exceptions import ValidationError
from apps.log_databus.constants import EtlConfig
from apps.log_databus.handlers.etl_storage import EtlStorage
from apps.log_databus.handlers.etl_storage.utils.transfer import preview


class BkLogRegexpEtlStorage(EtlStorage):
    etl_config = EtlConfig.BK_LOG_REGEXP

    def etl_preview(self, data, etl_params=None) -> list:
        """
        字段提取预览
        :param data: 日志原文
        :param etl_params: 字段提取参数
        :return: 字段列表 list
        """
        if not etl_params.get("separator_regexp"):
            raise ValidationError(_("正则表达式不能为空"))

        # 先从python获取
        regexp_match = re.compile(etl_params["separator_regexp"], re.S).match(data)
        if not regexp_match:
            raise ValidationError(_("无法匹配正则表达式"))
        groupdict = regexp_match.groupdict()

        # 在线上使用python确保正则有序返回
        fields = [key for (key, __) in groupdict.items()]
        preview_fields = preview("regexp", data, separator_regexp=etl_params["separator_regexp"], etl_only=True)

        result = []
        i = 1
        for field in fields:
            if field not in preview_fields:
                continue
            result.append({"field_index": i, "field_name": field, "value": preview_fields[field]})
            del preview_fields[field]
            i += 1

        if len(preview_fields):  # pylint:disable=len-as-condition
            for field, value in preview_fields.items():
                result.append({"field_index": i, "field_name": field, "value": value})
                i += 1
        return result

    def etl_preview_v4(self, data, etl_params=None) -> list:
        """
        V4版本字段提取预览，直接调用BkDataDatabusApi.databus_clean_debug方法
        :param data: 日志原文
        :param etl_params: 字段提取参数
        :return: 字段列表 list
        """
        if not etl_params.get("separator_regexp"):
            raise ValidationError(_("正则表达式不能为空"))
        
        # 组装API请求参数
        api_request = {
            "input": data,
            "rules": [
                {
                    "input_id": "__raw_data",
                    "output_id": "bk_separator_object",
                    "operator": {
                        "type": "regex",
                        "regex": etl_params["separator_regexp"]
                    }
                }
            ],
            "filter_rules": []
        }
        
        # 调用BkDataDatabusApi.databus_clean_debug方法
        from apps.api.BkDataDatabusApi import BkDataDatabusApi
        api_response = BkDataDatabusApi.databus_clean_debug(api_request)
        
        # 解析API响应
        rules_output = api_response.get("rules_output", {})
        values = rules_output.get("value", {})
        key_index = rules_output.get("key_index", [])
        
        # 构建返回结果
        result = []
        for i, key_info in enumerate(key_index):
            if key_info.get("type") == "key":
                field_name = key_info.get("value", "")
                field_value = values.get(field_name, "")
                result.append({
                    "field_index": i + 1,
                    "field_name": field_name,
                    "value": field_value
                })
        
        return result

    def get_result_table_config(self, fields, etl_params, built_in_config, es_version="5.X", bk_biz_id=None):
        """
        配置清洗入库策略，需兼容新增、编辑
        """
        # 判断字段是否都在正则表达式中定义
        for field in fields:
            if field.get("is_config_by_user") and f'<{field["field_name"]}>' not in etl_params["separator_regexp"]:
                raise ValidationError(_("字段未在正则表达式中定义：") + field["field_name"])

        # option
        option = {
            "retain_original_text": etl_params.get("retain_original_text", False),
            "separator_node_source": "data",
            "separator_node_action": etl_params.get("separator_node_action", "regexp"),
            "separator_node_name": self.separator_node_name,
            "separator_regexp": etl_params.get("separator_regexp", ""),
            "etl_flat": etl_params.get("etl_flat", False),
            "enable_retain_content": etl_params.get("enable_retain_content", False),
        }

        if built_in_config.get("option") and isinstance(built_in_config["option"], dict):
            option = dict(built_in_config["option"], **option)

        result_table_fields = self.get_result_table_fields(fields, etl_params, built_in_config, es_version=es_version)

        result_table_config = {
            "option": option,
            "field_list": result_table_fields["fields"],
            "time_alias_name": result_table_fields["time_field"]["alias_name"],
            "time_option": result_table_fields["time_field"]["option"],
        }
        
        # 检查是否启用V4数据链路
        from apps.feature_toggle.handlers.toggle import FeatureToggleObject
        if FeatureToggleObject.switch("log_v4_data_link", bk_biz_id):
            result_table_config["option"]["enable_log_v4_data_link"] = True
            result_table_config["option"]["log_v4_data_link"] = self.build_log_v4_data_link(fields, etl_params, built_in_config)
        
        return result_table_config

    def build_log_v4_data_link(self, fields: list, etl_params: dict, built_in_config: dict) -> dict:
        """
        构建正则表达式类型的V4 clean_rules配置
        包含完整的数据流转规则：原始数据 -> JSON解析 -> 字段提取 -> 正则解析 -> 字段映射
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
        
        # 4. 从iter_item提取data字段作为原文
        rules.extend([
            {
                "input_id": "iter_item",
                "output_id": "log",
                "operator": {
                    "type": "assign",
                    "key_index": "data",
                    "alias": "log",
                    "output_type": "string"
                }
            },
            {
                "input_id": "iter_item",
                "output_id": "iter_string",
                "operator": {
                    "type": "get",
                    "key_index": [{"type": "key", "value": "data"}],
                    "missing_strategy": None
                }
            }
        ])
        
        # 5. 正则解析
        rules.append({
            "input_id": "iter_string",
            "output_id": "bk_separator_object",
            "operator": {
                "type": "regex",
                "regex": etl_params.get("separator_regexp", "")
            }
        })
        
        # 6. 字段映射
        for field in fields:
            if field.get("is_delete"):
                continue
                
            rules.append({
                "input_id": "bk_separator_object",
                "output_id": field["field_name"],
                "operator": {
                    "type": "assign",
                    "key_index": field["field_name"],
                    "alias": field["field_name"],
                    "output_type": self._get_output_type(field["field_type"])
                }
            })

        # 7. Path字段处理（根据separator_configs配置）
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
            "rules": rules,
            "filter_rules": []
        }

    def get_bkdata_etl_config(self, fields, etl_params, built_in_config):
        retain_original_text = etl_params.get("retain_original_text", False)
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
                "type": "fun",
                "method": "from_json",
                "result": "json_data",
                "label": "label04a222",
                "args": [],
                "next": {
                    "type": "branch",
                    "name": "",
                    "label": None,
                    "next": [
                        {
                            "type": "access",
                            "subtype": "access_obj",
                            "label": "label36c8ad",
                            "key": "items",
                            "result": "item_data",
                            "default_type": "null",
                            "default_value": "",
                            "next": {
                                "type": "fun",
                                "result": "iter_item",
                                "label": "label21ca91",
                                "args": [],
                                "method": "iterate",
                                "next": {
                                    "name": "",
                                    "type": "branch",
                                    "label": None,
                                    "next": [
                                        {
                                            "type": "assign",
                                            "subtype": "assign_obj",
                                            "label": "labelb140",
                                            "assign": (
                                                [{"key": "data", "assign_to": "data", "type": "text"}]
                                                if retain_original_text
                                                else []
                                            )
                                            + [
                                                self._to_bkdata_assign(built_in_field)
                                                for built_in_field in built_in_fields_no_type_object
                                                if built_in_field.get("flat_field", False)
                                            ],
                                            "next": None,
                                        },
                                        {
                                            "type": "access",
                                            "subtype": "access_obj",
                                            "label": "labelb140f1",
                                            "key": "data",
                                            "result": "log_data",
                                            "default_type": "null",
                                            "default_value": "",
                                            "next": {
                                                "type": "fun",
                                                "method": "regex_extract",
                                                "label": "label5e3d6f",
                                                "args": [
                                                    {
                                                        "result": "regexp_data",
                                                        "keys": [
                                                            field["alias_name"]
                                                            if field["alias_name"]
                                                            else field["field_name"]
                                                            for field in fields
                                                        ],
                                                        "regexp": etl_params.get("separator_regexp", "").replace(
                                                            "(?P<", "(?<"
                                                        ),
                                                    }
                                                ],
                                                "next": {
                                                    "type": "assign",
                                                    "subtype": "assign_obj",
                                                    "label": "labela2dfe3",
                                                    "assign": [self._to_bkdata_assign(field) for field in fields],
                                                    "next": None,
                                                },
                                            },
                                        },
                                    ],
                                },
                            },
                        },
                        {
                            "type": "assign",
                            "subtype": "assign_obj",
                            "label": "labelf676c9",
                            "assign": self._get_bkdata_default_fields(built_in_fields_no_type_object, time_field),
                            "next": None,
                        },
                    ]
                    + access_built_in_fields_type_object,
                },
            },
            "conf": self._to_bkdata_conf(time_field),
        }
