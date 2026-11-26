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

from bkmonitor.documents import AlertDocument
from bkmonitor.models import NO_DATA_TAG_DIMENSION
from constants.data_source import DataSourceLabel

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
        # 统一查询支持扩展语法，本地无法判定时不展示告警图。
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


def get_alert_graph_filter(alert: AlertDocument) -> dict[str, str] | None:
    """返回 PromQL 的前置过滤条件。None 表示隐藏图表，其他数据源沿用原查询。"""
    items = (alert.strategy or {}).get("items", [])
    configs = items[0]["query_configs"] if items else []
    if not any(config["data_source_label"] == DataSourceLabel.PROMETHEUS for config in configs):
        return {}
    if len(configs) != 1:
        return None

    event = alert.event.to_dict()
    data = event.get("extra_info", {}).get("origin_alarm", {}).get("data", {})
    fields = data.get("dimension_fields")
    if not fields or NO_DATA_TAG_DIMENSION in fields:
        return None
    values = {tag["key"]: tag["value"] for tag in event.get("tags", [])}
    values.update({key: value for key, value in data.get("dimensions", {}).items() if value is not None})
    labels = {key: values.get(key) for key in fields if not key.startswith("bk_task_index_")}
    if not can_push_down_alert_labels(configs[0]["promql"], labels):
        return None
    return {key: str(value) for key, value in labels.items()}
