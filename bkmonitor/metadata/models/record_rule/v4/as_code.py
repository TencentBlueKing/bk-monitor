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

# RecordRuleV4 模块内 AsCode 结构转换。
#
# 本文件刻意只做配置形态转换：Prometheus 风格 YAML <-> Operator 声明数据。
# 这里不访问数据库、不调用 unify-query，也不创建 output/Flow，方便后续
# bkmonitor/as_code 接入时把解析和执行解耦。

import copy
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, TypedDict

from bkmonitor.as_code.utils import (
    create_conditions_expression,
    create_function_expression,
    get_metric_id,
    parse_conditions,
    parse_function,
    parse_metric_id,
)
from metadata.models.record_rule.constants import (
    RECORD_RULE_V4_INTERVAL_CHOICES,
    RecordRuleV4DesiredStatus,
    RecordRuleV4InputType,
)
from metadata.models.record_rule.v4.models import RecordRuleV4, normalize_labels
from metadata.models.record_rule.v4.types import RecordRuleV4RecordInput

FORBIDDEN_CONTEXT_FIELDS = {"bk_biz_id", "bk_tenant_id", "space_uid", "bk_biz_ids"}
UNSUPPORTED_PROMETHEUS_FIELDS = {"alert", "for", "annotations", "limit", "query_offset"}
DEFAULT_GROUP_INTERVAL = "1min"
DEFAULT_QUERY_EXPRESSION = "a"
DEFAULT_QUERY_INTERVAL = 60

GROUP_ALLOWED_FIELDS = {"name", "interval", "labels", "bkmonitor", "rules"}
BKMONITOR_ALLOWED_FIELDS = {"description", "data_label", "auto_refresh", "desired_status"}
RULE_ALLOWED_FIELDS = {"record", "expr", "query", "labels"}
QUERY_ALLOWED_FIELDS = {"data_source", "data_type", "expression", "functions", "query_configs", "order_by"}
QUERY_CONFIG_ALLOWED_FIELDS = {
    "metric",
    "method",
    "interval",
    "group_by",
    "where",
    "functions",
    "alias",
    "time_field",
    "unit",
    "query_string",
}


class RecordRuleV4DeclarationData(TypedDict):
    name: str
    description: str
    data_label: str
    interval: str
    labels: list[dict[str, Any]]
    records: list[RecordRuleV4RecordInput]
    desired_status: str
    auto_refresh: bool
    raw_config: dict[str, Any]
    source_path: str


class RecordRuleV4AsCodeQueryConfig(TypedDict, total=False):
    metric: str
    method: str
    interval: int
    group_by: list[str]
    where: str
    functions: list[str]
    alias: str
    time_field: str
    unit: str
    query_string: str


class RecordRuleV4AsCodeQuery(TypedDict, total=False):
    data_source: str
    data_type: str
    expression: str
    functions: list[str]
    query_configs: list[RecordRuleV4AsCodeQueryConfig]
    order_by: list[str]


class RecordRuleV4AsCodeRule(TypedDict, total=False):
    record: str
    expr: str
    query: RecordRuleV4AsCodeQuery
    labels: dict[str, Any]


@dataclass(frozen=True)
class RecordRuleV4AsCodeExportEntry:
    filename: str
    content: dict[str, Any]


def parse_config(config: dict, *, source_path: str = "") -> list[RecordRuleV4DeclarationData]:
    """解析一个 RecordRuleV4 AsCode 文件内容，返回后续 operator 可直接声明的数据。

    source_path 只用于错误定位，调用方可以传入 AsCode 文件路径；解析结果本身
    不携带业务上下文，业务 / 租户 / 空间信息由外层导入入口补齐。
    """

    if not isinstance(config, dict):
        raise ValueError(_format_error(source_path, "config must be dict"))
    _reject_forbidden_fields(config, source_path=source_path)
    groups = config.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError(_format_error(source_path, "groups must be non-empty list"))

    return [
        parse_group(group, source_path=source_path, group_index=group_index) for group_index, group in enumerate(groups)
    ]


