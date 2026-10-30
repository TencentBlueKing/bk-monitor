"""Structured fields for standard SMS bodies; legacy template data is left intact."""

from datetime import datetime, timezone

from django.utils.translation import gettext as _

from bkmonitor.utils.sms import format_sms_time
from constants.action import ACTION_STATUS_DICT
from constants.alert import EVENT_SEVERITY_DICT
from constants.incident import IncidentLevel


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _latest_time(values):
    timestamps = []
    for value in values:
        if isinstance(value, datetime):
            value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
            timestamps.append(value.timestamp())
        elif value:
            timestamps.append(float(value))
    return max(timestamps) if timestamps else None


def standard_sms_values(kind, context):
    """Read event snapshots and raw severity, never the rendered legacy body."""
    if kind == "shield":
        return {
            "time": context.get("sms_event_time_formatted") or format_sms_time(None),
            "shield_action": context.get("notice_type", ""),
            "duration": context.get("cycle_duration", ""),
        }
    if kind == "incident":
        level = context.get("sms_level")
        return {
            "time": format_sms_time(context.get("sms_event_time")),
            "level": str(IncidentLevel(level).alias) if level else _("未知"),
            "count": context.get("sms_alert_count", 0),
        }
    if kind == "fta_action":
        action = context.get("action")
        status = context.get("sms_action_status") or _get(action, "status")
        return {
            "time": format_sms_time(context.get("sms_event_time")),
            "name": _get(context.get("action_instance"), "name", ""),
            "status": str(ACTION_STATUS_DICT.get(status, _("未知"))),
        }

    signal = kind.split("/", 1)[0]
    alarm = context.get("alarm")
    alert = context.get("alert")
    severity = _get(alert, "severity") or context.get("alert_level")
    values = {
        "level": str(EVENT_SEVERITY_DICT.get(severity, _("未知"))),
        "name": _get(alarm, "name", ""),
        "count": _get(alarm, "collect_count", 1),
        "operator": _get(alarm, "ack_operators", []),
    }
    if signal == "ack":
        logs = _get(alarm, "ack_logs", [])
        event_time = _get(logs[0], "create_time") if logs else None
    else:
        parent = _get(alarm, "parent")
        actions = _get(parent, "related_actions") or [context.get("action")]
        field = "alert_end_time" if signal in ("recovered", "closed") else "alert_latest_time"
        event_time = _latest_time(_get(_get(action, "inputs", {}), field) for action in actions)
    values["time"] = format_sms_time(event_time)
    return values
