"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
from collections import defaultdict

from django.conf import settings

from rum_web.calculation import (
    Calculation,
)
from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.utils.cache import CacheType, using_cache
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from bkmonitor.utils.time_tools import get_datetime_range
from bkm_space.utils import bk_biz_id_to_space_uid
from core.drf_resource import resource, api

logger = logging.getLogger("rum")


class MetricHandler:
    """
    继承此类以定义指标, 指标支持以下两种查询方式
    Range 查询：（返回多个点）
        方法一：通过 GraphUnifyQuery 接口进行查询
        方法二：通过 Datasource 进行查询
            !!! 建议仅在使用了 promql 查询时使用 DataSource 方法来查询 Range ，否则会增加 convert 耗时
    Instance 查询: （返回一个点）
        只能通过 Datasource 进行查询
    """

    default_where = []
    aggs_method = "AVG"
    default_group_by = []
    default_functions = []
    metric_id = None
    calculation = Calculation
    query_type = "instance"
    dimension_field = ""
    metric_field = "bk_apm_duration"
    data_source_label = "custom"
    datasource_query = False

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
        functions=None,
    ):
        self.application = application
        self.start_time = start_time
        self.end_time = end_time
        self.where = [*self.default_where, *(where or [])]
        self.aggs_method = aggs_method or self.aggs_method
        self.group_by = [*(group_by or []), *self.default_group_by]
        self.filter_dict = filter_dict or {}
        self.interval = interval
        self.result_map = result_map
        self.functions = functions or self.default_functions

    def _get_app_attr(self, item):
        """
        取application的属性
        self.application类型可能为Application或者字典
        """
        try:
            return getattr(self.application, item)
        except AttributeError:
            return self.application[item]

    def _unify_query_params(self):
        """获取 GraphUnifyQuery 接口查询参数"""
        interval = self.interval
        database_name, _ = self._get_app_attr("metric_result_table_id").split(".")

        extra_param = {}
        if interval:
            extra_param["interval"] = interval
        return {
            "id": self.metric_id,
            "expression": "a",
            "display": True,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "dimension_field": "",
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
                    "functions": self.functions,
                    **extra_param,
                }
            ],
            "target": [],
            "bk_biz_id": str(self._get_app_attr("bk_biz_id")),
        }

    def _datasource_query_params(self, instant):
        """获取 DataSource 查询参数"""
        database_name, _ = self._get_app_attr("metric_result_table_id").split(".")

        extra_param = {}
        if instant:
            # Instant 计算只返回一个点
            extra_param["interval"] = self.end_time - self.start_time
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
            "functions": self.functions,
            "instant": instant,
            **extra_param,
        }

    def query_by_datasource(self, params):
        logger.info(f"[MetricQuery - DataSource] queryParams: \n----\n{json.dumps(params)}\n----")
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
            instant=params.get("instant", False),
        )

        return points

    def query_by_unify_query(self, params):
        logger.info(f"[MetricQuery - GraphUnifyQuery] queryParams: \n----\n{json.dumps(params)}\n----")
        return resource.grafana.graph_unify_query(params)

    def query(self):
        if self.query_type == "instance":
            # instance 查询都使用
            return self.result_map(self.query_instance())
        elif self.query_type == "range":
            return self.result_map(self.query_range())

        raise ValueError(f"不支持的查询类型: {self.query_type}")

    def query_instance(self):
        """Instance 查询 & 处理值"""
        return self.calculation.instance_cal(self.query_by_datasource(self._datasource_query_params(instant=True)))

    def query_range(self):
        """Range 类型查询 + 范围值计算"""
        if self.datasource_query:
            return self.calculation.range_cal(
                self._convert_to_series(self.query_by_datasource(self._datasource_query_params(instant=False)))
            )
        else:
            return self.calculation.range_cal(self.query_by_unify_query(self._unify_query_params()))

    def origin_query_range(self):
        """Range 查询 & 不处理值"""
        if self.datasource_query:
            return self._convert_to_series(self.query_by_datasource(self._datasource_query_params(instant=False)))
        else:
            return self.query_by_unify_query(self._unify_query_params())

    def origin_query_instance(self):
        """Instant 查询 & 不处理值"""
        return self.query_by_datasource(self._datasource_query_params(instant=True))

    def group_query(self, *group_key: str):
        """按照维度汇总返回"""
        result = self.origin_query_instance()
        group_map = defaultdict(list)
        for serie in result:
            g_key = "|".join([serie.get(key, "") for key in group_key])
            group_map[g_key].append(serie)
        result = defaultdict(dict)
        for key, series in group_map.items():
            result[key][self.metric_id] = self.result_map(self.calculation.instance_cal(series))
        return result

    def get_dimension_values_mapping(self):
        """获取维度出现过的值 返回[{"dimension1": "dimension1-value1"}]"""
        res = []
        keys = []
        result = self.origin_query_instance()
        for i in result:
            info = {}
            key = ""
            for g in self.group_by:
                if g in i:
                    info[g] = i[g]
                    key += i[g]
            if len(info) != len(self.group_by):
                continue
            # 只有全部 group_key 都有值才可以作为有效数据
            if key not in keys:
                keys.append(key)
                res.append(info)

        return res

    def get_instance_values_mapping(self, ignore_keys=None):
        """获取实例维度-值映射 返回
        {
            (*group_by): {"<metric>": <metric_value>}
        }
        """
        if not ignore_keys:
            ignore_keys = []
        response = self.origin_query_instance()
        res = defaultdict(lambda: defaultdict(int))
        for item in response:
            res[tuple(item.get(i, "") for i in self.group_by if i not in ignore_keys)][self.metric_id] += item[
                "_result_"
            ]
        return res

    def get_instance_calculate_values_mapping(self, ignore_keys=None):
        """获取实例维度-值映射(值经过计算) 返回
        {
            (*group_by): {"<metric>": <calculate_value>}
        }
        """
        if not ignore_keys:
            ignore_keys = []

        response = self.origin_query_instance()
        group_values = defaultdict(list)
        for item in response:
            group_values[tuple(item.get(i, "") for i in self.group_by if i not in ignore_keys)].append(item)

        res = defaultdict(lambda: defaultdict(int))
        for k, v in group_values.items():
            res[k][self.metric_id] = self.calculation.instance_cal(v)

        return res

    def get_range_values_mapping(self, ignore_keys=None):
        """获取范围-值映射 返回
        {
            (*group_by): [[10, timestamp], [20, timestamp]]
        }
        """
        if not ignore_keys:
            ignore_keys = []

        response = self.origin_query_range()
        res = defaultdict(list)
        for series in response.get("series", []):
            res[tuple(series.get("dimensions", {}).get(i) for i in self.group_by if i not in ignore_keys)].extend(
                series["datapoints"]
            )

        return res

    def get_range_calculate_values_mapping(self, ignore_keys=None):
        """获取范围-值映射(值经过计算) 返回
        {
            (*group_by): [[<calculate_value>, timestamp], [<calculate_value>, timestamp]]
        }
        """
        if not ignore_keys:
            ignore_keys = []
        response = self.origin_query_range()
        group_values = defaultdict(list)
        for series in response.get("series", []):
            key = tuple(series.get("dimensions", {}).get(i) for i in self.group_by if i not in ignore_keys)
            group_values[key].append(series)

        res = defaultdict(list)
        for k, series_list in group_values.items():
            calculate_v = self.calculation.range_cal({"series": series_list})
            series_response = calculate_v.get("series")
            if series_response:
                res[k] = series_response[0].get("datapoints")

        return res

    def _convert_to_series(self, datasource_range_response):
        """将使用 DataSource 查询的 range 数据转换为使用 GraphUnifyQuery 得到的 range 数据"""
        series_mapping = defaultdict(list)
        for i in datasource_range_response:
            dimensions = tuple(i.get(j) for j in self.group_by)
            series_mapping[dimensions].append([i["_result_"], i["_time_"]])

        series = []
        for k, v in series_mapping.items():
            series.append(
                {
                    "alias": "_result_",
                    "datapoints": v,
                    "dimensions": {i: k[index] for index, i in enumerate(self.group_by)},
                    "metric_field": "_result_",
                }
            )

        return {"metrics": [], "series": series}


