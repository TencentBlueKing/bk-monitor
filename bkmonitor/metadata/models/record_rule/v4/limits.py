"""RecordingRule V4 部署上限，仅用于预解析判定和下发前检查。"""

from typing import Any

from django.conf import settings


def check_deployment_limits(*, source_count: int, rule_count: int) -> dict[str, Any]:
    config = settings.RECORD_RULE_V4_CONFIG
    max_sources = config.get("max_sources", 20)
    max_rules = config.get("max_rules", 20)
    errors = []
    if source_count > max_sources:
        errors.append(
            {
                "code": "SOURCE_LIMIT_EXCEEDED",
                "message": f"Flow source 数量 {source_count} 超过上限 {max_sources}（max_sources）",
                "path": "config.rules",
                "actual": source_count,
                "limit": max_sources,
            }
        )
    if rule_count > max_rules:
        errors.append(
            {
                "code": "RULE_LIMIT_EXCEEDED",
                "message": f"group rule 数量 {rule_count} 超过上限 {max_rules}（max_rules）",
                "path": "config.rules",
                "actual": rule_count,
                "limit": max_rules,
            }
        )
    return {
        "can_apply": not errors,
        "source_count": source_count,
        "max_sources": max_sources,
        "rule_count": rule_count,
        "max_rules": max_rules,
        "errors": errors,
    }
