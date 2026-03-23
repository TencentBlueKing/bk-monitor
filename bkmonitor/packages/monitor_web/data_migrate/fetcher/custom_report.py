from monitor_web.data_migrate.fetcher.base import FetcherResultType
from monitor_web.models.custom_report import (
    CustomEventGroup,
    CustomEventItem,
    CustomTSField,
    CustomTSGroupingRule,
    CustomTSItem,
    CustomTSTable,
)


def get_custom_report_fetcher(bk_biz_id: int | None) -> list[FetcherResultType]:
    """
    获取 monitor_web 下自定义事件与自定义指标相关表。

    规则：
    - 主表 ``CustomEventGroup``、``CustomTSTable`` 直接按业务过滤
    - 明细表没有业务字段，因此通过主表主键关联回查
    """
    event_group_filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}
    ts_table_filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}

    event_group_ids = CustomEventGroup.objects.filter(**(event_group_filters or {})).values_list(
        "bk_event_group_id", flat=True
    )
    time_series_group_ids = CustomTSTable.objects.filter(**(ts_table_filters or {})).values_list(
        "time_series_group_id", flat=True
    )

    return [
        (CustomEventGroup, event_group_filters, None),
        (CustomEventItem, {"bk_event_group_id__in": event_group_ids}, None),
        (CustomTSTable, ts_table_filters, None),
        (CustomTSField, {"time_series_group_id__in": time_series_group_ids}, None),
        (CustomTSItem, {"table_id__in": time_series_group_ids}, None),
        (CustomTSGroupingRule, {"time_series_group_id__in": time_series_group_ids}, None),
    ]
