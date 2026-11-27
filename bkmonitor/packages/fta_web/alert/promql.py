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


def _label_name(arg) -> str | None:
    while isinstance(arg, promql.ParenExpr):
        arg = arg.expr
    return arg.val if isinstance(arg, promql.StringLiteral) else None


def can_push_down_alert_labels(expression: str, labels: dict) -> bool:
    """默认允许前过滤，仅拦截会改变告警维度或其计算范围的操作。"""
    if not labels or any(
        key.startswith("__") or key in {"targets", "rank", "cookies"} or value in (None, "", "undefined")
        for key, value in labels.items()
    ):
        return False
    try:
        expr = promql.parse(expression)
    except ValueError:
        # 统一查询支持扩展语法，本地无法解析时保留原查询行为。
        return True

    def allows_filter(node) -> bool:
        if isinstance(node, promql.AggregateExpr):
            if str(node.op) == "count_values":
                return _label_name(node.param) not in labels
            if str(node.op) in {"topk", "bottomk"}:
                # 只允许过滤整个排名分组，组内序列必须一起参与每个时刻的排名。
                grouping = node.modifier
                if grouping is None:
                    return False
                if grouping.type == promql.AggModifierType.By:
                    return labels.keys() <= set(grouping.labels)
                return labels.keys().isdisjoint(grouping.labels)

        if isinstance(node, promql.BinaryExpr) and node.modifier:
            modifier = node.modifier
            # group_left / group_right 可以从一侧复制标签，不能拿复制出的标签过滤另一侧。
            if not labels.keys().isdisjoint(modifier.group_labels or []):
                return False
            matching = modifier.matching
            if matching:
                if matching.type == promql.LabelModifierType.Include:
                    return labels.keys() <= set(matching.labels)
                return labels.keys().isdisjoint(matching.labels)

        if isinstance(node, promql.Call):
            name = node.func.name
            if name in {"label_replace", "label_join"}:
                return _label_name(node.args[1]) not in labels
            if name in {"absent", "absent_over_time", "info"}:
                return False
            if name == "scalar":
                # 动态标量依赖整个输入向量，提前缩小它会改变其他序列使用的值。
                return promql.walk(node.args[0], lambda arg: not isinstance(arg, promql.VectorSelector))
            if name in {"histogram_quantile", "histogram_fraction"} and "le" in labels:
                return False
        return True

    return promql.walk(expr, allows_filter)


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
