# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from collections import defaultdict

from django.conf import settings
from opentelemetry.trace import StatusCode

from apm_web.calculation import (
    ApdexCalculation,
    Calculation,
    ErrorRateCalculation,
    ErrorRateOriginCalculation,
)
from apm_web.constants import Apdex, CalculationMethod
from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.utils.cache import CacheType, using_cache
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from bkmonitor.utils.time_tools import get_datetime_range
from constants.apm import OtlpKey
from core.drf_resource import resource


class MetricHandler:
    default_where = []
    aggs_method = "AVG"
    default_group_by = []
    metric_id = None
    calculation = Calculation
    query_type = "instance"
    dimension_field = ""
    metric_field = "bk_apm_duration"
    data_source_label = "custom"

    def __init__(
        self,
        application,
        start_time,
        end_time,
        where=None,
        aggs_method=None,
        group_by=None,
        filter_dict=None,
        interval=None,
        result_map=lambda x: x,
    ):
        self.application = application
        self.start_time = start_time
        self.end_time = end_time
        self.where = [*self.default_where, *(where or [])]
        self.aggs_method = aggs_method or self.aggs_method
        self.group_by = [*self.default_group_by, *(group_by or [])]
        self.filter_dict = filter_dict or {}
        self.interval = interval
        self.result_map = result_map

    def _get_app_attr(self, item):
        """
        取application的属性
        self.application类型可能为Application或者字典
        """
        try:
            return getattr(self.application, item)
        except AttributeError:
            return self.application[item]

    def _unify_query_param(self, is_instance: bool = False, dimension_field=""):
        interval = self.interval
        database_name, _ = self._get_app_attr("metric_result_table_id").split(".")

        if is_instance:
            interval = self.end_time - self.start_time
        extra_param = {}
        if interval:
            extra_param["interval"] = interval
        return {
            "id": self.metric_id,
            "expression": "a",
            "display": True,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "dimension_field": dimension_field,
            "query_configs": [
                {
                    "data_source_label": "custom",
                    "data_type_label": "time_series",
                    "metrics": [
                        {
                            "field": self.metric_field,
                            "method": self.aggs_method,
                            "alias": "a",
                        }
                    ],
                    "table": f"{database_name}.__default__",
                    "group_by": self.group_by,
                    "display": True,
                    "where": self.where,
                    "interval_unit": "s",
                    "time_field": "time",
                    "filter_dict": {
                        **self.filter_dict,
                    },
                    "functions": [],
                    **extra_param,
                }
            ],
            "target": [],
            "bk_biz_id": str(self._get_app_attr("bk_biz_id")),
        }

    def _get_interval(self):
        interval = self.interval
        if not interval:
            interval = self.end_time - self.start_time
        return interval

    def _get_instance_unify_query_params(self):
        database_name, _ = self._get_app_attr("metric_result_table_id").split(".")

        extra_param = {}
        extra_param["interval"] = self._get_interval()
        return {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "metrics": [
                {
                    "field": self.metric_field,
                    "method": self.aggs_method,
                    "alias": "a",
                }
            ],
            "table": f"{database_name}.__default__",
            "group_by": self.group_by,
            "display": True,
            "where": self.where,
            "interval_unit": "s",
            "time_field": "time",
            "filter_dict": {
                **self.filter_dict,
            },
            "functions": [],
            **extra_param,
        }

    def instance_unify_query(self, params):
        """
        自定义时许数据: 对于获取近一小时、近三小时等等时间范围的数据之和 不适用于图表查询的graph_unify_query接口
        """
        data_source_class = load_data_source(self.data_source_label, "time_series")
        data_sources = [data_source_class(bk_biz_id=self._get_app_attr("bk_biz_id"), **params)]

        query = UnifyQuery(
            bk_biz_id=self._get_app_attr("bk_biz_id"),
            data_sources=data_sources,
            expression="",
            functions=[],
        )

        points = query.query_data(
            start_time=self.start_time * 1000,
            end_time=self.end_time * 1000,
            limit=settings.SQL_MAX_LIMIT,
            slimit=settings.SQL_MAX_LIMIT,
            time_alignment=False,
            instant=params.get("instant"),
        )

        return points

    def query(self):
        if self.query_type == "instance":
            return self.result_map(self.query_instance())
        if self.query_type == "range":
            return self.result_map(self.query_range())
        return self.result_map(self.query_dimension_count(self.dimension_field))

    def _query(self, is_instance: bool):
        return resource.grafana.graph_unify_query(self._unify_query_param(is_instance))

    def query_instance(self):
        return self.calculation.instance_cal(self.instance_unify_query(self._get_instance_unify_query_params()))

    def query_range(self):
        return self.calculation.range_cal(self._query(False))

    def query_dimension_count(self, dimension_field: str):
        return resource.grafana.dimension_count_unify_query(self._unify_query_param(False, dimension_field))

    def origin_query_instance(self):
        return self.instance_unify_query(self._get_instance_unify_query_params())

    def group_query(self, *group_key: str):
        result = self.instance_unify_query(self._get_instance_unify_query_params())
        group_map = defaultdict(list)
        for serie in result:
            g_key = "|".join([serie.get(key, "") for key in group_key])
            group_map[g_key].append(serie)
        result = defaultdict(dict)
        for key, series in group_map.items():
            result[key][self.metric_id] = self.result_map(self.calculation.instance_cal(series))
        return result

    def get_dimension_value(self):
        """获取维度出现过的值"""
        res = set()
        result = self.instance_unify_query(self._get_instance_unify_query_params())
        for i in result:
            for g in self.group_by:
                if g in i:
                    res.add(i[g])
        return res


