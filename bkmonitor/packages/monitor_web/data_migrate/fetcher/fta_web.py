from fta_web.models.alert import AlertExperience, AlertSuggestion, MetricRecommendationFeedback
from monitor_web.data_migrate.fetcher.base import FetcherResultType


def get_fta_web_fetcher(bk_biz_id: int | None) -> list[FetcherResultType]:
    """
    获取 fta_web 中与业务绑定的配置类表。

    这里只处理新版且带业务字段的表，不迁移 ``old_fta`` 里的历史模型。
    同时也不包含没有业务字段的检索历史、检索收藏、反馈类运行态数据，
    避免业务导出时混入用户操作痕迹。
    """
    alert_filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}

    return [
        (AlertExperience, alert_filters, None),
        (AlertSuggestion, alert_filters, None),
        (MetricRecommendationFeedback, alert_filters, None),
    ]
