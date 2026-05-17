"""
插件新旧格式兼容转换工具。

提供 旧格式 dict ↔ bk-monitor-base 领域模型 之间的双向转换：

* ``convert_metric_json_to_legacy``   新 metric_json → 旧 metric_json
* ``convert_metric_json_to_base``     旧 metric_json → 新 metric_json
* ``convert_plugin_type_to_legacy``   bk-monitor-base 小写类型 → 旧 PluginType 常量
"""

from __future__ import annotations

from typing import Any

# bk-monitor-base 全小写类型 → 旧 PluginType 混合大小写常量值的映射。
# 两侧值域不完全对称（如 "built_in" vs "Built-In"），不能简单 `.lower()` / `.title()` 互转。
_BASE_TYPE_TO_LEGACY_TYPE: dict[str, str] = {
    "exporter": "Exporter",
    "script": "Script",
    "jmx": "JMX",
    "datadog": "DataDog",
    "pushgateway": "Pushgateway",
    "built_in": "Built-In",
    "log": "Log",
    "process": "Process",
    "snmp_trap": "SNMP_Trap",
    "snmp": "SNMP",
    "k8s": "K8S",
}
_LEGACY_TYPE_TO_BASE_TYPE: dict[str, str] = {v: k for k, v in _BASE_TYPE_TO_LEGACY_TYPE.items()}


def convert_plugin_type_to_legacy(base_type: str) -> str:
    """将 bk-monitor-base 的小写插件类型转换为旧 ``PluginType`` 常量格式。

    如果传入的值已经是旧格式（存在于 ``_LEGACY_TYPE_TO_BASE_TYPE`` 的键中），
    则直接原样返回，实现幂等性。

    Args:
        base_type: bk-monitor-base 侧的插件类型字符串，如 ``"exporter"``。

    Returns:
        旧 ``PluginType`` 常量值，如 ``"Exporter"``。未知类型原样返回。
    """
    if base_type in _LEGACY_TYPE_TO_BASE_TYPE:
        return base_type
    return _BASE_TYPE_TO_LEGACY_TYPE.get(base_type, base_type)


def _dump_payload(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def _normalize_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def convert_metric_json_to_base(metric_json: list[dict[str, Any]]) -> list[Any]:
    """将旧接口的 metric_json 转换为 bk-monitor-base 的 MetricPluginMetricGroup 列表。

    旧接口使用 ``rule_list`` 作为分组规则的字段名，而 bk-monitor-base 侧使用
    ``rules``；本函数同时兼容两种字段名，以确保无论数据来源于旧导出包还是新 API
    返回值，都能正确完成转换。

    Args:
        metric_json: 旧格式的指标组字典列表，每个元素至少包含 ``table_name``
            和 ``fields`` 两个键。

    Returns:
        ``MetricPluginMetricGroup`` 实例列表，可直接用于 ``CreatePluginParams.metrics``
        等 bk-monitor-base 领域参数。
    """
    from bk_monitor_base.metric_plugin import MetricPluginMetricField, MetricPluginMetricGroup

    groups: list[MetricPluginMetricGroup] = []
    for mg in metric_json:
        groups.append(
            MetricPluginMetricGroup(
                table_name=mg["table_name"],
                table_desc=mg.get("table_desc", ""),
                rules=mg.get("rule_list") or mg.get("rules") or [],
                fields=[
                    MetricPluginMetricField(
                        name=f["name"],
                        type=f["type"],
                        description=f.get("description", ""),
                        monitor_type=f["monitor_type"],
                        unit=f.get("unit", "none"),
                        is_active=f.get("is_active", True),
                        source_name=f.get("source_name", ""),
                    )
                    for f in mg.get("fields", [])
                ],
            )
        )
    return groups


def convert_metric_json_to_legacy(metric_json: list[Any]) -> list[dict[str, Any]]:
    """
    将新的 metric_json 结构转换成旧接口结构。

    当前兼容规则：
    1. `rules` 统一转成 `rule_list`
    2. `dimensions` 默认补空数组
    3. `is_diff_metric` 默认补 `False`
    4. `is_manual` 在缺失时根据 `rule_list` 推断
    5. `tag_list` 优先使用旧字段，没有时兼容读取 `tags`
    """

    legacy_metric_json: list[dict[str, Any]] = []

    for metric_group in metric_json:
        metric_group_payload = _dump_payload(metric_group)
        rule_list = _normalize_list(metric_group_payload.get("rule_list") or metric_group_payload.get("rules"))

        legacy_fields: list[dict[str, Any]] = []
        for field in metric_group_payload.get("fields", []):
            field_payload = _dump_payload(field)
            tag_list = field_payload.get("tag_list")
            if tag_list is None:
                tag_list = field_payload.get("tags", [])

            legacy_fields.append(
                {
                    "description": field_payload.get("description", ""),
                    "type": field_payload.get("type"),
                    "monitor_type": field_payload.get("monitor_type"),
                    "unit": field_payload.get("unit", "none"),
                    "name": field_payload.get("name"),
                    "is_diff_metric": field_payload.get("is_diff_metric", False),
                    "is_active": field_payload.get("is_active", True),
                    "source_name": field_payload.get("source_name", ""),
                    "dimensions": _normalize_list(field_payload.get("dimensions")),
                    "is_manual": field_payload.get("is_manual", not bool(rule_list)),
                    "tag_list": _normalize_list(tag_list),
                }
            )

        legacy_metric_json.append(
            {
                "table_name": metric_group_payload.get("table_name"),
                "table_desc": metric_group_payload.get("table_desc", ""),
                "fields": legacy_fields,
                "rule_list": rule_list,
            }
        )

    return legacy_metric_json