class AvgDurationInstance(MetricHandler):
    """
    平均耗时为promql实现 不查询指标
    """

    metric_id = CalculationMethod.AVG_DURATION
    data_source_label = "prometheus"

    promql_format = (
        'sum(increase('
        '{{__name__="bkmonitor:{table_id}:__default__:bk_apm_duration_sum"{where}}}[{interval}s])) '
        '{group_by} '
        '/ sum(increase('
        '{{__name__="bkmonitor:{table_id}:__default__:bk_apm_total"{where}}}[{interval}s])) '
        '{group_by}'
    )

    def query(self):
        return self.result_map(self.query_instance())

    def _get_instance_unify_query_params(self):
        table_id, _ = self._get_app_attr("metric_result_table_id").split(".")

        group_by = ""
        if self.group_by:
            group_by = "by ({keys})".format(keys=",".join(self.group_by))

        where = []
        for i in self.where:
            where.append(f'{i["key"]}={"" if i["method"] == "eq" else "~"}"{"|".join(i["value"])}"')

        for k, v in self.filter_dict.items():
            where.append(f'{k}="{v}"')

        interval = self._get_interval()
        return {
            "promql": self.promql_format.format(
                table_id=table_id,
                group_by=group_by,
                interval=interval,
                where=f", {','.join(where)}" if where else "",
            ),
            "interval": interval,
        }


class RequestCountInstance(MetricHandler):
    metric_id = CalculationMethod.REQUEST_COUNT
    aggs_method = "SUM"
    metric_field = "bk_apm_count"


class ErrorCountInstance(MetricHandler):
    metric_id = CalculationMethod.ERROR_COUNT
    aggs_method = "SUM"
    metric_field = "bk_apm_count"
    default_where = [{"key": "status_code", "method": "eq", "value": [str(StatusCode.ERROR.value)]}]


class ErrorRateInstance(MetricHandler):
    metric_id = CalculationMethod.ERROR_RATE
    aggs_method = "SUM"
    metric_field = "bk_apm_count"
    default_group_by = [OtlpKey.get_metric_dimension_key(OtlpKey.STATUS_CODE)]
    calculation = ErrorRateCalculation


class ErrorRateOriginInstance(ErrorRateInstance):
    calculation = ErrorRateOriginCalculation


class ApdexInstance(MetricHandler):
    metric_id = CalculationMethod.APDEX
    aggs_method = "SUM"
    default_group_by = [OtlpKey.get_metric_dimension_key(OtlpKey.STATUS_CODE), Apdex.DIMENSION_KEY]
    calculation = ApdexCalculation
    metric_field = "bk_apm_count"


class ApdexRange(MetricHandler):
    metric_id = CalculationMethod.APDEX
    aggs_method = "SUM"
    default_group_by = [OtlpKey.get_metric_dimension_key(OtlpKey.STATUS_CODE), Apdex.DIMENSION_KEY]
    calculation = ApdexCalculation
    metric_field = "bk_apm_count"


@using_cache(CacheType.APM(60 * 15))
def cache_batch_metric_query_group(
    application,
    period=None,
    distance=None,
    start_time=None,
    end_time=None,
    group_key: list = None,
    metric_handler_cls: list = None,
    where: list = None,
):
    if not start_time or not end_time:
        # start_time/end_time 和 period/distance 二选一填写
        start_time, end_time = get_datetime_range(period, distance)
        start_time, end_time = int(start_time.timestamp()), int(end_time.timestamp())

    return batch_metric_query_group(application, start_time, end_time, group_key, metric_handler_cls, where)


def batch_metric_query_group(
    application,
    start_time: int,
    end_time: int,
    group_key: list,
    metric_handler_cls: list,
    where: list,
):
    def metric_query(data_map, metric_handler):
        value = metric_handler.group_query(*group_key)
        for k, v in value.items():
            data_map[k].update(v)

    data_map = defaultdict(dict)
    th_list = []
    for metric_handler in metric_handler_cls:
        metric_handler_instance = metric_handler(
            application,
            start_time,
            end_time,
            group_by=group_key,
            where=where,
        )
        th_list.append(
            InheritParentThread(
                target=metric_query,
                args=(data_map, metric_handler_instance),
            )
        )
    run_threads(th_list)
    return data_map


@using_cache(CacheType.APM(60 * 15))
def cache_batch_metric_query(
    iteritems,
    period: str = None,
    distance: int = None,
    start_time=None,
    end_time=None,
    metric_handler_cls: list = None,
    id_get=lambda x: x,
    filter_dict_build=lambda x: None,
    get_application=lambda x: x,
):
    if not start_time or not end_time:
        # start_time/end_time 和 period/distance 二选一填写
        start_time, end_time = get_datetime_range(period, distance)
        start_time, end_time = int(start_time.timestamp()), int(end_time.timestamp())
    return batch_metric_query(
        start_time,
        end_time,
        iteritems,
        metric_handler_cls,
        id_get,
        filter_dict_build,
        get_application,
    )


def batch_metric_query(
    start_time,
    end_time,
    iteritems,
    metric_handler_cls: list,
    id_get=lambda x: x,
    filter_dict_build=lambda x: None,
    get_application=lambda x: x,
):
    def metric_query(item_id, data_map, metric_handler):
        data_map[str(item_id)][metric_handler.metric_id] = metric_handler.query()

    data_map = defaultdict(dict)
    th_list = []
    for item in iteritems:
        for metric_handler in metric_handler_cls:
            item_id = id_get(item)
            filter_dict = filter_dict_build(item)
            metric_handler_instance = metric_handler(
                get_application(item), start_time, end_time, filter_dict=filter_dict
            )
            th_list.append(
                InheritParentThread(
                    target=metric_query,
                    args=(item_id, data_map, metric_handler_instance),
                )
            )
    run_threads(th_list)
    return data_map
