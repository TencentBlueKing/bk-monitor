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
import datetime
import functools
import re
from collections import defaultdict
from typing import Any

import arrow
import pytz
from django.conf import settings
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from apps.api import BkDataStorekitApi, BkLogApi, TransferApi
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import DIRECT_ESQUERY_SEARCH
from apps.log_clustering.handlers.dataflow.constants import PATTERN_SEARCH_FIELDS
from apps.log_clustering.models import ClusteringConfig
from apps.log_search.constants import (
    BKDATA_ASYNC_CONTAINER_FIELDS,
    BKDATA_ASYNC_FIELDS,
    DEFAULT_INDEX_OBJECT_FIELDS_PRIORITY,
    DEFAULT_INDEX_SET_FIELDS_CONFIG_NAME,
    DEFAULT_TIME_FIELD,
    DEFAULT_TIME_FIELD_ALIAS_NAME,
    FEATURE_ASYNC_EXPORT_COMMON,
    LOG_ASYNC_FIELDS,
    OPERATORS,
    FieldBuiltInEnum,
    FieldDataTypeEnum,
    SearchScopeEnum,
)
from apps.log_search.exceptions import (
    FieldsDateNotExistException,
    IndexSetNotHaveConflictIndex,
    MultiFieldsErrorException,
)
from apps.log_search.models import (
    IndexSetFieldsConfig,
    LogIndexSet,
    LogIndexSetData,
    Scenario,
    StorageClusterRecord,
    UserIndexSetFieldsConfig,
)
from apps.log_search.utils import split_object_fields
from apps.utils.cache import cache_one_minute, cache_ten_minute
from apps.utils.codecs import unicode_str_encode
from apps.utils.drf import custom_params_valid
from apps.utils.local import (
    get_local_param,
    get_request_app_code,
    get_request_external_username,
    get_request_username,
)
from apps.utils.log import logger
from apps.utils.thread import MultiExecuteFunc
from apps.utils.time_handler import generate_time_range

INNER_COMMIT_FIELDS = ["dteventtime", "report_time"]
INNER_PRODUCE_FIELDS = [
    "dteventtimestamp",
    "dtEventTimeStamp",
    "_iteration_idx",
    "iterationIndex",
    "gseindex",
    "gseIndex",
    "timestamp",
]
OUTER_PRODUCE_FIELDS = []
TIME_TYPE = ["date"]
TRACE_SCOPE = ["trace", "trace_detail", "trace_detail_log"]


