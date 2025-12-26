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
import hashlib
import re
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _

from apps.api import TransferApi
from apps.exceptions import ApiResultError, ValidationError
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.log_databus.constants import (
    BKDATA_ES_TYPE_MAP,
    CACHE_KEY_CLUSTER_INFO,
    FIELD_TEMPLATE,
    PARSE_FAILURE_FIELD,
    EtlConfig,
    MetadataTypeEnum,
    MIN_FLATTENED_SUPPORT_VERSION,
)
from apps.log_databus.exceptions import (
    EtlParseTimeFieldException,
    HotColdCheckException,
)
from apps.log_databus.handlers.collector_scenario import CollectorScenario
from apps.log_databus.handlers.collector_scenario.utils import build_es_option_type
from apps.log_databus.models import CollectorConfig, CollectorPlugin
from apps.log_databus.utils.es_config import get_es_config, is_version_less_than
from apps.log_search.constants import (
    FieldBuiltInEnum,
    FieldDataTypeEnum,
    FieldDateFormatEnum,
)
from apps.utils import is_match_variate
from apps.utils.codecs import unicode_str_decode
from apps.utils.db import array_group


class EtlStorage:
    """
    清洗入库
    """

    # 子类需重载
    etl_config = None
    separator_node_name = "bk_separator_object"
    path_separator_node_name = "bk_separator_object_path"

    @classmethod
    def get_instance(cls, etl_config=None):
        mapping = {
            EtlConfig.BK_LOG_TEXT: "BkLogTextEtlStorage",
            EtlConfig.BK_LOG_JSON: "BkLogJsonEtlStorage",
            EtlConfig.BK_LOG_DELIMITER: "BkLogDelimiterEtlStorage",
            EtlConfig.BK_LOG_REGEXP: "BkLogRegexpEtlStorage",
        }
        try:
            etl_storage = import_string(f"apps.log_databus.handlers.etl_storage.{etl_config}.{mapping.get(etl_config)}")
            return etl_storage()
        except ImportError as error:
            raise NotImplementedError(f"{etl_config} not implement, error: {error}")

    @classmethod
    def get_etl_config(cls, result_table_config, default="bk_log_text"):
        """
        根据RT表配置返回etl_config类型
        """
        separator_node_action = result_table_config.get("option", {}).get("separator_node_action")
        return {"regexp": "bk_log_regexp", "delimiter": "bk_log_delimiter", "json": "bk_log_json"}.get(
            separator_node_action, default
        )

    def etl_preview(self, data, etl_params) -> list:
        """
        字段提取预览
        :param data: 日志原文
        :param etl_params: 字段提取参数
        :return: 字段列表 list
        """
        raise NotImplementedError(_("功能暂未实现"))

    def etl_preview_v4(self, data, etl_params) -> list:
        """
        V4版本字段提取预览，直接调用BkDataDatabusApi.databus_clean_debug方法
        :param data: 日志原文
        :param etl_params: 字段提取参数
        :return: 字段列表 list
        """
        raise NotImplementedError(_("V4版本功能暂未实现"))

    def get_bkdata_etl_config(self, fields, etl_params, built_in_config):
        raise NotImplementedError(_("功能暂未实现"))

    def get_result_table_config(self, fields, etl_params, built_in_config, es_version="5.X", enable_v4=False):
        """
        配置清洗入库策略，需兼容新增、编辑
        """
        raise NotImplementedError(_("功能暂未实现"))

    def build_log_v4_data_link(self, fields: list, etl_params: dict, built_in_config: dict) -> dict:
        """
        构建V4版本的clean_rules配置
        :param fields: 字段列表
        :param etl_params: 清洗参数
        :param built_in_config: 内置配置，包含fields和time_field
        :return: clean_rules配置字典
        """
        raise NotImplementedError(_("V4版本clean_rules构建功能暂未实现"))

    @staticmethod
    def get_es_field_type(field):
        es_type = field.get("option", {}).get("es_type")
        if not es_type:
            es_type = FieldDataTypeEnum.get_es_field_type(field["field_type"], is_analyzed=field["is_analyzed"])
        return BKDATA_ES_TYPE_MAP.get(es_type, "string")

    @staticmethod
    def _get_output_type(field_type: str) -> str:
        """
        将字段类型转换为V4 clean_rules的output_type
        """
        type_mapping = {
            "string": "string",
            "int": "long",
            "long": "long",
            "float": "double",
            "double": "double",
            "object": "dict",
            "bool": "boolean",
            "boolean": "boolean",
        }
        return type_mapping.get(field_type, "string")

    @staticmethod
    def _convert_v3_to_v4_time_format(v3_time_format: str) -> dict:
        """
        将V3时间格式转换为V4 in_place_time_parsing配置
        :param v3_time_format: V3版本的时间格式字符串
        :return: V4版本的in_place_time_parsing配置字典
        """
        # V3到V4时间格式映射表
        time_format_mapping = {
            # 标准日期时间格式
            "yyyy-MM-dd HH:mm:ss": {"format": "%Y-%m-%d %H:%M:%S", "zone": 0},
            "yyyy-MM-dd HH:mm:ss,SSS": {"format": "%Y-%m-%d %H:%M:%S,%3f", "zone": 0},
            "yyyy-MM-dd HH:mm:ss.SSS": {"format": "%Y-%m-%d %H:%M:%S.%3f", "zone": 0},
            "yyyy-MM-dd HH:mm:ss.SSSSSS": {"format": "%Y-%m-%d %H:%M:%S.%6f", "zone": 0},
            "yy-MM-dd HH:mm:ss.SSSSSS": {"format": "%y-%m-%d %H:%M:%S.%6f", "zone": 0},
            "yyyy-MM-ddTHH:mm:ss.SSSSSS": {"format": "%Y-%m-%dT%H:%M:%S.%6f", "zone": 0},
            "yyyy-MM-dd+HH:mm:ss": {"format": "%Y-%m-%d+%H:%M:%S", "zone": 0},
            "MM/dd/yyyy HH:mm:ss": {"format": "%m/%d/%Y %H:%M:%S", "zone": 0},
            "yyyyMMddHHmmss": {"format": "%Y%m%d%H%M%S", "zone": 0},
            "yyyyMMdd HHmmss": {"format": "%Y%m%d %H%M%S", "zone": 0},
            "yyyyMMdd HHmmss.SSS": {"format": "%Y%m%d %H%M%S.%3f", "zone": 0},
            "dd/MMM/yyyy:HH:mm:ss": {"format": "%d/%b/%Y:%H:%M:%S", "zone": 0},
            "dd/MMM/yyyy:HH:mm:ssZ": {"format": "%d/%b/%Y:%H:%M:%S%:z", "zone": None},
            "dd/MMM/yyyy:HH:mm:ss Z": {"format": "%d/%b/%Y:%H:%M:%S %:z", "zone": None},
            "dd/MMM/yyyy:HH:mm:ssZZ": {"format": "%d/%b/%Y:%H:%M:%S%:z", "zone": None},
            "dd/MMM/yyyy:HH:mm:ss ZZ": {"format": "%d/%b/%Y:%H:%M:%S %:z", "zone": None},
            "rfc3339": {"format": "%+", "zone": None},
            "yyyy-MM-ddTHH:mm:ss": {"format": "%Y-%m-%dT%H:%M:%S", "zone": 0},
            "yyyy-MM-ddTHH:mm:ss.SSS": {"format": "%Y-%m-%dT%H:%M:%S.%3f", "zone": 0},
            "yyyyMMddTHHmmssZ": {"format": "%Y%m%dT%H%M%S%:z", "zone": None},
            "yyyyMMddTHHmmss.SSSSSSZ": {"format": "%Y%m%dT%H%M%S.%6f%:z", "zone": None},
            "yyyy-MM-ddTHH:mm:ss.SSSZ": {"format": "%Y-%m-%dT%H:%M:%S.%3f%:z", "zone": None},
            "yyyy-MM-ddTHH:mm:ss.SSSSSSZ": {"format": "%Y-%m-%dT%H:%M:%S.%6fZ", "zone": None},
            "ISO8601": {"format": "%+", "zone": None},
            "yyyy-MM-ddTHH:mm:ssZ": {"format": "%Y-%m-%dT%H:%M:%S%:z", "zone": None},
            "yyyy-MM-ddTHH:mm:ss.SSSSSSZZ": {"format": "%Y-%m-%dT%H:%M:%S.%6f%:z", "zone": None},
            "yyyy.MM.dd-HH.mm.ss:SSS": {"format": "%Y.%m.%d-%H.%M.%S:%3f", "zone": 0},
            "date_hour_minute_second": {"format": "%Y-%m-%dT%H:%M:%S", "zone": 0},
            "date_hour_minute_second_millis": {"format": "%Y-%m-%dT%H:%M:%S.%3f", "zone": 0},
            "basic_date_time": {"format": "%Y%m%dT%H%M%S.%3f%z", "zone": None},
            "basic_date_time_no_millis": {"format": "%Y%m%dT%H%M%S%z", "zone": None},
            "basic_date_time_micros": {"format": "%Y%m%dT%H%M%S.%6f%z", "zone": None},
            "strict_date_time": {"format": "%Y-%m-%dT%H:%M:%S.%3f%:z", "zone": None},
            "strict_date_time_no_millis": {"format": "%Y-%m-%dT%H:%M:%S%:z", "zone": None},
            "strict_date_time_micros": {"format": "%Y-%m-%dT%H:%M:%S.%6f%:z", "zone": None},
            # Unix时间戳格式
            "epoch_micros": {"format": "Unix Timestamp", "zone": None},
            "Unix Time Stamp(milliseconds)": {"format": "Unix Timestamp", "zone": None},
            "epoch_millis": {"format": "Unix Timestamp", "zone": None},
            "epoch_second": {"format": "Unix Timestamp", "zone": None},
        }

        # 获取映射配置
        format_config = time_format_mapping.get(v3_time_format)
        if not format_config:
            # 如果找不到映射，使用默认配置
            return {
                "from": {"format": "%Y-%m-%d %H:%M:%S", "zone": 0},
                "interval_format": None,
                "to": "millis",
                "now_if_parse_failed": True,
            }

        # 构建V4 in_place_time_parsing配置
        return {
            "from": {"format": format_config["format"], "zone": format_config["zone"]},
            "interval_format": None,
            "to": "millis",
            "now_if_parse_failed": True,
        }

    def _build_built_in_fields_v4(self, built_in_config: dict) -> list:
        """
        构建V4版本的内置字段规则
        :param built_in_config: 内置配置，包含fields和time_field
        :return: 内置字段规则列表
        """
        rules = []

        # 处理内置字段
        built_in_fields = built_in_config.get("fields", [])
        for field in built_in_fields:
            field_name = field["field_name"]
            alias_name = field.get("alias_name", field_name)
            field_type = field["field_type"]

            # 跳过log、iterationIndex字段，它会在后面单独处理
            if field_name in ["log", "iterationIndex"]:
                continue

            rules.append(
                {
                    "input_id": "json_data",
                    "output_id": field_name,
                    "operator": {
                        "type": "assign",
                        "key_index": alias_name,
                        "alias": field_name,
                        "desc": field.get("description"),
                        "input_type": None,
                        "output_type": self._get_output_type(field_type),
                        "fixed_value": None,
                        "is_time_field": None,
                        "time_format": None,
                        "in_place_time_parsing": None,
                        "default_value": None,
                    },
                }
            )

        # 处理时间字段
        time_field = built_in_config.get("time_field")
        if time_field:
            time_field_name = time_field["field_name"]
            time_alias_name = time_field.get("alias_name", time_field_name)
            time_field_type = time_field["field_type"]

            # 获取V3时间格式并转换为V4格式
            v3_time_format = time_field.get("option", {}).get("time_format", "yyyy-MM-dd HH:mm:ss")
            v4_time_parsing = self._convert_v3_to_v4_time_format(v3_time_format)

            rules.append(
                {
                    "input_id": "json_data",
                    "output_id": time_field_name,
                    "operator": {
                        "type": "assign",
                        "key_index": time_alias_name,
                        "alias": time_field_name,
                        "desc": time_field.get("description"),
                        "input_type": None,
                        "output_type": self._get_output_type(time_field_type),
                        "fixed_value": None,
                        "is_time_field": None,
                        "time_format": None,
                        "in_place_time_parsing": v4_time_parsing,
                        "default_value": None,
                    },
                }
            )

        return rules

    @staticmethod
    def generate_hash_str(
        type: str, field_name: str, field_alias: str, is_case_sensitive: bool, tokenize_on_chars: str, length: int = 8
    ) -> str:
        """
        根据字段的配置生成简化的hash值
        因为监控的索引分裂的判断条件只对比了option的es_analyzer, 当参数变动的时候, 利用生成新的hash值来触发分裂索引
        """
        data = {
            "field_name": field_name,
            "field_alias": field_alias,
            "is_case_sensitive": is_case_sensitive,
            "tokenize_on_chars": tokenize_on_chars,
        }
        # 将字典按照key的顺序转换为字符串, 防止顺序不固定导致的hash值不一致
        data_str = "".join([f"{k}{v}" for k, v in sorted(data.items())])
        # 使用SHA256算法生成hash值
        hash_obj = hashlib.sha256(data_str.encode("utf-8"))
        hash_str = hash_obj.hexdigest()[:length]
        # 截取指定长度的子串作为hash值
        return f"{type}_{hash_str}"

    def generate_field_analyzer_name(
        self, field_name: str, field_alias: str, is_case_sensitive: bool, tokenize_on_chars: str
    ) -> str:
        """
        生成analyzer名称
        """
        # 当大小写敏感和自定义分词器都为空时, 不使用自定义analyzer
        if not is_case_sensitive and not tokenize_on_chars:
            return ""
        if tokenize_on_chars:
            # 将unicode编码的字符串转换为正常字符串
            tokenize_on_chars = unicode_str_decode(tokenize_on_chars)
        return self.generate_hash_str("analyzer", field_name, field_alias, is_case_sensitive, tokenize_on_chars)

    @staticmethod
    def generate_field_tokenizer_name(field_name: str, field_alias: str, tokenize_on_chars: str) -> str:
        """
        生成tokenizer名称, 因为analyzer和tokenizer的名称是一一对应的, 所以不用特别的hash值
        """
        if not tokenize_on_chars:
            return ""
        return f"tokenizer_{field_name}_{field_alias}"

    def generate_fields_analysis(self, fields: list[dict[str, Any]], etl_params: dict[str, Any]) -> dict[str, Any]:
        """
        构建各个字段的分词器
        """
        result = {
            "analyzer": {},
            "tokenizer": {},
        }
        # 保留原文, 处理原文分词器
        if etl_params.get("retain_original_text", False):
            analyzer_name = self.generate_field_analyzer_name(
                field_name="log",
                field_alias="data",
                is_case_sensitive=etl_params.get("original_text_is_case_sensitive", False),
                tokenize_on_chars=etl_params.get("original_text_tokenize_on_chars", ""),
            )
            if analyzer_name:
                tokenizer_name = self.generate_field_tokenizer_name(
                    field_name="log",
                    field_alias="data",
                    tokenize_on_chars=etl_params.get("original_text_tokenize_on_chars", ""),
                )
                result["analyzer"][analyzer_name] = {
                    "type": "custom",
                    "filter": [],
                }
                # 大小写不敏感的时候，需要加入lowercase
                if not etl_params.get("original_text_is_case_sensitive", False):
                    result["analyzer"][analyzer_name]["filter"].append("lowercase")
                if tokenizer_name:
                    result["analyzer"][analyzer_name]["tokenizer"] = tokenizer_name
                    original_text_tokenize_on_chars = etl_params.get("original_text_tokenize_on_chars", "")
                    if original_text_tokenize_on_chars:
                        original_text_tokenize_on_chars = unicode_str_decode(original_text_tokenize_on_chars)
                    result["tokenizer"][tokenizer_name] = {
                        "type": "char_group",
                        "tokenize_on_chars": [x for x in original_text_tokenize_on_chars],
                    }
                else:
                    # 自定义分词器为空时, 使用standard分词器, 不传es会报错
                    result["analyzer"][analyzer_name]["tokenizer"] = "standard"
        # 处理用户配置的清洗字段
        for field in fields:
            if not field.get("is_analyzed", False):
                continue
            analyzer_name = self.generate_field_analyzer_name(
                field_name=field.get("field_name", ""),
                field_alias=field.get("alias_name", ""),
                is_case_sensitive=field.get("is_case_sensitive", False),
                tokenize_on_chars=field.get("tokenize_on_chars", ""),
            )
            if not analyzer_name:
                continue
            tokenizer_name = self.generate_field_tokenizer_name(
                field_name=field.get("field_name", ""),
                field_alias=field.get("alias_name", ""),
                tokenize_on_chars=field.get("tokenize_on_chars", ""),
            )
            result["analyzer"][analyzer_name] = {
                "type": "custom",
                "filter": [],
            }
            # 大小写不敏感的时候，需要加入lowercase
            if not field.get("is_case_sensitive", False):
                result["analyzer"][analyzer_name]["filter"].append("lowercase")
            if tokenizer_name:
                result["analyzer"][analyzer_name]["tokenizer"] = tokenizer_name
                tokenize_on_chars = field.get("tokenize_on_chars", "")
                if tokenize_on_chars:
                    tokenize_on_chars = unicode_str_decode(tokenize_on_chars)
                result["tokenizer"][tokenizer_name] = {
                    "type": "char_group",
                    "tokenize_on_chars": [x for x in tokenize_on_chars],
                }
            else:
                result["analyzer"][analyzer_name]["tokenizer"] = "standard"
        return result

    def get_result_table_fields(self, fields, etl_params, built_in_config, es_version="5.X"):
        """
        META
        """
        # field_list
        field_list = copy.deepcopy(built_in_config.get("fields", []))
        etl_flat = etl_params.get("etl_flat", False)

        # 是否保留原文
        if etl_params.get("retain_original_text"):
            # 保留原文默认text类型大小写敏感
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
            field_list.append(original_text_field)

        # 是否保留用户未定义字段
        if etl_params.get("retain_extra_json"):
            field_list.append(
                {
                    "field_name": "__ext_json",
                    "field_type": "object",
                    "tag": "dimension",
                    "alias_name": "ext_json",
                    "description": _("用户未定义JSON字段"),
                    "option": {
                        "es_type": "object",
                        "es_doc_values": True,
                        "es_include_in_all": False,
                        "real_path": f"{self.separator_node_name}.ext_json",
                    }
                    if es_version.startswith("5.")
                    else {
                        "es_type": "object",
                        "es_doc_values": True,
                        "real_path": f"{self.separator_node_name}.ext_json",
                    },
                },
            )

        # 增加清洗失败标记
        if etl_params.get("record_parse_failure"):
            field_list.append(
                {
                    "field_name": PARSE_FAILURE_FIELD,
                    "field_type": "boolean",
                    "tag": "dimension",
                    "alias_name": PARSE_FAILURE_FIELD,
                    "description": _("清洗失败标记"),
                    "option": {
                        "es_type": "boolean",
                        "es_doc_values": True,
                        "es_include_in_all": False,
                        "real_path": f"{self.separator_node_name}.{PARSE_FAILURE_FIELD}",
                    }
                    if es_version.startswith("5.")
                    else {
                        "es_type": "boolean",
                        "es_doc_values": True,
                        "real_path": f"{self.separator_node_name}.{PARSE_FAILURE_FIELD}",
                    },
                },
            )

        # 默认使用上报时间做为数据时间
        time_field = built_in_config["time_field"]
        nano_time_field = None
        built_in_keys = FieldBuiltInEnum.get_choices()

        etl_field_index = 1
        clustering_default_fields = self._get_log_clustering_default_fields()
        is_nanos = False
        for field in fields:
            # 当在聚类场景的时候 不做下面的format操作
            if etl_flat and field["field_name"] in clustering_default_fields:
                field_list.append(field)
                continue
            # 过滤掉删除的字段
            if field["is_delete"]:
                continue

            # 设置字段的来源与目标存储
            source_field = field["field_name"]
            target_field = field["field_name"]
            if field.get("alias_name") and self.etl_config in [EtlConfig.BK_LOG_JSON]:
                target_field = field["alias_name"]

            if target_field.lower() in built_in_keys:
                raise ValidationError(_("字段不能与标准字段重复") + f":{target_field}")

            if not is_match_variate(target_field):
                raise ValidationError(_("字段名不符合变量规则"))

            if field["field_type"] == FieldDataTypeEnum.FLATTENED.value and is_version_less_than(
                es_version, MIN_FLATTENED_SUPPORT_VERSION
            ):
                raise ValidationError(_(f"ES版本{es_version}不支持 flattened 字段类型"))

            option = field.get("option") or {}

            # option, 非时间字段的option里的time_zone和time_format都为"", 不需要入库
            field_option = {k: v for k, v in option.items() if k not in ["time_zone", "time_format", "es_format"]}
            field_option["field_index"] = etl_field_index
            etl_field_index += 1

            # ES_TYPE
            field_option["es_type"] = FieldDataTypeEnum.get_es_field_type(
                field["field_type"], is_analyzed=field["is_analyzed"]
            )
            # 分词场景下, 自定义分词器
            if field["is_analyzed"]:
                analyzer_name = self.generate_field_analyzer_name(
                    field_name=field["field_name"],
                    field_alias=field.get("alias_name", ""),
                    is_case_sensitive=field.get("is_case_sensitive", False),
                    tokenize_on_chars=field.get("tokenize_on_chars", ""),
                )
                if analyzer_name:
                    field_option["es_analyzer"] = analyzer_name

            # ES_INCLUDE_IN_ALL
            if field["is_analyzed"] and es_version.startswith("5."):
                field_option["es_include_in_all"] = True

            # ES_DOC_VALUES
            field_option["es_doc_values"] = field["is_dimension"]

            if not etl_flat:
                # REAL_PATH
                field_option["real_path"] = f"{self.separator_node_name}.{source_field}"

            # 时间字段处理
            if field["is_time"]:
                time_field["alias_name"] = source_field
                if field_option.get("real_path"):
                    time_field["option"]["real_path"] = field_option["real_path"]
                time_field["option"]["time_zone"] = field["option"]["time_zone"]
                time_field["option"]["time_format"] = field["option"]["time_format"]
                time_field["option"]["field_index"] = field_option["field_index"]

                # 时间精度设置
                time_fmts = array_group(FieldDateFormatEnum.get_choices_list_dict(), "id", True)
                time_fmt = time_fmts.get(field["option"]["time_format"], {})
                if time_fmt.get("es_format", "epoch_millis") == "strict_date_optional_time_nanos":
                    time_field["option"]["es_format"] = "epoch_millis"
                    time_field["option"]["es_type"] = "date"
                    time_field["option"]["timestamp_unit"] = "ms"
                    is_nanos = True
                else:
                    time_field["option"]["es_format"] = time_fmt.get("es_format", "epoch_millis")
                    time_field["option"]["es_type"] = time_fmt.get("es_type", "date")
                    time_field["option"]["timestamp_unit"] = time_fmt.get("timestamp_unit", "ms")
                if time_fmt.get("is_custom"):
                    # 如果是自定义时间格式,加入time_layout字段
                    time_field["option"]["time_layout"] = time_fmt.get("description", "")

                # 注入默认值
                time_field["option"]["default_function"] = "fn:timestamp_from_utctime"

                # 删除原时间字段配置
                field_option["es_doc_values"] = False

                nano_time_field = copy.deepcopy(time_field)
                nano_time_field["field_name"] = "dtEventTimeStampNanos"
                nano_time_field["option"]["es_format"] = time_fmt.get("es_format", "epoch_millis")
                nano_time_field["option"]["es_type"] = time_fmt.get("es_type", "date")
                nano_time_field["option"]["timestamp_unit"] = time_fmt.get("timestamp_unit", "ms")

            # 加入字段列表
            field_list.append(
                {
                    "field_name": target_field,
                    "field_type": FieldDataTypeEnum.get_meta_field_type(field_option["es_type"]),
                    "tag": "dimension" if field_option.get("es_doc_values", True) else "metric",
                    "description": field.get("description"),
                    "option": field_option,
                }
            )

        field_list.append(time_field)
        if is_nanos:
            field_list.append(nano_time_field)
        return {"fields": field_list, "time_field": time_field}

    def update_or_create_result_table(
        self,
        instance: CollectorConfig | CollectorPlugin,
        table_id: str,
        storage_cluster_id: int,
        retention: int,
        allocation_min_days: int,
        storage_replies: int,
        fields: list = None,
        etl_params: dict = None,
        es_version: str = "5.X",
        hot_warm_config: dict = None,
        es_shards: int = settings.ES_SHARDS,
        index_settings: dict = None,
        sort_fields: list = None,
        target_fields: list = None,
        total_shards_per_node: int = None,
    ):
        """
        创建或更新结果表
        :param instance: 采集项配置/采集插件
        :param table_id: 结果表ID
        :param storage_cluster_id: 存储集群id
        :param retention: 数据保留时间
        :param allocation_min_days: 执行分配的等待天数
        :param storage_replies: 存储副本数量
        :param fields: 字段列表
        :param etl_params: 清洗配置
        :param es_version: es
        :param hot_warm_config: 冷热数据配置
        :param es_shards: es分片数
        :param index_settings: 索引配置
        :param sort_fields: 排序字段
        :param target_fields: 定位字段
        :param total_shards_per_node: 每个节点的分片总数
        """
        from apps.log_databus.handlers.collector import CollectorHandler

        # ES 配置
        es_config = get_es_config(instance.get_bk_biz_id())

        # 时间格式
        date_format = es_config["ES_DATE_FORMAT"]

        # ES-分片数
        instance.storage_shards_nums = es_shards

        # ES-副本数
        instance.storage_replies = storage_replies

        # 需要切分的大小阈值，单位（GB）
        if not instance.storage_shards_size:
            instance.storage_shards_size = es_config["ES_SHARDS_SIZE"]
        slice_size = instance.storage_shards_nums * instance.storage_shards_size

        # index分片时间间隔，单位（分钟）
        slice_gap = es_config["ES_SLICE_GAP"]

        # 自定义analysis配置
        analysis = self.generate_fields_analysis(fields=fields, etl_params=etl_params)
        # ES兼容—mapping设置
        param_mapping = {
            "dynamic_templates": [
                {
                    "strings_as_keywords": {
                        "match_mapping_type": "string",
                        "mapping": {"norms": "false", "type": "keyword"},
                    }
                }
            ],
        }
        if es_version.startswith("5."):
            param_mapping["_all"] = {"enabled": True}
            param_mapping["include_in_all"] = False

        params = {
            "bk_data_id": instance.bk_data_id,
            # 必须为 库名.表名
            "table_id": CollectorHandler.build_result_table_id(instance.get_bk_biz_id(), table_id),
            "table_name_zh": instance.get_name(),
            "is_custom_table": True,
            "schema_type": "free",
            "default_storage": "elasticsearch",
            "default_storage_config": {
                "cluster_id": storage_cluster_id,
                "storage_cluster_id": storage_cluster_id,
                "retention": retention,
                "date_format": date_format,
                "slice_size": slice_size,
                "slice_gap": slice_gap,
                "mapping_settings": param_mapping,
                "index_settings": {
                    "number_of_shards": instance.storage_shards_nums,
                    "number_of_replicas": instance.storage_replies,
                    "analysis": analysis,
                },
            },
            "is_time_field_only": True,
            "bk_biz_id": instance.get_bk_biz_id(),
            "label": instance.category_id,
            "option": {},
            "field_list": [],
            "warm_phase_days": 0,
            "warm_phase_settings": {},
        }
        index_settings = index_settings or {}
        if total_shards_per_node is not None and total_shards_per_node > 0:
            index_settings.update({"index.routing.allocation.total_shards_per_node": total_shards_per_node})
        params["default_storage_config"]["index_settings"].update(index_settings)

        # 增加冷热集群配置参数
        params = self._deal_hot_warm_config(allocation_min_days, hot_warm_config, params)

        # 获取结果表是否已经创建，如果创建则选择更新
        table_id = ""
        try:
            table_id = TransferApi.get_result_table({"table_id": params["table_id"]}).get("table_id")
        except ApiResultError:
            pass

        if not table_id and FeatureToggleObject.switch("log_v4_data_link", instance.get_bk_biz_id()):
            if hasattr(instance, "enable_v4"):
                instance.enable_v4 = True
                instance.save()

        # 获取清洗配置
        collector_scenario = CollectorScenario.get_instance(collector_scenario_id=instance.collector_scenario_id)
        built_in_config = collector_scenario.get_built_in_config(
            es_version,
            self.etl_config,
            sort_fields=sort_fields,
            target_fields=target_fields,
        )
        enable_v4 = getattr(instance, "enable_v4", False)
        result_table_config = self.get_result_table_config(
            fields, etl_params, built_in_config, es_version=es_version, enable_v4=enable_v4
        )
        is_nanos = False
        for rt_field in result_table_config["field_list"]:
            if rt_field["field_name"] == "dtEventTimeStampNanos":
                is_nanos = True
                break

        # 添加元数据路径配置到结果表配置中
        etl_path_regexp = etl_params.get("path_regexp", "")
        self.add_metadata_path_configs(etl_path_regexp, result_table_config)

        params.update(result_table_config)

        # 字段mapping优化
        for field in params["field_list"]:
            # 如果datetype不支持doc_values，则不设置doc_values，避免meta判断类型不一致创建新的index
            if "es_doc_values" in field.get("option", {}):
                if field["option"]["es_doc_values"] or field["option"]["es_type"] in ["date", "text"]:
                    del field["option"]["es_doc_values"]
            # 移除计分
            if "es_type" in field.get("option", {}) and field["option"]["es_type"] in ["text"]:
                field["option"]["es_norms"] = False

        # 时间默认为维度
        if "time_option" in params and "es_doc_values" in params["time_option"]:
            del params["time_option"]["es_doc_values"]

        # 兼容插件与采集项
        if not table_id:
            # 创建结果表
            params["is_enable"] = True
            table_id = TransferApi.create_result_table(params)["table_id"]
        else:
            # 更新结果表
            params["table_id"] = table_id
            from apps.log_databus.tasks.collector import modify_result_table

            modify_result_table.delay(params)
            cache.delete(CACHE_KEY_CLUSTER_INFO.format(table_id))

        if not instance.table_id:
            instance.table_id = table_id
            instance.save()

        if is_nanos:
            instance.is_nanos = True
            instance.save()

        return {"table_id": instance.table_id, "params": params}

    @staticmethod
    def get_max_fields_index(field_list: list[dict]):
        """
        得到field_list中最大的field_index
        """
        field_index_list = [0]
        for item in field_list:
            field_option = item.get("option")
            if not field_option:
                continue
            field_index = field_option.get("field_index")
            if field_index:
                field_index_list.append(field_index)
        return max(field_index_list)

    def add_metadata_path_configs(self, etl_path_regexp: str, result_table_config: dict):
        """
        往结果表中添加元数据的路径配置
        :param etl_path_regexp: 采集路径分割正则
        :param result_table_config: 需要更新的结果表配置
        :return:
        """
        if not etl_path_regexp:
            return

        # 加入路径的清洗配置
        result_table_config["option"]["separator_configs"] = [
            {
                "separator_node_name": self.path_separator_node_name,
                "separator_node_action": "regexp",
                "separator_node_source": "filename",
                "separator_regexp": etl_path_regexp,
            }
        ]

        field_list = result_table_config["field_list"]
        etl_field_index = self.get_max_fields_index(field_list) + 1

        pattern = re.compile(etl_path_regexp)
        match_fields = list(pattern.groupindex.keys())
        for field_name in match_fields:
            result_table_config["field_list"].append(
                {
                    "description": "",
                    "field_name": field_name,
                    "field_type": "string",
                    "option": {
                        "metadata_type": MetadataTypeEnum.PATH.value,
                        "es_doc_values": True,
                        "es_type": "keyword",
                        "field_index": etl_field_index,
                        "real_path": f"{self.path_separator_node_name}.{field_name}",
                    },
                    "tag": "dimension",
                }
            )
            etl_field_index += 1

    @classmethod
    def switch_result_table(cls, collector_config: CollectorConfig, is_enable=True):
        """
        起停result_table
        :param collector_config: 采集项
        :param is_enable: 是否有效
        :return:
        """
        params = {
            "bk_data_id": collector_config.bk_data_id,
            # 必须为 库名.表名
            "table_id": f"{collector_config.table_id}",
            "is_enable": is_enable,
            "bk_biz_id": collector_config.bk_biz_id,
        }
        TransferApi.switch_result_table(params)
        return True

    @classmethod
    def parse_result_table_config(cls, result_table_config, result_table_storage=None, fields_dict=None):
        """
        根据meta配置返回前端格式
        :param result_table_config metadata_get_result_table
        :param result_table_storage metadata_get_result_table_storage
        :param 从mappings拉取的的字段信息
        """
        fields_dict = fields_dict or {}

        # 存储配置 && 清洗配置
        collector_config = {"etl_params": result_table_config.get("option", {})}
        if result_table_storage:
            collector_config["storage_cluster_id"] = result_table_storage["cluster_config"]["cluster_id"]
            collector_config["storage_cluster_name"] = (
                result_table_storage["cluster_config"].get("display_name")
                or result_table_storage["cluster_config"]["cluster_name"]
            )
            collector_config["retention"] = result_table_storage["storage_config"].get("retention")
            collector_config["allocation_min_days"] = result_table_storage["storage_config"].get("warm_phase_days")

        # 字段
        built_in_fields = FieldBuiltInEnum.get_choices()
        field_list = []
        time_fields = [item for item in result_table_config["field_list"] if item["field_name"] == "dtEventTimeStamp"]
        if not time_fields:
            raise EtlParseTimeFieldException()
        time_field = copy.deepcopy(time_fields[0])

        # log clustering fields
        log_clustering_fields = cls._get_log_clustering_default_fields()
        for field in result_table_config["field_list"]:
            # 加入大小写敏感和分词配置
            final_field_dict = fields_dict.get(field["field_name"])
            if final_field_dict:
                field.update(
                    {
                        "is_case_sensitive": final_field_dict.get("is_case_sensitive", False),
                        "tokenize_on_chars": final_field_dict.get("tokenize_on_chars", ""),
                    }
                )

            # 判断是不是标准字段
            if not field.get("is_built_in", False):
                field["is_built_in"] = True if field["field_name"].lower() in built_in_fields else False

            # 聚类保留字段
            if field["field_name"] in log_clustering_fields:
                continue

            # 如果有指定别名，则需要调转位置(field_name：ES入库的字段名称；alias_name：数据源的字段名称)
            field_option = field.get("option", {})
            if field_option.get("real_path"):
                if cls.path_separator_node_name in field_option["real_path"]:
                    field["alias_name"] = field_option["real_path"].replace(f"{cls.path_separator_node_name}.", "")
                else:
                    field["alias_name"] = field_option["real_path"].replace(f"{cls.separator_node_name}.", "")

            if field.get("alias_name"):
                field["field_name"], field["alias_name"] = field["alias_name"], field["field_name"]

            # 如果别名与field_name相同，则不返回
            if field["field_name"] == field["alias_name"]:
                field["alias_name"] = ""

            # 时间字段处理
            field["is_time"] = False
            if field["field_name"] == time_field["alias_name"]:
                field["is_time"] = True
                field["is_dimension"] = True
                # option
                field_es_type = field["option"]["es_type"]
                field["option"] = time_field["option"]
                field["option"]["time_zone"] = int(time_field["option"]["time_zone"])
                field["option"]["es_type"] = field_es_type

            es_type = field_option.get("es_type", "keyword")

            # 字段类型
            field["field_type"] = FieldDataTypeEnum.get_field_type(es_type)

            # 分词字段设置
            field["is_analyzed"] = False
            if es_type == "text":
                field["is_analyzed"] = True
                field["is_dimension"] = False
            field["is_delete"] = field.get("is_delete", False)

            # 如果未设置维度，则获取es_doc_values的值
            if "is_dimension" not in field:
                field["is_dimension"] = field_option.get("es_doc_values", True)
                if field_option.get("es_type") == "text":
                    field["is_dimension"] = False

            field_list.append(field)

        # 添加删除字段
        if result_table_config["option"].get("separator_fields_remove"):
            fields_remove = result_table_config["option"]["separator_fields_remove"].split(",")
            for field_name in fields_remove:
                field_name = field_name.strip()
                if field_name == "":
                    continue

                field_info = copy.deepcopy(FIELD_TEMPLATE)
                field_info["field_name"] = field_name
                field_list.append(field_info)

        collector_config["fields"] = sorted(field_list, key=lambda x: x.get("option", {}).get("field_index", 0))
        return collector_config

    def _to_bkdata_assign(self, field):
        key = field.get("alias_name")
        if not key:
            key = field.get("field_name")
        return {
            "key": key,
            "assign_to": key,
            "type": self.get_es_field_type(field),
        }

    def _to_bkdata_assign_obj(self, field):
        key = field.get("alias_name")
        if not key:
            key = field.get("field_name")
        return {
            "key": key,
            "assign_to": key,
            "type": self.get_es_field_type(field),
        }

    def _get_built_in_fields_type_fields(self, built_in_fields):
        built_in_fields_type_object = [field for field in built_in_fields if field["field_type"] == "object"]
        built_in_fields_no_type_object = [field for field in built_in_fields if field["field_type"] != "object"]
        if len(built_in_fields_no_type_object) == 0:
            access_built_in_fields_type_object = []
        else:
            access_built_in_fields_type_object = [
                {
                    "type": "assign",
                    "subtype": "assign_json",
                    "label": "label2af98b",
                    "assign": [self._to_bkdata_assign_obj(field)],
                    "next": None,
                }
                for field in built_in_fields_type_object
            ]
        return built_in_fields_type_object, built_in_fields_no_type_object, access_built_in_fields_type_object

    def _to_bkdata_conf(self, time_field):
        return {
            "output_field_name": "timestamp",
            "time_format": time_field["option"]["time_format"],
            "timezone": time_field["option"]["time_zone"],
            "encoding": "UTF-8",
            "timestamp_len": 0,
            "time_field_name": time_field.get("alias_name"),
        }

    def _get_bkdata_default_fields(self, built_in_fields, time_field):
        result = [
            self._to_bkdata_assign(built_in_field)
            for built_in_field in built_in_fields
            if not built_in_field.get("flat_field", False)
        ]
        if not time_field.get("option", {}).get("real_path"):
            result.append(self._to_bkdata_assign(time_field))
        result.append(
            self._to_bkdata_assign({"field_name": "time", "alias_name": "time", "option": {"es_type": "long"}})
        )
        return result

    @classmethod
    def _get_log_clustering_default_fields(cls):
        return {field["field_name"] for field in CollectorScenario.log_clustering_fields()}

    def get_path_field_configs(self, etl_path_regexp: str, field_list: list[dict]):
        """
        获取路径清洗配置
        """
        if not etl_path_regexp:
            return []

        etl_field_index = self.get_max_fields_index(field_list) + 1
        path_field_config_list = []
        pattern = re.compile(etl_path_regexp)
        match_fields = list(pattern.groupindex.keys())
        for field_name in match_fields:
            path_field_config_list.append(
                {
                    "description": "",
                    "field_name": field_name,
                    "field_type": "string",
                    "option": {
                        "metadata_type": MetadataTypeEnum.PATH.value,
                        "es_doc_values": True,
                        "es_type": "keyword",
                        "field_index": etl_field_index,
                        "real_path": f"{self.path_separator_node_name}.{field_name}",
                    },
                    "tag": "dimension",
                }
            )
            etl_field_index += 1
        return path_field_config_list

    def separate_fields_config(self, field_list: list[dict]):
        """
        把log和path的字段配置分开
        """
        log_fields = []
        path_fields = []
        for item in field_list:
            field_option = item.get("option") or {}
            if self.path_separator_node_name in field_option.get("real_path", ""):
                path_fields.append(item)
            else:
                log_fields.append(item)
        return log_fields, path_fields

    def add_path_configs(self, path_fields: list[dict], etl_path_regexp: str, bkdata_json_config):
        """
        把路径配置添加到bkdata_json_config中
        """
        if not etl_path_regexp or not path_fields:
            return
        path_config = {
            "type": "access",
            "subtype": "access_obj",
            "label": "labeld3fa8a",
            "key": "filename",
            "result": "filename",
            "default_type": "null",
            "default_value": "",
            "next": {
                "type": "fun",
                "method": "regex_extract",
                "label": "label533df5",
                "args": [
                    {
                        "result": "filename_item",
                        "keys": [
                            field["alias_name"] if field["alias_name"] else field["field_name"] for field in path_fields
                        ],
                        "regexp": etl_path_regexp.replace("(?P<", "(?<"),
                    }
                ],
                "next": {
                    "type": "assign",
                    "subtype": "assign_obj",
                    "label": "label04104e",
                    "assign": [self._to_bkdata_assign(field) for field in path_fields],
                    "next": None,
                },
            },
        }
        bkdata_json_config["extract"]["next"]["next"].append(path_config)

    @classmethod
    def _deal_hot_warm_config(cls, allocation_min_days: int, hot_warm_config: dict, params: dict) -> dict:
        # 是否启用冷热集群
        if not allocation_min_days:
            return params

        if not hot_warm_config or not hot_warm_config.get("is_enabled"):
            # 检查集群是否支持冷热数据功能
            raise HotColdCheckException()

        # 对于新数据，路由到热节点
        params["default_storage_config"]["index_settings"].update(
            {
                f"index.routing.allocation.include.{hot_warm_config['hot_attr_name']}": hot_warm_config[
                    "hot_attr_value"
                ],
            }
        )
        # n天后的数据，路由到冷节点
        params["default_storage_config"].update(
            {
                "warm_phase_days": allocation_min_days,
                "warm_phase_settings": {
                    "allocation_attr_name": hot_warm_config["warm_attr_name"],
                    "allocation_attr_value": hot_warm_config["warm_attr_value"],
                    "allocation_type": "include",
                },
            }
        )
        return params

    @classmethod
    def update_or_create_pattern_result_table(
        cls,
        instance: CollectorConfig,
        table_id: str,
        storage_cluster_id: int,
        allocation_min_days: int,
        storage_replies: int,
        es_version: str = "5.X",
        hot_warm_config: dict = None,
        es_shards: int = settings.ES_SHARDS,
        index_settings: dict = None,
        total_shards_per_node: int = None,
        retention: int = 180,
    ):
        """
        创建或更新 Pattern 结果表
        :param instance: 采集项配置/采集插件
        :param table_id: 结果表ID
        :param storage_cluster_id: 存储集群id
        :param retention: 数据保留时间
        :param allocation_min_days: 执行分配的等待天数
        :param storage_replies: 存储副本数量
        :param es_version: es
        :param hot_warm_config: 冷热数据配置
        :param es_shards: es分片数
        :param index_settings: 索引配置
        :param total_shards_per_node: 每个节点的分片总数
        """

        # ES 配置
        es_config = get_es_config(instance.get_bk_biz_id())

        # 时间格式
        date_format = es_config["ES_DATE_FORMAT"]

        # 需要切分的大小阈值，单位（GB）
        storage_shards_size = instance.storage_shards_size or es_config["ES_SHARDS_SIZE"]
        slice_size = es_shards * storage_shards_size

        # index分片时间间隔，单位（分钟）
        slice_gap = es_config["ES_SLICE_GAP"]

        # ES兼容—mapping设置
        param_mapping = {
            "dynamic_templates": [
                {
                    "strings_as_keywords": {
                        "match_mapping_type": "string",
                        "mapping": {"norms": "false", "type": "keyword"},
                    }
                }
            ],
        }
        if es_version.startswith("5."):
            param_mapping["_all"] = {"enabled": True}
            param_mapping["include_in_all"] = False

        params = {
            "bk_data_id": instance.bk_data_id,
            # 必须为 库名.表名
            "table_id": table_id,
            "table_name_zh": f"{instance.get_name()}_Pattern",
            "is_custom_table": True,
            "schema_type": "free",
            "default_storage": "elasticsearch",
            "default_storage_config": {
                "cluster_id": storage_cluster_id,
                "storage_cluster_id": storage_cluster_id,
                "retention": retention,
                "date_format": date_format,
                "slice_size": slice_size,
                "slice_gap": slice_gap,
                "mapping_settings": param_mapping,
                "index_settings": {
                    "number_of_shards": es_shards,
                    "number_of_replicas": storage_replies,
                },
            },
            "is_time_field_only": True,
            "bk_biz_id": instance.get_bk_biz_id(),
            "label": instance.category_id,
            "option": {
                "time_field": {"unit": "millisecond", "name": "dtEventTimeStamp", "type": "date"},
                "es_unique_field_list": ["signature"],
            },
            "time_alias_name": "utctime",
            "time_option": {
                "es_type": "date",
                "es_format": "epoch_millis",
                "time_format": "yyyy-MM-dd HH:mm:ss",
                "time_zone": 0,
            },
            "field_list": [
                {
                    "field_name": "dtEventTimeStamp",
                    "field_type": "timestamp",
                    "tag": "dimension",
                    "alias_name": "utctime",
                    "description": "数据时间",
                    "option": {
                        "es_type": "date",
                        "es_format": "epoch_millis",
                        "time_format": "yyyy-MM-dd HH:mm:ss",
                        "time_zone": 0,
                    },
                },
                {
                    "field_name": "log",
                    "field_type": "string",
                    "tag": "metric",
                    "alias_name": "data",
                    "description": "log",
                    "option": build_es_option_type("text", es_version),
                },
                {
                    "field_name": "pattern",
                    "field_type": "string",
                    "tag": "metric",
                    "alias_name": "pattern",
                    "description": "pattern",
                    "option": build_es_option_type("keyword", es_version),
                },
                {
                    "field_name": "signature",
                    "field_type": "string",
                    "tag": "metric",
                    "alias_name": "signature",
                    "description": "signature",
                    "option": build_es_option_type("keyword", es_version),
                },
            ],
            "warm_phase_days": 0,
            "warm_phase_settings": {},
        }
        index_settings = index_settings or {}
        if total_shards_per_node is not None and total_shards_per_node > 0:
            index_settings.update({"index.routing.allocation.total_shards_per_node": total_shards_per_node})
        params["default_storage_config"]["index_settings"].update(index_settings)

        # 增加冷热集群配置参数
        params = cls._deal_hot_warm_config(allocation_min_days, hot_warm_config, params)

        # 获取结果表是否已经创建，如果创建则选择更新
        table_id = ""
        try:
            table_id = TransferApi.get_result_table({"table_id": params["table_id"]}).get("table_id")
        except ApiResultError:
            pass

        # 兼容插件与采集项
        if not table_id:
            # 创建结果表
            params["is_enable"] = True
            table_id = TransferApi.create_result_table(params)["table_id"]
        else:
            # 更新结果表
            params["table_id"] = table_id
            from apps.log_databus.tasks.collector import modify_result_table

            modify_result_table.delay(params)
            cache.delete(CACHE_KEY_CLUSTER_INFO.format(table_id))

        return {"table_id": table_id, "params": params}
