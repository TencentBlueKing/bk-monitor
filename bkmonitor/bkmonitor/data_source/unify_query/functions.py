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
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from django.utils.translation import gettext_lazy as _lazy

from core.errors.bkmonitor.data_source import (
    FunctionNotFoundError,
    FunctionNotSupportedError,
)

_ParamsValue = Union[int, str, float]


@dataclass
class AggMethod:
    id: str
    method: str
    name: str
    description: str
    vargs_list: List[any] = None
    position: int = 0


@dataclass
class Params:
    """
    函数参数
    """

    id: str
    name: str
    description: str
    type: str
    default: Optional[_ParamsValue]
    shortlist: List[_ParamsValue]
    required: bool = True


@dataclass
class Function:
    """
    计算函数
    """

    id: str
    name: str
    description: str
    params: List[Params]
    position: int = 0
    time_aggregation: bool = False
    with_dimensions: bool = False
    support_expression: bool = False
    category: str = "default"
    ignore_unit: bool = False


@dataclass
class FunctionCategory:
    """
    函数分类
    """

    id: str
    name: str
    description: str


CpAggMethods: Dict[str, AggMethod] = dict(
    cp50=AggMethod(
        id="cp50",
        method="quantile",
        name=_lazy("50分位数"),
        description=_lazy("计算50分位数"),
        vargs_list=[0.5],
        position=1,
    ),
    cp90=AggMethod(
        id="cp90",
        method="quantile",
        name=_lazy("90分位数"),
        description=_lazy("计算90分位数"),
        vargs_list=[0.9],
        position=1,
    ),
    cp95=AggMethod(
        id="cp95",
        name=_lazy("95分位数"),
        method="quantile",
        description=_lazy("计算95分位数"),
        vargs_list=[0.95],
        position=1,
    ),
    cp99=AggMethod(
        id="cp99",
        method="quantile",
        name=_lazy("99分位数"),
        description=_lazy("计算99分位数"),
        vargs_list=[0.99],
        position=1,
    ),
)

AggMethods = dict(
    sum_without_time=AggMethod(
        id="sum_without_time",
        method="sum",
        name="SUM(PromQL)",
        description="",
    ),
    avg_without_time=AggMethod(
        id="avg_without_time",
        method="avg",
        name="AVG(PromQL)",
        description="",
    ),
    count_without_time=AggMethod(
        id="count_without_time",
        method="count",
        name="COUNT(PromQL)",
        description="",
    ),
    min_without_time=AggMethod(
        id="min_without_time",
        method="min",
        name="MIN(PromQL)",
        description="",
    ),
    max_without_time=AggMethod(
        id="max_without_time",
        method="max",
        name="MAX(PromQL)",
        description="",
    ),
)

FunctionCategories = [
    FunctionCategory(id="change", name=_lazy("指标变化"), description=_lazy("计算指标变化的相关函数")),
    FunctionCategory(id="arithmetic", name=_lazy("数学计算"), description=_lazy("一些数学计算函数")),
    FunctionCategory(id="sort", name=_lazy("排序"), description=_lazy("排序函数")),
    FunctionCategory(id="time_shift", name=_lazy("时间偏移"), description=_lazy("时间偏移函数")),
]