def parse_group(group: dict, *, source_path: str = "", group_index: int = 0) -> RecordRuleV4DeclarationData:
    """解析单个 Prometheus recording rule group + bkmonitor 扩展配置。

    返回的 raw_config 是规范化后的 group 快照，后续导出会优先回放它，
    以尽量保留用户导入时看到的 Prometheus 风格结构。
    """

    group_path = _join_path(source_path, f"groups[{group_index}]")
    if not isinstance(group, dict):
        raise ValueError(_format_error(group_path, "group must be dict"))
    _reject_forbidden_fields(group, source_path=group_path)
    _reject_unsupported_fields(group, allowed_fields=GROUP_ALLOWED_FIELDS, source_path=group_path)

    name = _require_text(group.get("name"), field_name="name", source_path=group_path)
    interval = normalize_interval(group.get("interval") or DEFAULT_GROUP_INTERVAL, source_path=group_path)
    labels = parse_labels(group.get("labels"), source_path=_join_path(group_path, "labels"))

    bkmonitor = group.get("bkmonitor") or {}
    if not isinstance(bkmonitor, dict):
        raise ValueError(_format_error(_join_path(group_path, "bkmonitor"), "bkmonitor must be dict"))
    _reject_unsupported_fields(bkmonitor, allowed_fields=BKMONITOR_ALLOWED_FIELDS, source_path=group_path)
    description = str(bkmonitor.get("description") or "")
    data_label = str(bkmonitor.get("data_label") or "")
    desired_status = str(bkmonitor.get("desired_status") or RecordRuleV4DesiredStatus.RUNNING.value)
    allowed_desired_statuses = {RecordRuleV4DesiredStatus.RUNNING.value, RecordRuleV4DesiredStatus.STOPPED.value}
    if desired_status not in allowed_desired_statuses:
        raise ValueError(_format_error(group_path, f"unsupported desired_status: {desired_status}"))
    auto_refresh = bool(bkmonitor.get("auto_refresh", True))

    rule_items = group.get("rules")
    if not isinstance(rule_items, list) or not rule_items:
        raise ValueError(_format_error(_join_path(group_path, "rules"), "rules must be non-empty list"))

    records: list[RecordRuleV4RecordInput] = []
    normalized_rules: list[RecordRuleV4AsCodeRule] = []
    for rule_index, rule_item in enumerate(rule_items):
        record, raw_rule = parse_rule(rule_item, source_path=_join_path(group_path, f"rules[{rule_index}]"))
        records.append(record)
        normalized_rules.append(raw_rule)

    raw_config = {
        "name": name,
        "interval": interval,
        "labels": labels_to_mapping(labels),
        "bkmonitor": {
            "description": description,
            "data_label": data_label,
            "auto_refresh": auto_refresh,
            "desired_status": desired_status,
        },
        "rules": normalized_rules,
    }
    return {
        "name": name,
        "description": description,
        "data_label": data_label,
        "interval": interval,
        "labels": labels,
        "records": records,
        "desired_status": desired_status,
        "auto_refresh": auto_refresh,
        "raw_config": raw_config,
        "source_path": source_path,
    }


def parse_rule(rule: dict, *, source_path: str = "") -> tuple[RecordRuleV4RecordInput, RecordRuleV4AsCodeRule]:
    """解析单条 recording rule。"""

    if not isinstance(rule, dict):
        raise ValueError(_format_error(source_path, "rule must be dict"))
    _reject_forbidden_fields(rule, source_path=source_path)
    _reject_unsupported_fields(rule, allowed_fields=RULE_ALLOWED_FIELDS, source_path=source_path)

    metric_name = _require_text(rule.get("record"), field_name="record", source_path=source_path)
    has_expr = "expr" in rule and rule.get("expr") not in (None, "")
    has_query = "query" in rule and rule.get("query") not in (None, "")
    if has_expr == has_query:
        raise ValueError(_format_error(source_path, "exactly one of expr or query is required"))

    labels = parse_labels(rule.get("labels"), source_path=_join_path(source_path, "labels"))
    if has_expr:
        expr = _require_text(rule.get("expr"), field_name="expr", source_path=source_path)
        record: RecordRuleV4RecordInput = {
            "input_type": RecordRuleV4InputType.PROMQL.value,
            "input_config": {"promql": expr},
            "metric_name": metric_name,
            "labels": labels,
        }
        raw_rule: RecordRuleV4AsCodeRule = {"record": metric_name, "expr": expr}
    else:
        query_input, raw_query = parse_query(rule.get("query"), source_path=_join_path(source_path, "query"))
        record = {
            "input_type": RecordRuleV4InputType.QUERY_TS.value,
            "input_config": query_input,
            "metric_name": metric_name,
            "labels": labels,
        }
        raw_rule = {"record": metric_name, "query": raw_query}

    if labels:
        raw_rule["labels"] = labels_to_mapping(labels)
    return record, raw_rule


