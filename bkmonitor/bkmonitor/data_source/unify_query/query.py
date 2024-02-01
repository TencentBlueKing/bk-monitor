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

import json
import logging
import re
import time
from itertools import chain
from typing import Dict, List, Optional, Union

import arrow
from django.conf import settings
from django.utils import timezone
from django.utils.functional import cached_property
from opentelemetry import trace

from bkm_space.utils import bk_biz_id_to_space_uid
from bkmonitor.data_source.data_source import DataSource, TimeSeriesDataSource
from bkmonitor.data_source.unify_query.functions import (
    AggMethods,
    CpAggMethods,
    add_expression_functions,
)
from bkmonitor.utils.time_tools import time_interval_align
from constants.data_source import GrayUnifyQueryDataSources, UnifyQueryDataSources
from core.drf_resource import api
from core.prometheus import metrics

tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)


class UnifyQuery:
    """
    统一查询模块
    """

    def __init__(
        self,
        bk_biz_id: Optional[int],
        data_sources: List[DataSource],
        expression: str,
        functions: List = None,
    ):
        self.functions = [] if functions is None else functions
        # 不传业务指标时传 0，为 None 时查询所有业务
        self.bk_biz_id = bk_biz_id
        self.data_sources = data_sources
        self.expression = expression

    @cached_property
    def space_uid(self):
        if self.bk_biz_id is None:
            return None

        return bk_biz_id_to_space_uid(self.bk_biz_id)

    @property
    def metrics(self) -> List[Dict]:
        """
        指标列表
        """
        metric_fields = set()
        metrics = []

        # 多指标查询仅支持最终计算结果展示，无法查询多余指标
        if len(self.data_sources) > 1:
            return [{"field": "_result_"}]

        for data_source in self.data_sources:
            for metric in data_source.metrics:
                metric_field = metric.get("alias") or metric["field"]
                if metric_field in metric_fields:
                    continue
                metrics.append(metric)

        # 目标值设置为_result_
        metrics.append({"field": "_result_"})
        return metrics

    @property
    def metric_display(self) -> str:
        return ",".join(data_source.metric_display for data_source in self.data_sources)

    @property
    def dimensions(self) -> Optional[List[str]]:
        if not hasattr(self.data_sources[0], "group_by"):
            return None

        dimensions = set()
        for data_source in self.data_sources:
            dimensions.update(data_source.group_by)
        return list(dimensions)

    @classmethod
    def process_unify_query_data(cls, params: Dict, data: Dict, end_time: int = None):
        """
        处理统一查询模块返回值
        """
        re_dimension = re.compile(r"_table\d+$")

        records = []

        rows = data["series"] or []
        for row in rows:
            dimensions = {}
            if not row["group_keys"]:
                row["group_keys"] = []
            for index, group_key in enumerate(row["group_keys"]):
                end_string = re_dimension.findall(group_key)
                if end_string:
                    end_string = end_string[0]
                    group_key = group_key[: -len(end_string)]

                dimensions[group_key] = row["group_values"][index]

            for value in row["values"]:
                record = {**dimensions}
                for column, column_type, v in zip(row["columns"], row["types"], value):
                    if column_type == "time":
                        v = arrow.get(v).timestamp * 1000

                    if column == "_time":
                        column = "_time_"
                    elif column in ["_result", "_value"]:
                        column = "_result_"

                    record[column] = v

                # 单指标情况下避免缺少_result_字段
                if "_result_" not in record:
                    record["_result_"] = record[params["query_list"][0]["reference_name"]]

                # 如果是最后一条数据，且时间戳等于结束时间，不返回
                if end_time and record.get("_time_") == end_time:
                    continue

                records.append(record)
        return records

    def use_unify_query(self) -> bool:
        """
        判断使用使用统一查询模块进行查询
        """
        # 数据源是否支持多指标
        if self.data_sources[0].id not in UnifyQueryDataSources + GrayUnifyQueryDataSources:
            return False

        if self.data_sources[0].id in GrayUnifyQueryDataSources:
            # 灰度数据源基于业务进行灰度
            if self.bk_biz_id not in settings.BKDATA_USE_UNIFY_QUERY_GRAY_BIZ_LIST:
                return False

        # 如果是多指标，必然会走统一查询模块
        if len(self.data_sources) > 1:
            return True

        # 如果使用了查询函数，比如会走统一查询模块
        if self.data_sources[0].functions:
            return True

        # 使用特殊函数必须走统一查询模块
        for metric in self.data_sources[0].metrics:
            method = metric["method"].lower()
            if method in AggMethods or method in CpAggMethods:
                return True

        # kubernetes，直接使用查询模块
        is_negative_biz_id = self.bk_biz_id is not None and int(self.bk_biz_id) < 0
        if not self.data_sources[0].table or is_negative_biz_id:
            return True

        # 接入数据平台时，cmdb level表在白名单中的，不走统一查询模块
        for data_source in self.data_sources:
            if (
                settings.IS_ACCESS_BK_DATA
                and data_source.is_cmdb_level_query(
                    where=data_source.where, filter_dict=data_source.filter_dict, group_by=data_source.group_by
                )
                and data_source.table in settings.BKDATA_CMDB_LEVEL_TABLES
            ):
                return False
        return True

    def get_unify_query_params(self, start_time: int = None, end_time: int = None, time_alignment: bool = True):
        """
        生成查询参数
        """
        self.data_sources: List[TimeSeriesDataSource]

        # 子查询配置
        query_list: List[Dict] = list(
            chain(*[data_source.to_unify_query_config() for data_source in self.data_sources])
        )

        # 计算查询步长
        step = 0
        for data_source in self.data_sources:
            if data_source.interval:
                step = min([data_source.interval, step]) if step else data_source.interval

        # 目前的默认步长为一分钟
        if not step:
            step = 60

        # 默认表达式
        if not self.expression:
            expression = " + ".join([query["reference_name"] for query in query_list])
        else:
            expression = self.expression

        params = {
            "query_list": query_list,
            "metric_merge": add_expression_functions(expression, self.functions),
            "order_by": ["-time"],
            "step": f"{step}s",
            "space_uid": self.space_uid,
        }

        if start_time and end_time:
            if time_alignment:
                params["start_time"] = str(time_interval_align(start_time // 1000, step))
                params["end_time"] = str(time_interval_align(end_time // 1000, step))
            else:
                params["start_time"] = str(start_time // 1000)
                params["end_time"] = str(end_time // 1000)

        return params

    def _query_unify_query(
        self,
        start_time: int,
        end_time: int,
        limit: Optional[int] = None,
        slimit: Optional[int] = None,
        down_sample_range: Optional[int] = "",
        time_alignment: bool = True,
    ) -> List[Dict]:
        """
        使用统一查询模块进行查询
        """
        params = self.get_unify_query_params(start_time, end_time, time_alignment)
        params.update(dict(down_sample_range=down_sample_range, timezone=timezone.get_current_timezone_name()))

        logger.info(f"UNIFY_QUERY: {json.dumps(params)}")

        with tracer.start_as_current_span("unify_query") as span:
            span.set_attribute("bk.system", "unify_query")
            span.set_attribute("bk.unify_query.statement", json.dumps(params))
            data = api.unify_query.query_data(**params)
            data = self.process_unify_query_data(params, data, end_time=end_time)
        return data

    def _query_data_source(
        self,
        start_time: int,
        end_time: int,
        limit: Optional[int] = None,
        slimit: Optional[int] = None,
    ) -> List[Dict]:
        """
        使用原始数据源进行查询
        """

        all_data = []

        for datasource in self.data_sources:
            data = datasource.query_data(
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                slimit=slimit,
            )
            if len(self.data_sources) == 1:
                # 如果只有一个指标，就直接将 result 字段当前指标，否则不设置
                for record in data:
                    if not datasource.metrics:
                        continue
                    metric_field = datasource.metrics[0].get("alias") or datasource.metrics[0]["field"]
                    record["_result_"] = record[metric_field]
            all_data.extend(data)

        return all_data

    def query_data(
        self,
        start_time: int = None,
        end_time: int = None,
        limit: Optional[int] = settings.SQL_MAX_LIMIT,
        slimit: Optional[int] = settings.SQL_MAX_LIMIT,
        down_sample_range: Optional[str] = "",
        *args,
        **kwargs,
    ) -> List[Dict]:
        if not self.data_sources:
            return []

        if not start_time or not end_time:
            end_time = int(time.time()) * 1000
            start_time = end_time - 60 * 60 * 1000

        result_tables = []
        # 补充特殊网络和磁盘维度过滤
        for data_source in self.data_sources:
            if data_source._is_system_disk():
                data_source.filter_dict[
                    f"{settings.FILE_SYSTEM_TYPE_FIELD_NAME}__neq"
                ] = settings.FILE_SYSTEM_TYPE_IGNORE
            elif data_source._is_system_net():
                value = [condition["sql_statement"] for condition in settings.ETH_FILTER_CONDITION_LIST]
                data_source.filter_dict[f"{settings.SYSTEM_NET_GROUP_FIELD_NAME}__neq"] = value

            result_table = str(
                getattr(data_source, "table", "")
                or getattr(data_source, "index_set_id", "")
                or getattr(data_source, "alert_name", "")
            )

            if not result_table and data_source.metrics:
                result_table = data_source.metrics[0]["field"]
            result_tables.append(result_table)
        result_tables.sort()

        # 上报数据源查询时间指标
        labels = {
            "data_source_label": self.data_sources[0].data_source_label,
            "data_type_label": self.data_sources[0].data_type_label,
            "role": settings.ROLE,
            "result_table": "|".join(result_tables),
        }

        exc = None

        # 使用统一查询模块或原始数据源进行查询
        if self.use_unify_query():
            labels["api"] = "unify_query"
            try:
                with metrics.DATASOURCE_QUERY_TIME.labels(**labels).time():
                    data = self._query_unify_query(
                        start_time=start_time,
                        end_time=end_time,
                        limit=limit,
                        slimit=slimit,
                        down_sample_range=down_sample_range,
                        time_alignment=kwargs.get("time_alignment", True),
                    )
            except Exception as e:
                exc = e
        else:
            try:
                labels["api"] = "query_api"
                with metrics.DATASOURCE_QUERY_TIME.labels(**labels).time():
                    data = self._query_data_source(
                        start_time=start_time,
                        end_time=end_time,
                        limit=limit,
                        slimit=slimit,
                    )
            except Exception as e:
                exc = e

        metrics.DATASOURCE_QUERY_COUNT.labels(**labels, status=metrics.StatusEnum.from_exc(exc), exception=exc).inc()
        metrics.report_all()

        if exc:
            raise exc

        return data

    def query_dimensions(self, dimension_field: Union[List, str], limit, start_time, end_time, *args, **kwargs):
        """
        查询维度
        """
        if len(self.data_sources) == 1:
            return self.data_sources[0].query_dimensions(
                dimension_field=dimension_field, limit=limit, start_time=start_time, end_time=end_time, *args, **kwargs
            )
        else:
            if isinstance(dimension_field, list):
                dimension_field = dimension_field[0]
            points = self.query_data(start_time, end_time)
            dimensions = set()
            for point in points:
                dimension = point.get(dimension_field)
                if dimension is None:
                    continue
                dimensions.add(dimension)
            return list(dimensions)
