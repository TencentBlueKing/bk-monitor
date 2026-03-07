from bkmonitor.data_migrate.fetcher.base import FetcherResultType
from bkmonitor.models.aiops import AIFeatureSettings
from bkmonitor.models.config import MonitorMigration
from bkmonitor.models.home import HomeAlarmGraphConfig
from bkmonitor.models.strategy import DefaultStrategyBizAccessModel
from monitor.models.models import ApplicationConfig, UploadedFile
from monitor_web.models.file import UploadedFileInfo


def get_internal_config_fetcher(bk_biz_id: int | None) -> list[FetcherResultType]:
    """
    获取内部配置类表的迁移 ORM 查询配置。

    这两个表都自带业务字段，因此直接按业务过滤：
    - ``DefaultStrategyBizAccessModel.bk_biz_id``
    - ``ApplicationConfig.cc_biz_id``
    - ``AIFeatureSettings.bk_biz_id``
    - ``HomeAlarmGraphConfig.bk_biz_id``
    """
    default_strategy_access_filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}
    application_config_filters = None if bk_biz_id is None else {"cc_biz_id": bk_biz_id}
    ai_feature_settings_filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}
    home_alarm_graph_filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}

    return [
        (DefaultStrategyBizAccessModel, default_strategy_access_filters, None),
        (ApplicationConfig, application_config_filters, None),
        (AIFeatureSettings, ai_feature_settings_filters, None),
        (HomeAlarmGraphConfig, home_alarm_graph_filters, None),
    ]


def get_global_meta_fetcher() -> list[FetcherResultType]:
    """
    获取无业务维度的全局元数据表。

    这些表都没有业务字段，不应该混入业务维度导出。
    """
    return [
        (MonitorMigration, None, None),
        (UploadedFile, None, None),
        (UploadedFileInfo, None, None),
    ]
