from calendars.models import CalendarItemModel, CalendarModel

from bkmonitor.data_migrate.fetcher.base import FetcherResultType


def get_calendar_fetcher() -> list[FetcherResultType]:
    """
    获取日历配置。

    日历与业务无关，因此直接导出全部日历及事项。
    """
    calendar_ids = CalendarModel.objects.values_list("id", flat=True)
    return [
        (CalendarModel, None, None),
        (CalendarItemModel, {"calendar_id__in": calendar_ids}, None),
    ]
