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
import hashlib
import json
import operator
import time
from typing import Any

import arrow
import pytz
import ujson
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext as _

from apps.api import BcsApi, BkLogApi, MonitorApi
from apps.api.base import DataApiRetryClass
from apps.api.modules.utils import get_non_bkcc_space_related_bkcc_biz_id
from apps.exceptions import ApiResultError
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import DIRECT_ESQUERY_SEARCH, LOG_DESENSITIZE
from apps.log_clustering.models import ClusteringConfig
from apps.log_databus.constants import EtlConfig
from apps.log_databus.models import CollectorConfig
from apps.log_desensitize.handlers.desensitize import DesensitizeHandler
from apps.log_desensitize.models import DesensitizeConfig, DesensitizeFieldConfig
from apps.log_desensitize.utils import expand_nested_data, merge_nested_data
from apps.log_esquery import metrics
from apps.log_esquery.esquery.esquery import EsQuery
from apps.log_esquery.serializers import (
    EsQueryDslAttrSerializer,
    EsQueryScrollAttrSerializer,
    EsQuerySearchAttrSerializer,
)
from apps.log_search.constants import (
    ASYNC_DIR,
    ASYNC_SORTED,
    CHECK_FIELD_LIST,
    CHECK_FIELD_MAX_VALUE_MAPPING,
    CHECK_FIELD_MIN_VALUE_MAPPING,
    DateFormat,
    DEFAULT_INDEX_SET_FIELDS_CONFIG_NAME,
    ERROR_MSG_CHECK_FIELDS_FROM_BKDATA,
    ERROR_MSG_CHECK_FIELDS_FROM_LOG,
    MAX_ASYNC_COUNT,
    MAX_EXPORT_REQUEST_RETRY,
    MAX_QUICK_EXPORT_ASYNC_COUNT,
    MAX_QUICK_EXPORT_ASYNC_SLICE_COUNT,
    MAX_RESULT_WINDOW,
    MAX_SEARCH_SIZE,
    SCROLL,
    SEARCH_OPTION_HISTORY_NUM,
    TIME_FIELD_MULTIPLE_MAPPING,
    FieldDataTypeEnum,
    IndexSetType,
    OperatorEnum,
    SearchScopeEnum,
    TimeEnum,
    TimeFieldTypeEnum,
    TimeFieldUnitEnum,
)
from apps.log_search.exceptions import (
    BaseSearchIndexSetDataDoseNotExists,
    BaseSearchIndexSetException,
    BaseSearchResultAnalyzeException,
    BaseSearchSortListException,
    IntegerErrorException,
    IntegerMaxErrorException,
    LogSearchException,
    MultiSearchErrorException,
    SearchExceedMaxSizeException,
    SearchIndexNoTimeFieldException,
    SearchIndicesNotExists,
    SearchUnKnowTimeField,
    SearchUnKnowTimeFieldType,
    UnionSearchErrorException,
    UnionSearchFieldsFailException,
    UserIndexSetSearchHistoryNotExistException,
)
from apps.log_search.handlers.es.dsl_bkdata_builder import (
    DslCreateSearchContextBodyCustomField,
    DslCreateSearchContextBodyScenarioBkData,
    DslCreateSearchContextBodyScenarioLog,
    DslCreateSearchTailBodyCustomField,
    DslCreateSearchTailBodyScenarioBkData,
    DslCreateSearchTailBodyScenarioLog,
)
from apps.log_search.handlers.es.indices_optimizer_context_tail import (
    IndicesOptimizerContextTail,
)
from apps.log_search.handlers.search.mapping_handlers import MappingHandlers
from apps.log_search.handlers.search.pre_search_handlers import PreSearchHandlers
from apps.log_search.models import (
    IndexSetFieldsConfig,
    LogIndexSet,
    LogIndexSetData,
    Scenario,
    Space,
    StorageClusterRecord,
    UserIndexSetFieldsConfig,
    UserIndexSetSearchHistory,
)
from apps.log_search.permission import Permission
from apps.log_search.utils import sort_func
from apps.models import model_to_dict
from apps.utils.cache import cache_five_minute
from apps.utils.core.cache.cmdb_host import CmdbHostCache
from apps.utils.db import array_group
from apps.utils.drf import custom_params_valid
from apps.utils.ipchooser import IPChooser
from apps.utils.local import (
    get_local_param,
    get_request_app_code,
    get_request_external_username,
    get_request_username, get_request,
)
from apps.utils.log import logger
from apps.utils.lucene import EnhanceLuceneAdapter, generate_query_string
from apps.utils.thread import MultiExecuteFunc
from bkm_ipchooser.constants import CommonEnum

max_len_dict = dict[str, int]  # pylint: disable=invalid-name


def fields_config(name: str, is_active: bool = False):
    def decorator(func):
        def func_decorator(*args, **kwargs):
            config = {"name": name, "is_active": is_active}
            result = func(*args, **kwargs)
            if isinstance(result, tuple):
                config["is_active"], config["extra"] = result
                return config
            if result is None:
                return config
            config["is_active"] = result
            return config

        return func_decorator

    return decorator


