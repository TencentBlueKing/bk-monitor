"""Resolve the concrete occurrence of an existing shield time matcher."""

from datetime import datetime, timedelta

import arrow
from django.conf import settings

from alarm_backends.core.cache.cmdb.business import BusinessManager

from bkmonitor.utils import time_tools
from bkmonitor.utils.range.period import TimeMatch, TimeMatchByDay, TimeMatchByMonth, TimeMatchBySingle, TimeMatchByWeek


def business_timezone(bk_biz_id):
    business = BusinessManager.get(bk_biz_id) if bk_biz_id is not None else None
    return (business.time_zone if business else None) or settings.TIME_ZONE


class _BusinessCalendar:
    """Close shields use the business calendar, never the worker OS timezone."""

    def is_week_match(self, data_time):
        return isinstance(self.week_list, list) and time_tools.localtime(data_time).isoweekday() in self.week_list

    def is_month_match(self, data_time):
        return isinstance(self.day_list, list) and time_tools.localtime(data_time).day in self.day_list


class _CloseDay(_BusinessCalendar, TimeMatchByDay):
    pass


class _CloseWeek(_BusinessCalendar, TimeMatchByWeek):
    pass


class _CloseMonth(_BusinessCalendar, TimeMatchByMonth):
    pass


def close_time_matcher(cycle, begin_time, end_time):
    """Construct under the caller's business timezone.override context."""
    matcher_class = {2: _CloseDay, 3: _CloseWeek, 4: _CloseMonth}.get(int(cycle.get("type", -1)), TimeMatchBySingle)
    return matcher_class(
        cycle, TimeMatch.convert_datetime_to_arrow(begin_time), TimeMatch.convert_datetime_to_arrow(end_time)
    )


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
