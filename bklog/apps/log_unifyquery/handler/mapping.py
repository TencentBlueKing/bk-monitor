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
from typing import Any

from django.conf import settings
from django.utils.translation import gettext as _

from apps.api import BkDataStorekitApi, TransferApi, UnifyQueryApi
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
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
    SearchScopeEnum,
    DorisFieldTypeEnum,
)
from apps.log_search.models import (
    IndexSetFieldsConfig,
    LogIndexSet,
    LogIndexSetData,
    Scenario,
    UserIndexSetFieldsConfig,
    IndexSetTag,
)
from apps.log_search.utils import split_object_fields
from apps.utils.cache import cache_one_minute, cache_ten_minute
from apps.utils.local import (
    get_request_app_code,
    get_request_external_username,
    get_request_username,
)
from apps.utils.thread import MultiExecuteFunc

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


class UnifyQueryMappingHandler:
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
    ):
        self.indices = indices
        self.index_set_id = index_set_id
        self.bk_biz_id = bk_biz_id
        self.scenario_id = scenario_id
        self.storage_cluster_id = storage_cluster_id
        self.time_field = time_field
        self.start_time = start_time
        self.end_time = end_time
        # 最终字段
        self._final_fields = None

        # 仅查询使用
        self.only_search = only_search

        self._index_set = index_set

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
        if "__ext.bk_bcs_cluster_id" in fields:
            field_list.append(
                {
                    "field_type": "__virtual__",
                    "field_name": "__bcs_cluster_name__",
                    "field_alias": _("BCS 集群名称"),
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
        fields_result = self.get_all_index_fields()
        if not fields_result:
            # 如果一个字段都不存在，就用快照字段兜底
            if self.index_set.fields_snapshot:
                return self.index_set.fields_snapshot.get("fields", [])
            return []

        fields_list: list = [
            {
                "field_type": field["field_type"],
                "field_name": field["field_name"],
                "field_alias": field.get("field_alias", ""),
                "query_alias": field.get("alias_name", ""),
                "is_display": False,
                "is_editable": True,
                "tag": field.get("tag", ""),
                "origin_field": field.get("origin_field", ""),
                "es_doc_values": field.get("is_agg", False),
                "is_analyzed": field.get("is_analyzed", False),
                "field_operator": OPERATORS.get(field["field_type"], []),
                "is_case_sensitive": field.get("is_case_sensitive", False),
                "tokenize_on_chars": "".join(field.get("tokenize_on_chars", [])),
            }
            for field in fields_result
        ]
        # doris需要映射字段类型，根据新的类型获取操作列表
        is_doris = str(IndexSetTag.get_tag_id("Doris")) in list(self.index_set.tag_ids)
        if is_doris:
            for field in fields_list:
                field["field_type"] = DorisFieldTypeEnum.get_es_field_type(field)
                field["field_operator"] = OPERATORS.get(field["field_type"], [])
                field["es_doc_values"] = field["field_type"] not in ["text", "object"]

        for field in fields_list:
            # @TODO tag：兼容前端代码，后面需要删除
            tag = "metric"
            if field.get("field_type") == "date":
                tag = "timestamp"
            elif field.get("es_doc_values"):
                tag = "dimension"
            field["tag"] = tag

        fields_list = self.add_clustered_fields(fields_list)
        fields_list = self.virtual_fields(fields_list)
        if not self.only_search:
            fields_list = self._combine_description_field(fields_list)
        fields_list = self._combine_fields(fields_list)

        built_in_fields = FieldBuiltInEnum.get_choices()
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

    def get_all_index_fields(self) -> list:
        from apps.log_search.handlers.index_set import BaseIndexSetHandler

        params = {
            "data_source": settings.UNIFY_QUERY_DATA_SOURCE,
            "start_time": str(self.start_time),
            "end_time": str(self.end_time),
            "table_id": BaseIndexSetHandler.get_data_label(self.index_set_id),
            "bk_biz_id": self.bk_biz_id,  # 发送请求时，需要使用bk_biz_id获取bk_tenant_id
        }
        result = UnifyQueryApi.query_field_map(params)
        return result.get("data", [])

    @staticmethod
    def get_fields_directly(bk_biz_id: int, scenario_id: str, storage_cluster_id: int, result_table_id: str):
        # 需要区分是 bkdata 还是其他
        source_type = scenario_id if scenario_id == Scenario.BKDATA else settings.UNIFY_QUERY_DATA_SOURCE
        result_table_list = [rt if rt.endswith("*") else f"{rt}_*" for rt in result_table_id.split(",")]
        params = {
            "bk_biz_id": bk_biz_id,
            "tsdb_map": {
                "a": [
                    {
                        "source_type": source_type,
                        "storage_type": "elasticsearch",
                        "storage_id": str(storage_cluster_id),
                        "db": ",".join(result_table_list),
                    }
                ]
            },
        }
        result = UnifyQueryApi.query_field_map(params)
        return result.get("data", [])

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

        return fields_list

    def get_bkdata_schema(self, index: str) -> list:
        index, *_ = index.split(",")
        return self._inner_get_bkdata_schema(index=index)

    @staticmethod
    @cache_ten_minute("{index}_schema_uq", need_md5=True)
    def _inner_get_bkdata_schema(*, index):
        try:
            data: dict = BkDataStorekitApi.get_schema_and_sql({"result_table_id": index})
            field_list: list = data["storage"]["es"]["fields"]
            return field_list
        except Exception:  # pylint: disable=broad-except
            return []

    @staticmethod
    @cache_one_minute("{indices}_meta_schema_uq", need_md5=True)
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
            "gseindex": ["integer", "long", "double"],
            "iteration": ["integer", "long", "double"],
            "iterationIndex": ["integer", "long", "double"],
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

    @staticmethod
    def get_date_candidate(field_list):
        """
        获取可供选择的时间字段
        """
        return [
            {"field_name": field["field_name"], "field_type": field["field_type"]}
            for field in field_list
            if field["field_type"] in settings.FEATURE_TOGGLE.get("es_date_candidate", ["date", "long"])
        ]