class SearchHandler:
    def __init__(
        self,
        index_set_id: int,
        search_dict: dict,
        pre_check_enable=True,
        can_highlight=True,
        export_fields=None,
        export_log: bool = False,
        only_for_agg: bool = False,
    ):
        # 请求用户名
        self.request_username = get_request_external_username() or get_request_username()

        self.search_dict: dict = search_dict
        self.export_log = export_log

        # 是否只用于聚合，可以简化某些查询语句
        self.only_for_agg = only_for_agg

        # 透传查询类型
        self.index_set_id = index_set_id
        self.search_dict.update({"index_set_id": index_set_id})

        # 原始索引和场景id（初始化mapping时传递）
        self.origin_indices: str = ""
        self.origin_scenario_id: str = ""

        self.scenario_id: str = ""
        self.storage_cluster_id: int = -1

        # 是否使用了聚类代理查询
        self.using_clustering_proxy = False

        # 构建索引集字符串, 并初始化scenario_id、storage_cluster_id
        self.indices: str = self._init_indices_str()
        self.search_dict.update(
            {"indices": self.indices, "scenario_id": self.scenario_id, "storage_cluster_id": self.storage_cluster_id}
        )

        # 拥有以上信息后可以进行初始化检查
        # 添加是否强校验的开关来控制是否强校验
        if pre_check_enable:
            self.search_dict.update(
                PreSearchHandlers.pre_check_fields(self.indices, self.scenario_id, self.storage_cluster_id)
            )
        # 是否包含嵌套字段
        self.include_nested_fields: bool = self.search_dict.get("include_nested_fields", True)

        # track_total_hits,默认不统计总数
        self.track_total_hits: bool = self.search_dict.get("track_total_hits", False)

        # 检索历史记录
        self.addition = copy.deepcopy(search_dict.get("addition", []))
        self.ip_chooser = copy.deepcopy(search_dict.get("ip_chooser", {}))
        self.from_favorite_id = self.search_dict.get("from_favorite_id", 0)
        # 检索模式
        self.search_mode = self.search_dict.get("search_mode", "ui")

        self.use_time_range = search_dict.get("use_time_range", True)
        # 构建时间字段
        self.time_field, self.time_field_type, self.time_field_unit = self.init_time_field(
            index_set_id, self.scenario_id
        )
        if not self.time_field:
            raise SearchIndexNoTimeFieldException()
        self.search_dict.update(
            {
                "time_field": self.time_field,
                "time_field_type": self.time_field_type,
                "time_field_unit": self.time_field_unit,
            }
        )
        # 根据时间字段确定时间字段类型，根据预查询强校验es拉取到的时间类型
        # 添加是否强校验的开关来控制是否强校验
        if pre_check_enable:
            self.time_field_type = self._set_time_filed_type(
                self.time_field, self.search_dict.get("fields_from_es", [])
            )
        self.search_dict.update({"time_field_type": self.time_field_type})

        # 设置IP字段对应的field ip serverIp
        self.ip_field: str = "ip" if self.scenario_id in [Scenario.BKDATA, Scenario.ES] else "serverIp"

        # 上下文、实时日志传递查询类型
        self.search_type_tag: str = search_dict.get("search_type_tag")

        # 透传时间
        self.time_range: str = search_dict.get("time_range")
        self.start_time: str = search_dict.get("start_time")
        self.end_time: str = search_dict.get("end_time")
        self.time_zone: str = get_local_param("time_zone", settings.TIME_ZONE)

        # 透传query string
        self.query_string: str = search_dict.get("keyword")
        self.origin_query_string: str = search_dict.get("keyword")
        self._enhance()
        self._add_all_fields_search()

        # 透传start
        self.start: int = search_dict.get("begin", 0)

        # 透传size
        self.size: int = search_dict.get("size", 30)

        # 透传filter. 初始化为None,表示filter还没有被初始化
        self._filter = None

        # 字段信息列表. 初始化为None,表示final_fields_list还没有被初始化
        self._mapping_handlers = None
        self._final_fields_list = None

        # 构建排序list
        self.sort_list: list = self._init_sort()

        # 构建aggs 聚合
        self.aggs: dict = self._init_aggs()

        # 初始化highlight
        self.highlight: dict = self._init_highlight(can_highlight)

        # result fields
        self.field: dict[str, max_len_dict] = {}

        # scroll 分页查询
        self.is_scroll: bool = settings.FEATURE_EXPORT_SCROLL

        # scroll
        self.scroll = SCROLL if self.is_scroll else None

        # collapse
        self.collapse = self.search_dict.get("collapse")

        # context search
        self.gseindex: int = search_dict.get("gseindex")
        self.gseIndex: int = search_dict.get("gseIndex")  # pylint: disable=invalid-name
        self.serverIp: str = search_dict.get("serverIp")  # pylint: disable=invalid-name
        self.ip: str = search_dict.get("ip", "undefined")
        self.path: str = search_dict.get("path", "")
        self.container_id: str = search_dict.get("container_id", None) or search_dict.get("__ext.container_id", None)
        self.logfile: str = search_dict.get("logfile", None)
        self._iteration_idx: str = search_dict.get("_iteration_idx", None)
        self.iterationIdx: str = search_dict.get("iterationIdx", None)  # pylint: disable=invalid-name
        self.iterationIndex: str = search_dict.get("iterationIndex", None)  # pylint: disable=invalid-name
        self.dtEventTimeStamp = search_dict.get("dtEventTimeStamp", None)  # pylint: disable=invalid-name
        self.bk_host_id = search_dict.get("bk_host_id", None)  # pylint: disable=invalid-name

        # 上下文初始化标记
        self.zero: bool = search_dict.get("zero", False)

        # 导出字段
        self.export_fields = export_fields

        self.is_desensitize = self._init_desensitize()

        # 初始化DB脱敏配置
        desensitize_config_obj = DesensitizeConfig.objects.filter(index_set_id=self.index_set_id).first()
        desensitize_field_config_objs = DesensitizeFieldConfig.objects.filter(index_set_id=self.index_set_id)

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

    def _enhance(self):
        """
        语法增强
        """
        if self.query_string is not None:
            enhance_lucene_adapter = EnhanceLuceneAdapter(query_string=self.query_string)
            self.query_string = enhance_lucene_adapter.enhance()

    def _add_all_fields_search(self):
        """
        补充全文检索条件
        """
        for item in self.addition:
            field: str = item.get("key") if item.get("key") else item.get("field")
            # 全文检索key & 存量query_string转换
            if field in ["*", "__query_string__"]:
                value = item.get("value", [])
                value_list = value if isinstance(value, list) else value.split(",")
                new_value_list = []
                for value in value_list:
                    if field == "*":
                        value = '"' + value.replace('"', '\\"') + '"'
                    if value:
                        new_value_list.append(value)
                if new_value_list:
                    new_query_string = " OR ".join(new_value_list)
                    if field == "*" and self.query_string != "*":
                        self.query_string = self.query_string + " AND (" + new_query_string + ")"
                    else:
                        self.query_string = new_query_string

    @property
    def index_set(self):
        if not hasattr(self, "_index_set"):
            self._index_set = LogIndexSet.objects.filter(index_set_id=self.index_set_id).first()
        return self._index_set

    def fields(self, scope="default"):
        is_union_search = self.search_dict.get("is_union_search", False)
        mapping_handlers = MappingHandlers(
            self.origin_indices,
            self.index_set_id,
            self.origin_scenario_id,
            self.storage_cluster_id,
            self.time_field,
            start_time=self.start_time,
            end_time=self.end_time,
            time_zone=self.time_zone,
        )
        field_result, display_fields = mapping_handlers.get_all_fields_by_index_id(
            scope=scope, is_union_search=is_union_search
        )

        if not is_union_search:
            sort_list: list = MappingHandlers.get_sort_list_by_index_id(index_set_id=self.index_set_id, scope=scope)
        else:
            sort_list = list()

        # 校验sort_list字段是否存在
        field_result_list = [i["field_name"] for i in field_result]
        sort_field_list = [j for j in sort_list if j[0] in field_result_list]

        if not sort_field_list and self.scenario_id in [Scenario.BKDATA, Scenario.LOG]:
            sort_field_list = self.sort_list

        result_dict: dict = {
            "fields": field_result,
            "display_fields": display_fields,
            "sort_list": sort_field_list,
            "time_field": self.time_field,
            "time_field_type": self.time_field_type,
            "time_field_unit": self.time_field_unit,
            "config": [],
        }

        if is_union_search:
            result_dict["config"].append(self.analyze_fields(field_result))
            return result_dict

        for fields_config in [
            self.bcs_web_console(field_result_list),
            self.bk_log_to_trace(),
            self.analyze_fields(field_result),
            self.bkmonitor(field_result_list),
            self.async_export(field_result),
            self.ip_topo_switch(),
            self.apm_relation(),
            self.clustering_config(),
            self.clean_config(),
        ]:
            result_dict["config"].append(fields_config)
        # 将用户当前使用的配置id传递给前端
        config_obj = UserIndexSetFieldsConfig.get_config(
            index_set_id=self.index_set_id, username=self.request_username, scope=scope
        )
        result_dict["config_id"] = config_obj.id if config_obj else ""

        return result_dict

    @fields_config("async_export")
    def async_export(self, field_result):
        """
        async_export
        @param field_result:
        @return:
        """
        sort_fields = self.index_set.sort_fields if self.index_set else []
        result = MappingHandlers.async_export_fields(field_result, self.scenario_id, sort_fields)
        if result["async_export_usable"]:
            return True, {"fields": result["async_export_fields"]}
        return False, {"usable_reason": result["async_export_usable_reason"]}

    @fields_config("bkmonitor")
    def bkmonitor(self, field_result_list):
        if "ip" in field_result_list or "serverIp" in field_result_list:
            return True
        reason = _("缺少字段, ip 和 serverIp 不能同时为空") + self._get_message_by_scenario()
        return False, {"reason": reason}

    @fields_config("ip_topo_switch")
    def ip_topo_switch(self):
        return MappingHandlers.init_ip_topo_switch(self.index_set_id)

    @fields_config("apm_relation")
    def apm_relation(self):
        qs = CollectorConfig.objects.filter(collector_config_id=self.index_set.collector_config_id)
        try:
            if qs.exists():
                collector_config = qs.first()
                params = {
                    "index_set_id": int(self.index_set_id),
                    "bk_data_id": int(collector_config.bk_data_id),
                    "bk_biz_id": collector_config.bk_biz_id,
                    "related_bk_biz_id": get_non_bkcc_space_related_bkcc_biz_id(collector_config.bk_biz_id),
                }
                if self.start_time and self.end_time:
                    params["start_time"] = self.start_time
                    params["end_time"] = self.end_time
                res = MonitorApi.query_log_relation(params=params)
            else:
                res = MonitorApi.query_log_relation(params={"index_set_id": int(self.index_set_id)})
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(f"fail to request log relation => index_set_id: {self.index_set_id}, exception => {e}")
            return False

        if not res:
            return False

        return True, res

    @fields_config("clustering_config")
    def clustering_config(self):
        """
        判断聚类配置
        """
        clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=self.index_set_id, raise_exception=False)
        if clustering_config:
            return (
                clustering_config.signature_enable,
                {
                    "collector_config_id": self.index_set.collector_config_id,
                    "signature_switch": clustering_config.signature_enable,
                    "clustering_field": clustering_config.clustering_fields,
                },
            )
        return False, {"collector_config_id": None, "signature_switch": False, "clustering_field": None}

    @fields_config("clean_config")
    def clean_config(self):
        """
        获取清洗配置
        """
        if not self.index_set.collector_config_id:
            return False, {"collector_config_id": None}
        collector_config = CollectorConfig.objects.get(collector_config_id=self.index_set.collector_config_id)
        return (
            collector_config.etl_config != EtlConfig.BK_LOG_TEXT,
            {
                "collector_scenario_id": collector_config.collector_scenario_id,
                "collector_config_id": self.index_set.collector_config_id,
            },
        )

    @fields_config("context_and_realtime")
    def analyze_fields(self, field_result):
        """
        analyze_fields
        @param field_result:
        @return:
        """
        # 设置了自定义排序字段的，默认认为支持上下文
        if self.index_set.target_fields and self.index_set.sort_fields:
            return True, {"reason": "", "context_fields": []}
        result = MappingHandlers.analyze_fields(field_result)
        if result["context_search_usable"]:
            return True, {"reason": "", "context_fields": result.get("context_fields", [])}
        return False, {"reason": result["usable_reason"]}

    @fields_config("bcs_web_console")
    def bcs_web_console(self, field_result_list):
        """
        bcs_web_console
        @param field_result_list:
        @return:
        """
        if not self._enable_bcs_manage():
            return False, {"reason": _("未配置BCS WEB CONSOLE")}

        container_fields = (
            ("cluster", "container_id"),
            ("__ext.io_tencent_bcs_cluster", "__ext.container_id"),
            ("__ext.bk_bcs_cluster_id", "__ext.container_id"),
        )

        for cluster_field, container_id_field in container_fields:
            if cluster_field in field_result_list and container_id_field in field_result_list:
                return True

        reason = _("{} 不能同时为空").format(container_fields)
        return False, {"reason": reason + self._get_message_by_scenario()}

    @fields_config("trace")
    def bk_log_to_trace(self):
        """
        [{
            "log_config": [{
                "index_set_id": 111,
                "field": "span_id"
            }],
            "trace_config": {
                "index_set_name": "xxxxxx"
            }
        }]
        """
        if not FeatureToggleObject.switch("bk_log_to_trace"):
            return False
        toggle = FeatureToggleObject.toggle("bk_log_to_trace")
        feature_config = toggle.feature_config
        if isinstance(feature_config, dict):
            feature_config = [feature_config]

        if not feature_config:
            return False

        for config in feature_config:
            log_config = config.get("log_config", [])
            target_config = [c for c in log_config if str(c["index_set_id"]) == str(self.index_set_id)]
            if not target_config:
                continue
            target_config, *_ = target_config
            return True, {**config.get("trace_config"), "field": target_config["field"]}

    def search(self, search_type="default", is_export=False):
        """
        search
        @param search_type:
        @return:
        """
        # 校验是否超出最大查询数量
        if not self.is_scroll and self.size > MAX_RESULT_WINDOW:
            self.size = MAX_RESULT_WINDOW

        if self.is_scroll and self.size > MAX_SEARCH_SIZE:
            raise SearchExceedMaxSizeException(SearchExceedMaxSizeException.MESSAGE.format(size=MAX_SEARCH_SIZE))

        # 判断size，单次最大查询10000条数据
        once_size = copy.deepcopy(self.size)
        if self.size > MAX_RESULT_WINDOW:
            once_size = MAX_RESULT_WINDOW

        # 把time_field,gseIndex,iterationIndex做为一个排序组
        new_sort_list = self.get_sort_group()
        if new_sort_list:
            self.sort_list = new_sort_list

        # 下载操作
        if is_export:
            once_size = MAX_RESULT_WINDOW
            self.size = MAX_RESULT_WINDOW

        # 有聚合时、预查询设置为0时, 不启用预查询
        time_difference = 0
        if self.aggs or settings.PRE_SEARCH_SECONDS == 0:
            pre_search = False
        else:
            pre_search = True
            if self.start_time and self.end_time:
                # 计算时间差
                time_difference = (arrow.get(self.end_time) - arrow.get(self.start_time)).total_seconds()
        # 预查询
        result = self._multi_search(once_size=once_size, pre_search=pre_search)
        if pre_search and len(result["hits"]["hits"]) != self.size and time_difference > settings.PRE_SEARCH_SECONDS:
            # 全量查询
            result = self._multi_search(once_size=once_size)

        # 需要scroll滚动查询：is_scroll为True，size超出单次最大查询限制，total大于MAX_RESULT_WINDOW
        # @TODO bkdata暂不支持scroll查询
        if self._can_scroll(result):
            result = self._scroll(result)

        _scroll_id = result.get("_scroll_id")

        result = self._deal_query_result(result)
        # 脱敏配置日志原文检索 提前返回
        if self.search_dict.get("original_search"):
            return result
        field_dict = self._analyze_field_length(result.get("list"))
        result.update({"fields": field_dict})

        # 保存检索历史，按用户、索引集、检索条件缓存5分钟
        # 保存首页检索和trace通用查询检索历史
        # 联合检索不保存单个索引集的检索历史
        is_union_search = self.search_dict.get("is_union_search", False)
        if search_type and not is_union_search:
            self._save_history(result, search_type)

        # 补充scroll id
        if _scroll_id:
            result.update({"scroll_id": _scroll_id})

        return result

    def get_sort_group(self):
        """
        排序字段是self.time_field时,那么补充上gseIndex/gseindex, iterationIndex/_iteration_idx
        """
        target_fields = self.index_set.target_fields
        sort_fields = self.index_set.sort_fields
        # 根据不同情景为排序组字段赋予不同的名称
        if self.scenario_id == Scenario.LOG:
            gse_index = "gseIndex"
            iteration_index = "iterationIndex"
        elif (
            self.scenario_id == Scenario.BKDATA
            and not (target_fields and sort_fields)
            and not self.using_clustering_proxy
        ):
            gse_index = "gseindex"
            iteration_index = "_iteration_idx"
        else:
            gse_index = iteration_index = ""

        # 排序字段映射
        sort_field_mappings = {}
        for field_list in self.sort_list:
            sort_field_mappings[field_list[0]] = field_list[1]

        new_sort_list = []
        if self.time_field in sort_field_mappings:
            for sort_field in self.sort_list:
                _field, order = sort_field
                if _field == self.time_field:
                    # 获取拉取字段信息列表
                    field_result_list = [i["field_name"] for i in self.final_fields_list]

                    new_sort_list.append([_field, order])
                    if gse_index in field_result_list:
                        new_sort_list.append([gse_index, order])
                    if iteration_index in field_result_list:
                        new_sort_list.append([iteration_index, order])
                elif _field not in [gse_index, iteration_index]:
                    new_sort_list.append(sort_field)

        return new_sort_list

    def fetch_esquery_method(self, method_name="search"):
        """
        根据特性开关和传入方法名，返回不同方式的调用方法
        :param method_name: 默认返回esquery的search方法
        :return: esquery中定义的方法
        """
        if FeatureToggleObject.switch(DIRECT_ESQUERY_SEARCH, self.search_dict.get("bk_biz_id")):
            return getattr(self, f"direct_esquery_{method_name}")
        else:
            return getattr(BkLogApi, method_name)

    @classmethod
    def direct_esquery_search(cls, params, **kwargs):
        data = custom_params_valid(EsQuerySearchAttrSerializer, params)
        start_at = time.time()
        exc = None
        try:
            result = EsQuery(data).search()
        except Exception as e:
            exc = e
            raise
        finally:
            labels = {
                "index_set_id": data.get("index_set_id") or -1,
                "indices": data.get("indices") or "",
                "scenario_id": data.get("scenario_id") or "",
                "storage_cluster_id": data.get("storage_cluster_id") or -1,
                "status": str(exc),
                "source_app_code": get_request_app_code(),
            }
            metrics.ESQUERY_SEARCH_LATENCY.labels(**labels).observe(time.time() - start_at)
            metrics.ESQUERY_SEARCH_COUNT.labels(**labels).inc()
        return result

    @classmethod
    def direct_esquery_dsl(cls, params, **kwargs):
        data = custom_params_valid(EsQueryDslAttrSerializer, params)
        return EsQuery(data).dsl()

    @classmethod
    def direct_esquery_scroll(cls, params, **kwargs):
        data = custom_params_valid(EsQueryScrollAttrSerializer, params)
        return EsQuery(data).scroll()

    def _multi_search(self, once_size: int, pre_search: bool = False):
        """
        根据存储集群切换记录多线程请求 BkLogApi.search
        """

        params = {
            "indices": self.indices,
            "scenario_id": self.scenario_id,
            "storage_cluster_id": self.storage_cluster_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "filter": self.filter,
            "query_string": self.query_string,
            "sort_list": self.sort_list,
            "start": self.start,
            "size": once_size,
            "aggs": self.aggs,
            "highlight": self.highlight,
            "use_time_range": self.use_time_range,
            "time_zone": self.time_zone,
            "time_range": self.time_range,
            "time_field": self.time_field,
            "time_field_type": self.time_field_type,
            "time_field_unit": self.time_field_unit,
            "scroll": self.scroll,
            "collapse": self.collapse,
            "include_nested_fields": self.include_nested_fields,
            "track_total_hits": self.track_total_hits,
        }

        storage_cluster_record_objs = StorageClusterRecord.objects.none()

        if self.start_time:
            try:
                tz_info = pytz.timezone(get_local_param("time_zone", settings.TIME_ZONE))
                if type(self.start_time) in [int, float]:
                    start_time = arrow.get(self.start_time).to(tz=tz_info).datetime
                    end_time = arrow.get(self.end_time).to(tz=tz_info).datetime
                else:
                    start_time = arrow.get(self.start_time).replace(tzinfo=tz_info).datetime
                    end_time = arrow.get(self.end_time).replace(tzinfo=tz_info).datetime
                storage_cluster_record_objs = StorageClusterRecord.objects.filter(
                    index_set_id=int(self.index_set_id), created_at__gt=(start_time - datetime.timedelta(hours=1))
                ).exclude(storage_cluster_id=self.storage_cluster_id)

                # 预查询处理
                pre_search_seconds = settings.PRE_SEARCH_SECONDS
                first_field, order = self.sort_list[0] if self.sort_list else [None, None]
                if pre_search and pre_search_seconds and first_field == self.time_field:
                    date_format = DateFormat.DATETIME_FORMAT
                    pre_search_end_time = start_time + datetime.timedelta(seconds=pre_search_seconds)
                    pre_search_start_time = end_time - datetime.timedelta(seconds=pre_search_seconds)
                    if order == "desc" and start_time < pre_search_start_time:
                        params.update({"start_time": pre_search_start_time.strftime(date_format)})
                    elif order == "asc" and end_time > pre_search_end_time:
                        params.update({"end_time": pre_search_end_time.strftime(date_format)})
            except Exception as e:  # pylint: disable=broad-except
                logger.exception(f"[_multi_search] parse time error -> e: {e}")

        # 获取search对应的esquery方法
        search_func = self.fetch_esquery_method(method_name="search")

        if not storage_cluster_record_objs:
            try:
                data = search_func(params)
                # 把shards中的failures信息解析后raise异常出来
                if data.get("_shards", {}).get("failed"):
                    errors = data["_shards"]["failures"][0]["reason"]["reason"]
                    raise LogSearchException(errors)

                return data
            except Exception as e:
                raise LogSearchException(LogSearchException.MESSAGE.format(e=e))

        storage_cluster_ids = {self.storage_cluster_id}

        multi_execute_func = MultiExecuteFunc()

        multi_num = 1

        # 查询多个集群数据时 start 每次从0开始
        params["start"] = 0
        params["size"] = once_size + self.start

        # 获取当前使用的存储集群数据
        multi_execute_func.append(result_key=f"multi_search_{multi_num}", func=search_func, params=params)

        # 获取历史使用的存储集群数据
        for storage_cluster_record_obj in storage_cluster_record_objs:
            if storage_cluster_record_obj.storage_cluster_id not in storage_cluster_ids:
                multi_params = copy.deepcopy(params)
                multi_params["storage_cluster_id"] = storage_cluster_record_obj.storage_cluster_id
                multi_num += 1
                multi_execute_func.append(result_key=f"multi_search_{multi_num}", func=search_func, params=multi_params)
                storage_cluster_ids.add(storage_cluster_record_obj.storage_cluster_id)

        multi_result = multi_execute_func.run()

        # 合并多个集群的检索结果
        merge_result = dict()
        try:
            for _key, _result in multi_result.items():
                if not _result:
                    continue

                if not merge_result:
                    merge_result = _result
                    continue

                # 处理took
                merge_result["took"] = max(_result.get("took", 0), merge_result.get("took", 0))

                # 处理 _shards
                if "_shards" not in merge_result:
                    merge_result["_shards"] = dict()
                for _k, _v in _result.get("_shards", {}).items():
                    if _k not in merge_result["_shards"]:
                        merge_result["_shards"][_k] = 0
                    merge_result["_shards"][_k] += _v

                # 处理 hits
                if "hits" not in merge_result:
                    merge_result["hits"] = {"total": 0, "max_score": None, "hits": []}
                merge_result["hits"]["total"] += _result.get("hits", {}).get("total", 0)
                merge_result["hits"]["hits"].extend(_result.get("hits", {}).get("hits", []))

                # 处理 aggregations
                if "aggregations" not in _result:
                    continue

                if "aggregations" not in merge_result:
                    merge_result["aggregations"] = _result.get("aggregations", {})
                    continue

                for _agg_k, _agg_v in _result.get("aggregations", {}).items():
                    if _agg_k not in merge_result["aggregations"]:
                        merge_result["aggregations"][_agg_k] = _agg_v
                        continue
                    if not isinstance(_agg_v, dict):
                        continue
                    for _agg_v_k, _agg_v_v in _agg_v.items():
                        if _agg_v_k not in merge_result["aggregations"][_agg_k]:
                            merge_result["aggregations"][_agg_k][_agg_v_k] = _agg_v_v
                            continue
                        if isinstance(_agg_v_v, int):
                            merge_result["aggregations"][_agg_k][_agg_v_k] += _agg_v_v
                        elif isinstance(_agg_v_v, list):
                            merge_result["aggregations"][_agg_k][_agg_v_k].extend(_agg_v_v)
                        else:
                            continue

            # 排序分页处理
            if not merge_result:
                return merge_result

            # hits 排序处理
            hits = merge_result.get("hits", {}).get("hits", [])
            if hits:
                sorted_hits = sort_func(data=hits, sort_list=self.sort_list, key_func=lambda x: x["_source"])
                merge_result["hits"]["hits"] = sorted_hits[self.start : (once_size + self.start)]

            aggregations = merge_result.get("aggregations", {})

            # buckets 排序合并处理
            if aggregations:
                for _kk, _vv in aggregations.items():
                    if not isinstance(_vv, dict) or "buckets" not in _vv:
                        continue
                    buckets = _vv.get("buckets", [])
                    if buckets:
                        # 合并
                        buckets_info = dict()
                        for bucket in buckets:
                            _key = bucket["key"]
                            if _key not in buckets_info:
                                buckets_info[_key] = bucket
                                continue
                            buckets_info[_key]["doc_count"] += bucket["doc_count"]
                        sorted_buckets = sorted(list(buckets_info.values()), key=operator.itemgetter("key"))
                        merge_result["aggregations"][_kk]["buckets"] = sorted_buckets
        except Exception as e:
            logger.error(f"[_multi_search] error -> e: {e}")
            raise MultiSearchErrorException()

        return merge_result

    def scroll_search(self):
        """
        日志scroll查询
        """
        # scroll初次查询，性能考虑暂不支持用户透传scroll 默认1m
        self.scroll = SCROLL
        scroll_id = self.search_dict.get("scroll_id")
        if not scroll_id:
            self.is_scroll = True
            return self.search()

        # scroll查询
        try:
            result = BkLogApi.scroll(
                {
                    "indices": self.indices,
                    "scenario_id": self.scenario_id,
                    "storage_cluster_id": self.storage_cluster_id,
                    "scroll": self.scroll,
                    "scroll_id": scroll_id,
                }
            )
        except ApiResultError as e:
            logger.error(f"scroll 查询失败：{e}")
            raise ApiResultError(_("scroll 查询失败"), code=e.code, errors=e.errors)
        _scroll_id = result.get("_scroll_id")
        result = self._deal_query_result(result)
        result.update({"scroll_id": _scroll_id})
        return result

    def _save_history(self, result, search_type):
        # 避免回显尴尬, 检索历史存原始未增强的query_string
        params = {"keyword": self.origin_query_string, "ip_chooser": self.ip_chooser, "addition": self.addition}
        # 全局查询不记录
        if (not self.origin_query_string or self.origin_query_string == "*") and not self.addition:
            return
        self._cache_history(
            username=self.request_username,
            index_set_id=self.index_set_id,
            params=params,
            search_type=search_type,
            search_mode=self.search_mode,
            result=result,
        )

    @cache_five_minute("search_history_{username}_{index_set_id}_{search_type}_{params}_{search_mode}", need_md5=True)
    def _cache_history(self, *, username, index_set_id, params, search_type, search_mode, result):  # noqa
        history_params = copy.deepcopy(params)
        history_params.update({"start_time": self.start_time, "end_time": self.end_time, "time_range": self.time_range})

        # 首页检索历史在decorator记录
        if search_type == "default":
            result.update(
                {
                    "history_obj": {
                        "params": history_params,
                        "index_set_id": self.index_set_id,
                        "search_type": search_type,
                        "search_mode": search_mode,
                        "from_favorite_id": self.from_favorite_id,
                    }
                }
            )
        else:
            UserIndexSetSearchHistory.objects.create(
                index_set_id=self.index_set_id,
                params=history_params,
                search_type=search_type,
                search_mode=search_mode,
                from_favorite_id=self.from_favorite_id,
            )

    def _can_scroll(self, result) -> bool:
        return (
            self.scenario_id != Scenario.BKDATA
            and self.is_scroll
            and result["hits"]["total"] > MAX_RESULT_WINDOW
            and self.size > MAX_RESULT_WINDOW
        )

    def _scroll(self, search_result):
        scroll_result = copy.deepcopy(search_result)
        scroll_size = len(scroll_result["hits"]["hits"])
        result_size = len(search_result["hits"]["hits"])

        # 判断是否继续查询：scroll_result["hits"]["hits"] == 10000 & 查询doc数量不足size
        while scroll_size == MAX_RESULT_WINDOW and result_size < self.size:
            _scroll_id = scroll_result["_scroll_id"]
            scroll_result = BkLogApi.scroll(
                {
                    "indices": self.indices,
                    "scenario_id": self.scenario_id,
                    "storage_cluster_id": self.storage_cluster_id,
                    "scroll": self.scroll,
                    "scroll_id": _scroll_id,
                }
            )

            scroll_size = len(scroll_result["hits"]["hits"])
            less_size = self.size - result_size
            if less_size < scroll_size:
                search_result["hits"]["hits"].extend(scroll_result["hits"]["hits"][:less_size])
            else:
                search_result["hits"]["hits"].extend(scroll_result["hits"]["hits"])
            result_size = len(search_result["hits"]["hits"])
            search_result["hits"]["total"] = scroll_result["hits"]["total"]

        return search_result

    def pre_get_result(self, sorted_fields: list, size: int):
        """
        pre_get_result
        @param sorted_fields:
        @param size:
        @return:
        """
        # 获取search对应的esquery方法
        search_func = self.fetch_esquery_method(method_name="search")
        if self.scenario_id == Scenario.ES:
            result = search_func(
                {
                    "indices": self.indices,
                    "scenario_id": self.scenario_id,
                    "storage_cluster_id": self.storage_cluster_id,
                    "start_time": self.start_time,
                    "end_time": self.end_time,
                    "query_string": self.query_string,
                    "filter": self.filter,
                    "sort_list": self.sort_list,
                    "start": self.start,
                    "size": size,
                    "aggs": self.aggs,
                    "highlight": self.highlight,
                    "time_zone": self.time_zone,
                    "time_range": self.time_range,
                    "use_time_range": self.use_time_range,
                    "time_field": self.time_field,
                    "time_field_type": self.time_field_type,
                    "time_field_unit": self.time_field_unit,
                    "scroll": SCROLL,
                    "collapse": self.collapse,
                },
                data_api_retry_cls=DataApiRetryClass.create_retry_obj(
                    exceptions=[BaseException],
                    stop_max_attempt_number=MAX_EXPORT_REQUEST_RETRY,
                ),
            )
            return result

        result = search_func(
            {
                "indices": self.indices,
                "scenario_id": self.scenario_id,
                "storage_cluster_id": self.storage_cluster_id,
                "start_time": self.start_time,
                "end_time": self.end_time,
                "query_string": self.query_string,
                "filter": self.filter,
                "sort_list": sorted_fields,
                "start": self.start,
                "size": size,
                "aggs": self.aggs,
                "highlight": self.highlight,
                "time_zone": self.time_zone,
                "time_range": self.time_range,
                "time_field": self.time_field,
                "use_time_range": self.use_time_range,
                "time_field_type": self.time_field_type,
                "time_field_unit": self.time_field_unit,
                "scroll": None,
                "collapse": self.collapse,
            },
            data_api_retry_cls=DataApiRetryClass.create_retry_obj(
                exceptions=[BaseException], stop_max_attempt_number=MAX_EXPORT_REQUEST_RETRY
            ),
        )
        return result

    def search_after_result(self, search_result, sorted_fields):
        """
        search_after_result
        @param search_result:
        @param sorted_fields:
        @return:
        """
        # 获取search对应的esquery方法
        search_func = self.fetch_esquery_method(method_name="search")
        search_after_size = len(search_result["hits"]["hits"])
        result_size = search_after_size
        max_result_window = self.index_set.result_window
        while search_after_size == max_result_window and result_size < max(
            self.index_set.max_async_count, MAX_ASYNC_COUNT
        ):
            search_after = []
            for sorted_field in sorted_fields:
                search_after.append(search_result["hits"]["hits"][-1]["_source"].get(sorted_field[0]))
            search_result = search_func(
                {
                    "indices": self.indices,
                    "scenario_id": self.scenario_id,
                    "storage_cluster_id": self.storage_cluster_id,
                    "start_time": self.start_time,
                    "end_time": self.end_time,
                    "query_string": self.query_string,
                    "filter": self.filter,
                    "sort_list": sorted_fields,
                    "start": self.start,
                    "size": max_result_window,
                    "aggs": self.aggs,
                    "highlight": self.highlight,
                    "time_zone": self.time_zone,
                    "time_range": self.time_range,
                    "use_time_range": self.use_time_range,
                    "time_field": self.time_field,
                    "time_field_type": self.time_field_type,
                    "time_field_unit": self.time_field_unit,
                    "scroll": self.scroll,
                    "collapse": self.collapse,
                    "search_after": search_after,
                    "track_total_hits": False,
                },
                data_api_retry_cls=DataApiRetryClass.create_retry_obj(
                    exceptions=[BaseException], stop_max_attempt_number=MAX_EXPORT_REQUEST_RETRY
                ),
            )

            search_after_size = len(search_result["hits"]["hits"])
            result_size += search_after_size
            yield self._deal_query_result(search_result)

    def scroll_result(self, scroll_result):
        """
        scroll_result
        @param scroll_result:
        @return:
        """
        # 获取scroll对应的esquery方法
        scroll_func = self.fetch_esquery_method(method_name="scroll")
        scroll_size = len(scroll_result["hits"]["hits"])
        result_size = scroll_size
        max_result_window = self.index_set.result_window
        while scroll_size == max_result_window and result_size < max(self.index_set.max_async_count, MAX_ASYNC_COUNT):
            _scroll_id = scroll_result["_scroll_id"]
            scroll_result = scroll_func(
                {
                    "indices": self.indices,
                    "scenario_id": self.scenario_id,
                    "storage_cluster_id": self.storage_cluster_id,
                    "scroll": SCROLL,
                    "scroll_id": _scroll_id,
                },
                data_api_retry_cls=DataApiRetryClass.create_retry_obj(
                    exceptions=[BaseException], stop_max_attempt_number=MAX_EXPORT_REQUEST_RETRY
                ),
            )
            scroll_size = len(scroll_result["hits"]["hits"])
            result_size += scroll_size
            yield self._deal_query_result(scroll_result)

    def multi_get_slice_data(self, pre_file_name, export_file_type):
        collector_config = CollectorConfig.objects.filter(index_set_id=self.index_set_id).first()
        if collector_config:
            storage_shards_nums = collector_config.storage_shards_nums
            if storage_shards_nums == 1 or storage_shards_nums >= MAX_QUICK_EXPORT_ASYNC_SLICE_COUNT:
                slice_max = MAX_QUICK_EXPORT_ASYNC_SLICE_COUNT
            else:
                slice_max = storage_shards_nums
        else:
            slice_max = MAX_QUICK_EXPORT_ASYNC_SLICE_COUNT
        multi_execute_func = MultiExecuteFunc(max_workers=slice_max)
        for idx in range(slice_max):
            body = {
                "slice_id": idx,
                "slice_max": slice_max,
                "file_name": f"{pre_file_name}_slice_{idx}",
                "export_file_type": export_file_type,
            }
            multi_execute_func.append(result_key=idx, func=self.get_slice_data, params=body, multi_func_params=True)
        result = multi_execute_func.run(return_exception=True)
        return result

    def get_slice_data(self, slice_id: int, slice_max: int, file_name: str, export_file_type: str):
        """
        get_slice_data
        @param slice_id:
        @param slice_max:
        @param file_name:
        @param export_file_type:
        @return:
        """
        result = self.slice_pre_get_result(size=MAX_RESULT_WINDOW, slice_id=slice_id, slice_max=slice_max)
        generate_result = self.sliced_scroll_result(result)

        # 文件路径
        file_path = f"{ASYNC_DIR}/{file_name}_cluster_{self.storage_cluster_id}.{export_file_type}"

        def content_generator():
            yield from result.get("hits", {}).get("hits", [])
            for res in generate_result:
                origin_result_list = res.get("hits", {}).get("hits", [])
                yield from origin_result_list

        with open(file_path, "a+", encoding="utf-8") as f:
            for content in content_generator():
                f.write(f"{ujson.dumps(content, ensure_ascii=False)}\n")
        return file_path

    def slice_pre_get_result(self, size: int, slice_id: int, slice_max: int):
        """
        slice_pre_get_result
        @param size:
        @param slice_id:
        @param slice_max:
        @return:
        """
        # 获取search对应的esquery方法
        search_func = self.fetch_esquery_method(method_name="search")
        result = search_func(
            {
                "indices": self.indices,
                "scenario_id": self.scenario_id,
                "storage_cluster_id": self.storage_cluster_id,
                "start_time": self.start_time,
                "end_time": self.end_time,
                "query_string": self.query_string,
                "filter": self.filter,
                "start": self.start,
                "size": size,
                "aggs": self.aggs,
                "highlight": self.highlight,
                "time_zone": self.time_zone,
                "time_range": self.time_range,
                "time_field": self.time_field,
                "use_time_range": self.use_time_range,
                "time_field_type": self.time_field_type,
                "time_field_unit": self.time_field_unit,
                "scroll": SCROLL,
                "collapse": self.collapse,
                "slice_search": True,
                "slice_id": slice_id,
                "slice_max": slice_max,
            },
            data_api_retry_cls=DataApiRetryClass.create_retry_obj(
                exceptions=[BaseException], stop_max_attempt_number=MAX_EXPORT_REQUEST_RETRY
            ),
        )
        return result

    def sliced_scroll_result(self, scroll_result):
        """
        sliced_scroll_result
        @param scroll_result:
        @return:
        """
        # 获取scroll对应的esquery方法
        scroll_func = self.fetch_esquery_method(method_name="scroll")
        scroll_size = len(scroll_result["hits"]["hits"])
        result_size = scroll_size
        while scroll_size == MAX_RESULT_WINDOW and result_size < MAX_QUICK_EXPORT_ASYNC_COUNT:
            _scroll_id = scroll_result["_scroll_id"]
            scroll_result = scroll_func(
                {
                    "indices": self.indices,
                    "scenario_id": self.scenario_id,
                    "storage_cluster_id": self.storage_cluster_id,
                    "scroll": SCROLL,
                    "scroll_id": _scroll_id,
                },
                data_api_retry_cls=DataApiRetryClass.create_retry_obj(
                    exceptions=[BaseException], stop_max_attempt_number=MAX_EXPORT_REQUEST_RETRY
                ),
            )
            scroll_size = len(scroll_result["hits"]["hits"])
            result_size += scroll_size
            yield scroll_result

    @staticmethod
    def get_bcs_manage_url(cluster_id, container_id):
        """
        get_bcs_manage_url
        @param cluster_id:
        @param container_id:
        @return:
        """
        bcs_cluster_info = BcsApi.get_cluster_by_cluster_id({"cluster_id": cluster_id.upper()})
        space = Space.objects.filter(space_code=bcs_cluster_info["projectID"]).first()
        project_code = ""
        if space:
            project_code = space.space_id
        url = (
            settings.BCS_WEB_CONSOLE_DOMAIN
            + f"/bcsapi/v4/webconsole/projects/{project_code}/clusters/{cluster_id.upper()}/?container_id={container_id}"
        )
        return url

    @staticmethod
    def _get_cache_key(basic_key, params):
        cache_str = f"{basic_key}_{json.dumps(params)}"
        hash_md5 = hashlib.new("md5")
        hash_md5.update(cache_str.encode("utf-8"))
        cache_key = hash_md5.hexdigest()
        return cache_key

    @staticmethod
    def search_option_history(space_uid: str, index_set_type: str = IndexSetType.SINGLE.value):
        """
        用户检索选项历史记录
        """
        username = get_request_external_username() or get_request_username()

        # 找出用户指定索引集类型下所有记录
        history_objs = UserIndexSetSearchHistory.objects.filter(
            created_by=username, index_set_type=index_set_type
        ).order_by("-created_at")

        # 过滤出当前空间下的记录
        if index_set_type == IndexSetType.SINGLE.value:
            index_set_id_all = list(set(history_objs.values_list("index_set_id", flat=True)))
        else:
            index_set_id_all = list()
            for obj in history_objs:
                index_set_id_all.extend(obj.index_set_ids)

        if not index_set_id_all:
            return []
        from apps.log_search.handlers.index_set import IndexSetHandler

        # 获取当前空间关联空间的索引集
        space_uids = IndexSetHandler.get_all_related_space_uids(space_uid)
        index_set_objs = LogIndexSet.objects.filter(index_set_id__in=index_set_id_all, space_uid__in=space_uids).values(
            "index_set_id", "index_set_name"
        )

        effect_index_set_mapping = {obj["index_set_id"]: obj["index_set_name"] for obj in index_set_objs}

        if not effect_index_set_mapping:
            return []

        ret = list()

        option_set = set()

        for obj in history_objs:
            # 最多只返回10条记录
            if len(ret) >= SEARCH_OPTION_HISTORY_NUM:
                break

            info = model_to_dict(obj)
            if obj.index_set_type == IndexSetType.SINGLE.value:
                if obj.index_set_id not in effect_index_set_mapping or obj.index_set_id in option_set:
                    continue
                info["index_set_name"] = effect_index_set_mapping[obj.index_set_id]
                ret.append(info)
                option_set.add(info["index_set_id"])
            else:
                if obj.index_set_ids[0] not in effect_index_set_mapping or tuple(obj.index_set_ids) in option_set:
                    continue
                info["index_set_names"] = [
                    effect_index_set_mapping.get(index_set_id) for index_set_id in obj.index_set_ids
                ]
                ret.append(info)
                option_set.add(tuple(info["index_set_ids"]))

        return ret

    @staticmethod
    def search_option_history_delete(
        space_uid: str, history_id: int = None, index_set_type: str = IndexSetType.SINGLE.value, is_delete_all=False
    ):
        """删除用户检索选项历史记录"""
        if not is_delete_all:
            obj = UserIndexSetSearchHistory.objects.filter(pk=int(history_id)).first()

            if not obj:
                raise UserIndexSetSearchHistoryNotExistException()

            delete_params = {
                "created_by": obj.created_by,
                "index_set_type": obj.index_set_type,
            }

            if obj.index_set_type == IndexSetType.SINGLE.value:
                delete_params.update({"index_set_id": obj.index_set_id})
            else:
                delete_params.update({"index_set_ids": obj.index_set_ids})

            return UserIndexSetSearchHistory.objects.filter(**delete_params).delete()
        else:
            username = get_request_external_username() or get_request_username()

            history_objs = UserIndexSetSearchHistory.objects.filter(created_by=username, index_set_type=index_set_type)

            if index_set_type == IndexSetType.SINGLE.value:
                index_set_id_all = list(set(history_objs.values_list("index_set_id", flat=True)))
            else:
                index_set_id_all = list()
                for obj in history_objs:
                    index_set_ids = obj.index_set_ids or []
                    index_set_id_all.extend(index_set_ids)
                index_set_id_all = list(set(index_set_id_all))

            from apps.log_search.handlers.index_set import IndexSetHandler

            # 获取当前空间关联空间的索引集
            space_uids = IndexSetHandler.get_all_related_space_uids(space_uid)
            effect_index_set_ids = list(
                LogIndexSet.objects.filter(index_set_id__in=index_set_id_all, space_uid__in=space_uids).values_list(
                    "index_set_id", flat=True
                )
            )

            delete_history_ids = set()
            for obj in history_objs:
                obj_index_set_type = obj.index_set_type or IndexSetType.SINGLE.value
                if obj_index_set_type == IndexSetType.SINGLE.value:
                    check_id = obj.index_set_id or 0
                else:
                    check_id = obj.index_set_ids[0] if obj.index_set_ids else 0

                if check_id and check_id in effect_index_set_ids:
                    delete_history_ids.add(obj.pk)

            return UserIndexSetSearchHistory.objects.filter(pk__in=delete_history_ids).delete()

    @staticmethod
    def search_history(index_set_id=None, index_set_ids=None, is_union_search=False, **kwargs):
        """
        search_history
        @param index_set_id:
        @param is_union_search:
        @param index_set_ids:
        @param kwargs:
        @return:
        """
        # 外部用户获取搜索历史的时候, 用external_username
        username = get_request_external_username() or get_request_username()

        if not is_union_search:
            if index_set_id:
                history_obj = (
                    UserIndexSetSearchHistory.objects.filter(
                        is_deleted=False,
                        created_by=username,
                        index_set_id=index_set_id,
                        search_type="default",
                        index_set_type=IndexSetType.SINGLE.value,
                    )
                    .order_by("-rank", "-created_at")
                    .values("id", "params", "search_mode", "created_by", "created_at")
                )
            else:
                history_obj = (
                    UserIndexSetSearchHistory.objects.filter(
                        is_deleted=False,
                        search_type="default",
                        created_at__range=[kwargs["start_time"], kwargs["end_time"]],
                        index_set_type=IndexSetType.SINGLE.value,
                    )
                    .order_by("created_by", "-created_at")
                    .values("id", "params", "search_mode", "created_by", "created_at")
                )
        else:
            history_obj = (
                UserIndexSetSearchHistory.objects.filter(
                    is_deleted=False,
                    search_type="default",
                    index_set_ids=index_set_ids,
                    index_set_type=IndexSetType.UNION.value,
                )
                .order_by("-rank", "-created_at")
                .values("id", "params", "search_mode", "created_by", "created_at")
            )
        history_obj = SearchHandler._deal_repeat_history(history_obj)
        return_data = []
        for _history in history_obj:
            return_data.append(SearchHandler._build_query_string(_history))
        return return_data

    @staticmethod
    def _build_query_string(history):
        history["query_string"] = generate_query_string(history["params"])
        return history

    @staticmethod
    def _deal_repeat_history(history_obj):
        not_repeat_history: list = []

        def _eq_history(op1, op2):
            op1_params: dict = op1["params"]
            op2_params: dict = op2["params"]
            if op1_params["keyword"] != op2_params["keyword"]:
                return False
            if op1_params["addition"] != op2_params["addition"]:
                return False
            ip_chooser_op1: dict = op1_params.get("ip_chooser", {})
            ip_chooser_op2: dict = op2_params.get("ip_chooser", {})

            if ip_chooser_op1.keys() != ip_chooser_op2.keys():
                return False

            for k in ip_chooser_op1:
                if ip_chooser_op1[k] != ip_chooser_op2[k]:
                    return False

            return True

        def _not_repeat(history):
            for _not_repeat_history in not_repeat_history:
                if _eq_history(_not_repeat_history, history):
                    return
            not_repeat_history.append(history)

        # 使用 iterator() 逐行处理记录
        for _history_obj in history_obj.iterator():
            _not_repeat(_history_obj)
            if len(not_repeat_history) >= 30:
                break
        return not_repeat_history

    @staticmethod
    def user_search_history(start_time, end_time):
        history_obj = (
            UserIndexSetSearchHistory.objects.filter(
                is_deleted=False,
                search_type="default",
                created_at__range=[start_time, end_time],
            )
            .order_by("created_by", "-created_at")
            .values("id", "index_set_id", "duration", "created_by", "created_at")
        )

        # 获取索引集所在的bk_biz_id
        index_sets = array_group(LogIndexSet.get_index_set(show_indices=False), "index_set_id", group=True)
        return_data = []
        for _history in history_obj:
            if _history["index_set_id"] not in index_sets:
                continue
            _history["bk_biz_id"] = index_sets[_history["index_set_id"]]["bk_biz_id"]
            return_data.append(_history)
        return return_data

    def verify_sort_list_item(self, sort_list):
        # field_result, _ = self._get_all_fields_by_index_id()
        mapping_handlers = MappingHandlers(
            self.origin_indices,
            self.index_set_id,
            self.origin_scenario_id,
            self.storage_cluster_id,
            self.time_field,
            self.search_dict.get("bk_biz_id"),
            time_zone=self.time_zone,
        )
        field_result, _ = mapping_handlers.get_all_fields_by_index_id()
        field_dict = dict()
        for _field in field_result:
            field_dict[_field["field_name"]] = _field["es_doc_values"]

        for _item in sort_list:
            field, *_ = _item
            item_doc_value = field_dict.get(field)
            if not item_doc_value:
                raise BaseSearchSortListException(BaseSearchSortListException.MESSAGE.format(sort_item=field))

    def search_context(self):
        if self.scenario_id == Scenario.ES and not (self.index_set.target_fields or self.index_set.sort_fields):
            return {"total": 0, "took": 0, "list": []}

        context_indice = IndicesOptimizerContextTail(
            self.indices, self.scenario_id, dtEventTimeStamp=self.dtEventTimeStamp, search_type_tag="context"
        ).index

        record_obj = StorageClusterRecord.objects.none()

        if self.dtEventTimeStamp:
            try:
                timestamp_datetime = arrow.get(int(self.dtEventTimeStamp) / 1000)
            except Exception:  # pylint: disable=broad-except
                # 如果不是时间戳，那有可能就是纳秒格式 2024-04-09T09:26:57.123456789Z
                timestamp_datetime = arrow.get(self.dtEventTimeStamp)

            record_obj = (
                StorageClusterRecord.objects.filter(
                    index_set_id=int(self.index_set_id), created_at__gt=timestamp_datetime.datetime
                )
                .order_by("created_at")
                .first()
            )

        dsl_params_base = {"indices": context_indice, "scenario_id": self.scenario_id}

        if self.scenario_id == Scenario.ES:
            # 第三方ES必须带上storage_cluster_id
            dsl_params_base.update({"storage_cluster_id": self.index_set.storage_cluster_id})

        if record_obj:
            dsl_params_base.update({"storage_cluster_id": record_obj.storage_cluster_id})

        # 获取dsl对应的esquery方法
        dsl_func = self.fetch_esquery_method(method_name="dsl")

        if self.zero:
            # up
            body: dict = self._get_context_body("-")
            dsl_params_up = copy.deepcopy(dsl_params_base)
            dsl_params_up.update({"body": body})
            result_up: dict = dsl_func(dsl_params_up)
            result_up: dict = self._deal_query_result(result_up)
            result_up.update(
                {
                    "list": list(reversed(result_up.get("list"))),
                    "origin_log_list": list(reversed(result_up.get("origin_log_list"))),
                }
            )

            # down
            body: dict = self._get_context_body("+")

            dsl_params_down = copy.deepcopy(dsl_params_base)
            dsl_params_down.update({"body": body})
            result_down: dict = dsl_func(dsl_params_down)

            result_down: dict = self._deal_query_result(result_down)
            result_down.update({"list": result_down.get("list"), "origin_log_list": result_down.get("origin_log_list")})
            total = result_up["total"] + result_down["total"]
            took = result_up["took"] + result_down["took"]
            new_list = result_up["list"] + result_down["list"]
            origin_log_list = result_up["origin_log_list"] + result_down["origin_log_list"]
            target_fields = self.index_set.target_fields if self.index_set else []
            sort_fields = self.index_set.sort_fields if self.index_set else []
            if sort_fields:
                analyze_result_dict: dict = self._analyze_context_result(
                    new_list, target_fields=target_fields, sort_fields=sort_fields
                )
            else:
                analyze_result_dict: dict = self._analyze_context_result(
                    new_list, mark_gseindex=self.gseindex, mark_gseIndex=self.gseIndex
                )
            zero_index: int = analyze_result_dict.get("zero_index", -1)
            count_start: int = analyze_result_dict.get("count_start", -1)

            new_list = self._analyze_empty_log(new_list)
            origin_log_list = self._analyze_empty_log(origin_log_list)
            return {
                "total": total,
                "took": took,
                "list": new_list,
                "origin_log_list": origin_log_list,
                "zero_index": zero_index,
                "count_start": count_start,
                "dsl": json.dumps(body),
            }
        if self.start < 0:
            body: dict = self._get_context_body("-")

            dsl_params_up = copy.deepcopy(dsl_params_base)
            dsl_params_up.update({"body": body})
            result_up = dsl_func(dsl_params_up)

            result_up: dict = self._deal_query_result(result_up)
            result_up.update(
                {
                    "list": list(reversed(result_up.get("list"))),
                    "origin_log_list": list(reversed(result_up.get("origin_log_list"))),
                }
            )
            result_up.update(
                {
                    "list": self._analyze_empty_log(result_up.get("list")),
                    "origin_log_list": self._analyze_empty_log(result_up.get("origin_log_list")),
                }
            )
            return result_up
        if self.start > 0:
            body: dict = self._get_context_body("+")

            dsl_params_down = copy.deepcopy(dsl_params_base)
            dsl_params_down.update({"body": body})
            result_down = dsl_func(dsl_params_down)

            result_down = self._deal_query_result(result_down)
            result_down.update({"list": result_down.get("list"), "origin_log_list": result_down.get("origin_log_list")})
            result_down.update(
                {
                    "list": self._analyze_empty_log(result_down.get("list")),
                    "origin_log_list": self._analyze_empty_log(result_down.get("origin_log_list")),
                }
            )
            return result_down

        return {"list": []}

    def _get_context_body(self, order):
        target_fields = self.index_set.target_fields
        sort_fields = self.index_set.sort_fields

        if sort_fields:
            return DslCreateSearchContextBodyCustomField(
                size=self.size,
                start=self.start,
                order=order,
                target_fields=target_fields,
                sort_fields=sort_fields,
                params=self.search_dict,
            ).body

        elif self.scenario_id == Scenario.BKDATA:
            return DslCreateSearchContextBodyScenarioBkData(
                size=self.size,
                start=self.start,
                gse_index=self.gseindex,
                iteration_idx=self._iteration_idx,
                dt_event_time_stamp=self.dtEventTimeStamp,
                path=self.path,
                ip=self.ip,
                bk_host_id=self.bk_host_id,
                container_id=self.container_id,
                logfile=self.logfile,
                order=order,
                sort_list=["dtEventTimeStamp", "gseindex", "_iteration_idx"],
            ).body

        elif self.scenario_id == Scenario.LOG:
            return DslCreateSearchContextBodyScenarioLog(
                size=self.size,
                start=self.start,
                gse_index=self.gseIndex,
                iteration_index=self.iterationIndex,
                dt_event_time_stamp=self.dtEventTimeStamp,
                path=self.path,
                server_ip=self.serverIp,
                bk_host_id=self.bk_host_id,
                container_id=self.container_id,
                logfile=self.logfile,
                order=order,
                sort_list=["dtEventTimeStamp", "gseIndex", "iterationIndex"],
            ).body

        return {}

    def search_tail_f(self):
        tail_indice = IndicesOptimizerContextTail(
            self.indices, self.scenario_id, dtEventTimeStamp=self.dtEventTimeStamp, search_type_tag="tail"
        ).index
        if self.scenario_id not in [Scenario.BKDATA, Scenario.LOG, Scenario.ES]:
            return {"total": 0, "took": 0, "list": []}
        else:
            body: dict = {}

            target_fields = self.index_set.target_fields if self.index_set else []
            sort_fields = self.index_set.sort_fields if self.index_set else []

            if sort_fields:
                body: dict = DslCreateSearchTailBodyCustomField(
                    start=self.start,
                    size=self.size,
                    zero=self.zero,
                    time_field=self.time_field,
                    target_fields=target_fields,
                    sort_fields=sort_fields,
                    params=self.search_dict,
                ).body

            elif self.scenario_id == Scenario.BKDATA:
                body: dict = DslCreateSearchTailBodyScenarioBkData(
                    sort_list=["dtEventTimeStamp", "gseindex", "_iteration_idx"],
                    size=self.size,
                    start=self.start,
                    gseindex=self.gseindex,
                    path=self.path,
                    ip=self.ip,
                    bk_host_id=self.bk_host_id,
                    container_id=self.container_id,
                    logfile=self.logfile,
                    zero=self.zero,
                ).body
            elif self.scenario_id == Scenario.LOG:
                body: dict = DslCreateSearchTailBodyScenarioLog(
                    sort_list=["dtEventTimeStamp", "gseIndex", "iterationIndex"],
                    size=self.size,
                    start=self.start,
                    gseIndex=self.gseIndex,
                    path=self.path,
                    bk_host_id=self.bk_host_id,
                    serverIp=self.serverIp,
                    container_id=self.container_id,
                    logfile=self.logfile,
                    zero=self.zero,
                ).body

            dsl_params = {"indices": tail_indice, "scenario_id": self.scenario_id, "body": body}

            if self.scenario_id == Scenario.ES:
                # 第三方ES必须带上storage_cluster_id
                dsl_params.update({"storage_cluster_id": self.index_set.storage_cluster_id})

            result = BkLogApi.dsl(dsl_params)

            result: dict = self._deal_query_result(result)
            if self.zero:
                result.update(
                    {
                        "list": list(reversed(result.get("list"))),
                        "origin_log_list": list(reversed(result.get("origin_log_list"))),
                    }
                )
            result.update(
                {
                    "list": self._analyze_empty_log(result.get("list")),
                    "origin_log_list": self._analyze_empty_log(result.get("origin_log_list")),
                }
            )
            return result

    def _init_indices_str(self) -> str:
        if self.index_set:
            self.index_set_name = self.index_set.index_set_name
            self.scenario_id = self.index_set.scenario_id
            self.storage_cluster_id = self.index_set.storage_cluster_id

            index_set_data_obj_list: list = self.index_set.get_indexes(has_applied=True)
            if len(index_set_data_obj_list) > 0:
                index_list: list = [x.get("result_table_id", None) for x in index_set_data_obj_list]
            else:
                raise BaseSearchIndexSetDataDoseNotExists(
                    BaseSearchIndexSetDataDoseNotExists.MESSAGE.format(
                        index_set_id=str(self.index_set_id) + "_" + self.index_set.index_set_name
                    )
                )
            self.origin_indices = ",".join(index_list)
            self.custom_indices = self.search_dict.get("custom_indices")
            if self.custom_indices and index_list:
                self.origin_indices = ",".join(
                    _index for _index in self.custom_indices.split(",") if _index in index_list
                )
            self.origin_scenario_id = self.index_set.scenario_id
            # 增加判定逻辑：如果 search_dict 中的 keyword 字符串包含 "__dist_05"，也要走clustering的路由
            if self.search_dict.get("keyword") and "__dist_05" in self.search_dict["keyword"]:
                if clustered_rt := self._get_clustering_config_clustered_rt():
                    return clustered_rt

            for addition in self.search_dict.get("addition", []):
                # 查询条件中包含__dist_xx  则查询聚类结果表：xxx_bklog_xxx_clustered
                if addition.get("field", "").startswith("__dist"):
                    if clustered_rt := self._get_clustering_config_clustered_rt():
                        return clustered_rt
            return self.origin_indices
        raise BaseSearchIndexSetException(BaseSearchIndexSetException.MESSAGE.format(index_set_id=self.index_set_id))

    def _get_clustering_config_clustered_rt(self) -> str | None:
        clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=self.index_set_id, raise_exception=False)
        if clustering_config and clustering_config.clustered_rt:
            # 如果是查询bkbase端的表，即场景需要对应改为bkdata
            self.scenario_id = Scenario.BKDATA
            self.using_clustering_proxy = True
            return clustering_config.clustered_rt
        return None

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

    def _init_sort(self) -> list:
        if self.only_for_agg:
            # 仅聚合时无需排序
            return []

        index_set_id = self.search_dict.get("index_set_id")
        # 获取用户对sort的排序需求
        sort_list: list = self.search_dict.get("sort_list", [])
        is_union_search = self.search_dict.get("is_union_search", False)

        if sort_list:
            return sort_list

        # 用户已设置排序规则  （联合检索时不使用用户在单个索引集上设置的排序规则）
        scope = self.search_dict.get("search_type", "default")
        if not is_union_search:
            config_obj = UserIndexSetFieldsConfig.get_config(
                index_set_id=index_set_id, username=self.request_username, scope=scope
            )
            if config_obj:
                sort_list = config_obj.sort_list
                if sort_list:
                    return sort_list
        # 安全措施, 用户未设置排序规则，且未创建默认配置时, 使用默认排序规则
        return self.mapping_handlers.get_default_sort_list(
            index_set_id=index_set_id,
            scenario_id=self.scenario_id,
            scope=scope,
            default_sort_tag=self.search_dict.get("default_sort_tag", False),
        )

    def _init_desensitize(self) -> bool:
        is_desensitize = self.search_dict.get("is_desensitize", True)

        if not is_desensitize:
            request = get_request(peaceful=True)
            if request:
                auth_info = Permission.get_auth_info(request, raise_exception=False)
                # 应用不在白名单 → 强制开启脱敏
                if not auth_info or auth_info["bk_app_code"] not in settings.ESQUERY_WHITE_LIST:
                    is_desensitize = True

        if is_desensitize:
            bk_biz_id = self.search_dict.get("bk_biz_id", "")
            request_user = get_request_username()
            feature_toggle = FeatureToggleObject.toggle(LOG_DESENSITIZE)
            if feature_toggle and isinstance(feature_toggle.feature_config, dict):
                user_white_list = feature_toggle.feature_config.get("user_white_list", {})
                if request_user in user_white_list.get(str(bk_biz_id), []):
                    is_desensitize = False  # 特权用户关闭脱敏

        return is_desensitize

    @property
    def filter(self) -> list:
        # 当filter被访问时，如果还没有被初始化，则调用_init_filter()进行初始化
        if self._filter is None:
            self._filter = self._init_filter()
        return self._filter

    @property
    def mapping_handlers(self) -> MappingHandlers:
        if self._mapping_handlers is None:
            self._mapping_handlers = MappingHandlers(
                index_set_id=self.index_set_id,
                indices=self.origin_indices,
                scenario_id=self.origin_scenario_id,
                storage_cluster_id=self.storage_cluster_id,
                bk_biz_id=self.search_dict.get("bk_biz_id"),
                only_search=True,
                index_set=self.index_set,
                time_zone=self.time_zone,
            )
        return self._mapping_handlers

    @property
    def final_fields_list(self) -> list:
        if self._final_fields_list is None:
            # 获取各个字段类型
            self._final_fields_list, __ = self.mapping_handlers.get_all_fields_by_index_id()
        return self._final_fields_list

    # 过滤filter
    def _init_filter(self):
        field_type_map = {i["field_name"]: i["field_type"] for i in self.final_fields_list}
        # 如果历史索引不包含bk_host_id, 则不需要进行bk_host_id的过滤
        include_bk_host_id = "bk_host_id" in field_type_map.keys() and settings.ENABLE_DHCP
        new_attrs: dict = self._combine_addition_ip_chooser(
            attrs=self.search_dict, include_bk_host_id=include_bk_host_id
        )
        filter_list: list = new_attrs.get("addition", [])
        new_filter_list: list = []
        for item in filter_list:
            field: str = item.get("key") if item.get("key") else item.get("field")
            # 全文检索key & 存量query_string转换
            if field in ["*", "__query_string__"]:
                continue
            _type = "field"
            if self.mapping_handlers.is_nested_field(field):
                _type = FieldDataTypeEnum.NESTED.value
            value = item.get("value")
            # value 校验逻辑
            value_type = field_type_map.get(field)
            value_list = value.split(",") if isinstance(value, str) else value
            if value_type in CHECK_FIELD_LIST and value_list:
                for _v in value_list:
                    max_value = CHECK_FIELD_MAX_VALUE_MAPPING.get(value_type, 0)
                    min_value = CHECK_FIELD_MIN_VALUE_MAPPING.get(value_type, 0)
                    try:
                        if max_value and min_value and (int(_v) > max_value or int(_v) < min_value):
                            raise IntegerMaxErrorException(IntegerMaxErrorException.MESSAGE.format(num=_v))
                    except IntegerErrorException as e:
                        raise IntegerErrorException(
                            IntegerErrorException.MESSAGE.format(num=_v), code=e.code, errors=e.errors
                        )

            operator: str = item.get("method") if item.get("method") else item.get("operator")
            condition: str = item.get("condition", "and")

            if operator in [OperatorEnum.EXISTS["operator"], OperatorEnum.NOT_EXISTS["operator"]]:
                new_filter_list.append(
                    {"field": field, "value": "0", "operator": operator, "condition": condition, "type": _type}
                )

            # 此处对于前端传递filter为空字符串需要放行
            if (not field or not value or not operator) and not isinstance(value, str):
                continue

            new_filter_list.append(
                {"field": field, "value": value, "operator": operator, "condition": condition, "type": _type}
            )

        return new_filter_list

    # 需要esquery提供mapping接口
    def _get_filed_set_default_sort_tag(self) -> bool:
        result_table_id_list: list = self.indices.split(",")
        if len(result_table_id_list) <= 0:
            default_sort_tag: bool = False
            return default_sort_tag
        result_table_id, *_ = result_table_id_list
        # default_sort_tag: bool = False
        # get fields from cache
        fields_from_cache: str = cache.get(result_table_id)
        if not fields_from_cache:
            mapping_from_es: list = BkLogApi.mapping(
                {
                    "indices": result_table_id,
                    "scenario_id": self.scenario_id,
                    "storage_cluster_id": self.storage_cluster_id,
                }
            )
            property_dict: dict = MappingHandlers.find_property_dict(mapping_from_es)
            fields_result: list = MappingHandlers.get_all_index_fields_by_mapping(property_dict)
            fields_from_es: list = [
                {
                    "field_type": field["field_type"],
                    "field": field["field_name"],
                    "field_alias": field.get("field_alias"),
                    "is_display": False,
                    "is_editable": True,
                    "tag": field.get("tag", "metric"),
                    "es_doc_values": field.get("es_doc_values", False),
                }
                for field in fields_result
            ]
            if not fields_from_es:
                default_sort_tag: bool = False
                return default_sort_tag

            cache.set(result_table_id, json.dumps({"data": fields_from_es}), TimeEnum.ONE_DAY_SECOND.value)
            fields: list = fields_from_es
            fields_list: list = [x["field"] for x in fields]
            if ("gseindex" in fields_list and "_iteration_idx" in fields_list) or (
                "gseIndex" in fields_list and "iterationIndex" in fields_list
            ):
                default_sort_tag: bool = True
                return default_sort_tag
            default_sort_tag: bool = False
            return default_sort_tag

        fields_from_cache_dict: dict[str, dict] = json.loads(fields_from_cache)
        fields: list = fields_from_cache_dict.get("data", list())
        fields_list: list = [x["field"] for x in fields]
        if ("gseindex" in fields_list and "_iteration_idx" in fields_list) or (
            "gseIndex" in fields_list and "iterationIndex" in fields_list
        ):
            default_sort_tag: bool = True
            return default_sort_tag
        default_sort_tag: bool = False
        return default_sort_tag

    def _init_aggs(self):
        if not self.search_dict.get("aggs"):
            return {}

        # 存在聚合参数，且时间聚合更新默认设置
        aggs_dict = self.search_dict["aggs"]
        return aggs_dict

    def _init_highlight(self, can_highlight=True):
        if not can_highlight or self.index_set.max_analyzed_offset == -1:
            return {}
        # 避免多字段高亮
        if self.query_string and ":" in self.query_string:
            require_field_match = True
        else:
            require_field_match = False

        highlight = {
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fields": {"*": {"number_of_fragments": 0}},
            "require_field_match": require_field_match,
        }
        if self.index_set and self.index_set.max_analyzed_offset and not self.using_clustering_proxy:
            highlight["max_analyzed_offset"] = self.index_set.max_analyzed_offset

        if self.export_log:
            highlight = {}

        return highlight

    def _add_cmdb_fields(self, log):
        if not self.search_dict.get("bk_biz_id"):
            return log

        bk_biz_id = self.search_dict.get("bk_biz_id")
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

    def _deal_query_result(self, result_dict: dict) -> dict:
        if self.export_fields:
            # 将导出字段和检索日志有的字段取交集
            support_fields_list = [i["field_name"] for i in self.fields()["fields"]]
            self.export_fields = list(set(self.export_fields).intersection(set(support_fields_list)))
        result: dict = {
            "aggregations": result_dict.get("aggregations", {}),
        }
        # 将_shards 字段返回以供saas判断错误
        _shards = result_dict.get("_shards", {})
        result.update({"_shards": _shards})
        log_list: list = []
        agg_result: dict = {}
        origin_log_list: list = []
        if not result_dict.get("hits", {}).get("total"):
            result.update(
                {"total": 0, "took": 0, "list": log_list, "aggs": agg_result, "origin_log_list": origin_log_list}
            )
            return result
        # hit data
        for hit in result_dict["hits"]["hits"]:
            log = hit["_source"]
            # 脱敏处理
            if (self.field_configs or self.text_fields_field_configs) and self.is_desensitize:
                log = self._log_desensitize(log)
            else:
                log = self.convert_keys(log)
            # 联合检索补充索引集信息
            log["__index_set_id__"] = self.index_set_id
            log = self._add_cmdb_fields(log)
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
            _index = hit["_index"]
            log.update({"index": _index})
            if self.search_dict.get("is_return_doc_id"):
                log.update({"__id__": hit["_id"]})

            if "highlight" not in hit:
                origin_log_list.append(origin_log)
                log_list.append(log)
                continue
            else:
                origin_log_list.append(copy.deepcopy(origin_log))

            if not (self.field_configs or self.text_fields_field_configs) or not self.is_desensitize:
                log = self._deal_object_highlight(log=log, highlight=hit["highlight"])
            log_list.append(log)

        result.update(
            {
                "total": result_dict["hits"]["total"],
                "took": result_dict["took"],
                "list": log_list,
                "origin_log_list": origin_log_list,
            }
        )
        # 处理聚合
        agg_dict = result_dict.get("aggregations", {})
        result.update({"aggs": agg_dict})
        return result

    def convert_keys(self, data):
        new_dict = {}

        for key, value in data.items():
            # 如果值是字典，递归调用
            if isinstance(value, dict):
                value = self.convert_keys(value)  # 递归处理嵌套字典
            # 如果值是列表，处理列表中的每个字典
            elif isinstance(value, list):
                value = [self.convert_keys(item) if isinstance(item, dict) else item for item in value]

            # 如果键中有点，进行转换
            if "." in key:
                # 分割键
                parts = key.split(".")
                nested_dict = new_dict

                for part in parts[:-1]:  # 所有部分，除了最后一部分
                    if part not in nested_dict:
                        nested_dict[part] = {}
                    nested_dict = nested_dict[part]

                # 设置最后一个部分的值
                nested_dict[parts[-1]] = value
            else:
                # 如果没有点，直接赋值
                new_dict[key] = value

        return new_dict

    @classmethod
    def update_nested_dict(cls, base_dict: dict[str, Any], update_dict: dict[str, Any]) -> dict[str, Any]:
        """
        递归更新嵌套字典
        """
        if not isinstance(base_dict, dict):
            return base_dict
        for key, value in update_dict.items():
            if key not in base_dict:
                continue
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
                            _key = f"{key}"
                    if _key:
                        self._update_result_fields(_key, _item[key])

            get_field_and_get_length(item)
        return self.field

    def _update_result_fields(self, _key: str, _item: Any):
        max_len_dict_obj: max_len_dict = self.field.get(_key)
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

    def _analyze_context_result(
        self,
        log_list: list[dict[str, Any]],
        mark_gseindex: int = None,
        mark_gseIndex: int = None,
        target_fields: list = None,
        sort_fields: list = None,
        # pylint: disable=invalid-name
    ) -> dict[str, Any]:
        log_list_reversed: list = log_list
        if self.start < 0:
            log_list_reversed = list(reversed(log_list))

        # find the search one
        _index: int = -1

        target_fields = target_fields or []
        sort_fields = sort_fields or []

        if sort_fields:
            for index, item in enumerate(log_list):
                for field in sort_fields + target_fields:
                    tmp_item = item.copy()
                    sub_field = field
                    while "." in sub_field:
                        prefix, sub_field = sub_field.split(".", 1)
                        tmp_item = tmp_item.get(prefix, {})
                        if sub_field in tmp_item:
                            break
                    item_field = tmp_item.get(sub_field)
                    if str(item_field) != str(self.search_dict.get(field)):
                        break
                else:
                    _index = index
                    break
        elif self.scenario_id == Scenario.BKDATA:
            for index, item in enumerate(log_list):
                gseindex: str = item.get("gseindex")
                ip: str = item.get("ip")
                bk_host_id: int = item.get("bk_host_id")
                path: str = item.get("path")
                container_id: str = item.get("container_id")
                logfile: str = item.get("logfile")
                _iteration_idx: str = item.get("_iteration_idx")

                if (
                    (
                        self.gseindex == str(gseindex)
                        and self.bk_host_id == bk_host_id
                        and self.path == path
                        and self._iteration_idx == str(_iteration_idx)
                    )
                    or (
                        self.gseindex == str(gseindex)
                        and self.ip == ip
                        and self.path == path
                        and self._iteration_idx == str(_iteration_idx)
                    )
                    or (
                        self.gseindex == str(gseindex)
                        and self.container_id == container_id
                        and self.logfile == logfile
                        and self._iteration_idx == str(_iteration_idx)
                    )
                ):
                    _index = index
                    break
        elif self.scenario_id == Scenario.LOG:
            for index, item in enumerate(log_list):
                gseIndex: str = item.get("gseIndex")  # pylint: disable=invalid-name
                serverIp: str = item.get("serverIp")  # pylint: disable=invalid-name
                bk_host_id: int = item.get("bk_host_id")
                path: str = item.get("path", "")
                iterationIndex: str = item.get("iterationIndex")  # pylint: disable=invalid-name

                if (
                    self.gseIndex == str(gseIndex)
                    and self.bk_host_id == bk_host_id
                    and self.path == path
                    and self.iterationIndex == str(iterationIndex)
                ) or (
                    self.gseIndex == str(gseIndex)
                    and self.serverIp == serverIp
                    and self.path == path
                    and self.iterationIndex == str(iterationIndex)
                ):
                    _index = index
                    break

        _count_start = _index
        return {"list": log_list_reversed, "zero_index": _index, "count_start": _count_start}

    def _analyze_empty_log(self, log_list: list[dict[str, Any]]):
        log_not_empty_list: list[dict[str, Any]] = []
        for item in log_list:
            a_item_dict: dict[str:Any] = item

            # 只要存在log字段则直接显示
            if "log" in a_item_dict:
                log_not_empty_list.append(a_item_dict)
                continue
            # 递归打平每条记录
            new_log_context_list: list[str] = []

            def get_field_and_get_context(_item: dict, fater: str = ""):
                for key in _item:
                    _key: str = ""
                    if isinstance(_item[key], dict):
                        get_field_and_get_context(_item[key], key)
                    else:
                        if fater:
                            _key = f"{fater}.{key}"
                        else:
                            _key = f"{key}"
                    if _key:
                        a_context: str = f"{_key}: {_item[key]}"
                        new_log_context_list.append(a_context)

            get_field_and_get_context(a_item_dict)
            a_item_dict.update({"log": " ".join(new_log_context_list)})
            log_not_empty_list.append(a_item_dict)
        return log_not_empty_list

    def _combine_addition_ip_chooser(self, attrs: dict, include_bk_host_id: bool = True):
        """
        合并ip_chooser和addition
        :param attrs:   attrs
        :param include_bk_host_id: 是否包含bk_host_id
        """
        ip_chooser_ip_list: list = []
        ip_chooser_host_id_list: list = []
        ip_chooser: dict = attrs.get("ip_chooser")
        if ip_chooser:
            ip_chooser_host_list = IPChooser(
                bk_biz_id=attrs["bk_biz_id"], fields=CommonEnum.SIMPLE_HOST_FIELDS.value
            ).transfer2host(ip_chooser)
            ip_chooser_host_id_list = [host["bk_host_id"] for host in ip_chooser_host_list]
            ip_chooser_ip_list = [host["bk_host_innerip"] for host in ip_chooser_host_list]
        addition_ip_list, new_addition = self._deal_addition(attrs)
        if addition_ip_list:
            search_ip_list = addition_ip_list
        elif not addition_ip_list and ip_chooser_ip_list:
            search_ip_list = ip_chooser_ip_list
        else:
            search_ip_list = []
        # 旧的采集器不会上报bk_host_id, 所以如果意外加入了这个条件会导致检索失败
        if include_bk_host_id and ip_chooser_host_id_list:
            new_addition.append({"field": "bk_host_id", "operator": "is one of", "value": ip_chooser_host_id_list})
        new_addition.append({"field": self.ip_field, "operator": "is one of", "value": list(set(search_ip_list))})
        # 当IP选择器传了模块,模版,动态拓扑但是实际没有主机时, 此时应不返回任何数据, 塞入特殊数据bk_host_id=0来实现
        if ip_chooser and not ip_chooser_host_id_list and not ip_chooser_ip_list:
            new_addition.append({"field": "bk_host_id", "operator": "is one of", "value": [0]})
        attrs["addition"] = new_addition
        return attrs

    def _deal_addition(self, attrs):
        addition_ip_list: list = []
        addition: list = attrs.get("addition")
        new_addition: list = []
        if not addition:
            return [], []
        for _add in addition:
            field: str = _add.get("key") if _add.get("key") else _add.get("field")
            _operator: str = _add.get("method") if _add.get("method") else _add.get("operator")
            if field == self.ip_field:
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

    def _deal_normal_addition(self, value, _operator: str) -> str | list:
        operator = _operator
        addition_return_value = {
            "is": lambda: value,
            "is one of": lambda: value.split(","),
            "is not": lambda: value,
            "is not one of": lambda: value.split(","),
        }
        return addition_return_value.get(operator, lambda: value)()

    def _set_time_filed_type(self, time_field: str, fields_from_es: list):
        if not fields_from_es:
            raise SearchIndicesNotExists(SearchIndicesNotExists.MESSAGE.format(index_set_name=self.index_set_name))

        for item in fields_from_es:
            field_name = item["field_name"]
            if field_name == time_field:
                return item["field_type"]
        raise SearchUnKnowTimeFieldType()

    def _enable_bcs_manage(self):
        return settings.BCS_WEB_CONSOLE_DOMAIN if settings.BCS_WEB_CONSOLE_DOMAIN != "" else None

    def _get_message_by_scenario(self):
        if self.scenario_id == Scenario.BKDATA:
            return ERROR_MSG_CHECK_FIELDS_FROM_BKDATA
        else:
            return ERROR_MSG_CHECK_FIELDS_FROM_LOG

    def _get_user_sorted_list(self, sorted_fields):
        config = UserIndexSetFieldsConfig.get_config(index_set_id=self.index_set_id, username=self.request_username)
        if not config:
            return [[sorted_field, ASYNC_SORTED] for sorted_field in sorted_fields]
        user_sort_list = config.sort_list
        user_sort_fields = [i[0] for i in user_sort_list]
        for sorted_field in sorted_fields:
            if sorted_field in user_sort_fields:
                continue
            user_sort_list.append([sorted_field, ASYNC_SORTED])

        return user_sort_list


