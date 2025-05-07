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
from typing import Any

import arrow
from django.conf import settings

from apps.api import UnifyQueryApi
from apps.log_clustering.models import ClusteringConfig
from apps.log_desensitize.handlers.desensitize import DesensitizeHandler
from apps.log_desensitize.models import DesensitizeConfig, DesensitizeFieldConfig
from apps.log_desensitize.utils import expand_nested_data, merge_nested_data
from apps.log_esquery.esquery.builder.query_string_builder import QueryStringBuilder
from apps.log_esquery.exceptions import (
    BaseSearchIndexSetDataDoseNotExists,
    BaseSearchIndexSetException,
)
from apps.log_search.constants import (
    MAX_RESULT_WINDOW,
    OperatorEnum,
    TimeFieldTypeEnum,
    TimeFieldUnitEnum,
)
from apps.log_search.exceptions import BaseSearchResultAnalyzeException
from apps.log_search.handlers.index_set import BaseIndexSetHandler
from apps.log_search.handlers.search.aggs_handlers import AggsHandlers
from apps.log_search.handlers.search.mapping_handlers import MappingHandlers
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_search.models import (
    LogIndexSet,
    LogIndexSetData,
    Scenario,
    UserIndexSetFieldsConfig,
    UserIndexSetSearchHistory,
)
from apps.log_unifyquery.constants import BASE_OP_MAP, MAX_LEN_DICT, REFERENCE_ALIAS
from apps.log_unifyquery.utils import deal_time_format, transform_advanced_addition
from apps.utils.cache import cache_five_minute
from apps.utils.core.cache.cmdb_host import CmdbHostCache
from apps.utils.ipchooser import IPChooser
from apps.utils.local import (
    get_local_param,
    get_request_external_username,
    get_request_username,
)
from apps.utils.log import logger
from apps.utils.lucene import EnhanceLuceneAdapter
from apps.utils.time_handler import timestamp_to_timeformat
from bkm_ipchooser.constants import CommonEnum


