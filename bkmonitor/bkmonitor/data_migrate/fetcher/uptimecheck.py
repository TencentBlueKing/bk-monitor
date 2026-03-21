from bkmonitor.data_migrate.fetcher.base import FetcherResultType
from monitor.models import UptimeCheckGroup, UptimeCheckNode, UptimeCheckTask, UptimeCheckTaskSubscription


def get_uptimecheck_fetcher(bk_biz_id: int | None) -> list[FetcherResultType]:
    """
    获取服务拨测配置相关数据。

    以业务为根优先过滤：
    - 有 ``bk_biz_id`` 的表直接按业务过滤，避免因为任务关联不完整而漏数
    - 仅在表本身没有业务字段时，才使用关联条件回查
    """
    biz_filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}

    return [
        (UptimeCheckNode, biz_filters, None),
        (UptimeCheckTask, biz_filters, None),
        (UptimeCheckTaskSubscription, biz_filters, None),
        (UptimeCheckGroup, biz_filters, None),
    ]