class MappingHandlers:
    def __init__(
        self,
        indices,
        index_set_id,
        scenario_id,
        storage_cluster_id,
        time_field="",
        start_time="",
        end_time="",
        bk_biz_id=None,
        only_search=False,
        index_set=None,
        time_zone=None,
    ):
        self.indices = indices
        self.index_set_id = index_set_id
        self.bk_biz_id = bk_biz_id
        self.scenario_id = scenario_id
        self.storage_cluster_id = storage_cluster_id
        self.time_field = time_field
        self.start_time = start_time
        self.end_time = end_time
        self.time_zone: str = time_zone or get_local_param("time_zone", settings.TIME_ZONE)
        # 最终字段
        self._final_fields = None

        # 仅查询使用
        self.only_search = only_search

        self._index_set = index_set

    def check_fields_not_conflict(self, raise_exception=True):
        """
        check_fields_not_conflict
        @param raise_exception:
        @return:
        """
        if len(self.indices.split(",")) == 1:
            return True

        mapping_list: list = BkLogApi.mapping(
            {
                "indices": self.indices,
                "scenario_id": self.scenario_id,
                "storage_cluster_id": self.storage_cluster_id,
                "bkdata_authentication_method": "user",
            }
        )
        all_propertys = self._get_all_property(mapping_list)
        conflict_result = defaultdict(set)
        for property in all_propertys:
            self._get_sub_fields(conflict_result, property, "")
        have_conflict = {key: list(type_list) for key, type_list in conflict_result.items() if len(type_list) > 1}
        if have_conflict:
            if raise_exception:
                raise IndexSetNotHaveConflictIndex(data=have_conflict)
            return False

    def is_nested_field(self, field):
        parent_path, *_ = field.split(".")
        return parent_path in self.nested_fields

    @cached_property
    def nested_fields(self):
        """
        nested_fields
        @return:
        """
        mapping_list: list = self._get_mapping()
        property_dict: dict = self.find_merged_property(mapping_list)
        nested_fields = set()
        for key, value in property_dict.items():
            if FieldDataTypeEnum.NESTED.value == value.get("type", ""):
                nested_fields.add(key)
        return nested_fields

    def _get_sub_fields(self, conflict_result, properties, last_key):
        for property_key, property_define in properties.items():
            if "properties" in property_define:
                self._get_sub_fields(conflict_result, property_define["properties"], f"{last_key}.{property_key}")
                continue
            key = f"{last_key}.{property_key}" if last_key else property_key
            conflict_result[key].add(property_define["type"])

    def add_clustered_fields(self, field_list):
        clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=self.index_set_id, raise_exception=False)
        if clustering_config and clustering_config.clustered_rt:
            all_field_names = [field["field_name"] for field in field_list if "field_name" in field]
            for field in PATTERN_SEARCH_FIELDS:
                if field["field_name"] not in all_field_names:
                    field_list.append(field)
            return field_list
        return field_list

    def virtual_fields(self, field_list):
        """
        virtual_fields
        @param field_list:
        @return:
        """
        fields = {f["field_name"] for f in field_list}
        virtual_predicate = [{"serverIp", "cloudId"}, {"ip", "cloudid"}, {"ip"}]
        if any([fields.issuperset(predicate) for predicate in virtual_predicate]):
            field_list.append(
                {
                    "field_type": "__virtual__",
                    "field_name": "__module__",
                    "field_alias": _("模块"),
                    "is_display": False,
                    "is_editable": True,
                    "tag": "dimension",
                    "es_doc_values": False,
                    "is_analyzed": False,
                }
            )
            field_list.append(
                {
                    "field_type": "__virtual__",
                    "field_name": "__set__",
                    "field_alias": _("集群"),
                    "is_display": False,
                    "is_editable": True,
                    "tag": "dimension",
                    "es_doc_values": False,
                    "is_analyzed": False,
                }
            )
        if "bk_host_id" in fields:
            field_list.append(
                {
                    "field_type": "__virtual__",
                    "field_name": "__ipv6__",
                    "field_alias": "IPv6",
                    "is_display": False,
                    "is_editable": True,
                    "tag": "dimension",
                    "es_doc_values": False,
                    "is_analyzed": False,
                }
            )
        return field_list

    @property
    def final_fields(self):
        """添加最终字段的缓存"""
        if self._final_fields is None:
            self._final_fields = self.get_final_fields()
        # 使用深拷贝,避免上文的内容被修改
        final_fields_list = copy.deepcopy(self._final_fields)
        return final_fields_list

    def get_final_fields(self):
        """获取最终字段"""
        mapping_list: list = self._get_mapping()
        # 未获取到mapping信息 提前返回
        if not mapping_list:
            return []
        property_dict: dict = self.find_merged_property(mapping_list)
        fields_result: list = MappingHandlers.get_all_index_fields_by_mapping(property_dict)
        built_in_fields = FieldBuiltInEnum.get_choices()
        fields_list: list = [
            {
                "field_type": field["field_type"],
                "field_name": field["field_name"],
                "field_alias": field.get("field_alias"),
                "is_display": False,
                "is_editable": True,
                "tag": field.get("tag", "metric"),
                "origin_field": field.get("path", ""),
                "es_doc_values": field.get("es_doc_values", False),
                "is_analyzed": field.get("is_analyzed", False),
                "field_operator": OPERATORS.get(field["field_type"], []),
                "is_built_in": field["field_name"].lower() in built_in_fields,
                "is_case_sensitive": field.get("is_case_sensitive", False),
                "tokenize_on_chars": field.get("tokenize_on_chars", ""),
            }
            for field in fields_result
        ]
        fields_list = self.add_clustered_fields(fields_list)
        fields_list = self.virtual_fields(fields_list)
        if not self.only_search:
            fields_list = self._combine_description_field(fields_list)
        fields_list = self._combine_fields(fields_list)

        for field in fields_list:
            # 判断是否为内置字段
            field_name = field.get("field_name", "").lower()
            field["is_built_in"] = field_name in built_in_fields or field_name.startswith("__ext.")

        return fields_list

    def get_all_fields_by_index_id(self, scope=SearchScopeEnum.DEFAULT.value, is_union_search=False):
        """
        get_all_fields_by_index_id
        @param scope:
        @return:
        """
        final_fields_list = self.final_fields
        # search_context情况，默认只显示log字段
        # if scope in CONTEXT_SCOPE:
        #     return self._get_context_fields(final_fields_list)

        # 其它情况
        if final_fields_list:
            # mapping拉取到数据时才创建配置
            default_config = self.get_or_create_default_config(scope=scope)
            display_fields = default_config.display_fields
        else:
            display_fields = []
        if is_union_search:
            return final_fields_list, display_fields

        username = get_request_external_username() or get_request_username()
        user_index_set_config_obj = UserIndexSetFieldsConfig.get_config(
            index_set_id=self.index_set_id, username=username, scope=scope
        )
        # 用户已手动配置字段
        if user_index_set_config_obj:
            display_fields = user_index_set_config_obj.display_fields
            if not display_fields:
                # 如果用户配置为空，使用默认配置
                __, display_fields_list = self.get_default_fields(scope=scope)
            else:
                # 检查display_fields每个字段是否存在
                final_fields = [i["field_name"].lower() for i in final_fields_list]
                # 对object类型的字段进行拆分
                final_fields = split_object_fields(final_fields)
                display_fields_list = [
                    _filed_obj for _filed_obj in display_fields if _filed_obj.lower() in final_fields
                ]
            # 字段不一致更新字段, 并防止获取mapping失败导致的final_fields_list为空进而将用户默认配置给冲掉
            if final_fields_list and display_fields != display_fields_list:
                user_index_set_config_obj.display_fields = display_fields_list
                user_index_set_config_obj.save()

            for final_field in final_fields_list:
                field_name = final_field["field_name"]
                if field_name in display_fields_list:
                    final_field["is_display"] = True
            return final_fields_list, display_fields_list

        return final_fields_list, display_fields

    def get_or_create_default_config(self, scope=SearchScopeEnum.DEFAULT.value):
        """获取默认配置"""
        # 获取当前请求用户(兼容外部用户)
        username = get_request_external_username() or get_request_username()
        final_fields_list, display_fields = self.get_default_fields(scope=scope)
        default_sort_tag: bool = False
        # 判断是否有gseindex和_iteration_idx字段
        final_fields_list = [i["field_name"] for i in final_fields_list]
        if ("gseindex" in final_fields_list and "_iteration_idx" in final_fields_list) or (
            "gseIndex" in final_fields_list and "iterationIndex" in final_fields_list
        ):
            default_sort_tag = True
        sort_list = self.get_default_sort_list(
            index_set_id=self.index_set_id, scenario_id=self.scenario_id, default_sort_tag=default_sort_tag
        )
        obj, created = IndexSetFieldsConfig.objects.get_or_create(
            index_set_id=self.index_set_id,
            name=DEFAULT_INDEX_SET_FIELDS_CONFIG_NAME,
            scope=scope,
            source_app_code=get_request_app_code(),
            defaults={"display_fields": display_fields, "sort_list": sort_list},
        )
        # 创建的时候, 如果存在外部用户, 手动修改created_by为外部用户
        if created:
            obj.created_by = username
            obj.save()

        return obj

    @property
    def index_set(self):
        if not self._index_set:
            self._index_set = LogIndexSet.objects.filter(index_set_id=self.index_set_id).first()
        return self._index_set

    def get_default_sort_list(
        self,
        index_set_id: int = None,
        scenario_id: str = None,
        default_sort_tag: bool = False,
    ):
        """默认字段排序规则"""
        time_field = self.get_time_field(index_set_id, self.index_set)
        if not time_field:
            return []

        # 先看索引集有没有配排序字段
        sort_fields = self.index_set.sort_fields if self.index_set else []
        if sort_fields:
            return [[field, "desc"] for field in sort_fields]

        if default_sort_tag and scenario_id == Scenario.BKDATA:
            return [[time_field, "desc"], ["gseindex", "desc"], ["_iteration_idx", "desc"]]
        if default_sort_tag and scenario_id == Scenario.LOG:
            return [[time_field, "desc"], ["gseIndex", "desc"], ["iterationIndex", "desc"]]
        return [[time_field, "desc"]]

    def get_default_fields(self, scope=SearchScopeEnum.DEFAULT.value):
        """获取索引集默认字段"""
        final_fields_list = self.final_fields
        if scope == SearchScopeEnum.SEARCH_CONTEXT.value:
            for _field in final_fields_list:
                if _field["field_name"] == "log":
                    _field["is_display"] = True
                    return final_fields_list, ["log"]
            return final_fields_list, []
        display_fields_list = [self.get_time_field(self.index_set_id, self.index_set)]
        if self._get_object_field(final_fields_list):
            display_fields_list.append(self._get_object_field(final_fields_list))
        display_fields_list.extend(self._get_text_fields(final_fields_list))

        for field_n in range(len(final_fields_list)):
            field_name = final_fields_list[field_n]["field_name"]
            if field_name in display_fields_list:
                final_fields_list[field_n]["is_display"] = True
            else:
                final_fields_list[field_n]["is_display"] = False

        return final_fields_list, display_fields_list

    @classmethod
    def get_time_field(cls, index_set_id: int, index_set_obj: LogIndexSet = None):
        """获取索引时间字段"""
        index_set_obj: LogIndexSet = index_set_obj or LogIndexSet.objects.filter(index_set_id=index_set_id).first()
        if index_set_obj.scenario_id in [Scenario.BKDATA, Scenario.LOG]:
            return "dtEventTimeStamp"

        if index_set_obj.time_field:
            return index_set_obj.time_field
        # 遍历index_set_data取任意一个不为空的时间字段
        time_field_list = LogIndexSetData.objects.filter(index_set_id=index_set_id).values_list("time_field", flat=True)
        for time_field in time_field_list:
            if time_field:
                return time_field
        return

    def _get_object_field(self, final_fields_list):
        """获取对象字段"""
        final_field_name_list = [field["field_name"] for field in final_fields_list]
        for field in DEFAULT_INDEX_OBJECT_FIELDS_PRIORITY:
            if field in final_field_name_list:
                return field
        return None

    def _get_text_fields(self, final_fields_list: list):
        """获取text类型字段"""
        final_field_name_list = [field["field_name"] for field in final_fields_list]
        if "log" in final_field_name_list:
            return ["log"]
        type_text_fields = [
            field["field_name"]
            for field in final_fields_list
            if field["field_type"] == "text" and not field["field_name"].startswith("_")
        ]
        if type_text_fields:
            return type_text_fields[:2]
        type_keyword_fields = [
            field["field_name"]
            for field in final_fields_list
            if field["field_type"] == "keyword" and not field["field_name"].startswith("_")
        ]
        return type_keyword_fields[:2]

    def _get_mapping(self):
        # 当没有指定时间范围时，默认获取最近一天的mapping
        if not self.start_time and not self.end_time:
            start_time, end_time = generate_time_range("1d", "", "", self.time_zone)
        else:
            try:
                start_time = arrow.get(int(self.start_time)).to(self.time_zone)
                end_time = arrow.get(int(self.end_time)).to(self.time_zone)
            except ValueError:
                start_time = arrow.get(self.start_time, tzinfo=self.time_zone)
                end_time = arrow.get(self.end_time, tzinfo=self.time_zone)

        start_time_format = start_time.floor("hour").strftime("%Y-%m-%d %H:%M:%S")
        end_time_format = end_time.ceil("hour").strftime("%Y-%m-%d %H:%M:%S")

        return self._get_latest_mapping(
            indices=self.indices,
            start_time=start_time_format,
            end_time=end_time_format,
            only_search=self.only_search,
        )

    def _direct_latest_mapping(self, params):
        from apps.log_esquery.esquery.esquery import EsQuery
        from apps.log_esquery.serializers import EsQueryMappingAttrSerializer

        if FeatureToggleObject.switch(DIRECT_ESQUERY_SEARCH, self.bk_biz_id):
            data = custom_params_valid(EsQueryMappingAttrSerializer, params)
            latest_mapping = EsQuery(data).mapping()
        else:
            latest_mapping = BkLogApi.mapping(params)
        return latest_mapping

    @cache_one_minute("latest_mapping_key_{indices}_{start_time}_{end_time}_{only_search}", need_md5=True)
    def _get_latest_mapping(self, indices, start_time, end_time, only_search=False):  # noqa
        storage_cluster_record_objs = StorageClusterRecord.objects.none()

        if self.start_time:
            try:
                tz_info = pytz.timezone(get_local_param("time_zone", settings.TIME_ZONE))
                if isinstance(self.start_time, int | float) or (
                    isinstance(self.start_time, str) and self.start_time.isdigit()
                ):
                    start_datetime = arrow.get(int(self.start_time)).to(tz=tz_info).datetime
                else:
                    start_datetime = arrow.get(self.start_time).replace(tzinfo=tz_info).datetime
                storage_cluster_record_objs = StorageClusterRecord.objects.filter(
                    index_set_id=int(self.index_set_id), created_at__gt=(start_datetime - datetime.timedelta(hours=1))
                ).exclude(storage_cluster_id=self.storage_cluster_id)
            except Exception as e:  # pylint: disable=broad-except
                logger.exception(f"[_multi_mappings] parse time error -> e: {e}")

        params = {
            "indices": self.indices,
            "scenario_id": self.scenario_id,
            "storage_cluster_id": self.storage_cluster_id,
            "time_zone": self.time_zone,
            "start_time": start_time,
            "end_time": end_time,
            "add_settings_details": False if only_search else True,
        }
        if not storage_cluster_record_objs.exists():
            return self._direct_latest_mapping(params)
        multi_execute_func = MultiExecuteFunc()
        multi_num = 1
        storage_cluster_ids = {self.storage_cluster_id}

        # 获取当前使用的存储集群数据
        multi_execute_func.append(
            result_key=f"multi_mappings_{multi_num}", func=self._direct_latest_mapping, params=params
        )

        # 获取历史使用的存储集群数据
        for storage_cluster_record_obj in storage_cluster_record_objs:
            if storage_cluster_record_obj.storage_cluster_id not in storage_cluster_ids:
                multi_params = copy.deepcopy(params)
                multi_params["storage_cluster_id"] = storage_cluster_record_obj.storage_cluster_id
                multi_num += 1
                multi_execute_func.append(
                    result_key=f"multi_mappings_{multi_num}", func=self._direct_latest_mapping, params=multi_params
                )
                storage_cluster_ids.add(storage_cluster_record_obj.storage_cluster_id)

        multi_result = multi_execute_func.run()

        # 合并多个集群的检索结果
        merge_result = list()
        try:
            for _key, _result in multi_result.items():
                merge_result.extend(_result)
        except Exception as e:
            logger.error(f"[_multi_get_latest_mapping] error -> e: {e}")
            raise MultiFieldsErrorException()
        return merge_result

    @staticmethod
    def _get_context_fields(final_fields_list):
        for _field in final_fields_list:
            if _field["field_name"] == "log":
                _field["is_display"] = True
                return final_fields_list, ["log"]
        return final_fields_list, []

    @classmethod
    def is_case_sensitive(cls, field_dict: dict[str, Any]) -> bool:
        # 历史清洗的格式内, 未配置大小写敏感和分词器的字段, 所以不存在analyzer和analyzer_details
        if not field_dict.get("analyzer"):
            return False
        if not field_dict.get("analyzer_details"):
            return False
        return "lowercase" not in field_dict["analyzer_details"].get("filter", [])

    @classmethod
    def tokenize_on_chars(cls, field_dict: dict[str, Any]) -> str:
        # 历史清洗的格式内, 未配置大小写敏感和分词器的字段, 所以不存在analyzer,analyzer_details,tokenizer_details
        if not field_dict.get("analyzer_details"):
            return ""
        # tokenizer_details在analyzer_details中
        if not field_dict["analyzer_details"].get("tokenizer_details", {}):
            return ""
        if not field_dict.get("analyzer"):
            return ""
        elif field_dict.get("analyzer") == "bkbase_custom":
            return field_dict["analyzer_details"].get("tokenizer_details", {}).get("tokenize_on_chars", "")
        result = "".join(field_dict["analyzer_details"].get("tokenizer_details", {}).get("tokenize_on_chars", []))
        return unicode_str_encode(result)

    @classmethod
    def get_all_index_fields_by_mapping(cls, properties_dict: dict) -> list:
        """
        通过mapping集合获取所有的index下的fields
        :return:
        """
        fields_result: list = list()
        for key in properties_dict.keys():
            k_keys: list = properties_dict[key].keys()
            if "properties" in k_keys:
                fields_result.extend(cls.get_fields_recursively(p_key=key, properties_dict=properties_dict[key]))
                continue
            if "type" in k_keys:
                field_type: str = properties_dict[key]["type"]
                latest_field_type: str = properties_dict[key]["latest_field_type"]
                doc_values_farther_dict: dict = properties_dict[key]
                doc_values = False

                if isinstance(doc_values_farther_dict, dict):
                    doc_values = doc_values_farther_dict.get("doc_values", True)

                es_doc_values = doc_values
                if field_type in ["text", "object"]:
                    es_doc_values = False

                is_case_sensitive = cls.is_case_sensitive(properties_dict[key])
                tokenize_on_chars = cls.tokenize_on_chars(properties_dict[key])

                # @TODO tag：兼容前端代码，后面需要删除
                tag = "metric"
                if field_type == "date":
                    tag = "timestamp"
                elif es_doc_values:
                    tag = "dimension"

                data: dict[str, Any] = dict()
                data.update(
                    {
                        "field_type": field_type,
                        "field_name": key,
                        "field_alias": "",
                        "description": "",
                        "es_doc_values": es_doc_values,
                        "tag": tag,
                        "is_analyzed": cls._is_analyzed(latest_field_type),
                        "latest_field_type": latest_field_type,
                        "is_case_sensitive": is_case_sensitive,
                        "tokenize_on_chars": tokenize_on_chars,
                    }
                )
                if field_type == "alias":
                    data["path"] = properties_dict[key]["path"]
                fields_result.append(data)
                continue
        return fields_result

    @staticmethod
    def _is_analyzed(field_type: str):
        return field_type == "text"

    @classmethod
    def get_fields_recursively(cls, p_key, properties_dict: dict, field_types=None) -> list:
        """
        递归拿取mapping集合获取所有的index下的fields
        :param p_key:
        :param properties_dict:
        :param field_types:
        :return:
        """
        fields_result: list = list()
        common_index: int = 1
        for key in properties_dict.keys():
            if "properties" in key:
                fields_result.extend(cls.get_fields_recursively(p_key=p_key, properties_dict=properties_dict[key]))
            else:
                if key in ["include_in_all"] or not isinstance(properties_dict[key], dict):
                    continue
                k_keys: list = properties_dict[key].keys()
                filed_name: str = f"{p_key}.{key}"
                if "type" in k_keys:
                    field_type: str = properties_dict[key]["type"]
                    if field_types and field_type not in field_types:
                        continue
                    doc_values_farther_dict: dict = properties_dict[key]
                    doc_values = None
                    if isinstance(doc_values_farther_dict, dict):
                        doc_values = doc_values_farther_dict.get("doc_values", True)

                    es_doc_values = doc_values
                    if field_type in ["text", "object"]:
                        es_doc_values = False

                    # @TODO tag：兼容前端代码，后面需要删除
                    tag = "metric"
                    if field_type == "date":
                        tag = "timestamp"
                    elif es_doc_values:
                        tag = "dimension"

                    data = dict()
                    data.update(
                        {
                            "field_type": field_type,
                            "field_name": filed_name,
                            "es_index": common_index,
                            # "analyzed": analyzed,
                            "field_alias": "",
                            "description": "",
                            "es_doc_values": es_doc_values,
                            "tag": tag,
                            "is_analyzed": cls._is_analyzed(field_type),
                        }
                    )
                    fields_result.append(data)
                elif "properties" in k_keys:
                    fields_result.extend(
                        cls.get_fields_recursively(p_key=f"{p_key}.{key}", properties_dict=properties_dict[key])
                    )
        return fields_result

    @staticmethod
    def compare_indices_by_date(index_a, index_b):
        """
        compare_indices_by_date
        @param index_a:
        @param index_b:
        @return:
        """
        index_a = list(index_a.keys())[0]
        index_b = list(index_b.keys())[0]

        def convert_to_normal_date_tuple(index_name) -> tuple:
            # example 1: 2_bklog_xxxx_20200321_1 -> (20200321, 1)
            # example 2: 2_xxxx_2020032101 -> (20200321, 1)
            result = re.findall(r"(\d{8})_(\d{1,7})$", index_name) or re.findall(r"(\d{8})(\d{2})$", index_name)
            if result:
                return result[0][0], int(result[0][1])
            # not match
            return index_name, 0

        converted_index_a = convert_to_normal_date_tuple(index_a)
        converted_index_b = convert_to_normal_date_tuple(index_b)

        return (converted_index_a > converted_index_b) - (converted_index_a < converted_index_b)

    def find_merged_property(self, mapping_result) -> dict:
        """
        find_merged_property
        @param mapping_result:
        @return:
        """
        return self._merge_property(self._get_all_property(mapping_result))

    def _get_all_property(self, mapping_result):
        index_es_rt: str = self.indices.replace(".", "_")
        index_es_rts = index_es_rt.split(",")
        mapping_group: dict = self._mapping_group(index_es_rts, mapping_result)
        return [self.find_property_dict(mapping_list) for mapping_list in mapping_group.values()]

    @classmethod
    def _merge_property(cls, propertys: list):
        merge_dict = {}
        for property in propertys:
            for property_key, property_define in property.items():
                if property_key not in merge_dict:
                    merge_dict[property_key] = property_define
                    # 这里由于该函数会被调用两次，所以只有在第一次调用且为最新mapping的时候来赋值
                    if not merge_dict[property_key].get("latest_field_type"):
                        merge_dict[property_key]["latest_field_type"] = property_define["type"]
                    continue
        return {property_key: property for property_key, property in merge_dict.items()}

    def _mapping_group(self, index_result_tables: list, mapping_result: list):
        # 第三方不合并mapping
        if self.scenario_id in [Scenario.ES]:
            return {"es": mapping_result}
        mapping_group = defaultdict(list)
        # 排序rt表 最长的在前面保障类似 bk_test_test, bk_test
        index_result_tables.sort(key=lambda s: len(s), reverse=True)
        # 数平rt和索引对应不区分大小写
        if self.scenario_id in [Scenario.BKDATA]:
            index_result_tables = [index.lower() for index in index_result_tables]
        for mapping in mapping_result:
            index: str = next(iter(mapping.keys()))
            for index_es_rt in index_result_tables:
                if index_es_rt in index:
                    mapping_group[index_es_rt].append(mapping)
                    break
        return mapping_group

    @classmethod
    def find_property_dict(cls, result_list: list) -> dict:
        """
        获取最新索引mapping
        :param result_list:
        :return:
        """
        sorted_result_list = sorted(result_list, key=functools.cmp_to_key(cls.compare_indices_by_date), reverse=True)
        property_list = []
        for _inner_dict in sorted_result_list:
            property_dict = cls.get_property_dict(_inner_dict)
            if property_dict:
                property_list.append(property_dict)
        return cls._merge_property(property_list)

    def _combine_description_field(self, fields_list=None, scope=None):
        if fields_list is None:
            return []
        # mapping 和schema对比
        schema_result: list = []
        if self.scenario_id in [Scenario.BKDATA]:
            schema_result: list = self.get_bkdata_schema(self.indices)
        if self.scenario_id in [Scenario.LOG]:
            schema_result: list = self.get_meta_schema(indices=self.indices)

        field_time_format_dict = {}
        # list to dict
        schema_dict: dict = {}
        for item in schema_result:
            _field_name = item.get("field_name", "")
            temp_dict: dict = {}
            for k, v in item.items():
                temp_dict.update({k: v})
                # 记录指定日志时间字段信息
            if _field_name == DEFAULT_TIME_FIELD and item.get("option"):
                _alias_name = item.get("alias_name")
                field_time_format_dict = {
                    "field_name": _field_name if _alias_name == DEFAULT_TIME_FIELD_ALIAS_NAME else _alias_name,
                    "field_time_zone": item["option"].get("time_zone"),
                    "field_time_format": item["option"].get("time_format"),
                }
            if _field_name:
                schema_dict.update({_field_name: temp_dict})

        alias_dict = {}
        if query_alias_settings := self.index_set.query_alias_settings:
            for item in query_alias_settings:
                alias_dict[item["field_name"]] = item["query_alias"]

        remove_field_list = list()
        # 增加description别名字段
        for _field in fields_list:
            a_field_name = _field.get("field_name", "")
            if a_field_name:
                field_info = schema_dict.get(a_field_name)
                if field_info:
                    if self.scenario_id in [Scenario.BKDATA]:
                        field_alias: str = field_info.get("field_alias")
                    elif self.scenario_id in [Scenario.LOG]:
                        field_alias: str = field_info.get("description")
                    else:
                        field_alias: str = ""
                    _field.update({"description": field_alias, "field_alias": field_alias})

                    field_option = field_info.get("option")
                    if field_option:
                        # 加入元数据标识
                        metadata_type = field_option.get("metadata_type")
                        if metadata_type:
                            _field.update({"metadata_type": metadata_type})
                else:
                    _field.update({"description": None})

                # 为指定日志时间字段添加标识,时区和格式
                if a_field_name == field_time_format_dict.get("field_name"):
                    _field.update(
                        {
                            "is_time": True,
                            "field_time_zone": field_time_format_dict.get("field_time_zone"),
                            "field_time_format": field_time_format_dict.get("field_time_format"),
                        }
                    )

                # 添加别名信息
                if a_field_name in alias_dict:
                    _field["query_alias"] = alias_dict[a_field_name]

                # 别名字段
                if _field.get("field_type") == "alias":
                    remove_field_list.append(_field)

        # 移除不展示的别名字段
        for field in remove_field_list:
            if field in fields_list:
                fields_list.remove(field)

        return fields_list

    def get_bkdata_schema(self, index: str) -> list:
        index, *_ = index.split(",")
        return self._inner_get_bkdata_schema(index=index)

    @staticmethod
    @cache_ten_minute("{index}_schema")
    def _inner_get_bkdata_schema(*, index):
        try:
            data: dict = BkDataStorekitApi.get_schema_and_sql({"result_table_id": index})
            field_list: list = data["storage"]["es"]["fields"]
            return field_list
        except Exception:  # pylint: disable=broad-except
            return []

    @staticmethod
    @cache_one_minute("{indices}_meta_schema")
    def get_meta_schema(*, indices):
        indices = indices.split(",")
        try:
            all_field_list = list()
            all_field_set = set()

            multi_execute_func = MultiExecuteFunc()

            for index in indices:
                multi_execute_func.append(
                    result_key=f"get_result_table_{index}",
                    func=TransferApi.get_result_table,
                    params={"params": {"table_id": index}},
                    multi_func_params=True,
                )

            multi_result = multi_execute_func.run()

            for index in indices:
                data = multi_result.get(f"get_result_table_{index}")
                if not data:
                    continue

                for field_info in data["field_list"]:
                    if field_info["field_name"] not in all_field_set:
                        all_field_set.add(field_info["field_name"])
                        all_field_list.append(field_info)

            return all_field_list
        except Exception:  # pylint: disable=broad-except
            return []

    def _combine_fields(self, fields_list):
        """
        组装fields
        :param fields_list:
        :return:
        """

        # inner
        if self.scenario_id == Scenario.BKDATA:
            return self.combine_bkdata_fields(fields_list)
        # original es
        if self.scenario_id == Scenario.ES:
            return self.combine_es_fields(fields_list, self.time_field)
        return self.combine_bkdata_fields(fields_list)

    @staticmethod
    def combine_bkdata_fields(fields_list):
        """
        for bkdata
        :param fields_list:
        :return:
        """
        final_fields_list = list()
        commit_list = list()
        common_list = list()
        time_list = list()
        produce_list = list()
        for s_field in fields_list:
            field_name = s_field["field_name"]
            field_type = s_field["field_type"]
            if isinstance(field_name, str):
                field_name = field_name.lower()
            if field_name in INNER_PRODUCE_FIELDS:
                s_field["is_editable"] = True
                produce_list.append(s_field)
                continue
            if field_name in INNER_COMMIT_FIELDS:
                commit_list.append(s_field)
            elif field_type in TIME_TYPE:
                time_list.append(s_field)
            else:
                common_list.append(s_field)
        if len(commit_list) <= 1:
            final_fields_list.extend(commit_list)
        else:
            for common_single in commit_list:
                if common_single["field_name"].lower() == "report_time":
                    final_fields_list.append(common_single)
        final_fields_list.extend(time_list)
        final_fields_list.extend(common_list)
        final_fields_list.extend(produce_list)
        return final_fields_list

    @staticmethod
    def combine_es_fields(fields_list, time_field):
        """
        for es
        :param fields_list:
        :return:
        """
        final_fields_list = list()
        commit_list = list()
        common_list = list()
        time_list = list()
        produce_list = list()
        for s_field in fields_list:
            field_name = s_field["field_name"]
            field_type = s_field["field_type"]
            if isinstance(field_name, str):
                field_name = field_name.lower()
            if field_name in OUTER_PRODUCE_FIELDS:
                s_field["is_editable"] = False
                produce_list.append(s_field)
                continue
            if field_name == time_field:
                commit_list.append(s_field)
            elif field_type in TIME_TYPE:
                time_list.append(s_field)
            else:
                common_list.append(s_field)
        final_fields_list.extend(commit_list)
        final_fields_list.extend(time_list)
        final_fields_list.extend(common_list)
        final_fields_list.extend(produce_list)
        return final_fields_list

    @staticmethod
    def _sort_display_fields(display_fields: list) -> list:
        """
        检索字段显示时间排序规则: 默认dtEventTimeStamp放前面，time放最后
        :param display_fields:
        :return:
        """
        if "dtEventTimeStamp" in display_fields:
            dt_time_index = display_fields.index("dtEventTimeStamp")
            if dt_time_index != 0:
                display_fields[0], display_fields[dt_time_index] = "dtEventTimeStamp", display_fields[0]

        if "time" in display_fields:
            time_index = display_fields.index("time")
            if time_index != len(display_fields) - 1:
                display_fields[-1], display_fields[time_index] = "time", display_fields[-1]
        return display_fields

    @classmethod
    def get_sort_list_by_index_id(cls, index_set_id, scope: str = SearchScopeEnum.DEFAULT.value):
        """
        get_sort_list_by_index_id
        @param index_set_id:
        @param scope: 请求来源
        @return:
        """
        username = get_request_external_username() or get_request_username()
        index_config_obj = UserIndexSetFieldsConfig.get_config(
            index_set_id=index_set_id, username=username, scope=scope
        )
        if not index_config_obj:
            return list()

        sort_list = index_config_obj.sort_list
        return sort_list if isinstance(sort_list, list) else list()

    @classmethod
    def init_ip_topo_switch(cls, index_set_id: int) -> bool:
        """
        init_ip_topo_switch
        @param index_set_id:
        @return:
        """
        log_index_set_obj = LogIndexSet.objects.filter(index_set_id=index_set_id).first()
        if not log_index_set_obj:
            return False
        # 如果第三方es的话设置为ip_topo_switch为False
        if log_index_set_obj.scenario_id == Scenario.ES:
            return False
        return True

    @classmethod
    def analyze_fields(cls, final_fields_list: list[dict[str, Any]]) -> dict:
        """
        analyze_fields
        @param final_fields_list:
        @return:
        """
        # 上下文实时日志可否使用判断
        fields_list = [x["field_name"] for x in final_fields_list]
        context_search_usable: bool = False
        realtime_search_usable: bool = False
        fields_list = set(fields_list)
        context_and_realtime_judge_fields = [
            {"gseindex", "ip", "path", "_iteration_idx"},
            {"gseindex", "container_id", "logfile", "_iteration_idx"},
            {"gseIndex", "serverIp", "path", "_iteration_idx"},
            {"gseIndex", "serverIp", "path", "iterationIndex"},
            {"gseIndex", "path", "iterationIndex", "__ext.container_id"},
        ]
        for judge in context_and_realtime_judge_fields:
            if not fields_list.issuperset(judge):
                continue

            analyze_fields_type_result = cls._analyze_fields_type(final_fields_list)
            if analyze_fields_type_result:
                if "bk_host_id" in fields_list:
                    judge.add("bk_host_id")
                return {
                    "context_search_usable": context_search_usable,
                    "realtime_search_usable": realtime_search_usable,
                    "context_fields": list(judge.copy()),
                    "usable_reason": analyze_fields_type_result,
                }
            context_search_usable = True
            realtime_search_usable = True
            if "bk_host_id" in fields_list:
                judge.add("bk_host_id")
            if "container_id" in fields_list and "container_id" not in judge:
                judge.add("container_id")
            if "__ext.container_id" in fields_list and "__ext.container_id" not in judge:
                judge.add("__ext.container_id")
            return {
                "context_search_usable": context_search_usable,
                "realtime_search_usable": realtime_search_usable,
                "context_fields": list(judge.copy()),
                "usable_reason": "",
            }
        return {
            "context_search_usable": context_search_usable,
            "realtime_search_usable": realtime_search_usable,
            "context_fields": [],
            "usable_reason": cls._analyze_require_fields(fields_list),
        }

    @classmethod
    def _analyze_fields_type(cls, final_fields_list: list[dict[str, Any]]):
        # 上下文实时日志校验字段类型
        fields_type = {
            "gseindex": ["integer", "long"],
            "iteration": ["integer", "long"],
            "iterationIndex": ["integer", "long"],
        }
        for x in final_fields_list:
            field_name = x["field_name"]
            if fields_type.get(field_name):
                if x["field_type"] in fields_type.get(field_name):
                    continue
                type_msg = str(_("或者")).join(fields_type.get(x["field_name"]))
                return _("{field_name}必须为{type_msg}类型").format(field_name=field_name, type_msg=type_msg)
        return None

    @classmethod
    def _analyze_require_fields(cls, fields_list):
        def _analyze_path_fields(fields):
            if "path" and "logfile" not in fields:
                return _("必须path或者logfile字段")
            return ""

        if "gseindex" in fields_list:
            if "_iteration_idx" not in fields_list:
                return _("必须_iteration_idx字段")

            if "ip" in fields_list:
                return _analyze_path_fields(fields_list)
            if "container_id" in fields_list:
                return _analyze_path_fields(fields_list)
            return _("必须ip或者container_id字段")

        elif "gseIndex" in fields_list:
            if "serverIp" not in fields_list:
                return _("必须serverIp字段")

            if "path" not in fields_list:
                return _("必须path字段")

            if "iterationIndex" and "_iteration_idx" not in fields_list:
                return _("必须iterationIndex或者_iteration_idx字段")
            return ""
        return _("必须gseindex或者gseIndex字段")

    @classmethod
    def get_date_candidate(cls, mapping_list: list):
        """
        1、校验索引mapping字段类型是否一致；
        2、获取可供选择的时间字段（long&data类型）
        """
        date_field_list: list = []
        for item in mapping_list:
            property_dict = cls.get_property_dict(item)
            if property_dict:
                item_data_field = []
                for key, info in property_dict.items():
                    field_type = info.get("type", "")
                    if field_type in settings.FEATURE_TOGGLE.get("es_date_candidate", ["date", "long"]):
                        item_data_field.append(f"{key}:{field_type}")
                # 校验是否有相同的时间字段（long和date类型)
                if not date_field_list:
                    date_field_list = item_data_field
                date_field_list = list(set(date_field_list).intersection(item_data_field))
                if not date_field_list:
                    raise FieldsDateNotExistException()
        if not date_field_list:
            raise FieldsDateNotExistException()

        date_candidate = []
        for _field in date_field_list:
            field_name, field_type = _field.split(":")
            date_candidate.append({"field_name": field_name, "field_type": field_type})
        return date_candidate

    @classmethod
    def get_property_dict(cls, dict_item, prefix_key="", match_key="properties"):
        """
        根据ES-mapping递归获取所有properties的字段列表
        """
        result = {}
        if match_key in dict_item:
            property_dict = dict_item[match_key]
            for k, v in property_dict.items():
                p_key = k
                if prefix_key:
                    p_key = f"{prefix_key}.{k}"
                if match_key in v:
                    result.update(cls.get_property_dict(v, prefix_key=p_key, match_key=match_key))
                else:
                    result[p_key] = v
            return result

        for _key, _value in dict_item.items():
            if isinstance(_value, dict):
                result = cls.get_property_dict(_value, prefix_key, match_key)
                if result:
                    return result
        return None

    @classmethod
    def async_export_fields(cls, final_fields_list: list[dict[str, Any]], scenario_id: str, sort_fields: list) -> dict:
        """
        判断是否可以支持大额导出
        """
        fields = {final_field["field_name"] for final_field in final_fields_list}
        agg_fields = {final_field["field_name"] for final_field in final_fields_list if final_field["es_doc_values"]}
        result = {"async_export_usable": False, "async_export_fields": [], "async_export_usable_reason": ""}
        if not FeatureToggleObject.switch(FEATURE_ASYNC_EXPORT_COMMON):
            result["async_export_usable_reason"] = _("【异步导出功能尚未开放】")
            return result
        if sort_fields and fields.issuperset(set(sort_fields)):
            return cls._judge_missing_agg_field(result, agg_fields, sort_fields)

        if scenario_id == Scenario.BKDATA and fields.issuperset(set(BKDATA_ASYNC_FIELDS)):
            return cls._judge_missing_agg_field(result, agg_fields, BKDATA_ASYNC_FIELDS)

        if scenario_id == Scenario.BKDATA and fields.issuperset(set(BKDATA_ASYNC_CONTAINER_FIELDS)):
            return cls._judge_missing_agg_field(result, agg_fields, BKDATA_ASYNC_CONTAINER_FIELDS)

        if scenario_id == Scenario.LOG and fields.issuperset(set(LOG_ASYNC_FIELDS)):
            return cls._judge_missing_agg_field(result, agg_fields, LOG_ASYNC_FIELDS)

        if scenario_id == Scenario.ES:
            result["async_export_usable"] = True
            return result

        return cls._generate_async_export_reason(scenario_id=scenario_id, result=result)

    @classmethod
    def _judge_missing_agg_field(cls, result: dict, agg_fields: set, scenario_fields: list) -> dict:
        """
        判断聚合字段是否缺失
        """
        if agg_fields.issuperset(set(scenario_fields)):
            result["async_export_fields"] = scenario_fields
            result["async_export_usable"] = True
        else:
            result["async_export_usable_reason"] = _("检查{}字段是否为聚合字段").format(",".join(scenario_fields))
        return result

    @classmethod
    def _generate_async_export_reason(cls, scenario_id: str, result: dict):
        reason_map = {
            Scenario.BKDATA: _("缺少必备字段: {async_fields} or {async_container_fields}").format(
                async_fields=", ".join(BKDATA_ASYNC_FIELDS),
                async_container_fields=", ".join(BKDATA_ASYNC_CONTAINER_FIELDS),
            ),
            Scenario.LOG: _("缺少必备字段: {async_fields}").format(async_fields=", ".join(LOG_ASYNC_FIELDS)),
        }
        result["async_export_usable_reason"] = reason_map[scenario_id]
        return result