Functions = dict(
    # 时间聚合函数
    rate=Function(
        id="rate",
        name="rate",
        description=_lazy("每秒平均增长率（仅支持单调增长指标，遇到下降会从0开始计算）"),
        time_aggregation=True,
        params=[
            Params(
                id="window",
                name="window",
                default="2m",
                description=_lazy("时间窗口"),
                shortlist=["1m", "2m", "5m", "10m", "20m"],
                type="string",
            )
        ],
        category="change",
    ),
    irate=Function(
        id="irate",
        name="irate",
        description=_lazy("每秒平均增长率(按周期内最后两个点计算，仅支持单调增长指标，仅支持单调增长指标，遇到下降会从0开始计算）"),
        time_aggregation=True,
        params=[
            Params(
                id="window",
                name="window",
                default="2m",
                description=_lazy("时间窗口"),
                shortlist=["1m", "2m", "5m", "10m", "20m"],
                type="string",
            )
        ],
        category="change",
    ),
    increase=Function(
        id="increase",
        name="increase",
        description=_lazy("增加量(仅支持单调增长指标，仅支持单调增长指标，遇到下降会从0开始计算）"),
        time_aggregation=True,
        params=[
            Params(
                id="window",
                name="window",
                default="2m",
                description=_lazy("时间窗口"),
                shortlist=["1m", "2m", "5m", "10m", "20m"],
                type="string",
            )
        ],
        category="change",
    ),
    deriv=Function(
        id="deriv",
        name="deriv",
        description=_lazy("导数"),
        time_aggregation=True,
        params=[
            Params(
                id="window",
                name="window",
                default="2m",
                description=_lazy("时间窗口"),
                shortlist=["1m", "2m", "5m", "10m", "20m"],
                type="string",
            )
        ],
        category="change",
    ),
    delta=Function(
        id="delta",
        name="delta",
        description=_lazy("差值（按周期内第一个点和最后一个点计算）"),
        time_aggregation=True,
        params=[
            Params(
                id="window",
                name="window",
                default="2m",
                description=_lazy("时间窗口"),
                shortlist=["1m", "2m", "5m", "10m", "20m"],
                type="string",
            )
        ],
        category="change",
    ),
    idelta=Function(
        id="idelta",
        name="idelta",
        description=_lazy("差值（按周期内最后两个点）"),
        time_aggregation=True,
        params=[
            Params(
                id="window",
                name="window",
                default="2m",
                description=_lazy("时间窗口"),
                shortlist=["1m", "2m", "5m", "10m", "20m"],
                type="string",
            )
        ],
        category="change",
    ),
    changes=Function(
        id="changes",
        name="changes",
        description=_lazy("数值变化次数"),
        time_aggregation=True,
        params=[
            Params(
                id="window",
                name="window",
                default="2m",
                description=_lazy("时间窗口"),
                shortlist=["1m", "2m", "5m", "10m", "20m"],
                type="string",
            )
        ],
        category="change",
        ignore_unit=True,
    ),
    resets=Function(
        id="resets",
        name="resets",
        description=_lazy("计数器重置次数（单调增长指标，下降即为重置）"),
        time_aggregation=True,
        params=[
            Params(
                id="window",
                name="window",
                default="2m",
                description=_lazy("时间窗口"),
                shortlist=["1m", "2m", "5m", "10m", "20m"],
                type="string",
            )
        ],
        category="change",
        ignore_unit=True,
    ),
    # 维度聚合函数
    topk=Function(
        id="topk",
        name="topk",
        description=_lazy("最大的k个维度"),
        support_expression=True,
        position=1,
        category="sort",
        params=[Params(id="k", name="k", default=5, description=_lazy("最大的k个维度"), shortlist=[1, 3, 5, 10], type="int")],
    ),
    bottomk=Function(
        id="bottomk",
        name="bottomk",
        description=_lazy("最小的k个维度"),
        support_expression=True,
        position=1,
        category="sort",
        params=[Params(id="k", name="k", default=5, description=_lazy("最小的k个维度"), shortlist=[1, 3, 5, 10], type="int")],
    ),
    # 普通函数
    abs=Function(
        id="abs", name="abs", description=_lazy("绝对值"), support_expression=True, params=[], category="arithmetic"
    ),
    ceil=Function(
        id="ceil", name="ceil", description=_lazy("向上取整"), support_expression=True, params=[], category="arithmetic"
    ),
    floor=Function(
        id="floor", name="floor", description=_lazy("向下取整"), support_expression=True, params=[], category="arithmetic"
    ),
    round=Function(
        id="round", name="round", description=_lazy("四舍五入"), support_expression=True, params=[], category="arithmetic"
    ),
    ln=Function(
        id="ln",
        name="ln",
        description=_lazy("自然对数"),
        params=[],
        support_expression=True,
        category="arithmetic",
        ignore_unit=True,
    ),
    log2=Function(
        id="log2",
        name="log2",
        description=_lazy("以2为底的对数"),
        params=[],
        support_expression=True,
        category="arithmetic",
        ignore_unit=True,
    ),
    log10=Function(
        id="log10",
        name="log10",
        description=_lazy("以10为底的对数"),
        params=[],
        support_expression=True,
        category="arithmetic",
        ignore_unit=True,
    ),
    sgn=Function(
        id="sgn",
        name="sgn",
        description=_lazy("所有的样本值，正数转为1，负数转为0，零则为0"),
        support_expression=True,
        params=[],
        category="arithmetic",
        ignore_unit=True,
    ),
    sqrt=Function(
        id="sqrt",
        name="sqrt",
        description=_lazy("平方根"),
        support_expression=True,
        params=[],
        category="arithmetic",
        ignore_unit=True,
    ),
    histogram_quantile=Function(
        id="histogram_quantile",
        name="histogram_quantile",
        position=1,
        description=_lazy("直方图统计"),
        category="arithmetic",
        params=[
            Params(
                id="scalar",
                name="scalar",
                default=0.95,
                description=_lazy("分位数(0 ≤ φ ≤ 1)"),
                shortlist=[0.05, 0.1, 0.5, 0.9, 0.95],
                type="float",
            )
        ],
        ignore_unit=True,
    ),
    time_shift=Function(
        id="time_shift",
        name="time_shift",
        description=_lazy("时间偏移"),
        params=[
            Params(
                id="n",
                name="n",
                default="",
                description=_lazy("维度数量"),
                shortlist=["", "1h", "6h", "12h", "1d", "1w"],
                type="string",
            )
        ],
        category="time_shift",
    ),
)

