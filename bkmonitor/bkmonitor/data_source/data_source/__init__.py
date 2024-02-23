# -*- coding: utf-8 -*-
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
import json
import logging
import re
from abc import ABCMeta
from collections import defaultdict
from itertools import product
from typing import Any, Dict, List, Optional, Tuple, Type

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from bkmonitor.data_source.unify_query.functions import (
    AggMethods,
    CpAggMethods,
    Functions,
)
from bkmonitor.utils.common_utils import to_bk_data_rt_id
from bkmonitor.utils.range import load_agg_condition_instance
from bkmonitor.utils.time_tools import (
    parse_time_compare_abbreviation,
    time_interval_align,
)
from constants.alert import EventStatus
from constants.data_source import RECOVERY, DataSourceLabel, DataTypeLabel
from constants.strategy import (
    AGG_METHOD_REAL_TIME,
    SPLIT_DIMENSIONS,
    AdvanceConditionMethod,
)
from core.drf_resource import api
from core.errors.bkmonitor.data_source import (
    FunctionNotFoundError,
    FunctionNotSupportedError,
    MultipleTimeAggregateFunctionError,
    ParamRequiredError,
)
from core.errors.iam import PermissionDeniedError

logger = logging.getLogger(__name__)

allowed_interval = [10, 30, 60, 120, 300, 600, 1800, 3600, 7200, 10800]


def get_auto_interval(collect_interval: int, start_time: int, end_time: int):
    """
    自动周期计算
    """
    # 以2880个为预期聚合后点数计算汇聚周期
    expect_interval = (end_time - start_time) / collect_interval / 1440 * 60

    # 如果预期周期比采集周期小，则直接使用采集周期
    if expect_interval <= collect_interval:
        return collect_interval

    # 在预定的聚合周期中选择合适的汇聚周期
    for interval in allowed_interval:
        if expect_interval <= interval:
            return interval

    return allowed_interval[-1]


def is_build_in_process_data_source(table_id: str):
    # BuildInProcessMetric.result_table_list() only in web
    return table_id in ["process.perf", "process.port"]


def dict_to_q(filter_dict):
    """
    把前端传过来的filter_dict的格式变成django的Q
    规则：遍历每一个key:
    #         1.当val是个列表时：
    #            a.列表的内容是dict则递归调用自身，得到条件列表，用and拼接成一个条件字符串
    #            b.列表内容不是dict则根据key op val 生成一个条件字符串
    #            用or拼接上面列表生成的条件字符串
    #         2.当val不是个列表时：则根据key op val 生成一个条件字符串
    #         用and拼接上面的条件字符串
    """
    ret = None
    # dict下都是and条件
    list_filter = {}
    single_filter = {}
    for key, value in filter_dict.items():
        if isinstance(value, list):
            list_filter[key] = value
        elif isinstance(value, dict):
            _ret = dict_to_q(value)
            if not _ret:
                continue

            if ret is None:
                ret = _ret
            else:
                ret &= _ret
        else:
            single_filter[key] = value

    if single_filter:
        ret = Q(**single_filter) if ret is None else ret & Q(**single_filter)

    for key, value in list_filter.items():
        _ret = _list_to_q(key, value)
        if not _ret.children:
            continue

        if ret:
            ret &= _ret
        else:
            ret = _ret

    return ret


def _list_to_q(key, value):
    # value是list,key是上一个循环的键
    # 用于辅助dict_to_q
    ret = Q()
    operator, operator_is_false = _operator_is_exist(key)

    # 判断value是否为空
    if operator:
        if not value:
            # 没有操作符的空列表不解析,跳过
            return Q()
    else:
        if not value:
            # 有操作符的空列表解析空字符串
            return Q(**{key: ""})

    #  # list要看下里面的元素是什么类型,list条件下的三种情况,dict,list,str
    #  双层否定会表肯定,变成and条件
    if operator_is_false:
        if isinstance(value[0], dict):
            # temp_ret用来防止第一个q是空的情况,不能让空q取或
            temp_ret = dict_to_q(value[0])
            ret = (ret | temp_ret) if temp_ret else ret
            for i in value[1:]:
                ret = ret | dict_to_q(i)
        elif isinstance(value[0], list):
            temp_ret = _list_to_q(key, value[0])
            ret = (ret | temp_ret) if temp_ret else ret
            for i in value[1:]:
                ret = ret | _list_to_q(key, i)
        else:
            temp_ret = Q(**{key: value[0]})
            ret = (ret | temp_ret) if temp_ret else ret
            for i in value[1:]:
                ret = ret | Q(**{key: i})
    else:
        if isinstance(value[0], dict):
            for i in value:
                ret = ret & dict_to_q(i)
        elif isinstance(value[0], list):
            for i in value:
                ret = ret & _list_to_q(key, i)
        else:
            for i in value:
                ret = ret & Q(**{key: i})
    return ret


def _operator_is_exist(key):
    key_split = key.split("__")
    # 列表下默认or条件
    operator_is_false = True
    if len(key_split) > 1:
        operator = key_split[-1]
        if operator in ["neq", "!=", "not like"]:
            operator_is_false = False
    else:
        operator = ""

    return operator, operator_is_false


def _filter_dict_to_conditions(filter_dict: Dict, conditions: List[Dict]) -> List[Dict]:
    """
    将filter_dict解析为condition，filter_dict最多只有两层嵌套
    """

    def parse_key(_k: str):
        _key: List[str] = _k.split("__")
        if len(_key) > 1 and _key[-2]:
            return "__".join(_key[:-1]), _key[-1]
        else:
            return "__".join(_key), "eq"

    filter_dict = copy.deepcopy(filter_dict)
    conditions = copy.deepcopy(conditions)

    filter_conditions_list: List[List[Dict]] = []
    extend_conditions_list: List[List[List[Dict]]] = []
    filter_dict_list = [filter_dict]
    while filter_dict_list:
        filter_dict = filter_dict_list.pop()
        filter_conditions = []
        for key, value in filter_dict.items():
            if isinstance(value, Dict):
                for k, v in value.items():
                    k, method = parse_key(k)
                    v = v if isinstance(v, list) else [v]
                    v = [str(value) for value in v]
                    filter_conditions.append({"condition": "and", "key": k, "value": v, "method": method})
            elif isinstance(value, List):
                if not value:
                    continue
                if isinstance(value[0], Dict):
                    _conditions_list = []
                    for record in value:
                        _conditions: List[Dict] = []
                        for k, v in record.items():
                            k, method = parse_key(k)
                            v = v if isinstance(v, list) else [v]
                            v = [str(value) for value in v]
                            _conditions.append({"condition": "and", "key": k, "value": v, "method": method})
                        _conditions_list.append(_conditions)
                    extend_conditions_list.append(_conditions_list)
                else:
                    key, method = parse_key(key)
                    value = [str(v) for v in value]
                    filter_conditions.append({"condition": "and", "key": key, "value": value, "method": method})
            else:
                key, method = parse_key(key)
                value = str(value)
                filter_conditions.append({"condition": "and", "key": key, "value": [value], "method": method})
        if not filter_conditions:
            continue
        filter_conditions_list.append(filter_conditions)

    conditions_list: List[List[Dict]] = []
    _conditions = []
    for condition in conditions:
        if condition.get("condition") == "or":
            if _conditions:
                conditions_list.append(_conditions)
            _conditions = []
        else:
            condition["condition"] = "and"
        _conditions.append(condition)

    if _conditions:
        conditions_list.append(_conditions)

    result = []
    if not filter_conditions_list:
        filter_conditions_list = [[]]
    if not conditions_list:
        conditions_list = [[]]

    for conditions in product(filter_conditions_list, conditions_list, *extend_conditions_list):
        new_condition = []
        for condition in conditions:
            new_condition.extend(condition)
        new_condition = copy.deepcopy(new_condition)
        for condition in new_condition:
            condition["condition"] = "and"
        if result:
            new_condition[0]["condition"] = "or"
        result.extend(new_condition)

    if result and "condition" in result[0]:
        del result[0]["condition"]

    return result