def parse_query(query: Any, *, source_path: str = "") -> tuple[dict[str, Any], RecordRuleV4AsCodeQuery]:
    """把策略 AsCode 风格的简化 query_configs 转成 resolver 已支持的 structured query input。

    AsCode 侧暴露 metric/method/where/functions 等短字段；resolver 仍消费
    monitor 查询接口已有的 query_configs 结构，因此这里是唯一的字段展开层。
    """

    if not isinstance(query, dict):
        raise ValueError(_format_error(source_path, "query must be dict"))
    _reject_forbidden_fields(query, source_path=source_path)
    _reject_unsupported_fields(query, allowed_fields=QUERY_ALLOWED_FIELDS, source_path=source_path)

    data_source = _require_text(query.get("data_source"), field_name="data_source", source_path=source_path)
    data_type = _require_text(query.get("data_type"), field_name="data_type", source_path=source_path)
    expression = str(query.get("expression") or DEFAULT_QUERY_EXPRESSION)
    query_configs = query.get("query_configs")
    if not isinstance(query_configs, list) or not query_configs:
        raise ValueError(
            _format_error(_join_path(source_path, "query_configs"), "query_configs must be non-empty list")
        )

    structured_configs: list[dict[str, Any]] = []
    normalized_configs: list[RecordRuleV4AsCodeQueryConfig] = []
    for index, query_config in enumerate(query_configs):
        structured_config, raw_query_config = parse_query_config(
            query_config,
            data_source=data_source,
            data_type=data_type,
            source_path=_join_path(source_path, f"query_configs[{index}]"),
        )
        structured_configs.append(structured_config)
        normalized_configs.append(raw_query_config)

    functions = parse_functions(query.get("functions") or [], source_path=_join_path(source_path, "functions"))
    raw_functions = dump_functions(functions)

    structured_input: dict[str, Any] = {
        "query_configs": structured_configs,
        "expression": expression,
        "functions": functions,
    }
    raw_query: RecordRuleV4AsCodeQuery = {
        "data_source": data_source,
        "data_type": data_type,
        "expression": expression,
        "query_configs": normalized_configs,
    }
    if raw_functions:
        raw_query["functions"] = raw_functions
    if query.get("order_by"):
        order_by = _ensure_str_list(query.get("order_by"), field_name="order_by", source_path=source_path)
        structured_input["order_by"] = order_by
        raw_query["order_by"] = order_by
    return structured_input, raw_query


