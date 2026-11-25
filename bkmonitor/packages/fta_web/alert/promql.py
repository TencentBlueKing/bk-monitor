"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import promql_parser as promql
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

WINDOW_FUNCTIONS = {
    "rate",
    "irate",
    "increase",
    "delta",
    "idelta",
    "changes",
    "resets",
    "sum_over_time",
    "avg_over_time",
    "min_over_time",
    "max_over_time",
    "count_over_time",
    "last_over_time",
}
GROUP_AGGREGATIONS = {"sum", "avg", "count", "min", "max", "group", "stddev", "stdvar"}


def can_push_down_alert_labels(expression: str, labels: dict) -> bool:
    """只有全部告警标签都能逐层穿过表达式到达同一个指标时，才向输入追加 matcher。"""
    if not labels or any(
        key.startswith("__") or key in {"targets", "rank", "cookies"} or value in (None, "", "undefined")
        for key, value in labels.items()
    ):
        return False
    try:
        node = promql.parse(expression)
    except ValueError:
        # 统一查询还支持标准 PromQL 以外的语法，交给原查询执行。
        return False

    while True:
        if isinstance(node, promql.VectorSelector):
            return bool(node.name) and not node.matchers.or_matchers
        if isinstance(node, promql.ParenExpr):
            node = node.expr
        elif isinstance(node, promql.AggregateExpr):
            operator = str(node.op)
            if operator in {"topk", "bottomk"}:
                if not isinstance(node.param, promql.NumberLiteral):
                    return False
            elif operator not in GROUP_AGGREGATIONS:
                return False

            grouping = node.modifier
            if grouping is None:
                return False
            if grouping.type == promql.AggModifierType.By:
                if not labels.keys() <= set(grouping.labels):
                    return False
            elif not labels.keys().isdisjoint(grouping.labels):
                return False
            node = node.expr
        elif isinstance(node, promql.Call):
            args = node.args
            if node.func.name in WINDOW_FUNCTIONS and isinstance(args[0], promql.MatrixSelector):
                node = args[0].vector_selector
            elif (
                node.func.name in {"label_replace", "label_join"}
                and isinstance(args[1], promql.StringLiteral)
                and args[1].val not in labels
            ):
                node = args[0]
            else:
                return False
        elif isinstance(node, promql.BinaryExpr) and isinstance(node.lhs, promql.NumberLiteral):
            node = node.rhs
        elif isinstance(node, promql.BinaryExpr) and isinstance(node.rhs, promql.NumberLiteral):
            node = node.lhs
        else:
            return False


def prepare_alert_labels(configs: list[dict], data: dict, tags: list, fallback_fields: list) -> tuple[dict, bool]:
    """区分检测维度与请求原有的查询条件，兼容详情页回传的旧面板。"""
    fields = data.get("dimension_fields")
    keys = set(fallback_fields if fields is None else fields)
    keys = {key for key in keys if not key.startswith("bk_task_index_") and key != "__NO_DATA_DIMENSION__"}
    dimensions = data.get("dimensions", {})
    values = {tag["key"]: tag["value"] for tag in tags if tag["key"] in keys}
    values.update({key: dimensions[key] for key in keys & dimensions.keys() if dimensions[key] is not None})
    labels = {key: str(value) for key, value in values.items() if value is not None}
    complete = fields is not None and labels.keys() == keys and "__NO_DATA_DIMENSION__" not in fields

    push_down = len(configs) == 1 and can_push_down_alert_labels(configs[0]["promql"], labels)
    for config in configs:
        filters = config.setdefault("filter_dict", {})
        # 旧面板可能将原始 None 作为输入条件。它没有可用于匹配的标签值。
        for key in keys & dimensions.keys():
            if dimensions[key] is None and filters.get(key) is None:
                filters.pop(key, None)
        for key, value in labels.items():
            if push_down:
                filters.setdefault(key, value)
            elif key in filters and str(filters[key]) == value:
                del filters[key]
    return labels, complete


def select_alert_series(series: list[dict], labels: dict, complete: bool) -> list[dict]:
    """按原始标签选曲线；当前和时间对比具有相同身份，保留各自的采样点。"""
    expected = {key: value for key, value in labels.items() if value != ""}
    selected = []
    identity = None
    for row in series:
        dimensions = {
            key: str(value)
            for key, value in row["dimensions"].items()
            if value not in (None, "") and not key.startswith("bk_task_index_")
        }
        if complete:
            matches = dimensions == expected
        else:
            matches = all(dimensions.get(key, "") == value for key, value in labels.items())
        if matches:
            if identity is not None and identity != dimensions:
                raise ValidationError(_("告警记录中的维度无法唯一匹配一条 PromQL 序列"))
            identity = dimensions
            selected.append(row)
    return selected