class UnifyQueryHandler:
    def __init__(self, params):
        self.search_params: dict[str, Any] = params

        # 必需参数，索引集id列表
        self.index_set_ids = self.search_params["index_set_ids"]

        # 初始化索引信息（包括索引类型）
        self.index_info_list = self._init_index_info_list(self.search_params.get("index_set_ids", []))
        self.search_params.update({"scenario_id": self.index_info_list[0]["scenario_id"]})

        # 必需参数，业务id
        self.bk_biz_id = self.search_params["bk_biz_id"]

        # 查询语句
        self.query_string = self.search_params.get("keyword", "")
        self.origin_query_string: str = self.search_params.get("keyword")
        self._enhance()
        self.query_string = QueryStringBuilder(self.query_string).query_string

        # 聚合查询：字段名称
        self.agg_field = self.search_params.get("agg_field", "")

        # 请求用户名
        self.request_username = get_request_external_username() or get_request_username()

        # 排序参数
        self.order_by = []
        self.origin_order_by = self._init_sort()
        for param in self.origin_order_by:
            if param[1] == "asc":
                self.order_by.append(param[0])
            elif param[1] == "desc":
                self.order_by.append(f"-{param[0]}")

        # 是否为联合查询
        self.is_multi_rt: bool = len(self.index_set_ids) > 1

        # 查询时间范围
        self.start_time, self.end_time = deal_time_format(
            self.search_params["start_time"], self.search_params["end_time"]
        )

        # result fields
        self.field: dict[str, MAX_LEN_DICT] = {}

        self.is_desensitize = params.get("is_desensitize", True)

        # 初始化DB脱敏配置
        desensitize_config_obj = DesensitizeConfig.objects.filter(index_set_id=self.index_set_ids[0]).first()
        desensitize_field_config_objs = DesensitizeFieldConfig.objects.filter(index_set_id=self.index_set_ids[0])

        # 脱敏配置原文字段
        self.text_fields = desensitize_config_obj.text_fields if desensitize_config_obj else []

        self.field_configs = list()

        self.text_fields_field_configs = list()

        for field_config_obj in desensitize_field_config_objs:
            _config = {
                "field_name": field_config_obj.field_name or "",
                "rule_id": field_config_obj.rule_id or 0,
                "operator": field_config_obj.operator,
                "params": field_config_obj.params,
                "match_pattern": field_config_obj.match_pattern,
                "sort_index": field_config_obj.sort_index,
            }
            if field_config_obj.field_name not in self.text_fields:
                self.field_configs.append(_config)
            else:
                self.text_fields_field_configs.append(_config)

        # 初始化脱敏工厂对象
        self.desensitize_handler = DesensitizeHandler(self.field_configs)
        self.text_fields_desensitize_handler = DesensitizeHandler(self.text_fields_field_configs)

        # 导出字段
        self.export_fields = self.search_params.get("export_fields")

        # 是否开启高亮
        self.highlight = self.search_params.get("can_highlight", True)

        # 基础查询参数初始化
        self.base_dict = self.init_base_dict()

    @staticmethod
    def query_ts(search_dict, raise_exception=True):
        """
        查询时序型数据
        """
        try:
            return UnifyQueryApi.query_ts(search_dict)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("query ts error: %s, search params: %s", e, search_dict)
            if raise_exception:
                raise e

    @staticmethod
    def query_ts_reference(search_dict, raise_exception=False):
        """
        查询非时序型数据
        """
        try:
            return UnifyQueryApi.query_ts_reference(search_dict)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("query ts reference error: %s, search params: %s", e, search_dict)
            if raise_exception:
                raise e
            return {"series": []}

    def query_ts_raw(self, search_dict, raise_exception=False, pre_search=False):
        """
        查询时序型日志数据
        """
        try:
            pre_search_seconds = settings.PRE_SEARCH_SECONDS
            first_field, order = self.origin_order_by[0] if self.origin_order_by else [None, None]
            if (
                pre_search
                and pre_search_seconds
                and self.start_time
                and first_field == self.search_params.get("time_field", "")
            ):
                # 预查询处理
                pre_search_end_time = int(
                    arrow.get(self.start_time).shift(seconds=pre_search_seconds).timestamp() * 1000
                )
                pre_search_start_time = int(
                    arrow.get(self.end_time).shift(seconds=-pre_search_seconds).timestamp() * 1000
                )
                if order == "desc" and self.start_time < pre_search_start_time:
                    search_dict.update({"start_time": str(pre_search_start_time)})
                elif order == "asc" and self.end_time > pre_search_end_time:
                    search_dict.update({"end_time": str(pre_search_end_time)})
            return UnifyQueryApi.query_ts_raw(search_dict)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("query ts raw error: %s, search params: %s", e, search_dict)
            if raise_exception:
                raise e
            return {"list": []}

    def _enhance(self):
        """
        语法增强
        """
        if self.query_string is not None:
            enhance_lucene_adapter = EnhanceLuceneAdapter(query_string=self.query_string)
            self.query_string = enhance_lucene_adapter.enhance()

    def _init_default_interval(self):
        """
        初始化聚合周期
        """
        if not self.start_time or not self.end_time:
            # 兼容查询时间段为默认近十五分钟的情况
            return "1m"

        # 兼容毫秒查询
        hour_interval = (arrow.get(int(self.end_time)) - arrow.get(int(self.start_time))).total_seconds() / 3600
        if hour_interval <= 1:
            return "1m"
        elif hour_interval <= 6:
            return "5m"
        elif hour_interval <= 24 * 3:
            return "1h"
        else:
            return "1d"

    def _init_index_info_list(self, index_set_ids: list[int]) -> list:
        index_info_list = []
        for index_set_id in index_set_ids:
            index_info = {}
            tmp_index_obj: LogIndexSet = LogIndexSet.objects.filter(index_set_id=index_set_id).first()
            if tmp_index_obj:
                index_info["index_set_id"] = tmp_index_obj.index_set_id
                index_info["index_set_name"] = tmp_index_obj.index_set_name
                index_info["index_set_obj"] = tmp_index_obj
                index_info["scenario_id"] = tmp_index_obj.scenario_id
                index_info["storage_cluster_id"] = tmp_index_obj.storage_cluster_id
                index_info["target_fields"] = tmp_index_obj.target_fields
                index_info["sort_fields"] = tmp_index_obj.sort_fields

                index_set_data_obj_list: list = tmp_index_obj.get_indexes(has_applied=True)
                if len(index_set_data_obj_list) > 0:
                    index_list: list = [x.get("result_table_id", None) for x in index_set_data_obj_list]
                else:
                    raise BaseSearchIndexSetDataDoseNotExists(
                        BaseSearchIndexSetDataDoseNotExists.MESSAGE.format(
                            index_set_id=str(index_set_id) + "_" + tmp_index_obj.index_set_name
                        )
                    )
                index_info["indices"] = index_info["origin_indices"] = ",".join(index_list)
                index_info["origin_scenario_id"] = tmp_index_obj.scenario_id

                # 增加判定逻辑：如果 search_dict 中的 keyword 字符串包含 "__dist_05"，也要走clustering的路由
                if "__dist_05" in self.search_params.get("keyword", ""):
                    index_info = self._set_scenario_id_proxy_indices(index_set_id, index_info)
                    index_info_list.append(index_info)
                    continue

                for addition in self.search_params.get("addition", []):
                    # 查询条件中包含__dist_xx  则查询聚类结果表：xxx_bklog_xxx_clustered
                    if addition.get("field", "").startswith("__dist"):
                        index_info = self._set_scenario_id_proxy_indices(index_set_id, index_info)
                index_info_list.append(index_info)
            else:
                raise BaseSearchIndexSetException(BaseSearchIndexSetException.MESSAGE.format(index_set_id=index_set_id))
        return index_info_list

    @staticmethod
    def _set_scenario_id_proxy_indices(index_set_id, index_info) -> dict:
        clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=index_set_id, raise_exception=False)
        if clustering_config and clustering_config.clustered_rt:
            # 如果是查询bkbase端的表，即场景需要对应改为bkdata
            index_info["scenario_id"] = Scenario.BKDATA
            # 是否使用了聚类代理查询
            index_info["using_clustering_proxy"] = True
            index_info["indices"] = clustering_config.clustered_rt
        return index_info

    @staticmethod
    def _deal_normal_addition(value, _operator: str) -> str | list:
        operator = _operator
        addition_return_value = {
            "is": lambda: value,
            "is one of": lambda: value.split(","),
            "is not": lambda: value,
            "is not one of": lambda: value.split(","),
        }
        return addition_return_value.get(operator, lambda: value)()

    @staticmethod
    def init_time_field(index_set_id: int, scenario_id: str = None) -> tuple:
        if not scenario_id:
            scenario_id = LogIndexSet.objects.filter(index_set_id=index_set_id).first().scenario_id
        # get timestamp field
        if scenario_id in [Scenario.BKDATA, Scenario.LOG]:
            return "dtEventTimeStamp", TimeFieldTypeEnum.DATE.value, TimeFieldUnitEnum.SECOND.value
        else:
            log_index_set_obj = LogIndexSet.objects.filter(index_set_id=index_set_id).first()
            time_field = log_index_set_obj.time_field
            time_field_type = log_index_set_obj.time_field_type
            time_field_unit = log_index_set_obj.time_field_unit
            if time_field:
                return time_field, time_field_type, time_field_unit
            index_set_obj: LogIndexSetData = LogIndexSetData.objects.filter(index_set_id=index_set_id).first()
            if not index_set_obj:
                raise BaseSearchIndexSetException(BaseSearchIndexSetException.MESSAGE.format(index_set_id=index_set_id))
            time_field = index_set_obj.time_field
            return time_field, TimeFieldTypeEnum.DATE.value, TimeFieldUnitEnum.SECOND.value

    def _deal_addition(self, ip_field):
        addition_ip_list: list = []
        addition: list = self.search_params.get("addition")
        new_addition: list = []
        if not addition:
            return [], []
        for _add in addition:
            field: str = _add.get("key") if _add.get("key") else _add.get("field")
            _operator: str = _add.get("method") if _add.get("method") else _add.get("operator")
            if field == ip_field:
                value = _add.get("value")
                if value and _operator in ["is", OperatorEnum.EQ["operator"], OperatorEnum.EQ_WILDCARD["operator"]]:
                    if isinstance(value, str):
                        addition_ip_list.extend(value.split(","))
                        continue
                    elif isinstance(value, list):
                        addition_ip_list = addition_ip_list + value
                        continue
            # 处理逗号分隔in类型查询
            value = _add.get("value")
            new_value: list = []
            # 对于前端传递为空字符串的场景需要放行过去
            if isinstance(value, list):
                new_value = value
            elif isinstance(value, str) or value:
                new_value = self._deal_normal_addition(value, _operator)
            new_addition.append(
                {"field": field, "operator": _operator, "value": new_value, "condition": _add.get("condition", "and")}
            )
        return addition_ip_list, new_addition

    def _combine_addition_ip_chooser(self, index_info):
        """
        合并ip_chooser和addition
        :param index_info:   attrs
        """
        ip_chooser_ip_list: list = []
        ip_chooser_host_id_list: list = []
        ip_chooser: dict = self.search_params.get("ip_chooser")
        ip_field = "ip" if index_info["scenario_id"] in [Scenario.BKDATA, Scenario.ES] else "serverIp"

        if ip_chooser:
            ip_chooser_host_list = IPChooser(
                bk_biz_id=self.bk_biz_id, fields=CommonEnum.SIMPLE_HOST_FIELDS.value
            ).transfer2host(ip_chooser)
            ip_chooser_host_id_list = [str(host["bk_host_id"]) for host in ip_chooser_host_list]
            ip_chooser_ip_list = [host["bk_host_innerip"] for host in ip_chooser_host_list]
        addition_ip_list, new_addition = self._deal_addition(ip_field)
        if addition_ip_list:
            search_ip_list = addition_ip_list
        elif not addition_ip_list and ip_chooser_ip_list:
            search_ip_list = ip_chooser_ip_list
        else:
            search_ip_list = []

        final_fields_list, _ = MappingHandlers(
            index_set_id=index_info["index_set_id"],
            indices=index_info["origin_indices"],
            scenario_id=index_info["origin_scenario_id"],
            storage_cluster_id=index_info["storage_cluster_id"],
            bk_biz_id=self.bk_biz_id,
            only_search=True,
        ).get_all_fields_by_index_id()
        field_type_map = {i["field_name"]: i["field_type"] for i in final_fields_list}
        # 如果历史索引不包含bk_host_id, 则不需要进行bk_host_id的过滤
        include_bk_host_id = "bk_host_id" in field_type_map.keys() and settings.ENABLE_DHCP
        # 旧的采集器不会上报bk_host_id, 所以如果意外加入了这个条件会导致检索失败
        if include_bk_host_id and ip_chooser_host_id_list:
            new_addition.append({"field": "bk_host_id", "operator": "is one of", "value": ip_chooser_host_id_list})
        if search_ip_list:
            new_addition.append({"field": ip_field, "operator": "is one of", "value": list(set(search_ip_list))})
        # 当IP选择器传了模块,模版,动态拓扑但是实际没有主机时, 此时应不返回任何数据, 塞入特殊数据bk_host_id=0来实现
        if ip_chooser and not ip_chooser_host_id_list and not ip_chooser_ip_list:
            new_addition.append({"field": "bk_host_id", "operator": "is one of", "value": ["0"]})
        return new_addition

    def _transform_additions(self, index_info):
        field_list = []
        condition_list = []
        new_addition = self._combine_addition_ip_chooser(index_info=index_info)
        for addition in new_addition:
            # 全文检索key & 存量query_string转换
            if addition["field"] in ["*", "__query_string__"]:
                value_list = addition["value"] if isinstance(addition["value"], list) else addition["value"].split(",")
                new_value_list = []
                for value in value_list:
                    if addition["field"] == "*":
                        value = '"' + value.replace('"', '\\"') + '"'
                    if value:
                        new_value_list.append(value)
                if new_value_list:
                    new_query_string = " OR ".join(new_value_list)
                    if addition["field"] == "*" and self.query_string != "*":
                        self.query_string = self.query_string + " AND (" + new_query_string + ")"
                    else:
                        self.query_string = new_query_string
                continue
            if field_list:
                condition_list.append("and")
            if addition["operator"] in BASE_OP_MAP:
                field_list.append(
                    {
                        "field_name": addition["field"],
                        "op": BASE_OP_MAP[addition["operator"]],
                        "value": (
                            addition["value"] if isinstance(addition["value"], list) else addition["value"].split(",")
                        ),
                    }
                )
            else:
                new_field_list, new_condition_list = transform_advanced_addition(addition)
                field_list.extend(new_field_list)
                condition_list.extend(new_condition_list)
        for field in field_list:
            field["value"] = [str(value) for value in field["value"]]
        return {"field_list": field_list, "condition_list": condition_list}

    def _init_sort(self) -> list:
        index_set_id = self.search_params.get("index_set_ids", [])[0]
        # 获取用户对sort的排序需求
        sort_list: list = self.search_params.get("sort_list", [])
        is_union_search = self.search_params.get("is_union_search", False)

        if sort_list:
            return sort_list

        # 用户已设置排序规则  （联合检索时不使用用户在单个索引集上设置的排序规则）
        scope = self.search_params.get("search_type", "default")
        if not is_union_search:
            config_obj = UserIndexSetFieldsConfig.get_config(
                index_set_id=index_set_id, username=self.request_username, scope=scope
            )
            if config_obj:
                sort_list = config_obj.sort_list
                if sort_list:
                    return sort_list
        # 安全措施, 用户未设置排序规则，且未创建默认配置时, 使用默认排序规则
        index_info = self.index_info_list[0]
        return MappingHandlers(
            indices=index_info["scenario_id"],
            index_set_id=index_info["index_set_id"],
            scenario_id=index_info["scenario_id"],
            storage_cluster_id=index_info["storage_cluster_id"],
        ).get_default_sort_list(
            index_set_id=index_set_id,
            scenario_id=index_info["scenario_id"],
            scope=scope,
            default_sort_tag=self.search_params.get("default_sort_tag", False),
        )

    def init_base_dict(self):
        # 自动周期处理
        if self.search_params.get("interval", "auto") == "auto":
            interval = self._init_default_interval()
        else:
            interval = self.search_params["interval"]

        # 拼接查询参数列表
        query_list = []
        for index, index_info in enumerate(self.index_info_list):
            query_dict = {
                "data_source": settings.UNIFY_QUERY_DATA_SOURCE,
                "reference_name": REFERENCE_ALIAS[index],
                "dimensions": [],
                "time_field": "time",
                "conditions": self._transform_additions(index_info),
                "query_string": self.query_string,
                "function": [],
            }

            # 是否使用了聚类路由查询
            clustered_rt = None
            if index_info.get("using_clustering_proxy", False):
                clustered_rt = index_info["indices"]
            query_dict["table_id"] = BaseIndexSetHandler.get_data_label(
                index_info["origin_scenario_id"], index_info["index_set_id"], clustered_rt
            )

            if self.agg_field:
                query_dict["field_name"] = self.agg_field
            else:
                # 时间字段 & 类型 & 单位
                time_field, time_field_type, time_field_unit = SearchHandler.init_time_field(index_info["index_set_id"])
                query_dict["field_name"] = time_field

            query_list.append(query_dict)

        return {
            "query_list": query_list,
            "metric_merge": " + ".join([query["reference_name"] for query in query_list]),
            "order_by": self.order_by,
            "step": interval,
            "start_time": str(self.start_time),
            "end_time": str(self.end_time),
            "down_sample_range": "",
            "timezone": "UTC",  # 仅用于提供给 unify-query 生成读别名，对应存储入库时区
            "bk_biz_id": self.bk_biz_id,
        }

    def _deal_query_result(self, result_dict: dict) -> dict:
        log_list = []
        origin_log_list = []
        for log in result_dict["list"]:
            log = merge_nested_data(log)
            if (self.field_configs or self.text_fields_field_configs) and self.is_desensitize:
                log = self._log_desensitize(log)
            log = self._add_cmdb_fields(log)
            # 联合索引 增加索引集id信息
            log.update({"__index_set_id__": int(self.search_params["index_set_ids"][0])})
            if self.export_fields:
                new_origin_log = {}
                for _export_field in self.export_fields:
                    # 此处是为了虚拟字段[__set__, __module__, ipv6]可以导出
                    if _export_field in log:
                        new_origin_log[_export_field] = log[_export_field]
                    # 处理a.b.c的情况
                    elif "." in _export_field:
                        # 在log中找不到时,去log的子级查找
                        key, *field_list = _export_field.split(".")
                        _result = log.get(key, {})
                        for _field in field_list:
                            if isinstance(_result, dict) and _field in _result:
                                _result = _result[_field]
                            else:
                                _result = ""
                                break
                        new_origin_log[_export_field] = _result
                    else:
                        new_origin_log[_export_field] = log.get(_export_field, "")
                origin_log = new_origin_log
            else:
                origin_log = log
            _index = log.pop("__index", None)
            log.update({"index": _index})
            doc_id = log.pop("__doc_id", None)
            log.update({"__id__": doc_id})

            if "__highlight" not in log:
                origin_log_list.append(origin_log)
                log_list.append(log)
                continue
            else:
                origin_log_list.append(copy.deepcopy(origin_log))

            if not (self.field_configs or self.text_fields_field_configs) or not self.is_desensitize:
                log = self._deal_object_highlight(log=log, highlight=log["__highlight"])

            del log["__highlight"]
            log_list.append(log)
        result_dict.update(
            {
                "aggregations": {},
                "aggs": {},
                "list": log_list,
                "origin_log_list": origin_log_list,
                "total": result_dict.get("total", 0),
                "took": result_dict.get("took", 0),
            }
        )
        return result_dict

    def _analyze_field_length(self, log_list: list[dict[str, Any]]):
        for item in log_list:

            def get_field_and_get_length(_item: dict, father: str = ""):
                for key in _item:
                    _key: str = ""
                    if isinstance(_item[key], dict):
                        if father:
                            get_field_and_get_length(_item[key], f"{father}.{key}")
                        else:
                            get_field_and_get_length(_item[key], key)
                    else:
                        if father:
                            _key = f"{father}.{key}"
                        else:
                            _key = "%s" % key
                    if _key:
                        self._update_result_fields(_key, _item[key])

            get_field_and_get_length(item)
        return self.field

    def _update_result_fields(self, _key: str, _item: Any):
        max_len_dict_obj: MAX_LEN_DICT = self.field.get(_key)
        if max_len_dict_obj:
            # modify
            _len: int = max_len_dict_obj.get("max_length")
            try:
                new_len: int = len(str(_item))
            except BaseSearchResultAnalyzeException:
                new_len: int = 16
            if new_len >= _len:
                if new_len > len(_key):
                    max_len_dict_obj.update({"max_length": new_len})
                else:
                    max_len_dict_obj.update({"max_length": len(_key)})
            return
        # insert
        try:
            new_len: int = len(str(_item))
        except BaseSearchResultAnalyzeException:
            new_len: int = 16

        if new_len > len(_key):
            self.field.update({_key: {"max_length": new_len}})
        else:
            self.field.update({_key: {"max_length": len(_key)}})

    def _log_desensitize(self, log: dict = None):
        """
        字段脱敏
        """
        if not log:
            return log

        # 展开object对象
        log = expand_nested_data(log)
        # 保存一份未处理之前的log字段 用于脱敏之后的日志原文处理
        log_content_tmp = copy.deepcopy(log)

        # 字段脱敏处理
        log = self.desensitize_handler.transform_dict(log)

        # 原文字段应用其他字段的脱敏结果
        if not self.text_fields:
            return log

        for text_field in self.text_fields:  # ["log"]
            # 判断原文字段是否存在log中
            if text_field not in log.keys():
                continue

            for _config in self.field_configs:
                field_name = _config["field_name"]
                if field_name not in log.keys() or field_name == text_field:
                    continue
                log[text_field] = log[text_field].replace(str(log_content_tmp[field_name]), str(log[field_name]))

        # 处理原文字段自身绑定的脱敏逻辑
        if self.text_fields:
            log = self.text_fields_desensitize_handler.transform_dict(log)
        # 折叠object对象
        log = merge_nested_data(log)
        return log

    @classmethod
    def update_nested_dict(cls, base_dict: dict[str, Any], update_dict: dict[str, Any]) -> dict[str, Any]:
        """
        递归更新嵌套字典
        """
        if not isinstance(base_dict, dict):
            return base_dict
        for key, value in update_dict.items():
            if isinstance(value, dict):
                base_dict[key] = cls.update_nested_dict(base_dict.get(key, {}), value)
            else:
                base_dict[key] = value
        return base_dict

    @staticmethod
    def nested_dict_from_dotted_key(dotted_dict: dict[str, Any]) -> dict[str, Any]:
        result = {}
        for key, value in dotted_dict.items():
            parts = key.split(".")
            current_level = result
            for part in parts[:-1]:
                if part not in current_level:
                    current_level[part] = {}
                current_level = current_level[part]
            current_level[parts[-1]] = "".join(value)
        return result

    def _deal_object_highlight(self, log: dict[str, Any], highlight: dict[str, Any]) -> dict[str, Any]:
        """
        兼容Object类型字段的高亮
        ES层会返回打平后的高亮字段, 该函数将其高亮的字段更新至对应Object字段
        """
        nested_dict = self.nested_dict_from_dotted_key(dotted_dict=highlight)
        return self.update_nested_dict(log, nested_dict)

    def search(self, search_type="default", is_export=False):
        """
        search
        原始日志查询
        """
        search_dict = copy.deepcopy(self.base_dict)
        # 校验是否超出最大查询数量
        if self.search_params["size"] > MAX_RESULT_WINDOW:
            self.search_params["size"] = MAX_RESULT_WINDOW

        # 判断size，单次最大查询10000条数据
        once_size = copy.deepcopy(self.search_params["size"])
        if self.search_params["size"] > MAX_RESULT_WINDOW:
            once_size = MAX_RESULT_WINDOW

        pre_search = True
        time_difference = 0
        if self.start_time and self.end_time:
            # 计算时间差
            time_difference = (arrow.get(self.end_time) - arrow.get(self.start_time)).total_seconds()
        if time_difference < settings.PRE_SEARCH_SECONDS:
            pre_search = False

        # 下载操作
        if is_export:
            once_size = MAX_RESULT_WINDOW
            self.search_params["size"] = MAX_RESULT_WINDOW
            pre_search = False

        # 参数补充
        search_dict["from"] = self.search_params["begin"]
        search_dict["limit"] = once_size
        search_dict["highlight"] = {"enable": self.highlight}

        # 预查询
        result = self.query_ts_raw(search_dict, pre_search=pre_search)
        if pre_search and len(result["list"]) != once_size:
            # 全量查询
            result = self.query_ts_raw(search_dict)
        result = self._deal_query_result(result)

        # 脱敏配置日志原文检索 提前返回
        if self.search_params.get("original_search"):
            return result

        field_dict = self._analyze_field_length(result.get("list"))
        result.update({"fields": field_dict})

        # 保存检索历史，按用户、索引集、检索条件缓存5分钟
        # 保存首页检索和trace通用查询检索历史
        # 联合检索不保存单个索引集的检索历史
        is_union_search = self.search_params.get("is_union_search", False)
        if search_type and not is_union_search:
            self._save_history(result, search_type)

        return result

    def date_histogram(self):
        params = copy.deepcopy(self.base_dict)
        interval = self.search_params["interval"]
        # count聚合
        method = "count"
        for q in params["query_list"]:
            q["function"] = [{"method": method}, {"method": "date_histogram", "window": interval}]
            q["time_aggregation"] = {}
        params["step"] = interval
        params["order_by"] = []
        params["timezone"] = get_local_param("time_zone", settings.TIME_ZONE)
        response = self.query_ts_reference(params)
        return_data = {"aggs": {}}
        if not response["series"]:
            return return_data

        return_data = {"aggs": {"group_by_histogram": {"buckets": []}}}
        datetime_format = AggsHandlers.DATETIME_FORMAT_MAP.get(interval, AggsHandlers.DATETIME_FORMAT)
        time_multiplicator = 10**3
        values = response["series"][0]["values"]
        for value in values:
            key_as_string = timestamp_to_timeformat(
                value[0], time_multiplicator=time_multiplicator, t_format=datetime_format, tzformat=False
            )
            tmp = {"key_as_string": key_as_string, "key": value[0], "doc_count": value[1]}
            return_data["aggs"]["group_by_histogram"]["buckets"].append(tmp)
        return return_data

    def _add_cmdb_fields(self, log):
        if not self.search_params.get("bk_biz_id"):
            return log

        bk_biz_id = self.search_params.get("bk_biz_id")
        bk_host_id = log.get("bk_host_id")
        server_ip = log.get("serverIp", log.get("ip"))
        bk_cloud_id = log.get("cloudId", log.get("cloudid"))
        if not bk_host_id and not server_ip:
            return log
        # 以上情况说明请求不包含能去cmdb查询主机信息的字段，直接返回
        log["__module__"] = ""
        log["__set__"] = ""
        log["__ipv6__"] = ""

        host_key = bk_host_id if bk_host_id else server_ip
        host_info = CmdbHostCache.get(bk_biz_id, host_key)
        # 当主机被迁移业务或者删除的时候, 会导致缓存中没有该主机信息, 放空处理
        if not host_info:
            return log

        if bk_host_id and host_info:
            host = host_info
        else:
            if not bk_cloud_id:
                host = next(iter(host_info.values()))
            else:
                host = host_info.get(str(bk_cloud_id))
        if not host:
            return log

        set_list, module_list = [], []
        if host.get("topo"):
            for _set in host.get("topo", []):
                set_list.append(_set["bk_set_name"])
                for module in _set.get("module", []):
                    module_list.append(module["bk_module_name"])
        # 兼容旧缓存数据
        else:
            set_list = [_set["bk_inst_name"] for _set in host.get("set", [])]
            module_list = [_module["bk_inst_name"] for _module in host.get("module", [])]

        log["__set__"] = " | ".join(set_list)
        log["__module__"] = " | ".join(module_list)
        log["__ipv6__"] = host.get("bk_host_innerip_v6", "")
        return log

    def _save_history(self, result, search_type):
        # 避免回显尴尬, 检索历史存原始未增强的query_string
        params = {
            "keyword": self.origin_query_string,
            "ip_chooser": self.search_params.get("ip_chooser", {}),
            "addition": self.search_params.get("addition", []),
        }
        # 全局查询不记录
        if (not self.origin_query_string or self.origin_query_string == "*") and not self.search_params.get(
            "addition", []
        ):
            return
        self._cache_history(
            username=self.request_username,
            index_set_id=self.index_set_ids[0],
            params=params,
            search_type=search_type,
            search_mode=self.search_params.get("search_mode", "ui"),
            result=result,
        )

    @cache_five_minute("search_history_{username}_{index_set_id}_{search_type}_{params}_{search_mode}", need_md5=True)
    def _cache_history(self, *, username, index_set_id, params, search_type, search_mode, result):  # noqa
        history_params = copy.deepcopy(params)
        history_params.update(
            {
                "start_time": self.start_time,
                "end_time": self.end_time,
                "time_range": self.search_params.get("time_range"),
            }
        )

        # 首页检索历史在decorator记录
        if search_type == "default":
            result.update(
                {
                    "history_obj": {
                        "params": history_params,
                        "index_set_id": self.index_set_ids[0],
                        "search_type": search_type,
                        "search_mode": search_mode,
                        "from_favorite_id": self.search_params.get("from_favorite_id", 0),
                    }
                }
            )
        else:
            UserIndexSetSearchHistory.objects.create(
                index_set_id=self.index_set_ids[0],
                params=history_params,
                search_type=search_type,
                search_mode=search_mode,
                from_favorite_id=self.search_params.get("from_favorite_id", 0),
            )