def parse_query_config(
    query_config: Any,
    *,
    data_source: str,
    data_type: str,
    source_path: str = "",
) -> tuple[dict[str, Any], RecordRuleV4AsCodeQueryConfig]:
    """解析简化 query_configs 单项。"""

    if not isinstance(query_config, dict):
        raise ValueError(_format_error(source_path, "query_config must be dict"))
    _reject_forbidden_fields(query_config, source_path=source_path)
    _reject_unsupported_fields(query_config, allowed_fields=QUERY_CONFIG_ALLOWED_FIELDS, source_path=source_path)

    metric = _require_text(query_config.get("metric"), field_name="metric", source_path=source_path)
    metric_parts = parse_metric_id(data_source, data_type, metric)
    metric_field = str(metric_parts.get("metric_field") or "")
    if not metric_field:
        raise ValueError(_format_error(source_path, "query_config metric must include metric field"))

    method = str(query_config.get("method") or "").upper()
    alias = str(query_config.get("alias") or "a")
    interval = _normalize_int(query_config.get("interval", DEFAULT_QUERY_INTERVAL), "interval", source_path=source_path)
    group_by = _ensure_str_list(query_config.get("group_by") or [], field_name="group_by", source_path=source_path)
    where = parse_where(query_config.get("where") or "", source_path=_join_path(source_path, "where"))
    functions = parse_functions(query_config.get("functions") or [], source_path=_join_path(source_path, "functions"))

    # structured_config 是执行真值源，字段名保持 resolver / unify-query 已支持的结构。
    # raw_query_config 是导出回放形态，尽量保持 AsCode 侧的短字段。
    structured_config: dict[str, Any] = {
        "data_source_label": data_source,
        "data_type_label": data_type,
        "metrics": [{"field": metric_field, "method": method, "alias": alias}],
        "table": str(metric_parts.get("result_table_id") or ""),
        "data_label": str(metric_parts.get("data_label") or ""),
        "index_set_id": metric_parts.get("index_set_id"),
        "group_by": group_by,
        "where": where,
        "interval": interval,
        "interval_unit": "s",
        "time_field": query_config.get("time_field"),
        "filter_dict": {},
        "functions": functions,
    }
    if query_config.get("unit"):
        structured_config["unit"] = str(query_config["unit"])
    if query_config.get("query_string"):
        structured_config["query_string"] = str(query_config["query_string"])

    raw_query_config: RecordRuleV4AsCodeQueryConfig = {
        "metric": metric,
        "method": method.lower(),
        "interval": interval,
        "group_by": group_by,
        "alias": alias,
    }
    if where:
        raw_query_config["where"] = create_conditions_expression(where)
    if functions:
        raw_query_config["functions"] = dump_functions(functions)
    if query_config.get("time_field"):
        raw_query_config["time_field"] = str(query_config["time_field"])
    if query_config.get("unit"):
        raw_query_config["unit"] = str(query_config["unit"])
    if query_config.get("query_string"):
        raw_query_config["query_string"] = str(query_config["query_string"])
    return structured_config, raw_query_config


def dump_rule(rule: RecordRuleV4) -> dict[str, Any]:
    """导出单个 rule 对应的 group 配置，优先复用 spec.raw_config 中的原始表达形态。

    raw_config 只影响导出展示，不参与当前声明是否变更的判断；运行时状态
    始终以主表 metadata 和 current_spec 为准，因此这里会覆盖 name/labels 等
    可能被后续 update_declaration 修改过的字段。
    """

    spec = rule.current_spec
    if spec and isinstance(spec.raw_config, dict) and spec.raw_config.get("rules"):
        group_config = copy.deepcopy(spec.raw_config)
    else:
        group_config = dump_rule_from_spec(rule)

    if spec:
        group_config["interval"] = spec.interval
        group_config["labels"] = labels_to_mapping(spec.labels)
    group_config["name"] = rule.name
    group_config["bkmonitor"] = {
        "description": rule.description,
        "data_label": rule.data_label,
        "auto_refresh": rule.auto_refresh,
        "desired_status": rule.desired_status,
    }
    return group_config


def dump_rules(rules: Iterable[RecordRuleV4]) -> dict[str, Any]:
    """按 Prometheus recording rule 文件结构导出多个 group。"""

    return {"groups": [dump_rule(rule) for rule in rules]}


def build_export_entries(
    rules: Iterable[RecordRuleV4],
    *,
    lock_filename: bool = False,
) -> list[RecordRuleV4AsCodeExportEntry]:
    """构造后续 AsCode 模块可直接写入文件或压缩包的导出条目。"""

    entries: list[RecordRuleV4AsCodeExportEntry] = []
    used_filenames: set[str] = set()
    for rule in rules:
        filename_base = rule.table_id.split(".", 1)[0] if lock_filename else rule.name
        filename = f"{_safe_filename(filename_base or str(rule.pk))}.yaml"
        if filename in used_filenames:
            filename = f"{_safe_filename(filename_base or str(rule.pk))}-{rule.pk}.yaml"
        used_filenames.add(filename)
        entries.append(RecordRuleV4AsCodeExportEntry(filename=filename, content={"groups": [dump_rule(rule)]}))
    return entries


