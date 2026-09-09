"""Resolve the concrete occurrence of an existing shield time matcher."""

from datetime import datetime, timedelta

import arrow

from bkmonitor.utils import time_tools
from bkmonitor.utils.range.period import TimeMatchBySingle


def matching_window(matcher, at):
    """Return inclusive epoch-second bounds, preserving existing calendar matching."""
    if not matcher.is_match(at):
        return None
    if isinstance(matcher, TimeMatchBySingle):
        return int(matcher.begin_datetime.timestamp), int(matcher.end_datetime.timestamp)

    local = time_tools.localtime(at)
    start = datetime.strptime(matcher.start_time, "%H:%M:%S").time()
    end = datetime.strptime(matcher.end_time, "%H:%M:%S").time()
    begin = local.replace(hour=start.hour, minute=start.minute, second=start.second, microsecond=0)
    finish = local.replace(hour=end.hour, minute=end.minute, second=end.second, microsecond=0)
    if start > end:
        if local.time().replace(tzinfo=None) >= start:
            finish += timedelta(days=1)
            midnight = finish.replace(hour=0, minute=0, second=0)
            if not matcher.is_match(arrow.get(midnight)):
                finish = midnight - timedelta(seconds=1)
        else:
            begin -= timedelta(days=1)
            midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
            if not matcher.is_match(arrow.get(midnight - timedelta(seconds=1))):
                begin = midnight
    return (
        max(int(begin.timestamp()), int(matcher.begin_datetime.timestamp)),
        min(int(finish.timestamp()), int(matcher.end_datetime.timestamp)),
    )