class UnionSearchHandler:
    """
    联合检索
    """

    def __init__(self, search_dict=None):
        if search_dict is None:
            search_dict = {}
        self.search_dict = search_dict
        self.union_configs = search_dict.get("union_configs", [])
        self.sort_list = search_dict.get("sort_list", [])
        if search_dict.get("index_set_ids", []):
            self.index_set_ids = list(set(search_dict["index_set_ids"]))
        else:
            self.index_set_ids = list({info["index_set_id"] for info in self.union_configs})
        self.desensitize_mapping = {info["index_set_id"]: info["is_desensitize"] for info in self.union_configs}

    def _init_sort_list(self, index_set_id):
        sort_list = self.search_dict.get("sort_list", [])
        if not sort_list:
            return sort_list

        new_sort_list = list()
        # 判断是否指定了自定义的时间字段
        for sort_info in copy.deepcopy(sort_list):
            _time_field, _sort = sort_info
            if _time_field == "unionSearchTimeStamp":
                sort_info[0] = MappingHandlers.get_time_field(index_set_id=index_set_id)
            new_sort_list.append(sort_info)

        return new_sort_list

    def union_search(self, is_export=False):
        index_set_objs = LogIndexSet.objects.filter(index_set_id__in=self.index_set_ids)
        if not index_set_objs:
            raise BaseSearchIndexSetException(
                BaseSearchIndexSetException.MESSAGE.format(index_set_id=self.index_set_ids)
            )

        index_set_obj_mapping = {obj.index_set_id: obj for obj in index_set_objs}

        # 构建请求参数
        params = {
            "ip_chooser": self.search_dict.get("ip_chooser"),
            "bk_biz_id": self.search_dict.get("bk_biz_id"),
            "addition": self.search_dict.get("addition"),
            "start_time": self.search_dict.get("start_time"),
            "end_time": self.search_dict.get("end_time"),
            "time_range": self.search_dict.get("time_range"),
            "keyword": self.search_dict.get("keyword"),
            "size": self.search_dict.get("size"),
            "is_union_search": True,
            "track_total_hits": self.search_dict.get("track_total_hits", False),
        }

        # 数据排序处理  兼容第三方ES检索排序
        time_fields = set()
        time_fields_type = set()
        time_fields_unit = set()
        for index_set_obj in index_set_objs:
            if not index_set_obj.time_field or not index_set_obj.time_field_type or not index_set_obj.time_field_unit:
                raise SearchUnKnowTimeField()
            time_fields.add(index_set_obj.time_field)
            time_fields_type.add(index_set_obj.time_field_type)
            time_fields_unit.add(index_set_obj.time_field_unit)

        diff_fields = set()
        export_fields = self.search_dict.get("export_fields")
        # 在做导出操作时,记录time_fields比export_fields多的字段
        if export_fields:
            diff_fields = time_fields - set(export_fields)
            self.search_dict["export_fields"].extend(diff_fields)

        multi_execute_func = MultiExecuteFunc()
        if is_export:
            for index_set_id in self.index_set_ids:
                search_dict = copy.deepcopy(params)
                search_dict["begin"] = self.search_dict.get("begin", 0)
                search_dict["sort_list"] = self._init_sort_list(index_set_id=index_set_id)
                search_dict["is_desensitize"] = self.desensitize_mapping.get(index_set_id, True)
                search_handler = SearchHandler(
                    index_set_id=index_set_id,
                    search_dict=search_dict,
                    export_fields=self.search_dict.get("export_fields", []),
                )
                multi_execute_func.append(f"union_search_{index_set_id}", search_handler.search)
        else:
            for union_config in self.union_configs:
                search_dict = copy.deepcopy(params)
                search_dict["begin"] = union_config.get("begin", 0)
                search_dict["sort_list"] = self._init_sort_list(index_set_id=union_config["index_set_id"])
                search_dict["is_desensitize"] = union_config.get("is_desensitize", True)
                search_dict["custom_indices"] = union_config.get("custom_indices", "")
                search_handler = SearchHandler(index_set_id=union_config["index_set_id"], search_dict=search_dict)
                multi_execute_func.append(f"union_search_{union_config['index_set_id']}", search_handler.search)

        # 执行线程
        multi_result = multi_execute_func.run(return_exception=True)

        # 处理返回结果
        result_log_list = list()
        result_origin_log_list = list()
        fields = dict()
        total = 0
        took = 0
        for index_set_id in self.index_set_ids:
            ret = multi_result.get(f"union_search_{index_set_id}")

            if isinstance(ret, Exception):
                # 子查询异常
                raise UnionSearchErrorException(
                    UnionSearchErrorException.MESSAGE.format(index_set_id=index_set_id, e=ret)
                )

            result_log_list.extend(ret["list"])
            result_origin_log_list.extend(ret["origin_log_list"])
            total += int(ret["total"])
            took = max(took, ret["took"])
            for key, value in ret.get("fields", {}).items():
                if not isinstance(value, dict):
                    continue
                if key not in fields:
                    fields[key] = value
                else:
                    fields[key]["max_length"] = max(fields[key].get("max_length", 0), value.get("max_length", 0))

        is_use_custom_time_field = False

        if len(time_fields) != 1 or len(time_fields_type) != 1 or len(time_fields_unit) != 1:
            # 标准化时间字段
            is_use_custom_time_field = True
            for info in result_log_list:
                index_set_obj = index_set_obj_mapping.get(info["__index_set_id__"])
                num = TIME_FIELD_MULTIPLE_MAPPING.get(index_set_obj.time_field_unit, 1)
                try:
                    info["unionSearchTimeStamp"] = int(info[index_set_obj.time_field]) * num
                except ValueError:
                    info["unionSearchTimeStamp"] = info[index_set_obj.time_field]

            for info in result_origin_log_list:
                index_set_obj = index_set_obj_mapping.get(info["__index_set_id__"])
                num = TIME_FIELD_MULTIPLE_MAPPING.get(index_set_obj.time_field_unit, 1)
                try:
                    info["unionSearchTimeStamp"] = int(info[index_set_obj.time_field]) * num
                except ValueError:
                    info["unionSearchTimeStamp"] = info[index_set_obj.time_field]

        if not self.sort_list:
            # 默认使用时间字段排序
            if not is_use_custom_time_field:
                sort_field = list(time_fields)[0]
                # 时间字段相同 直接以相同时间字段为key进行排序 默认为降序
                result_log_list = sorted(result_log_list, key=lambda x: str(x[sort_field]), reverse=True)
                result_origin_log_list = sorted(result_origin_log_list, key=lambda x: str(x[sort_field]), reverse=True)
            else:
                # 时间字段/时间字段格式/时间字段单位不同  标准化时间字段作为key进行排序 标准字段单位为 millisecond
                result_log_list = sorted(result_log_list, key=lambda x: str(x["unionSearchTimeStamp"]), reverse=True)
                result_origin_log_list = sorted(
                    result_origin_log_list, key=lambda x: str(x["unionSearchTimeStamp"]), reverse=True
                )
        else:
            result_log_list = sort_func(data=result_log_list, sort_list=self.sort_list)
            result_origin_log_list = sort_func(data=result_origin_log_list, sort_list=self.sort_list)
        # 在导出结果中删除查询时补充的字段
        if diff_fields:
            tmp_list = []
            for dic in result_origin_log_list:
                tmp_list.append({k: v for k, v in dic.items() if k not in diff_fields})
            result_origin_log_list = tmp_list
        # 处理分页
        result_log_list = result_log_list[: self.search_dict.get("size")]
        result_origin_log_list = result_origin_log_list[: self.search_dict.get("size")]

        # 日志导出提前返回
        if is_export:
            return {"origin_log_list": result_origin_log_list}

        # 统计返回的数据中各个索引集分别占了多少条数据  用于下次begin查询
        result_log_index_set_ids = [result_log["__index_set_id__"] for result_log in result_log_list]

        for union_config in self.union_configs:
            union_config["begin"] = union_config["begin"] + result_log_index_set_ids.count(union_config["index_set_id"])

        res = {
            "total": total,
            "took": took,
            "fields": fields,
            "list": result_log_list,
            "origin_log_list": result_origin_log_list,
            "union_configs": self.union_configs,
        }

        # 保存联合检索检索历史
        self._save_union_search_history(res)

        return res

    def unifyquery_union_search(self, is_export=False):
        from apps.log_unifyquery.handler.base import UnifyQueryHandler

        index_set_objs = LogIndexSet.objects.filter(index_set_id__in=self.index_set_ids)
        if not index_set_objs:
            raise BaseSearchIndexSetException(
                BaseSearchIndexSetException.MESSAGE.format(index_set_id=self.index_set_ids)
            )

        index_set_obj_mapping = {obj.index_set_id: obj for obj in index_set_objs}

        # 构建请求参数
        params = {
            "ip_chooser": self.search_dict.get("ip_chooser"),
            "bk_biz_id": self.search_dict.get("bk_biz_id"),
            "addition": self.search_dict.get("addition"),
            "start_time": self.search_dict.get("start_time"),
            "end_time": self.search_dict.get("end_time"),
            "time_range": self.search_dict.get("time_range"),
            "keyword": self.search_dict.get("keyword"),
            "size": self.search_dict.get("size"),
            "is_union_search": True,
            "track_total_hits": self.search_dict.get("track_total_hits", False),
        }

        # 数据排序处理  兼容第三方ES检索排序
        time_fields = set()
        time_fields_type = set()
        time_fields_unit = set()
        for index_set_obj in index_set_objs:
            if not index_set_obj.time_field or not index_set_obj.time_field_type or not index_set_obj.time_field_unit:
                raise SearchUnKnowTimeField()
            time_fields.add(index_set_obj.time_field)
            time_fields_type.add(index_set_obj.time_field_type)
            time_fields_unit.add(index_set_obj.time_field_unit)

        diff_fields = set()
        export_fields = self.search_dict.get("export_fields")
        # 在做导出操作时,记录time_fields比export_fields多的字段
        if export_fields:
            diff_fields = time_fields - set(export_fields)
            self.search_dict["export_fields"].extend(diff_fields)

        multi_execute_func = MultiExecuteFunc()
        if is_export:
            for index_set_id in self.index_set_ids:
                search_dict = copy.deepcopy(params)
                search_dict["begin"] = self.search_dict.get("begin", 0)
                search_dict["sort_list"] = self._init_sort_list(index_set_id=index_set_id)
                search_dict["is_desensitize"] = self.desensitize_mapping.get(index_set_id, True)
                search_dict["export_fields"] = self.search_dict.get("export_fields", [])
                search_dict["index_set_ids"] = [index_set_id]
                query_handler = UnifyQueryHandler(search_dict)
                multi_execute_func.append(f"union_search_{index_set_id}", query_handler.search)
        else:
            for union_config in self.union_configs:
                search_dict = copy.deepcopy(params)
                search_dict["begin"] = union_config.get("begin", 0)
                search_dict["sort_list"] = self._init_sort_list(index_set_id=union_config["index_set_id"])
                search_dict["is_desensitize"] = union_config.get("is_desensitize", True)
                search_dict["index_set_ids"] = [union_config["index_set_id"]]
                query_handler = UnifyQueryHandler(search_dict)
                multi_execute_func.append(f"union_search_{union_config['index_set_id']}", query_handler.search)

        # 执行线程
        multi_result = multi_execute_func.run(return_exception=True)

        # 处理返回结果
        result_log_list = list()
        result_origin_log_list = list()
        fields = dict()
        total = 0
        took = 0
        for index_set_id in self.index_set_ids:
            ret = multi_result.get(f"union_search_{index_set_id}")

            if isinstance(ret, Exception):
                # 子查询异常
                raise UnionSearchErrorException(
                    UnionSearchErrorException.MESSAGE.format(index_set_id=index_set_id, e=ret)
                )

            result_log_list.extend(ret["list"])
            result_origin_log_list.extend(ret["origin_log_list"])
            total += int(ret["total"])
            took = max(took, ret["took"])
            for key, value in ret.get("fields", {}).items():
                if not isinstance(value, dict):
                    continue
                if key not in fields:
                    fields[key] = value
                else:
                    fields[key]["max_length"] = max(fields[key].get("max_length", 0), value.get("max_length", 0))

        is_use_custom_time_field = False

        if len(time_fields) != 1 or len(time_fields_type) != 1 or len(time_fields_unit) != 1:
            # 标准化时间字段
            is_use_custom_time_field = True
            for info in result_log_list:
                index_set_obj = index_set_obj_mapping.get(info["__index_set_id__"])
                num = TIME_FIELD_MULTIPLE_MAPPING.get(index_set_obj.time_field_unit, 1)
                try:
                    info["unionSearchTimeStamp"] = int(info[index_set_obj.time_field]) * num
                except ValueError:
                    info["unionSearchTimeStamp"] = info[index_set_obj.time_field]

            for info in result_origin_log_list:
                index_set_obj = index_set_obj_mapping.get(info["__index_set_id__"])
                num = TIME_FIELD_MULTIPLE_MAPPING.get(index_set_obj.time_field_unit, 1)
                try:
                    info["unionSearchTimeStamp"] = int(info[index_set_obj.time_field]) * num
                except ValueError:
                    info["unionSearchTimeStamp"] = info[index_set_obj.time_field]

        if not self.sort_list:
            # 默认使用时间字段排序
            if not is_use_custom_time_field:
                sort_field = list(time_fields)[0]
                # 时间字段相同 直接以相同时间字段为key进行排序 默认为降序
                result_log_list = sorted(result_log_list, key=lambda x: str(x[sort_field]), reverse=True)
                result_origin_log_list = sorted(result_origin_log_list, key=lambda x: str(x[sort_field]), reverse=True)
            else:
                # 时间字段/时间字段格式/时间字段单位不同  标准化时间字段作为key进行排序 标准字段单位为 millisecond
                result_log_list = sorted(result_log_list, key=lambda x: str(x["unionSearchTimeStamp"]), reverse=True)
                result_origin_log_list = sorted(
                    result_origin_log_list, key=lambda x: str(x["unionSearchTimeStamp"]), reverse=True
                )
        else:
            result_log_list = sort_func(data=result_log_list, sort_list=self.sort_list)
            result_origin_log_list = sort_func(data=result_origin_log_list, sort_list=self.sort_list)
        # 在导出结果中删除查询时补充的字段
        if diff_fields:
            tmp_list = []
            for dic in result_origin_log_list:
                tmp_list.append({k: v for k, v in dic.items() if k not in diff_fields})
            result_origin_log_list = tmp_list
        # 处理分页
        result_log_list = result_log_list[: self.search_dict.get("size")]
        result_origin_log_list = result_origin_log_list[: self.search_dict.get("size")]

        # 日志导出提前返回
        if is_export:
            return {"origin_log_list": result_origin_log_list}

        # 统计返回的数据中各个索引集分别占了多少条数据  用于下次begin查询
        result_log_index_set_ids = [result_log["__index_set_id__"] for result_log in result_log_list]

        for union_config in self.union_configs:
            union_config["begin"] = union_config["begin"] + result_log_index_set_ids.count(union_config["index_set_id"])

        res = {
            "total": total,
            "took": took,
            "fields": fields,
            "list": result_log_list,
            "origin_log_list": result_origin_log_list,
            "union_configs": self.union_configs,
        }

        # 保存联合检索检索历史
        self._save_union_search_history(res)

        return res

    def _save_union_search_history(self, result, search_type="default"):
        params = {
            "keyword": self.search_dict.get("keyword"),
            "ip_chooser": self.search_dict.get("ip_chooser"),
            "addition": self.search_dict.get("addition"),
            "start_time": self.search_dict.get("start_time"),
            "end_time": self.search_dict.get("end_time"),
            "time_range": self.search_dict.get("time_range"),
            "search_mode": self.search_dict.get("search_mode"),
        }

        result.update(
            {
                "union_search_history_obj": {
                    "params": params,
                    "index_set_ids": sorted(self.index_set_ids),
                    "search_type": search_type,
                    "from_favorite_id": self.search_dict.get("from_favorite_id", 0),
                }
            }
        )

        return result

    def union_search_fields(self, data):
        """
        获取字段mapping信息
        """
        index_set_ids = data.get("index_set_ids")
        start_time = data.get("start_time", "")
        end_time = data.get("end_time", "")

        index_set_objs = LogIndexSet.objects.filter(index_set_id__in=index_set_ids)

        if not index_set_objs:
            raise BaseSearchIndexSetException(BaseSearchIndexSetException.MESSAGE.format(index_set_id=index_set_ids))

        multi_execute_func = MultiExecuteFunc()

        # 构建请求参数
        params = {"start_time": start_time, "end_time": end_time, "is_union_search": True}

        for index_set_id in index_set_ids:
            search_handler = SearchHandler(index_set_id, params)
            multi_execute_func.append(f"union_search_fields_{index_set_id}", search_handler.fields)

        multi_result = multi_execute_func.run()

        if not multi_result:
            raise UnionSearchFieldsFailException()

        # 处理返回结果
        total_fields = list()
        fields_info = dict()
        union_field_names = list()
        union_display_fields = list()
        union_time_fields = set()
        union_time_fields_type = set()
        union_time_fields_unit = set()
        context_and_realtime_config = {"name": "context_and_realtime", "is_active": False, "extra": []}
        for index_set_id in index_set_ids:
            result = multi_result[f"union_search_fields_{index_set_id}"]
            fields = result["fields"]
            fields_info[index_set_id] = fields
            display_fields = result["display_fields"]
            result_config = result["config"][0]
            if result_config["is_active"]:
                context_and_realtime_config["is_active"] = True
            extra = result_config["extra"]
            extra.update({"index_set_id": index_set_id})
            context_and_realtime_config["extra"].append(extra)

            for field_info in fields:
                field_name = field_info["field_name"]
                field_type = field_info["field_type"]
                if field_name not in union_field_names:
                    field_info["index_set_ids"] = [index_set_id]
                    total_fields.append(field_info)
                    union_field_names.append(field_info["field_name"])
                else:
                    # 判断字段类型是否一致  不一致则标记为类型冲突
                    _index = union_field_names.index(field_name)
                    _field_type = total_fields[_index]["field_type"]
                    if field_type != _field_type:
                        if (field_type == "date" and _field_type == "date_nanos") or (
                            field_type == "date_nanos" and _field_type == "date"
                        ):
                            total_fields[_index]["field_type"] = "date_nanos"
                        else:
                            total_fields[_index]["field_type"] = "conflict"
                    total_fields[_index]["index_set_ids"].append(index_set_id)

            # 处理默认显示字段
            union_display_fields.extend(display_fields)

        # 处理公共的默认显示字段
        union_display_fields_all = list()
        for display_field in union_display_fields:
            if display_field not in union_display_fields_all:
                union_display_fields_all.append(display_field)

        # 处理时间字段
        for index_set_obj in index_set_objs:
            if not index_set_obj.time_field or not index_set_obj.time_field_type or not index_set_obj.time_field_unit:
                raise SearchUnKnowTimeField()
            union_time_fields.add(index_set_obj.time_field)
            union_time_fields_type.add(index_set_obj.time_field_type)
            union_time_fields_unit.add(index_set_obj.time_field_unit)

        # 处理公共的时间字段
        if len(union_time_fields) != 1 or len(union_time_fields_type) != 1 or len(union_time_fields_unit) != 1:
            time_field = "unionSearchTimeStamp"
            time_field_type = "date"
            time_field_unit = "millisecond"
        else:
            time_field = list(union_time_fields)[0]
            time_field_type = list(union_time_fields_type)[0]
            time_field_unit = list(union_time_fields_unit)[0]

        if not union_display_fields_all:
            union_display_fields_all.append(time_field)

        index_set_ids_hash = UserIndexSetFieldsConfig.get_index_set_ids_hash(index_set_ids)

        # 查询索引集ids是否有默认的显示配置  不存在则去创建
        # 考虑index_set_ids的查询性能 查询统一用index_set_ids_hash
        username = get_request_external_username() or get_request_username()
        try:
            user_index_set_config_obj = UserIndexSetFieldsConfig.objects.get(
                index_set_ids_hash=index_set_ids_hash,
                username=username,
                scope=SearchScopeEnum.DEFAULT.value,
            )
        except UserIndexSetFieldsConfig.DoesNotExist:
            user_index_set_config_obj = UserIndexSetFieldsConfig.objects.none()

        fields_names = [field_info.get("field_name") for field_info in total_fields]
        default_sort_list = [[time_field, "desc"]]
        for field_name in ["gseIndex", "gseindex", "iterationIndex", "_iteration_idx"]:
            if field_name in fields_names:
                default_sort_list.append([field_name, "desc"])

        if user_index_set_config_obj:
            try:
                obj = IndexSetFieldsConfig.objects.get(pk=user_index_set_config_obj.config_id)
            except IndexSetFieldsConfig.DoesNotExist:
                obj = self.get_or_create_default_config(
                    index_set_ids=index_set_ids, display_fields=union_display_fields_all, sort_list=default_sort_list
                )
                user_index_set_config_obj.config_id = obj.id
                user_index_set_config_obj.save()

        else:
            obj = self.get_or_create_default_config(
                index_set_ids=index_set_ids, display_fields=union_display_fields_all, sort_list=default_sort_list
            )
        ret = {
            "config_id": obj.id,
            "config": self.get_fields_config(context_and_realtime_config),
            "fields": total_fields,
            "fields_info": fields_info,
            "display_fields": obj.display_fields,
            "sort_list": obj.sort_list,
            "time_field": time_field,
            "time_field_type": time_field_type,
            "time_field_unit": time_field_unit,
        }
        return ret

    @staticmethod
    def get_or_create_default_config(
        index_set_ids: list, display_fields: list, sort_list: list
    ) -> IndexSetFieldsConfig:
        index_set_ids_hash = IndexSetFieldsConfig.get_index_set_ids_hash(index_set_ids)

        obj = IndexSetFieldsConfig.objects.filter(
            index_set_ids_hash=index_set_ids_hash,
            name=DEFAULT_INDEX_SET_FIELDS_CONFIG_NAME,
            scope=SearchScopeEnum.DEFAULT.value,
            source_app_code=get_request_app_code(),
        ).first()

        if not obj:
            obj = IndexSetFieldsConfig.objects.create(
                index_set_ids=index_set_ids,
                index_set_ids_hash=index_set_ids_hash,
                index_set_type=IndexSetType.UNION.value,
                name=DEFAULT_INDEX_SET_FIELDS_CONFIG_NAME,
                scope=SearchScopeEnum.DEFAULT.value,
                source_app_code=get_request_app_code(),
                display_fields=display_fields,
                sort_list=sort_list,
            )

        return obj

    @staticmethod
    def get_fields_config(context_and_realtime_config: dict):
        return [
            {"name": "bcs_web_console", "is_active": False},
            {"name": "trace", "is_active": False},
            {"name": "bkmonitor", "is_active": False},
            {"name": "async_export", "is_active": False},
            {"name": "ip_topo_switch", "is_active": False},
            {"name": "apm_relation", "is_active": False},
            {"name": "clustering_config", "is_active": False},
            {"name": "clean_config", "is_active": False},
            context_and_realtime_config,
        ]

    @property
    def index_sets(self):
        if not hasattr(self, "_index_sets"):
            self._index_sets = LogIndexSet.objects.filter(index_set_id__in=self.index_set_ids)
        return self._index_sets

    def pre_get_result(self, size: int):
        """
        pre_get_result
        @param size:
        @return:
        """
        if not self.index_sets:
            raise BaseSearchIndexSetException(
                BaseSearchIndexSetException.MESSAGE.format(index_set_id=self.index_set_ids)
            )

        # 构建请求参数
        params = {
            "ip_chooser": self.search_dict.get("ip_chooser"),
            "bk_biz_id": self.search_dict.get("bk_biz_id"),
            "addition": self.search_dict.get("addition"),
            "start_time": self.search_dict.get("start_time"),
            "end_time": self.search_dict.get("end_time"),
            "time_range": self.search_dict.get("time_range"),
            "keyword": self.search_dict.get("keyword"),
            "size": size,
            "is_union_search": True,
            "track_total_hits": self.search_dict.get("track_total_hits", False),
        }

        multi_execute_func = MultiExecuteFunc()
        for index_set_id in self.index_set_ids:
            search_dict = copy.deepcopy(params)
            search_dict["begin"] = self.search_dict.get("begin", 0)
            search_dict["sort_list"] = self._init_sort_list(index_set_id=index_set_id)
            search_dict["is_desensitize"] = self.desensitize_mapping.get(index_set_id, True)
            search_handler = SearchHandler(
                index_set_id=index_set_id,
                search_dict=search_dict,
                export_fields=self.search_dict.get("export_fields", []),
            )
            if search_handler.scenario_id == Scenario.ES:
                search_handler.scroll = SCROLL
            multi_execute_func.append(f"union_search_{index_set_id}", search_handler.search)

        # 执行线程
        multi_result = multi_execute_func.run(return_exception=True)
        for index_set_id in self.index_set_ids:
            ret = multi_result.get(f"union_search_{index_set_id}")
            if isinstance(ret, Exception):
                # 子查询异常
                raise UnionSearchErrorException(
                    UnionSearchErrorException.MESSAGE.format(index_set_id=index_set_id, e=ret)
                )
        return multi_result