def dump_rule_from_spec(rule: RecordRuleV4) -> dict[str, Any]:
    spec = rule.current_spec
    if spec is None:
        return {
            "name": rule.name,
            "interval": DEFAULT_GROUP_INTERVAL,
            "labels": {},
            "bkmonitor": {},
            "rules": [],
        }

    rules: list[dict[str, Any]] = []
    for record in spec.records.order_by("source_index", "id"):
        raw_rule: dict[str, Any] = {"record": record.metric_name}
        if record.input_type == RecordRuleV4InputType.PROMQL.value:
            raw_rule["expr"] = record.input_config.get("promql") or ""
        elif record.input_type == RecordRuleV4InputType.QUERY_TS.value:
            raw_rule["query"] = dump_query(record.input_config)
        else:
            raw_rule["input_type"] = record.input_type
            raw_rule["input_config"] = copy.deepcopy(record.input_config)

        labels = labels_to_mapping(record.labels)
        if labels:
            raw_rule["labels"] = labels
        rules.append(raw_rule)

    return {
        "name": rule.name,
        "interval": spec.interval,
        "labels": labels_to_mapping(spec.labels),
        "rules": rules,
    }


def dump_query(input_config: Mapping[str, Any]) -> dict[str, Any]:
    if not input_config.get("query_configs"):
        return copy.deepcopy(dict(input_config))

    query_configs = list(input_config.get("query_configs") or [])
    first_config = query_configs[0] if query_configs else {}
    data_source = str(first_config.get("data_source_label") or "")
    data_type = str(first_config.get("data_type_label") or "")
    query: dict[str, Any] = {
        "data_source": data_source,
        "data_type": data_type,
        "expression": input_config.get("expression") or DEFAULT_QUERY_EXPRESSION,
        "query_configs": [],
    }
    raw_functions = dump_functions(input_config.get("functions") or [])
    if raw_functions:
        query["functions"] = raw_functions
    if input_config.get("order_by"):
        query["order_by"] = copy.deepcopy(input_config["order_by"])

    for query_config in query_configs:
        query["query_configs"].append(dump_query_config(query_config, data_source=data_source, data_type=data_type))
    return query


def dump_query_config(query_config: Mapping[str, Any], *, data_source: str, data_type: str) -> dict[str, Any]:
    metric = ""
    metrics = query_config.get("metrics") or []
    first_metric = metrics[0] if metrics else {}
    if first_metric:
        metric_payload = {
            "result_table_id": query_config.get("table") or "",
            "metric_field": first_metric.get("field") or "",
            "data_label": query_config.get("data_label") or "",
            "index_set_id": query_config.get("index_set_id"),
        }
        metric = get_metric_id(data_source, data_type, metric_payload)

    raw_query_config: dict[str, Any] = {"metric": metric}
    method = str(first_metric.get("method") or "")
    if method:
        raw_query_config["method"] = method.lower()
    if query_config.get("interval") not in (None, ""):
        raw_query_config["interval"] = int(query_config["interval"])
    if query_config.get("group_by"):
        raw_query_config["group_by"] = copy.deepcopy(query_config["group_by"])
    if query_config.get("where"):
        raw_query_config["where"] = create_conditions_expression(list(query_config["where"]))
    if query_config.get("functions"):
        raw_query_config["functions"] = dump_functions(query_config["functions"])
    if first_metric.get("alias"):
        raw_query_config["alias"] = str(first_metric["alias"])
    if query_config.get("time_field"):
        raw_query_config["time_field"] = str(query_config["time_field"])
    if query_config.get("unit"):
        raw_query_config["unit"] = str(query_config["unit"])
    if query_config.get("query_string"):
        raw_query_config["query_string"] = str(query_config["query_string"])
    return raw_query_config


def normalize_interval(value: Any, *, source_path: str = "") -> str:
    text = str(value or "").strip()
    match = re.fullmatch(r"(\d+)\s*([a-zA-Z]+)", text)
    if not match:
        raise ValueError(_format_error(source_path, f"unsupported interval: {text}"))
    amount = int(match.group(1))
    unit = match.group(2).lower()
    if unit in {"s", "sec", "secs", "second", "seconds"}:
        if amount % 60 != 0:
            raise ValueError(_format_error(source_path, f"unsupported interval: {text}"))
        normalized = f"{amount // 60}min"
    elif unit in {"m", "min", "mins", "minute", "minutes"}:
        normalized = f"{amount}min"
    else:
        raise ValueError(_format_error(source_path, f"unsupported interval: {text}"))
    if normalized not in RECORD_RULE_V4_INTERVAL_CHOICES:
        raise ValueError(_format_error(source_path, f"unsupported interval: {text}"))
    return normalized


