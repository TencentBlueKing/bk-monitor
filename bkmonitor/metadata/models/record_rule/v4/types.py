"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

from typing import Any, NotRequired, Required, TypedDict


class CheckQueryTsInput(TypedDict, total=False):
    """直接传给 unify-query /check/query/ts 的结构化 QueryTs 输入。

    这里仅描述 record rule 当前会关心的公共形态；更细的 query_list
    内部结构由 unify-query schema 负责校验。
    """

    query_list: list[dict[str, Any]]
    metric_merge: str
    start_time: int | str
    end_time: int | str
    step: str
    order_by: list[str]
    space_uid: str
    bk_tenant_id: str
    not_time_align: bool


class CheckQueryPromQLInput(TypedDict, total=False):
    """直接传给 unify-query /check/query/ts/promql 的 PromQL 输入。

    start/end 是 check 接口参数，不是 recording rule 的稳定语义字段；
    调用方缺省时后续可以按统一默认窗口补齐。
    """

    promql: str
    start: int | str
    end: int | str
    step: str
    space_uid: str
    bk_tenant_id: str
    bk_biz_ids: list[str]


class RecordRuleV4RecordInput(TypedDict):
    """Operator.declare/update_declaration 接收的单条预计算 record。

    必填字段由模型层继续校验：input_type、input_config、metric_name。
    record_key 仅用于显式维持记录身份；隐藏 key 的模式会按 input_config / metric_name 继承。
    """

    input_type: Required[str]
    input_config: Required[RecordRuleV4InputConfig]
    metric_name: Required[str]
    record_key: NotRequired[str]
    labels: NotRequired[list[dict[str, str]]]


class StructuredQueryMetricInput(TypedDict, total=False):
    """SaaS 结构化 query_config.metrics 的最小输入形态。"""

    field: str
    method: str
    alias: str


class StructuredQueryConditionInput(TypedDict, total=False):
    """SaaS 结构化 query_config.where 的最小输入形态。"""

    condition: str
    key: str
    method: str
    value: list[Any]


class StructuredQueryFunctionParamInput(TypedDict, total=False):
    """SaaS 查询函数参数。"""

    id: str
    value: Any


class StructuredQueryFunctionInput(TypedDict, total=False):
    """SaaS 查询函数输入。"""

    id: str
    params: list[StructuredQueryFunctionParamInput]


class StructuredQueryConfigInput(TypedDict, total=False):
    """SaaS 结构化 query_configs 的单个查询项。"""

    data_source_label: str
    data_type_label: str
    metrics: list[StructuredQueryMetricInput]
    table: str
    data_label: str
    group_by: list[str]
    where: list[StructuredQueryConditionInput]
    interval: int
    interval_unit: str
    time_field: str | None
    filter_dict: dict[str, Any]
    functions: list[StructuredQueryFunctionInput]


class StructuredQueryInput(TypedDict, total=False):
    """用户结构化查询输入，resolver 会将其转换成 /check/query/ts 参数。"""

    bk_biz_id: int
    query_configs: list[StructuredQueryConfigInput]
    expression: str
    functions: list[StructuredQueryFunctionInput]
    start_time: int | str
    end_time: int | str
    order_by: list[str]


RecordRuleV4QueryTsInputConfig = CheckQueryTsInput | StructuredQueryInput
RecordRuleV4InputConfig = RecordRuleV4QueryTsInputConfig | CheckQueryPromQLInput