class LcpP75Instance(MetricHandler):
    """
    RUM LCP P75 指标处理类。
    查询 LCP（Largest Contentful Paint）的第 75 百分位值。
    """

    metric_id = "lcp_p75"
    aggs_method = "SUM"
    metric_field = "browser_web_vital_duration_bucket"
    query_type = "instance"
    default_group_by = ["le"]
    default_where = [{"key": "vital_metric", "method": "eq", "value": ["lcp"]}]
    default_functions = [{"id": "histogram_quantile", "params": [{"id": "scalar", "value": 0.75}]}]


class JsErrorRateInstance(MetricHandler):
    """
    RUM JS 错误率指标处理类。
    计算 JavaScript 错误率 = JS 错误数 / 总页面访问数。
    """

    metric_id = "js_error_rate"
    aggs_method = "SUM"
    metric_field = "attributes.view.url"
    query_type = "instance"
    default_functions = [{"method": "cardinality"}]

    def _unify_query_params(self):
        """获取 GraphUnifyQuery 接口查询参数"""

        return {
            "space_uid": bk_biz_id_to_space_uid(self._get_app_attr("bk_biz_id")),
            "start_time": self.start_time,
            "end_time": self.end_time,
            "step": "1m",
            "instant": True,
            "metric_merge": "a",
            "query_list": [
                {
                    "data_source": "bklog",
                    "table_id": self._get_app_attr("span_result_table_id"),
                    "field_name": "attributes.view.url",
                    "reference_name": "a",
                    "query_string": "",
                    "conditions": {"field_list": [], "condition_list": []},
                    "function": self.default_functions,
                }
            ],
        }

    def query_by_unify_query(self, params):
        logger.info(f"[UnifyQuery - QueryReference] queryParams: \n----\n{json.dumps(params)}\n----")
        return api.unify_query.query_reference(params)

    def query_instance(self):
        """JS 错误率需要同时查询错误数和总访问数"""
        # 查询 JS 错误数
        error_params = self._unify_query_params()
        error_params["query_list"][0]["conditions"] = {
            "field_list": [
                {"field_name": "attributes.span_type", "op": "eq", "value": ["error"]},
                {"field_name": "attributes.error_type", "op": "eq", "value": ["js"]},
            ],
            "condition_list": ["and"],
        }
        error_result = self.query_by_unify_query(error_params)["series"][0]["values"][0][1]

        # 查询总页面访问数
        total_params = self._unify_query_params()
        total_params["query_list"][0]["conditions"] = {
            "field_list": [
                {"field_name": "span_name", "op": "eq", "value": ["browser.web_vital"]},
                {"field_name": "attributes.span_subtype", "op": "eq", "value": ["lcp"]},
            ],
            "condition_list": ["and"],
        }
        total_result = self.query_by_unify_query(total_params)["series"][0]["values"][0][1]

        if not total_result or total_result == 0:
            return 0

        return round(error_result / total_result, 3) if error_result else 0