class DataSource(metaclass=ABCMeta):
    data_source_label = ""
    data_type_label = ""

    metrics: List[Dict]
    group_by: List[str]
    interval: int
    time_field: str
    where: List[Dict]
    _advance_where: List[Dict]
    functions: List[Dict]

    DEFAULT_TIME_FIELD = "time"
    ADVANCE_CONDITION_METHOD = AdvanceConditionMethod

    def __init__(self, *args, name="", functions: List[Dict] = None, **kwargs):
        self.name = name
        self.functions = functions or []
        self.functions, self.time_shift, self.time_offset = self._parse_time_shift_function(functions)
        self._advance_where = []

    @classmethod
    def query_data(cls, *args, **kwargs) -> List:
        return []

    @classmethod
    def query_dimensions(cls, *args, **kwargs) -> List:
        return []

    @classmethod
    def query_log(cls, *args, **kwargs) -> Tuple[List, int]:
        return [], 0

    @classmethod
    def init_by_query_config(cls, query_config: Dict, *args, **kwargs) -> "DataSource":
        return cls()

    @property
    def id(self) -> Tuple[str, str]:
        return self.data_source_label, self.data_type_label

    @classmethod
    def _get_time_field(cls, interval):
        if not interval:
            return
        return f"time({interval}s)"

    def _parse_time_shift_function(self, functions: List) -> Tuple[List, str, int]:
        time_shift = None
        functions = functions or []
        for f in functions:
            if f["id"] != "time_shift":
                continue
            time_shift = f["params"][0].get("value") if f["params"] else None

        functions = [f for f in functions if f["id"] != "time_shift"]
        if not time_shift:
            return functions, "", 0

        time_offset = parse_time_compare_abbreviation(time_shift) * 1000
        return functions, time_shift, time_offset

    @classmethod
    def _get_queryset(
        cls,
        *,
        metrics: List[Dict] = None,
        select: List[str] = None,
        table: str = None,
        agg_condition: List = None,
        where: Dict = None,
        group_by: List[str] = None,
        index_set_id: int = None,
        query_string: str = "",
        limit: int = None,
        offset: int = None,
        slimit: int = None,
        order_by: List[str] = None,
        time_field: str = None,
        interval: int = None,
        start_time: int = None,
        end_time: int = None,
        time_align: bool = True,
    ):
        from bkmonitor.data_source.handler import DataQueryHandler

        metrics = json.loads(json.dumps(metrics)) or []
        select = select or []
        agg_condition = agg_condition or []
        where = where.copy() or {}
        group_by = (group_by or [])[:]
        time_field = time_field or cls.DEFAULT_TIME_FIELD
        order_by = order_by or [f"{time_field} desc"]

        # 实时监控方法处理
        for metric in metrics:
            if metric.get("method") == AGG_METHOD_REAL_TIME:
                metric["method"] = "AVG"

        # 过滤条件中添加时间字段
        time_filter = {}

        if start_time:
            if interval and time_align:
                start_time = time_interval_align(start_time // 1000, interval) * 1000

            time_filter[f"{time_field}__gte"] = start_time
        if end_time:
            if interval and time_align:
                end_time = time_interval_align(end_time // 1000, interval) * 1000
            time_filter[f"{time_field}__lt"] = end_time

        # 添加时间聚合字段
        if interval:
            group_by.append(cls._get_time_field(interval))

        q = DataQueryHandler(cls.data_source_label, cls.data_type_label)
        if where:
            q = q.where(dict_to_q(where))

        if time_filter:
            q = q.where(**time_filter)

        return (
            q.select(*select)
            .metrics(metrics)
            .table(table)
            .agg_condition(agg_condition)
            .group_by(*group_by)
            .dsl_index_set_id(index_set_id)
            .dsl_raw_query_string(query_string)
            .order_by(*order_by)
            .limit(limit)
            .slimit(slimit)
            .offset(offset)
            .time_field(time_field)
        )

    def _format_time_series_records(self, records: List[Dict]):
        """
        数据标准化
        """

        if self.interval:
            interval = self.interval
        else:
            interval = 1

        for record in records:
            # 去除时间为空的数据
            if not record.get(self.time_field):
                continue

            # 时间字段统一
            record["_time_"] = time_interval_align(record[self.time_field] // 1000, interval) * 1000 - self.time_offset
            del record[self.time_field]

        return records

    def _filter_by_advance_method(self, records: List):
        """
        根据高级条件过滤数据
        """
        if not self.ADVANCE_CONDITION_METHOD or not self._advance_where:
            return records

        condition_filter = load_agg_condition_instance(self._advance_where)
        return [record for record in records if condition_filter.is_match(record)]

    def _update_params_by_advance_method(self):
        """
        如果存在高级过滤条件，不再查询时提供过滤条件，并且在聚合维度中添加过滤字段
        """
        has_advance_method = False
        condition_fields = set()
        # 有高级匹配条件的场景，数据查询后过滤
        if self.ADVANCE_CONDITION_METHOD:
            for condition in self.where:
                condition_fields.add(condition["key"])
                method = condition.get("_origin_method", condition["method"])
                if method in self.ADVANCE_CONDITION_METHOD:
                    has_advance_method = True

        if has_advance_method:
            self._advance_where = self.where
            self.where = []
            for field in condition_fields:
                if field in self.group_by:
                    continue
                self.group_by.append(field)

    @property
    def metric_display(self):
        return ""

    @classmethod
    def is_cmdb_level_query(cls, *args, **kwargs):
        return False

    def _is_system_disk(self):
        return False

    def _is_system_net(self):
        return False


class InfluxdbDimensionFetcher(object):
    def query_dimensions(
        self, dimension_field, limit=settings.SQL_MAX_LIMIT, start_time=None, end_time=None, *args, **kwargs
    ):
        conditions_param = self.to_unify_query_config()[0]
        query_data = {
            "limit": limit,
            "table_id": conditions_param["table_id"],
            "info_type": "tag_values",
        }

        if conditions_param["field_name"]:
            query_data["metric_name"] = conditions_param["field_name"]

        if start_time:
            query_data["start_time"] = start_time // 1000
            query_data["end_time"] = end_time // 1000

        if conditions_param.get("conditions"):
            query_data["conditions"] = conditions_param.get("conditions")

        if isinstance(dimension_field, str):
            dimension_field = [dimension_field]
        query_data["keys"] = dimension_field

        logger.info(f"UNIFY_QUERY DIMENSIONS: {json.dumps(query_data)}")
        return api.unify_query.get_dimension_data(**query_data)


class PrometheusTimeSeriesDataSource(DataSource):
    data_source_label = "prometheus"
    data_type_label = "time_series"
    metrics = []
    time_field = "time"

    @classmethod
    def init_by_query_config(cls, query_config: Dict, *args, bk_biz_id=None, **kwargs):
        if bk_biz_id is None:
            raise ValueError("bk_biz_id can not be empty")

        return cls(
            bk_biz_id=bk_biz_id,
            promql=query_config["promql"],
            interval=query_config["agg_interval"],
            filter_dict=query_config.get("filter_dict"),
        )

    def __init__(self, bk_biz_id: int, promql: str, interval: int, filter_dict: dict = None, *args, **kwargs):
        self.bk_biz_id = bk_biz_id
        self.promql = promql
        self.interval = interval
        self.filter_dict = filter_dict or {}
        super(PrometheusTimeSeriesDataSource, self).__init__()

    @staticmethod
    def filter_dict_to_promql_match(filter_dict: dict) -> str:
        """
        将filter_dict转换为promql的match表达式
        @param filter_dict: 过滤条件
        @return: match表达式
        """
        match = ""
        if not filter_dict:
            return match

        filter_items = [filter_dict]
        match_items = []
        while len(filter_items) > 0:
            item = filter_items.pop()
            for key, value in item.items():
                if isinstance(value, dict):
                    filter_items.append(value)
                elif isinstance(value, str):
                    match_items.append(f'{key}={repr(value)}')
        if match_items:
            match = f"{{{','.join(match_items)}}}"
        return match

    def query_data(self, start_time: int = None, end_time: int = None, *args, **kwargs) -> List:
        from bkmonitor.data_source.unify_query.query import UnifyQuery

        start_time = time_interval_align(start_time // 1000, self.interval)
        end_time = time_interval_align(end_time // 1000, self.interval)

        # 增加额外的过滤条件
        match = self.filter_dict_to_promql_match(self.filter_dict)
        params = dict(
            bk_biz_ids=[self.bk_biz_id],
            promql=self.promql,
            match=match,
            start=start_time,
            end=end_time,
            step=f"{self.interval}s",
            timezone=timezone.get_current_timezone_name(),
        )

        data = api.unify_query.query_data_by_promql(**params)
        return UnifyQuery.process_unify_query_data({}, data, end_time=end_time * 1000)


class TimeSeriesDataSource(DataSource):
    data_source_label = ""
    data_type_label = ""

    DEFAULT_TIME_FIELD = "time"

    @classmethod
    def init_by_query_config(cls, query_config: Dict, *args, bk_biz_id=0, name="", **kwargs):
        """
        根据查询配置实例化
        """
        # 过滤空维度
        agg_dimension = [dimension for dimension in query_config.get("agg_dimension", []) if dimension]
        agg_method = query_config.get("agg_method", "COUNT")

        # 指标设置
        metrics = []
        if query_config.get("metric_field"):
            alias = query_config.get("alias") or query_config["metric_field"]
            metrics.append({"field": query_config["metric_field"], "method": agg_method, "alias": alias})
        else:
            alias = query_config.get("alias") or "alias"
            metrics.append({"field": "_index", "method": "COUNT", "alias": alias})

        for extend_metric_field in query_config.get("values", []):
            if "data_flow_id" in query_config and extend_metric_field in [
                "extra_info",
                "predict",
                "cluster",
                "upper_bound",
                "lower_bound",
            ]:
                # !!! 特殊逻辑 重要提示 !!!
                # 如果查询配置是智能异常检测的，且查询字段为 extra_info 或者 predict，则不进行聚合
                # 因为它们是一个字符串，聚合之后会变成空字符串
                # 由于离群检测算法的使用，需要对cluster字段使用GROUP_CONCAT
                if extend_metric_field == "cluster":
                    metrics.append({"field": extend_metric_field, "method": "GROUP_CONCAT"})
                else:
                    metrics.append({"field": extend_metric_field, "method": ""})
            else:
                metrics.append({"field": extend_metric_field, "method": agg_method})

        time_field = query_config.get("time_field")
        index_set_id = query_config.get("index_set_id")

        return cls(
            name=name,
            table=query_config.get("result_table_id", ""),
            metrics=metrics,
            interval=query_config.get("agg_interval", 60),
            group_by=agg_dimension,
            where=query_config.get("agg_condition", []),
            time_field=time_field,
            index_set_id=index_set_id,
            query_string=query_config.get("query_string", ""),
            bk_biz_id=bk_biz_id,
            functions=query_config.get("functions", {}),
            data_label=query_config.get("data_label", ""),
        )

    def _parse_function_params(self) -> Tuple[Dict, List[Dict]]:
        """
        函数参数转换为查询配置
        """
        time_aggregation = {}
        functions = []
        for function_params in self.functions:
            name = function_params["id"]
            params = {param["id"]: param["value"] for param in function_params["params"]}

            # 函数不支持在多指标计算中使用
            if name in ["top", "bottom"]:
                raise FunctionNotSupportedError(func_name=name)

            # 函数不存在
            if name not in Functions:
                raise FunctionNotFoundError(func_name=name)

            function = Functions[name]

            # 不能有多个时间函数
            if function.time_aggregation and time_aggregation:
                raise MultipleTimeAggregateFunctionError()

            # 转换为位置参数
            vargs_list = []
            # 时间窗口参数
            window = None
            for param in function.params:
                # 参数不存在
                if param.id not in params:
                    raise ParamRequiredError(func_name=name, param_name=param.id)

                # 事件窗口参数特殊处理
                if function.time_aggregation and param.id == "window":
                    window = params[param.id]
                    continue

                value = params[param.id]

                # 参数类型转换
                if param.type == "int":
                    value = int(value)
                elif param.type == "float":
                    value = float(value)

                vargs_list.append(value)

            config = {"vargs_list": vargs_list}
            # 判断是否是时间聚合函数
            if function.time_aggregation:
                time_aggregation = config
                config["function"] = function.id
                if window is not None:
                    config["window"] = window
            else:
                functions.append(config)
                config["method"] = function.id

            # position参数
            if function.position:
                config["position"] = function.position
            else:
                config["position"] = 0

            # 是否是维度聚合函数
            if function.with_dimensions:
                config["dimensions"] = self.group_by

            # 分位数计算必须存在le维度
            if function.name == "histogram_quantile" and "le" not in self.group_by:
                raise ParamRequiredError(func_name=name, param_name="le")

        return time_aggregation, functions

    def to_unify_query_config(self) -> List[Dict]:
        """
        生成统一查询配置
        """
        # 查询条件格式转换，融合filter_dic和条件语句
        conditions = {"field_list": [], "condition_list": []}
        operator_mapping = {
            "reg": "req",
            "nreg": "nreq",
            "include": "req",
            "exclude": "nreq",
            "eq": "contains",
            "neq": "ncontains",
        }
        for condition in _filter_dict_to_conditions(self.filter_dict, self.where):
            if conditions["field_list"]:
                conditions["condition_list"].append(condition.get("condition", "and"))

            value = condition["value"] if isinstance(condition["value"], list) else [condition["value"]]
            value = [str(v) for v in value]
            operator = operator_mapping.get(condition["method"], condition["method"])
            if operator in ["include", "exclude"]:
                value = [re.escape(v) for v in value]
            conditions["field_list"].append({"field_name": condition["key"], "value": value, "op": operator})

        # 聚合方法参数
        query_list = []
        for metric in self.metrics:
            table = self.table.lower()

            # 如果接入了数据平台，且是cmdb level表的查询，则需要去除后缀
            if settings.IS_ACCESS_BK_DATA and self.is_cmdb_level_query(
                where=self.where, filter_dict=self.filter_dict, group_by=self.group_by
            ):
                table, _, _ = table.partition("_cmdb_level")

            query: Dict[str, Any] = {
                "table_id": self.data_label or table,
                "time_aggregation": {},
                "field_name": metric["field"],
                "reference_name": (metric.get("alias") or metric["field"]).lower(),
                "dimensions": self.group_by,
                "driver": "influxdb",
                "time_field": self.time_field,
                "conditions": conditions,
                "function": [],
                "offset": f"{abs(self.time_offset // 1000)}s" if self.time_shift else "",
                "offset_forward": self.time_offset > 0,
            }

            if metric.get("method") and metric["method"] != AGG_METHOD_REAL_TIME:
                method = metric["method"].lower()

                # 分位数method特殊处理
                cp_agg_method = CpAggMethods.get(method)
                if cp_agg_method:
                    query["time_aggregation"]["vargs_list"] = cp_agg_method.vargs_list
                    query["time_aggregation"]["position"] = cp_agg_method.position
                    method = cp_agg_method.method

                if method.lower() in AggMethods:
                    method_mapping = {"avg": "mean"}
                    method = AggMethods[method].method
                else:
                    method_mapping = {"avg": "mean", "count": "sum"}
                    query["time_aggregation"].update(
                        {
                            "function": f"{method}_over_time",
                            "window": f"{self.interval}s" if self.interval else "1h",
                        }
                    )

                time_aggregation_func = {"method": method_mapping.get(method, method), "dimensions": self.group_by}

                if query["time_aggregation"].get("vargs_list"):
                    time_aggregation_func["vargs_list"] = query["time_aggregation"]["vargs_list"]

                query["function"].append(time_aggregation_func)

            # 解析函数参数
            time_aggregation, functions = self._parse_function_params()
            if time_aggregation:
                query["time_aggregation"].update(time_aggregation)
            query["function"].extend(functions)

            query["keep_columns"] = ["_time", query["reference_name"], *self.group_by]
            query_list.append(query)
        return query_list

    def _is_system_disk(self):
        return (
            self.table == settings.FILE_SYSTEM_TYPE_RT_ID
            and self.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
            and self.data_type_label == DataTypeLabel.TIME_SERIES
        )

    def _is_system_net(self):
        return (
            self.table == settings.SYSTEM_NET_GROUP_RT_ID
            and self.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
            and self.data_type_label == DataTypeLabel.TIME_SERIES
        )

    def __init__(
        self,
        *args,
        table,
        metrics: List = None,
        interval: int = 0,
        where: List = None,
        filter_dict: Dict = None,
        group_by: List[str] = None,
        order_by: List[str] = None,
        time_field: str = None,
        index_set_id: int = None,
        query_string: str = "",
        data_label: str = "",
        **kwargs,
    ):
        super(TimeSeriesDataSource, self).__init__(*args, **kwargs)
        self.data_label = data_label
        self.table = table
        self.metrics = metrics or []
        self.interval = interval
        self.where = where or []
        self.filter_dict = filter_dict or {}
        self.group_by = group_by or []
        self.time_field = time_field or self.DEFAULT_TIME_FIELD
        self.index_set_id = index_set_id
        self.query_string = query_string
        self.order_by = order_by or [f"{self.time_field} desc"]

        # 过滤空维度
        self.group_by = [d for d in self.group_by if d]
        self._update_params_by_advance_method()

    def query_data(
        self,
        start_time: int = None,
        end_time: int = None,
        limit: Optional[int] = settings.SQL_MAX_LIMIT,
        slimit: Optional[int] = None,
        *args,
        **kwargs,
    ) -> List:
        filter_dict = self.filter_dict.copy()
        if self._is_system_disk():
            filter_dict[f"{settings.FILE_SYSTEM_TYPE_FIELD_NAME}__neq"] = settings.FILE_SYSTEM_TYPE_IGNORE
        elif self._is_system_net():
            value = [condition["sql_statement"] for condition in settings.ETH_FILTER_CONDITION_LIST]
            filter_dict[f"{settings.SYSTEM_NET_GROUP_FIELD_NAME}__neq"] = value

        if start_time:
            start_time = start_time + self.time_offset
        if end_time:
            end_time = end_time + self.time_offset

        q = self._get_queryset(
            metrics=self.metrics,
            table=self.table,
            index_set_id=self.index_set_id,
            query_string=self.query_string,
            agg_condition=self.where,
            group_by=self.group_by,
            interval=self.interval,
            where=filter_dict,
            time_field=self.time_field,
            order_by=self.order_by,
            limit=limit,
            slimit=slimit,
            start_time=start_time,
            end_time=end_time,
        )

        records = q.raw_data
        records = self._format_time_series_records(records)
        return self._filter_by_advance_method(records)

    def query_dimensions(
        self,
        dimension_field: str,
        start_time: int = None,
        end_time: int = None,
        limit: Optional[int] = None,
        slimit: Optional[int] = None,
        *args,
        **kwargs,
    ) -> List:
        if isinstance(dimension_field, list):
            dimension_field = dimension_field[0]

        q = self._get_queryset(
            metrics=self.metrics[:1],
            table=self.table,
            query_string=self.query_string,
            index_set_id=self.index_set_id,
            agg_condition=self.where,
            group_by=[dimension_field],
            where=self.filter_dict,
            limit=limit,
            slimit=slimit,
            time_field=self.time_field,
            order_by=self.order_by,
            start_time=start_time,
            end_time=end_time,
            interval=kwargs.get("interval"),
        )
        records = self._filter_by_advance_method(q.raw_data)
        return [record[dimension_field] for record in records]

    @property
    def metric_display(self):
        field = self.name or self.metrics[0]["field"]
        method = self.metrics[0].get("method", "").lower()
        if method and method != AGG_METHOD_REAL_TIME:
            return f"{method}({field})"
        else:
            return field


class BkMonitorTimeSeriesDataSource(TimeSeriesDataSource):
    """
    监控采集时序型数据源
    """

    data_source_label = DataSourceLabel.BK_MONITOR_COLLECTOR
    data_type_label = DataTypeLabel.TIME_SERIES
    query_dimensions = InfluxdbDimensionFetcher.query_dimensions

    ADVANCE_CONDITION_METHOD = []

    def __init__(self, *args, **kwargs):
        super(BkMonitorTimeSeriesDataSource, self).__init__(*args, **kwargs)

        if settings.IS_ACCESS_BK_DATA and self.is_cmdb_level_query(
            where=self.where, filter_dict=self.filter_dict, group_by=self.group_by
        ):
            self.time_field = BkdataTimeSeriesDataSource.DEFAULT_TIME_FIELD
            self.order_by = [f"{self.time_field} desc"]

    @classmethod
    def is_cmdb_level_query(cls, where: List = None, filter_dict: Dict = None, group_by: List[str] = None):
        where = where or []
        filter_dict = filter_dict or {}
        group_by = group_by or []

        fields = set()
        # 解析filter_dict，取出实际的过滤字段
        for key, value in filter_dict.items():
            if not value:
                continue

            if isinstance(value, dict):
                value = [value]

            # 如果值是字典类型，则取字典字段作为key
            if isinstance(value, list) and isinstance(value[0], dict):
                for v in value:
                    if not isinstance(v, dict):
                        continue
                    fields.update(v)
            else:
                fields.add(key)

        fields.update(condition["key"] for condition in where)
        fields.update(group_by)
        # 只要字段中包含有bk_obj_id 或者 bk_inst_id则转到计算平台查询
        return fields & set(SPLIT_DIMENSIONS)

    @classmethod
    def _get_queryset(
        cls, *, table: str = None, agg_condition: List = None, where: Dict = None, group_by: List[str] = None, **kwargs
    ):
        if settings.IS_ACCESS_BK_DATA and cls.is_cmdb_level_query(
            where=agg_condition, filter_dict=where, group_by=group_by
        ):
            raw_table, _, _ = table.partition("_cmdb_level")
            replace_table_id = to_bk_data_rt_id(raw_table, settings.BK_DATA_CMDB_SPLIT_TABLE_SUFFIX)
            return BkdataTimeSeriesDataSource._get_queryset(
                table=replace_table_id, agg_condition=agg_condition, where=where, group_by=group_by, **kwargs
            )

        return super(BkMonitorTimeSeriesDataSource, cls)._get_queryset(
            table=table, agg_condition=agg_condition, where=where, group_by=group_by, **kwargs
        )


class BkdataTimeSeriesDataSource(TimeSeriesDataSource):
    """
    计算平台时序型数据源
    """

    data_source_label = DataSourceLabel.BK_DATA
    data_type_label = DataTypeLabel.TIME_SERIES

    DEFAULT_TIME_FIELD = "dtEventTimeStamp"

    def __init__(self, *args, **kwargs):
        super(BkdataTimeSeriesDataSource, self).__init__(*args, **kwargs)

        # 对用户的请求进行鉴权
        if "bk_biz_id" in kwargs:
            bk_biz_id = str(kwargs["bk_biz_id"])
            table_prefix = re.match(r"^(\d*)", self.table).groups()[0]
            if not table_prefix or table_prefix == str(settings.BK_DATA_BK_BIZ_ID):
                # 目标表前缀没有业务信息，或者前缀业务属于监控平台对接计算平台的业务，则不需要鉴权
                return
            if table_prefix != bk_biz_id:
                logger.error(f"用户请求bkdata数据源无权限(result_table_id:{self.table}, 业务id: {bk_biz_id})")
                raise PermissionDeniedError(action_name=bk_biz_id)

    def to_unify_query_config(self) -> List[Dict]:
        # unify 定义 bkdata 查询配置制定data_source字段
        query_list = super().to_unify_query_config()
        for query in query_list:
            query["data_source"] = "bkdata"
        return query_list

    @classmethod
    def _get_queryset(cls, *, metrics: List[Dict] = None, **kwargs):
        # 计算平台查询的指标使用反引号，避免与关键字冲突
        metrics = copy.deepcopy(metrics)
        for metric in metrics:
            if not metric["field"].startswith("`"):
                metric["field"] = f"`{metric['field']}`"

            if metric.get("alias") and not metric["alias"].startswith("`"):
                metric["alias"] = f"`{metric['alias']}`"

        return super(BkdataTimeSeriesDataSource, cls)._get_queryset(metrics=metrics, **kwargs)

    @classmethod
    def _get_time_field(cls, interval):
        if not interval:
            return
        if interval < 60:
            raise Exception(_("计算平台聚合周期不能低于一分钟"))
        return f"minute{interval // 60}"

    def _format_time_series_records(self, records: List[Dict]):
        """
        数据标准化
        """
        # bkdata 数据源返回字段多了(minuteX)字段, 一并去除
        records = super(BkdataTimeSeriesDataSource, self)._format_time_series_records(records)
        minute_field = self._get_time_field(self.interval)
        for record in records:
            record.pop(minute_field, None)
        return records


class CustomTimeSeriesDataSource(TimeSeriesDataSource):
    """
    自定义时序型数据源
    """

    data_source_label = DataSourceLabel.CUSTOM
    data_type_label = DataTypeLabel.TIME_SERIES
    query_dimensions = InfluxdbDimensionFetcher.query_dimensions
    ADVANCE_CONDITION_METHOD = []

    def __init__(self, *args, **kwargs):
        super(CustomTimeSeriesDataSource, self).__init__(*args, **kwargs)

        if judge_auto_filter(kwargs.get("bk_biz_id", 0), self.table):
            self.filter_dict["bk_biz_id"] = str(kwargs["bk_biz_id"])


class LogSearchTimeSeriesDataSource(TimeSeriesDataSource):
    """
    日志时序型数据源
    """

    data_source_label = DataSourceLabel.BK_LOG_SEARCH
    data_type_label = DataTypeLabel.TIME_SERIES

    DEFAULT_TIME_FIELD = "dtEventTimeStamp"

    def __init__(self, *args, **kwargs):
        super(LogSearchTimeSeriesDataSource, self).__init__(*args, **kwargs)

        # 条件方法替换
        condition_mapping = {
            "eq": "is one of",
            "neq": "is not one of",
        }
        for condition in self.where:
            if condition["method"] in condition_mapping:
                condition["_origin_method"] = condition["method"]
                condition["method"] = condition_mapping[condition["method"]]

    def query_data(
        self,
        start_time: int = None,
        end_time: int = None,
        *args,
        **kwargs,
    ) -> List:
        # 日志查询中limit仅能限制返回的原始日志数量，因此固定为1
        if "limit" in kwargs:
            kwargs.pop("limit")

        return super(LogSearchTimeSeriesDataSource, self).query_data(start_time, end_time, limit=1, *args, **kwargs)

    def query_dimensions(
        self,
        dimension_field: str,
        start_time: int = None,
        end_time: int = None,
        limit: int = None,
        *args,
        **kwargs,
    ) -> List:
        # 日志查询中limit仅能限制返回的原始日志数量，因此固定为1
        if "limit" in kwargs:
            kwargs.pop("limit")

        if isinstance(dimension_field, list):
            assert len(dimension_field) > 0, _("维度查询参数，维度字段是必须的")
            dimension_field = dimension_field[0]

        return super(LogSearchTimeSeriesDataSource, self).query_dimensions(
            dimension_field, start_time, end_time, limit=1, *args, **kwargs
        )[:limit]

    def query_log(
        self,
        start_time: int = None,
        end_time: int = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        *args,
        **kwargs,
    ) -> Tuple[List, int]:
        q = self._get_queryset(
            query_string=self.query_string,
            table=self.table,
            index_set_id=self.index_set_id,
            agg_condition=self.where,
            where=self.filter_dict,
            time_field=self.time_field,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )

        data = q.original_data
        total = data["hits"]["total"]
        if isinstance(total, dict):
            total = total["value"]

        result = [record["_source"] for record in data["hits"]["hits"][:limit]]
        return result, total


class LogSearchLogDataSource(LogSearchTimeSeriesDataSource):
    """
    日志关键字数据源
    """

    data_source_label = DataSourceLabel.BK_LOG_SEARCH
    data_type_label = DataTypeLabel.LOG

    DEFAULT_TIME_FIELD = "dtEventTimeStamp"

    def __init__(self, *args, **kwargs):
        super(LogSearchLogDataSource, self).__init__(*args, **kwargs)
        self.metrics = [{"field": "_index", "method": "COUNT"}]

    @property
    def metric_display(self):
        time_display = _("{}秒").format(self.interval)
        if self.interval > 60:
            time_display = _("{}分钟").format(self.interval // 60)
        return _("{}内匹配到关键字次数").format(time_display)


class BkApmTraceDataSource(LogSearchLogDataSource):
    data_source_label = DataSourceLabel.BK_APM
    data_type_label = DataTypeLabel.LOG
    DEFAULT_TIME_FIELD = "time"


class BkApmTraceTimeSeriesDataSource(LogSearchTimeSeriesDataSource):
    data_source_label = DataSourceLabel.BK_APM
    data_type_label = DataTypeLabel.TIME_SERIES
    DEFAULT_TIME_FIELD = "time"


class BkMonitorLogDataSource(DataSource):
    data_source_label = DataSourceLabel.BK_MONITOR_COLLECTOR
    data_type_label = DataTypeLabel.LOG

    INNER_DIMENSIONS = ["event_name", "target"]
    DISTINCT_METHODS = {"AVG", "SUM", "COUNT"}
    METHOD_DESC = {"avg": _lazy("均值"), "sum": _lazy("总和"), "max": _lazy("最大值"), "min": _lazy("最小值"), "count": ""}

    @classmethod
    def init_by_query_config(cls, query_config: Dict, name="", *args, **kwargs):
        # 过滤空维度
        agg_dimension = [dimension for dimension in query_config.get("agg_dimension", []) if dimension]

        # 统计聚合目标节点
        topo_nodes = defaultdict(list)
        if query_config.get("target") and query_config["target"][0]:
            target = query_config["target"][0][0]
            if target["field"] in ["host_topo_node", "service_topo_node"]:
                for value in target["value"]:
                    topo_nodes[value["bk_obj_id"]].append(value["bk_inst_id"])

        # 指标设置
        metrics = [{"field": "event.count", "method": query_config["agg_method"]}]
        time_field = query_config.get("time_field")

        return cls(
            name=name,
            table=query_config["result_table_id"],
            metrics=metrics,
            interval=query_config.get("agg_interval", 60),
            group_by=agg_dimension,
            where=query_config.get("agg_condition", []),
            time_field=time_field,
            topo_nodes=topo_nodes,
        )

    def __init__(
        self,
        *,
        table,
        metrics: List[Dict] = None,
        interval: int = 0,
        where: List = None,
        filter_dict: Dict = None,
        query_string: str = "",
        group_by: List[str] = None,
        time_field: str = None,
        topo_nodes: Dict[str, List] = None,
        **kwargs,
    ):
        super(BkMonitorLogDataSource, self).__init__(**kwargs)
        self.metrics = metrics or []
        self.table = table
        self.interval = interval
        self.where = where or []
        self.filter_dict = filter_dict or {}
        self.query_string = query_string
        self.group_by = group_by or []
        self.time_field = time_field or self.DEFAULT_TIME_FIELD

        # 过滤空维度
        self.group_by = [d for d in self.group_by if d]
        self._update_params_by_advance_method()

        # 如果维度中包含实例，则不按节点聚合
        if {"bk_target_ip", "bk_target_service_instance_id"} & set(self.group_by):
            topo_nodes = {}
        self.topo_nodes = topo_nodes or {}

    def is_dimensions_field(self, field: str) -> bool:
        """
        判断是否需要补全dimensions前缀
        """
        return field not in self.INNER_DIMENSIONS and not field.startswith("dimensions")

    def _get_metrics(self):
        """
        metric字段处理
        """
        metrics = self.metrics.copy()
        methods = {metric.get("method", "").upper() for metric in self.metrics}
        if methods & self.DISTINCT_METHODS:
            metrics.append({"field": "dimensions.bk_module_id", "method": "distinct", "alias": "distinct"})
        return metrics

    def _get_group_by(self, bk_obj_id: str = None) -> List:
        """
        聚合维度处理，判断是否需要按节点聚合
        """
        group_by = self.group_by[:]

        # 去除补全的特殊维度
        if "bk_obj_id" in group_by:
            group_by.remove("bk_obj_id")
        if "bk_inst_id" in group_by:
            group_by.remove("bk_inst_id")

        # 如果没有实例维度，则按节点聚合
        if not ({"bk_target_ip", "bk_target_service_instance_id"} & set(group_by)) and bk_obj_id:
            group_by.append(f"bk_{bk_obj_id}_id")

        # 维度补充dimensions.前缀
        return [
            f"dimensions.{dimension}" if self.is_dimensions_field(dimension) else dimension for dimension in group_by
        ]

    def _get_where(self):
        """
        非内置维度需要补充dimensions.
        """
        where = copy.deepcopy(self.where)
        for condition in where:
            if self.is_dimensions_field(condition["key"]):
                condition["key"] = f"dimensions.{condition['key']}"

        # 去除采集配置ID条件
        where = [c for c in where if c["key"] != "dimensions.bk_collect_config_id"]
        return where

    def _add_dimension_prefix(self, filter_dict: Dict) -> Dict:
        """
        为filter_dict添加维度前缀
        """
        new_filter_dict = {}

        # 将bk_inst_id和bk_obj_id过滤条件调整真实的层级维度
        if "bk_inst_id" in filter_dict and "bk_obj_id" in filter_dict:
            new_filter_dict[f"dimensions.bk_{filter_dict['bk_obj_id']}_id"] = filter_dict["bk_inst_id"]

        for key, value in filter_dict.items():
            # 如果value是数组类型且其中为字典，则需要遍历每一个子value
            if isinstance(value, (list, Tuple)) and value and isinstance(value[0], Dict):
                new_filter_dict[key] = [self._add_dimension_prefix(v) for v in value]
                continue

            if key in ["bk_collect_config_id", "bk_inst_id", "bk_obj_id"]:
                continue

            # 如果是字典类型，则处理value中的key
            if isinstance(value, Dict):
                new_filter_dict[key] = self._add_dimension_prefix(value)
                continue

            if self.is_dimensions_field(key):
                key = f"dimensions.{key}"

            new_filter_dict[key] = value
        return new_filter_dict

    def _get_filter_dict(self, bk_obj_id: str = None, bk_inst_ids: List = None) -> Dict:
        """
        过滤条件按target过滤及添加dimensions.前缀
        """
        filter_dict = self.filter_dict.copy() if self.filter_dict else {}
        if bk_obj_id and bk_inst_ids:
            filter_dict[f"bk_{bk_obj_id}_id"] = bk_inst_ids

        return self._add_dimension_prefix(filter_dict)

    def _distinct_calculate(self, records: List[Dict], bk_obj_id: str = None) -> List:
        """
        根据聚合方法和bk_module_id的重复数量计算实际的值
        """
        group_by = self._get_group_by(bk_obj_id)
        group_by.append(self.time_field)

        metric_values = {}
        dimension_count = defaultdict(lambda: 0)
        for record in records:
            key = tuple((dimension, record[dimension]) for dimension in group_by)
            dimension_count[key] += 1

            # 维度初始化
            if key not in metric_values:
                metric_values[key] = defaultdict(lambda: 0)

            for metric in self.metrics:
                method = metric.get("method", "")
                alias = metric.get("alias") or metric["field"]

                if method in ["COUNT", "SUM"]:
                    record[alias] /= record["distinct"] or 1

                if method in self.DISTINCT_METHODS:
                    metric_values[key][alias] += record[alias] or 0
                else:
                    metric_values[key][alias] = record[alias] or 0

        # 平均值计算
        for metric in self.metrics:
            method = metric.get("method", "")
            alias = metric.get("alias") or metric["field"]

            if method != "AVG":
                continue

            for key, value in metric_values.items():
                value[alias] /= dimension_count[key]

        # 只保留需要的维度和指标
        new_result = []
        for key, value in metric_values.items():
            record = {dimension: dimension_value for dimension, dimension_value in key}
            record.update(value)
            new_result.append(record)

        return new_result

    @staticmethod
    def _remove_dimensions_prefix(data: List, bk_obj_id=None):
        """请求结果中去除dimensions.前缀"""
        result = []
        for record in data:
            new_record = {}
            for key, value in record.items():
                if key.startswith("dimensions."):
                    key = key[11:]

                if key == f"bk_{bk_obj_id}_id":
                    new_record["bk_obj_id"] = bk_obj_id
                    new_record["bk_inst_id"] = value
                else:
                    new_record[key] = value

            result.append(new_record)
        return result

    def query_data(
        self,
        start_time: int = None,
        end_time: int = None,
        limit: int = None,
        *args,
        **kwargs,
    ) -> List:
        metrics = self._get_metrics()
        where = self._get_where()

        if start_time:
            start_time = start_time + self.time_offset
        if end_time:
            end_time = end_time + self.time_offset

        topo_nodes = self.topo_nodes.copy()
        if not topo_nodes:
            topo_nodes[""] = []

        records = []
        for bk_obj_id, bk_inst_ids in topo_nodes.items():
            group_by = self._get_group_by(bk_obj_id)
            filter_dict = self._get_filter_dict(bk_obj_id, bk_inst_ids)

            if "dimensions.bk_target_ip" not in group_by:
                group_by.append("dimensions.bk_target_ip")
            if "dimensions.bk_target_cloud_id" not in group_by:
                group_by.append("dimensions.bk_target_cloud_id")

            q = self._get_queryset(
                metrics=metrics,
                table=self.table,
                agg_condition=where,
                group_by=group_by,
                interval=self.interval,
                where=filter_dict,
                limit=1,
                time_field=self.time_field,
                start_time=start_time,
                end_time=end_time,
                query_string=self.query_string,
            )
            data = self._distinct_calculate(q.raw_data, bk_obj_id)
            data = self._remove_dimensions_prefix(data, bk_obj_id)
            records.extend(data)
        records = self._filter_by_advance_method(records)
        records = self._format_time_series_records(records)
        return records[:limit]

    def query_dimensions(
        self,
        dimension_field: str,
        start_time: int = None,
        end_time: int = None,
        limit: int = None,
        *args,
        **kwargs,
    ) -> List:
        if isinstance(dimension_field, list):
            dimension_field = dimension_field[0]

        if self.is_dimensions_field(dimension_field):
            dimension_field = f"dimensions.{dimension_field}"

        q = self._get_queryset(
            metrics=self.metrics[:1],
            table=self.table,
            agg_condition=self._get_where(),
            group_by=[dimension_field],
            where=self._get_filter_dict(),
            limit=limit,
            time_field=self.time_field,
            start_time=start_time,
            end_time=end_time,
            query_string=self.query_string,
            interval=kwargs.get("interval"),
        )
        records = self._remove_dimensions_prefix(q.raw_data)
        records = self._filter_by_advance_method(records)
        if "." in dimension_field:
            dimension_field = dimension_field.split(".")[-1]
        return [record[dimension_field] for record in records][:limit]

    def query_log(
        self, start_time: int = None, end_time: int = None, limit: int = None, offset: int = None, *args, **kwargs
    ) -> Tuple[List, int]:
        q = self._get_queryset(
            table=self.table,
            agg_condition=self._get_where(),
            where=self._get_filter_dict(),
            limit=limit,
            offset=offset,
            time_field=self.time_field,
            start_time=start_time,
            end_time=end_time,
            query_string=self.query_string,
        )
        data = q.original_data
        total = data["hits"]["total"]
        if isinstance(total, dict):
            total = total["value"]

        result = [record["_source"] for record in data["hits"]["hits"][:limit]]
        return result, total

    @property
    def metric_display(self):
        time_display = _("{}秒").format(self.interval)
        if self.interval > 60:
            time_display = _("{}分钟").format(self.interval // 60)
        method = self.metrics[0]["method"].lower()
        return _("{}内接收到事件次数{}").format(time_display, self.METHOD_DESC[method])


class CustomEventDataSource(BkMonitorLogDataSource):
    """
    自定义事件数据源
    """

    data_source_label = DataSourceLabel.CUSTOM
    data_type_label = DataTypeLabel.EVENT
    INNER_DIMENSIONS = ["target", "event_name"]

    @classmethod
    def init_by_query_config(cls, query_config: Dict, name="", *args, **kwargs):
        # 过滤空维度
        agg_dimension = [dimension for dimension in query_config.get("agg_dimension", []) if dimension]
        time_fields = query_config.get("time_field")
        custom_event_name = query_config.get("custom_event_name", "")

        return cls(
            name=name,
            metrics=[{"field": "_index", "method": "COUNT"}],
            table=query_config.get("result_table_id", ""),
            interval=query_config.get("agg_interval", 60),
            group_by=agg_dimension,
            query_string=query_config.get("query_string", ""),
            where=query_config.get("agg_condition", []),
            time_field=time_fields,
            custom_event_name=custom_event_name,
            data_label=query_config.get("data_label", ""),
        )

    def __init__(self, *args, **kwargs):
        super(CustomEventDataSource, self).__init__(*args, **kwargs)

        # 添加自定义事件过滤条件
        if kwargs.get("custom_event_name"):
            self.filter_dict["event_name"] = kwargs["custom_event_name"]

        # 过滤掉恢复事件
        self.filter_dict["event_type__neq"] = RECOVERY

        # 支持metric_field为自定义事件名
        if (
            self.metrics
            and self.metrics[0]["field"] not in ["_index", "event.count"]
            and "event_name" not in self.filter_dict
        ):
            event_name = self.metrics[0]["field"]
            self.metrics[0]["field"] = "_index"
            self.metrics[0]["method"] = "COUNT"
            self.filter_dict["event_name"] = event_name

        # 锁定指标聚合方法为Count
        # todo count(_index) -> sum(event.count)X
        for metric in self.metrics:
            if metric["field"] == "_index":
                metric["method"] = "COUNT"

        # 平台级且业务不等于绑定的平台业务
        if judge_auto_filter(kwargs.get("bk_biz_id", 0), self.table):
            self.filter_dict["bk_biz_id"] = kwargs["bk_biz_id"]

    def add_recovery_filter(self, datasource):
        """
        去除原有默认的异常事件筛选，增加恢复过滤条件
        :return: 增加恢复事件筛选的DataSource
        """
        # 原有 datasource 默认不筛选恢复事件，弹出
        datasource.filter_dict.pop("event_type__neq")

        # 新增恢复事件筛选条件
        datasource.filter_dict["event_type__eq"] = RECOVERY

        return datasource

    def query_data(
        self,
        start_time: int = None,
        end_time: int = None,
        limit: int = None,
        *args,
        **kwargs,
    ) -> List:
        where = self._get_where()
        filter_dict = self._get_filter_dict()
        group_by = self._get_group_by()

        if start_time:
            start_time = start_time + self.time_offset
        if end_time:
            end_time = end_time + self.time_offset

        q = self._get_queryset(
            metrics=self.metrics,
            table=self.table,
            agg_condition=where,
            interval=self.interval,
            group_by=group_by,
            where=filter_dict,
            query_string=self.query_string,
            limit=1,
            time_field=self.time_field,
            start_time=start_time,
            end_time=end_time,
        )

        records = self._remove_dimensions_prefix(q.raw_data)
        records = self._filter_by_advance_method(records)
        records = self._format_time_series_records(records)
        return records[:limit]


class BkMonitorEventDataSource(DataSource):
    """
    系统事件数据源
    """

    data_source_label = DataSourceLabel.BK_MONITOR_COLLECTOR
    data_type_label = DataTypeLabel.EVENT


class BkFtaEventDataSource(DataSource):
    data_source_label = DataSourceLabel.BK_FTA
    data_type_label = DataTypeLabel.EVENT

    DEFAULT_TIME_FIELD = "time"
    ADVANCE_CONDITION_METHOD = []

    @classmethod
    def init_by_query_config(cls, query_config: Dict, name="", bk_biz_id=None, *args, **kwargs):
        return cls(
            name=name,
            metrics=[
                {
                    "field": query_config["alert_name"],
                    "method": "COUNT",
                    "alias": query_config.get("alias", ""),
                }
            ],
            interval=query_config.get("agg_interval", 60),
            group_by=query_config.get("agg_dimension", []),
            where=query_config.get("agg_condition", []),
            bk_biz_id=bk_biz_id,
        )

    def __init__(
        self,
        metrics: List[Dict] = None,
        interval: int = 60,
        where: List = None,
        group_by: List[str] = None,
        filter_dict: Dict = None,
        alert_name: str = None,
        bk_biz_id: int = None,
        **kwargs,
    ):
        super(BkFtaEventDataSource, self).__init__(**kwargs)
        self.interval = interval // 60
        self.where = copy.deepcopy(where) or []
        self.group_by = [d for d in group_by if d] if group_by else []
        self._update_params_by_advance_method()
        self.time_field = self.DEFAULT_TIME_FIELD

        self.metrics = copy.deepcopy(metrics)

        if alert_name:
            # 如果传了告警名称，就直接用
            self.alert_name = alert_name
        elif self.metrics:
            # 如果没有传告警名称，那必定传了 metrics，从 metrics 提取
            self.alert_name = self.metrics[0]["field"]
            self.metrics[0].update(
                {
                    "field": "_index",
                    "method": "COUNT",
                }
            )
        else:
            self.alert_name = None

        self.filter_dict = copy.deepcopy(filter_dict) or {}
        # 追加过滤条件
        self.filter_dict["status"] = EventStatus.ABNORMAL

        if self.alert_name:
            self.filter_dict["alert_name.raw"] = self.alert_name

        if bk_biz_id:
            self.filter_dict["bk_biz_id"] = bk_biz_id

    def query_data(
        self,
        start_time: int = None,
        end_time: int = None,
        limit: int = None,
        *args,
        **kwargs,
    ) -> List:
        if start_time:
            start_time = start_time + self.time_offset
        if end_time:
            end_time = end_time + self.time_offset

        q = self._get_queryset(
            table=f"{start_time}|{end_time}",
            metrics=self.metrics,
            agg_condition=self.where,
            interval=self.interval,
            group_by=self.group_by,
            where=self.filter_dict,
            limit=1,
            time_field=self.time_field,
            start_time=start_time,
            end_time=end_time,
        )
        records = q.raw_data
        records = self._filter_by_advance_method(records)
        records = self._format_time_series_records(records)
        return records[:limit]

    def query_dimensions(
        self,
        dimension_field: str,
        start_time: int = None,
        end_time: int = None,
        limit: Optional[int] = None,
        *args,
        **kwargs,
    ) -> List:
        if isinstance(dimension_field, list):
            dimension_field = dimension_field[0]

        if dimension_field in ["description"]:
            # 不可聚合字段，直接返回空
            return []

        q = self._get_queryset(
            table=f"{start_time}|{end_time}",
            metrics=self.metrics,
            agg_condition=self.where,
            interval=self.interval,
            group_by=[dimension_field],
            where=self.filter_dict,
            limit=1,
            time_field=self.time_field,
            start_time=start_time,
            end_time=end_time,
        )
        records = self._filter_by_advance_method(q.raw_data)
        return [record[dimension_field] for record in records]

    def query_log(
        self, start_time: int = None, end_time: int = None, limit: int = None, offset: int = None, *args, **kwargs
    ) -> Tuple[List, int]:
        q = self._get_queryset(
            table=f"{start_time}|{end_time}" if start_time and end_time else None,
            metrics=self.metrics,
            agg_condition=self.where,
            interval=self.interval,
            group_by=self.group_by,
            where=self.filter_dict,
            time_field=self.time_field,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )

        data = q.original_data
        total = data["hits"]["total"]
        if isinstance(total, dict):
            total = total["value"]

        result = [record["_source"] for record in data["hits"]["hits"][:limit]]
        return result, total

    @property
    def metric_display(self):
        return _("{}分钟内接收到事件次数").format(self.interval)


class BkFtaAlertDataSource(BkFtaEventDataSource):
    data_source_label = DataSourceLabel.BK_FTA
    data_type_label = DataTypeLabel.ALERT


class BkMonitorAlertDataSource(BkFtaEventDataSource):
    data_source_label = DataSourceLabel.BK_MONITOR_COLLECTOR
    data_type_label = DataTypeLabel.ALERT

    @classmethod
    def init_by_query_config(cls, query_config: Dict, name="", *args, **kwargs):
        return cls(
            name=name,
            metrics=[
                {
                    "field": query_config["bkmonitor_strategy_id"],
                    "method": "COUNT",
                    "alias": query_config.get("alias", ""),
                }
            ],
            interval=query_config.get("agg_interval", 60),
            group_by=query_config.get("agg_dimension", []),
            where=query_config.get("agg_condition", []),
        )

    def __init__(
        self, metrics: List[Dict] = None, filter_dict: Dict = None, bkmonitor_strategy_id: int = None, *args, **kwargs
    ):
        super(BkMonitorAlertDataSource, self).__init__(metrics, *args, **kwargs)

        self.metrics = copy.deepcopy(metrics)

        if bkmonitor_strategy_id:
            self.strategy_id = bkmonitor_strategy_id
        elif self.metrics:
            self.strategy_id = self.metrics[0]["field"]
            self.metrics[0].update(
                {
                    "field": "_index",
                    "method": "COUNT",
                }
            )
        else:
            self.strategy_id = None

        self.filter_dict = copy.deepcopy(filter_dict) or {}
        # 追加过滤条件
        self.filter_dict["status"] = EventStatus.ABNORMAL

        if self.strategy_id:
            self.filter_dict["strategy_id"] = self.strategy_id


def judge_auto_filter(bk_biz_id: int, table_id: str) -> bool:
    """
    是否注入bk_biz_id过滤条件逻辑：
    - 平台级自定义指标：
      - 查询参数业务id 等于 自定义指标的所属业务 不过滤(平台级查看)
      - 查询参数业务id 不等于 自定义指标的所属业务 过滤(单业务视角)
    - 内置进程采集 需要过滤(单业务视角)
    - 非平台级自定义指标 不需要过滤(自定义指标不一定有bk_biz_id字段，无需过滤)

    方案：
    api.metadata.get_result_table(table_id) -> 拿到所属业务信息，业务id为0 则表示为全局
    而绑定的平台业务id，在data_name里面获取
    data_name 生成规则：
    1. 事件： 业务id在最后面"{}_{}_{}".format(self.CUSTOM_EVENT_DATA_NAME, event_group_name, bk_biz_id)
    2. 指标： 业务id在最前面"{}_{}_{}".format(bk_biz_id, self.CUSTOM_TS_NAME, ts_name)
    """
    # todo 平台级判定需要根据项目空间调整
    from metadata.models import (
        DataSource,
        DataSourceResultTable,
        EventGroup,
        ResultTable,
    )

    if not bk_biz_id:
        return False

    if not table_id:
        return True

    need_add_filter = is_build_in_process_data_source(table_id=table_id)
    if need_add_filter:
        return need_add_filter

    if settings.ENVIRONMENT == "development":
        table_info = api.metadata.get_result_table(table_id=table_id)
        data_id = table_info["bk_data_id"]
        if table_info["bk_biz_id"] == 0:
            data_source_data = api.metadata.get_data_id(bk_data_id=data_id, with_rt_info=False)
            space_uid = data_source_data.get("space_uid", "")
            if space_uid:
                platform_biz_id = space_uid.split("__", -1)[-1]
            else:
                data_name = data_source_data.get("data_name", "0")
                event_groups = [
                    group
                    for group in api.metadata.query_event_group(bk_biz_id=bk_biz_id)
                    if group["bk_data_id"] == data_id
                ]
                if event_groups:
                    # 自定义事件 data_name 的业务ID在最后面
                    platform_biz_id = data_name.split("_")[-1]
                else:
                    platform_biz_id = data_name.split("_")[0]
            need_add_filter = platform_biz_id != str(bk_biz_id)
    else:
        result_table = ResultTable.objects.filter(table_id=table_id).first()
        if result_table and result_table.bk_biz_id == 0:
            data_id = DataSourceResultTable.objects.get(table_id=table_id).bk_data_id
            data_source_data = DataSource.objects.get(bk_data_id=data_id)
            space_uid = data_source_data.space_uid
            if space_uid:
                platform_biz_id = space_uid.split("__", -1)[-1]
            else:
                data_name = data_source_data.data_name
                if EventGroup.objects.filter(bk_data_id=data_id).exists():
                    platform_biz_id = data_name.split("_")[-1]
                else:
                    platform_biz_id = data_name.split("_")[0]
            need_add_filter = platform_biz_id != str(bk_biz_id)
    return need_add_filter


def load_data_source(data_source_label: str, data_type_label: str) -> Type[DataSource]:
    """
    加载对应的DataSource
    """
    data_sources = [
        BkMonitorTimeSeriesDataSource,
        BkMonitorLogDataSource,
        BkMonitorEventDataSource,
        BkdataTimeSeriesDataSource,
        CustomEventDataSource,
        CustomTimeSeriesDataSource,
        LogSearchLogDataSource,
        LogSearchTimeSeriesDataSource,
        BkMonitorAlertDataSource,
        BkFtaAlertDataSource,
        BkFtaEventDataSource,
        BkApmTraceDataSource,
        BkApmTraceTimeSeriesDataSource,
        PrometheusTimeSeriesDataSource,
    ]

    data_source_mapping = {
        (data_source.data_source_label, data_source.data_type_label): data_source for data_source in data_sources
    }

    return data_source_mapping[(data_source_label, data_type_label)]