GrafanaFunctions = dict(
    top=Function(
        id="top",
        name="top",
        description=_lazy("最大的N个维度，不可用于多指标计算"),
        params=[
            Params(
                id="n",
                name="n",
                default="5",
                description=_lazy("维度数量"),
                shortlist=["3", "5", "10", "20"],
                type="int",
            )
        ],
        category="sort",
    ),
    bottom=Function(
        id="bottom",
        name="bottom",
        description=_lazy("最小的N个维度，不可用于多指标计算"),
        params=[
            Params(
                id="n",
                name="n",
                default="5",
                description=_lazy("维度数量"),
                shortlist=["3", "5", "10", "20"],
                type="int",
            )
        ],
        category="sort",
    ),
)

SubQueryFunctions = dict(
    sum_over_time=Function(
        id="sum_over_time",
        name="sum_over_time",
        description=_lazy("求和"),
        time_aggregation=True,
        params=[
            Params(
                id="window",
                name="window",
                default="2m",
                description=_lazy("时间窗口"),
                shortlist=["1m", "2m", "5m", "10m", "20m"],
                type="string",
            ),
            # https://prometheus.io/blog/2019/01/28/subquery-support/
            # 一般和外层的 interval 保持一致
            Params(
                id="step",
                name="step",
                default="1m",
                description=_lazy("精度"),
                shortlist=["1m", "2m", "5m", "10m", "20m"],
                type="string",
            ),
        ],
        category="change",
    )
)


def add_expression_functions(expression, functions):
    new_expression = expression.lower()
    for func in functions:
        func_name = func["id"]
        func_params = func["params"]
        if func_name not in Functions and func_name not in GrafanaFunctions:
            raise FunctionNotFoundError(func_name=func_name)
        function = Functions.get(func_name, GrafanaFunctions.get(func_name))
        if not function.support_expression:
            raise FunctionNotSupportedError(func_name=func_name)
        if func_params:
            func_params = ",".join([str(params["value"]) for params in func_params])
            if function.position == 0:
                new_expression = f"{func_name}({new_expression},{func_params})"
            else:
                new_expression = f"{func_name}({func_params},{new_expression})"
        else:
            new_expression = f"{func_name}({new_expression})"
    return new_expression
