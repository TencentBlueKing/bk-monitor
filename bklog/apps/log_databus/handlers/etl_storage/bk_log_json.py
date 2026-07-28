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
import json

from django.utils.translation import gettext_lazy as _

from apps.exceptions import ValidationError
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import EXT_JSON_EXPAND_DEPTH
from apps.log_databus.constants import (
    DEFAULT_EXT_JSON_EXPAND_DEPTH,
    DORIS_CLUSTER_TYPE,
    EXT_JSON_EXPAND_DEPTH_CHOICES,
    MIN_FLATTENED_SUPPORT_VERSION,
    STORAGE_CLUSTER_TYPE,
    EtlConfig,
    ExtJsonOverflowStrategy,
)
from apps.log_databus.handlers.etl_storage import EtlStorage
from apps.log_databus.handlers.etl_storage.utils.transfer import preview
from apps.log_databus.utils.es_config import is_version_less_than


class BkLogJsonEtlStorage(EtlStorage):
    etl_config = EtlConfig.BK_LOG_JSON

    @staticmethod
    def _normalize_ext_json_config(config: dict | None) -> dict:
        config = config or {}
        expand_depth = config.get("expand_depth")
        overflow_strategy = config.get("overflow_strategy", ExtJsonOverflowStrategy.FLATTENED)
        if expand_depth is not None and expand_depth not in EXT_JSON_EXPAND_DEPTH_CHOICES:
            raise ValidationError(_("动态解析层级仅支持 1、2、3 或 null"))
        if overflow_strategy not in ExtJsonOverflowStrategy.values:
            raise ValidationError(_("不支持的未定义JSON字段溢出策略"))
        return {"expand_depth": expand_depth, "overflow_strategy": overflow_strategy}

    def customize_result_table_config(
        self,
        params: dict,
        etl_params: dict,
        current_result_table_config: dict,
        es_version: str,
        storage_cluster_type: str,
    ) -> None:
        current_config = current_result_table_config.get("option", {}).get("ext_json_config")
        # “键不存在”表示旧调用方从未启用该能力；显式传入空对象则表示启用并使用新配置默认值。
        has_new_config = "ext_json_config" in etl_params

        if not etl_params.get("retain_extra_json"):
            # 关闭未定义字段时同步清理请求态和 RT option，避免后续回显出已经失效的层级配置。
            etl_params.pop("ext_json_config", None)
            params["option"].pop("ext_json_config", None)
            return

        # 新旧配置均不存在时保持存量“无限展开”语义，不能把缺省值归一化成新配置默认深度 2。
        if not has_new_config and current_config is None:
            return

        if storage_cluster_type != STORAGE_CLUSTER_TYPE:
            raise ValidationError(_("未定义JSON字段动态解析层级仅支持 Elasticsearch 存储"))

        current_effective_config = self._normalize_ext_json_config(current_config)
        if has_new_config:
            requested_config = etl_params["ext_json_config"] or {}
            effective_config = {
                "expand_depth": requested_config.get("expand_depth", DEFAULT_EXT_JSON_EXPAND_DEPTH),
                "overflow_strategy": requested_config.get(
                    "overflow_strategy", current_effective_config["overflow_strategy"]
                ),
            }
        else:
            effective_config = current_effective_config
        effective_config = self._normalize_ext_json_config(effective_config)

        # 灰度只限制新增或变更；关闭实验开关后，已有配置仍需在普通采集项更新中继续生效。
        is_config_change = current_config is None or effective_config != current_effective_config
        if (
            has_new_config
            and is_config_change
            and not FeatureToggleObject.switch(EXT_JSON_EXPAND_DEPTH, etl_params.get("bk_biz_id"))
        ):
            raise ValidationError(_("当前业务未开启未定义JSON字段动态解析层级实验特性"))

        # expand_depth=null 不会生成 flattened mapping，仍是无限展开，因此无需校验 flattened 版本门槛。
        if (
            effective_config["overflow_strategy"] == ExtJsonOverflowStrategy.FLATTENED
            and effective_config["expand_depth"] is not None
            and is_version_less_than(es_version, MIN_FLATTENED_SUPPORT_VERSION)
        ):
            raise ValidationError(_(f"ES版本{es_version}不支持 flattened 字段类型"))

        # 同时回写本次清洗参数与 RT option，保证异步下发和后续配置回显使用同一份归一化配置。
        etl_params["ext_json_config"] = effective_config
        params["option"]["ext_json_config"] = effective_config

        ext_json_field = next(
            (field for field in params["field_list"] if field["field_name"] == "__ext_json"),
            None,
        )
        if not ext_json_field:
            raise ValidationError(_("未找到 __ext_json 结果表字段"))

        if effective_config["overflow_strategy"] == ExtJsonOverflowStrategy.SOURCE_ONLY:
            # 后台应急路径：关闭整个 __ext_json 的索引解析，但原始对象仍保留在 ES _source 中。
            ext_json_field["option"]["es_enabled"] = False
        elif effective_config["expand_depth"] is not None:
            depth = effective_config["expand_depth"]
            path_match = "__ext_json" + ".*" * depth
            # dynamic_templates 按顺序匹配，因此必须放在通用模板之前。通配符本身也能匹配更深路径，
            # 但第 N 层 object 一旦映射为 flattened，ES 就不会继续为其子树创建独立 mapping。
            # 该列表由基类 update_or_create_result_table 统一初始化，这里只追加 JSON 清洗的专属规则。
            dynamic_templates = params["default_storage_config"]["mapping_settings"]["dynamic_templates"]
            dynamic_templates.insert(
                0,
                {
                    f"ext_json_objects_at_depth_{depth}_as_flattened": {
                        "path_match": path_match,
                        "match_mapping_type": "object",
                        "mapping": {"type": "flattened"},
                    }
                },
            )

    def etl_preview(self, data, etl_params=None) -> list:
        """
        字段提取预览
        :param data: 日志原文
        :param etl_params: 字段提取参数
        :return: 字段列表 list
        """
        return preview("json", data)

    def etl_preview_v4(self, data, etl_params=None) -> list:
        """
        V4版本字段提取预览，直接调用BkDataDatabusApi.databus_clean_debug方法
        :param data: 日志原文
        :param etl_params: 字段提取参数
        :return: 字段列表 list
        """
        # 组装API请求参数
        api_request = {
            "input": data,
            "rules": [{"input_id": "__raw_data", "output_id": "bk_separator_object", "operator": {"type": "json_de"}}],
            "filter_rules": [],
        }

        # 调用BkDataDatabusApi.databus_clean_debug方法
        from apps.api import BkDataDatabusApi

        api_response = BkDataDatabusApi.databus_clean_debug(api_request)

        # 解析API响应
        rules_output_list = api_response.get("rules_output", [])
        rules_output = rules_output_list[0] if rules_output_list else {}
        values = rules_output.get("value", {})
        key_index = rules_output.get("key_index", [])

        # 构建返回结果
        result = []
        for key_info in key_index:
            if key_info.get("type") == "key":
                field_name = key_info.get("value", "")
                field_value = values.get(field_name, "")
                result.append({"field_name": field_name, "value": field_value})

        return result

    def get_result_table_config(
        self,
        fields,
        etl_params,
        built_in_config,
        es_version="5.X",
        enable_v4=False,
        storage_cluster_type=STORAGE_CLUSTER_TYPE,
    ):
        """
        配置清洗入库策略，需兼容新增、编辑
        """

        # option
        option = {
            "retain_original_text": etl_params.get("retain_original_text", False),
            "separator_node_source": "data",
            "separator_node_action": etl_params.get("separator_node_action", "json"),
            "separator_node_name": self.separator_node_name,
            "separator_fields_remove": "",
            "etl_flat": etl_params.get("etl_flat", False),
            "retain_extra_json": etl_params.get("retain_extra_json", False),
            # 当 JSON 中的某个字段类型为 string，且原始数据为 object 时，将 object 进行 JSON 序列化后再入库，提高数据可读性
            "enable_origin_string": True,
            # 当原始数据不符合 JSON 格式时，不对数据进行丢弃，直接强制写入到 log 字段
            "enable_retain_content": etl_params.get("enable_retain_content", True),
        }

        # 保存删除的字段
        remove_fields = [item["field_name"] for item in fields if item.get("is_delete", False)]
        if len(remove_fields):  # pylint:disable=len-as-condition
            option["separator_fields_remove"] = ",".join(remove_fields)

        if built_in_config.get("option") and isinstance(built_in_config["option"], dict):
            option = dict(built_in_config["option"], **option)
        result_table_fields = self.get_result_table_fields(
            fields, etl_params, built_in_config, es_version=es_version, storage_cluster_type=storage_cluster_type
        )

        result_table_config = {
            "option": option,
            "field_list": result_table_fields["fields"],
            "time_alias_name": result_table_fields["time_field"]["alias_name"],
            "time_option": result_table_fields["time_field"]["option"],
        }

        # 检查是否启用V4数据链路
        if enable_v4:
            result_table_config["option"]["enable_log_v4_data_link"] = True
            result_table_config["option"]["log_v4_data_link"] = self.build_log_v4_data_link(
                fields,
                etl_params,
                built_in_config,
                result_table_config["field_list"],
                storage_cluster_type=storage_cluster_type,
            )

        return result_table_config

    def build_log_v4_data_link(
        self,
        fields: list,
        etl_params: dict,
        built_in_config: dict,
        field_list: list,
        storage_cluster_type=STORAGE_CLUSTER_TYPE,
    ) -> dict:
        """
        构建JSON类型的V4 clean_rules配置
        包含完整的数据流转规则：原始数据 -> JSON解析 -> 字段提取 -> JSON解析 -> 字段映射
        """
        self._validate_v4_reserved_fields(fields)
        rules = []

        # 1. JSON解析阶段（原始数据 -> json_data）
        rules.append(
            {
                "input_id": "__raw_data",
                "output_id": "json_data",
                "operator": {"type": "json_de", "error_strategy": "drop"},
            }
        )

        # 1.1. 用户自定义时间字段时，提取utctime供时间解析失败兜底使用
        rules.extend(self._build_utctime_extract_v4(built_in_config))

        # 2. 提取内置字段（从json_data提取内置字段）
        built_in_rules = self._build_built_in_fields_v4(built_in_config, storage_cluster_type)
        rules.extend(built_in_rules)

        # 3. 提取items数组并迭代
        rules.extend(
            [
                {
                    "input_id": "json_data",
                    "output_id": "items",
                    "operator": {
                        "type": "get",
                        "key_index": [{"type": "key", "value": "items"}],
                        "missing_strategy": None,
                    },
                },
                {"input_id": "items", "output_id": "iter_item", "operator": {"type": "iter"}},
                {
                    "input_id": "iter_item",
                    "output_id": "iter_string",
                    "operator": {
                        "type": "get",
                        "key_index": [{"type": "key", "value": "data"}],
                        "missing_strategy": None,
                    },
                },
            ]
        )

        # 4. 从iter_item提取日志原文（保留原文 或 保留清洗失败日志时均需要）
        # enable_retain_content: 当原始数据不符合JSON格式时，不丢弃数据，直接强制写入log字段
        if etl_params.get("retain_original_text") or etl_params.get("enable_retain_content"):
            rules.append(
                {
                    "input_id": "iter_item",
                    "output_id": "log",
                    "operator": {
                        "type": "assign",
                        "key_index": "data",
                        "alias": "log",
                        "output_type": "string",
                        "default_value": None,
                    },
                }
            )

        # 4.1. 提取 flat_field=True 的内置字段（从iter_item提取）
        rules.extend(self._build_flat_built_in_fields_v4(built_in_config))

        # 5. JSON解析（解析iter_string中的JSON）
        # enable_retain_content=True时使用"null"策略，解析失败不丢弃数据，将字段置空
        json_de_error_strategy = "null" if etl_params.get("enable_retain_content") else "drop"
        rules.append(
            {
                "input_id": "iter_string",
                "output_id": "bk_separator_object",
                "operator": {"type": "json_de", "error_strategy": json_de_error_strategy},
            }
        )

        # 6. 字段映射（根据fields配置）
        for field in fields:
            if field.get("is_delete"):
                continue

            target_field = field.get("alias_name") or field["field_name"]

            rules.append(
                {
                    "input_id": "bk_separator_object",
                    "output_id": target_field,
                    "operator": {
                        "type": "assign",
                        "key_index": field["field_name"],
                        "alias": target_field,
                        "output_type": self._get_output_type(field["field_type"]),
                        "default_value": None,
                    },
                }
            )

        # 6.1. 处理用户指定的时间字段作为dtEventTimeStamp（从bk_separator_object提取）
        rules.extend(self._build_user_dt_event_time_field_v4(built_in_config, storage_cluster_type))

        # 6.2. 处理dtEventTimeStampNanos字段（从用户指定的时间字段提取）
        rules.extend(self._build_nanos_time_field_v4(built_in_config, storage_cluster_type))

        # 6.3. 处理ext_json字段
        rules.extend(self._build_extra_json_field_v4(etl_params, fields))

        # 7. Path字段处理
        rules.extend(self._build_path_regex_rules_v4(etl_params, built_in_config))

        data_link_config = {"clean_rules": rules}

        if storage_cluster_type == STORAGE_CLUSTER_TYPE:
            data_link_config["es_storage_config"] = {
                "unique_field_list": built_in_config["option"]["es_unique_field_list"],
                "timezone": 8,
            }
        elif storage_cluster_type == DORIS_CLUSTER_TYPE:
            json_fields = set()
            for check_rule in rules:
                if check_rule["operator"].get("output_type") == self._get_output_type("object"):
                    json_fields.add(check_rule["output_id"])

            need_analysis_fields = set()
            for check_field in field_list:
                if check_field["option"]["es_type"] == "text":
                    need_analysis_fields.add(check_field["field_name"])

            data_link_config["doris_storage_config"] = {
                "storage_keys": built_in_config["option"]["es_unique_field_list"],
                "json_fields": list(json_fields),
                "field_config_group": {"search_zh": list(need_analysis_fields)},
                # "flush_timeout": None
            }

        return data_link_config

    @staticmethod
    def _decode_transfer_field_name(field_name):
        """还原 Transfer 为表达字面字段名而保存的 JSON 字符串。"""
        if not isinstance(field_name, str) or not field_name.startswith('"') or not field_name.endswith('"'):
            return field_name

        try:
            decoded_field_name = json.loads(field_name)
        except json.JSONDecodeError:
            return field_name

        return decoded_field_name if isinstance(decoded_field_name, str) else field_name

    def _to_bkdata_assign_json(self, field):
        alias_name = field.get("alias_name")
        field_name = self._decode_transfer_field_name(field.get("field_name"))
        return {
            "key": field_name,
            "assign_to": alias_name if alias_name else field_name,
            "type": self.get_es_field_type(field),
        }

    def get_bkdata_fields_configs(self, bkdata_fields):
        fields_type_object = [field for field in bkdata_fields if field["field_type"] == "object"]
        fields_no_type_object = [field for field in bkdata_fields if field["field_type"] != "object"]
        fields_configs = []
        if fields_no_type_object:
            fields_configs.append(
                {
                    "next": None,
                    "subtype": "assign_obj",
                    "label": "labela2dfe3",
                    "assign": [self._to_bkdata_assign_json(field) for field in fields_no_type_object],
                    "type": "assign",
                }
            )
        if fields_type_object:
            fields_configs.extend(
                [
                    {
                        "type": "assign",
                        "subtype": "assign_json",
                        "label": "label6d9ab9" + str(count),
                        "assign": [self._to_bkdata_assign_obj(field)],
                        "next": None,
                    }
                    for count, field in enumerate(fields_type_object)
                ]
            )
        return fields_configs

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
        bkdata_fields = [field for field in fields if not field["is_delete"]]
        bkdata_fields_configs = self.get_bkdata_fields_configs(bkdata_fields)
        return {
            "extract": {
                "method": "from_json",
                "next": {
                    "next": [
                        {
                            "default_value": "",
                            "default_type": "null",
                            "next": {
                                "method": "iterate",
                                "next": {
                                    "next": [
                                        {
                                            "default_value": "",
                                            "default_type": "null",
                                            "next": {
                                                "next": [
                                                    {
                                                        "method": "from_json",
                                                        "next": {
                                                            "label": None,
                                                            "name": "",
                                                            "next": bkdata_fields_configs,
                                                            "type": "branch",
                                                        },
                                                        "result": "log_json",
                                                        "label": "label5e3d6f",
                                                        "args": [],
                                                        "type": "fun",
                                                    },
                                                ],
                                                "name": "",
                                                "label": None,
                                                "type": "branch",
                                            },
                                            "label": "labelb140f1",
                                            "key": "data",
                                            "result": "log_data",
                                            "subtype": "access_obj",
                                            "type": "access",
                                        },
                                        {
                                            "next": None,
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
                                            "type": "assign",
                                        },
                                    ],
                                    "name": "",
                                    "type": "branch",
                                    "label": None,
                                },
                                "result": "iter_item",
                                "label": "label21ca91",
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