def parse_labels(value: Any, *, source_path: str = "") -> list[dict[str, Any]]:
    if value in (None, ""):
        return []
    if isinstance(value, dict):
        return normalize_labels([{str(key): label_value} for key, label_value in value.items()])
    if isinstance(value, list):
        return normalize_labels(copy.deepcopy(value))
    raise ValueError(_format_error(source_path, "labels must be dict or list[dict]"))


def labels_to_mapping(labels: list[dict[str, Any]] | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for label in normalize_labels(labels):
        for key, value in label.items():
            result[str(key)] = value
    return result


def parse_where(value: Any, *, source_path: str = "") -> list[dict[str, Any]]:
    if not value:
        return []
    if isinstance(value, str):
        return parse_conditions(value)
    if isinstance(value, list):
        return copy.deepcopy(value)
    raise ValueError(_format_error(source_path, "where must be string or list"))


def parse_functions(value: Any, *, source_path: str = "") -> list[dict[str, Any]]:
    if not value:
        return []
    if not isinstance(value, list):
        raise ValueError(_format_error(source_path, "functions must be list"))

    functions: list[dict[str, Any]] = []
    for index, function in enumerate(value):
        if isinstance(function, str):
            functions.append(parse_function(function))
        elif isinstance(function, dict):
            functions.append(copy.deepcopy(function))
        else:
            raise ValueError(_format_error(_join_path(source_path, f"[{index}]"), "function must be string or dict"))
    return functions


def dump_functions(functions: list[dict[str, Any]]) -> list[str]:
    expressions: list[str] = []
    for function in functions:
        expression = create_function_expression(function)
        if expression is not None:
            expressions.append(expression)
    return expressions


def _require_text(value: Any, *, field_name: str, source_path: str = "") -> str:
    if value in (None, ""):
        raise ValueError(_format_error(source_path, f"{field_name} is required"))
    text = str(value).strip()
    if not text:
        raise ValueError(_format_error(source_path, f"{field_name} is required"))
    return text


def _normalize_int(value: Any, field_name: str, *, source_path: str = "") -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(_format_error(source_path, f"{field_name} must be int")) from error


def _ensure_str_list(value: Any, *, field_name: str, source_path: str = "") -> list[str]:
    if not isinstance(value, list):
        raise ValueError(_format_error(_join_path(source_path, field_name), f"{field_name} must be list"))
    return [str(item) for item in value]


def _reject_forbidden_fields(value: Any, *, source_path: str = "") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            path = _join_path(source_path, key_text)
            if key_text in FORBIDDEN_CONTEXT_FIELDS:
                raise ValueError(_format_error(path, f"{key_text} is not allowed in RecordRuleV4 AsCode config"))
            if key_text in UNSUPPORTED_PROMETHEUS_FIELDS:
                raise ValueError(_format_error(path, f"{key_text} is not supported by RecordRuleV4 AsCode"))
            _reject_forbidden_fields(item, source_path=path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_forbidden_fields(item, source_path=_join_path(source_path, f"[{index}]"))


def _reject_unsupported_fields(value: Mapping[str, Any], *, allowed_fields: set[str], source_path: str = "") -> None:
    unknown_fields = sorted(set(map(str, value.keys())) - allowed_fields)
    if unknown_fields:
        raise ValueError(_format_error(source_path, f"unsupported fields: {', '.join(unknown_fields)}"))


def _join_path(source_path: str, field: str) -> str:
    if not source_path:
        return field
    if field.startswith("["):
        return f"{source_path}{field}"
    return f"{source_path}.{field}"


def _format_error(source_path: str, message: str) -> str:
    return f"{source_path}: {message}" if source_path else message


def _safe_filename(value: str) -> str:
    filename = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value or "").strip()).strip("._")
    return filename or "record_rule_v4"


__all__ = [
    "RecordRuleV4AsCodeExportEntry",
    "RecordRuleV4DeclarationData",
    "build_export_entries",
    "dump_rule",
    "dump_rules",
    "parse_config",
    "parse_group",
]