class ApiFailRateInstance(MetricHandler):
    """
    RUM API 失败率指标处理类。
    计算 API 请求失败率 = API 失败数 / API 总请求数。
    """

    metric_id = "api_fail_rate"
    aggs_method = "SUM"
    metric_field = "span_name"
    query_type = "instance"
    default_functions = [{"method": "count"}]

    def _unify_query_params(self):
        """获取 GraphUnifyQuery 接口查询参数"""

        return {
            "space_uid": bk_biz_id_to_space_uid(self._get_app_attr("bk_biz_id")),
            "start_time": self.start_time,
            "end_time": self.end_time,
            "step": "1m",
            "instant": True,
            "metric_merge": "a",
            "query_list": [
                {
                    "data_source": "bklog",
                    "table_id": self._get_app_attr("span_result_table_id"),
                    "field_name": "attributes.view.url",
                    "reference_name": "a",
                    "query_string": "",
                    "conditions": {"field_list": [], "condition_list": []},
                    "function": self.default_functions,
                }
            ],
        }

    def query_by_unify_query(self, params):
        logger.info(f"[UnifyQuery - QueryReference] queryParams: \n----\n{json.dumps(params)}\n----")
        return api.unify_query.query_reference(params)

    def query_instance(self):
        """JS 错误率需要同时查询错误数和总访问数"""
        # 查询 JS 错误数
        error_params = self._unify_query_params()
        error_params["query_list"][0]["conditions"] = {
            "field_list": [
                {"field_name": "span_name", "op": "eq", "value": ["browser.resource"]},
                {"field_name": "attributes.span_subtype", "op": "eq", "value": ["xhr", "fetch"]},
                {"field_name": "status.code", "op": "eq", "value": ["2"]},
            ],
            "condition_list": ["and", "and"],
        }
        error_result = self.query_by_unify_query(error_params)["series"][0]["values"][0][1]

        # 查询总页面访问数
        total_params = self._unify_query_params()
        total_params["query_list"][0]["conditions"] = {
            "field_list": [
                {"field_name": "span_name", "op": "eq", "value": ["browser.resource"]},
                {"field_name": "attributes.span_subtype", "op": "eq", "value": ["xhr", "fetch"]},
            ],
            "condition_list": ["and"],
        }
        total_result = self.query_by_unify_query(total_params)["series"][0]["values"][0][1]

        if not total_result or total_result == 0:
            return 0

        return round(error_result / total_result, 3) if error_result else 0


@using_cache(CacheType.RUM(60 * 15))
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
