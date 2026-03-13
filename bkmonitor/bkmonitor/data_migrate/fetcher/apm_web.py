from bkmonitor.data_migrate.fetcher.base import FetcherResultType

from apm_web.models import (
    ApdexServiceRelation,
    ApmMetaConfig,
    AppServiceRelation,
    Application,
    ApplicationCustomService,
    ApplicationRelationInfo,
    CMDBServiceRelation,
    CodeRedefinedConfigRelation,
    EventServiceRelation,
    LogServiceRelation,
    ProfileUploadRecord,
    StrategyInstance,
    StrategyTemplate,
    TraceComparison,
    UriServiceRelation,
)


def get_apm_web_fetcher(bk_biz_id: int | None) -> list[FetcherResultType]:
    """
    获取 apm_web 模块迁移所需的 ORM 查询配置。

    原则：
    - 有 ``bk_biz_id`` 的表直接按业务过滤
    - ``ApplicationRelationInfo`` 通过 ``application_id`` 回查
    - ``ApmMetaConfig`` 按配置层级分别收敛
    """
    application_filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}
    application_ids = Application.objects.filter(**(application_filters or {})).values_list("application_id", flat=True)

    fetchers: list[FetcherResultType] = [
        (Application, application_filters, None),
        (ApplicationRelationInfo, {"application_id__in": application_ids}, None),
        (ApplicationCustomService, application_filters, None),
        (CMDBServiceRelation, application_filters, None),
        (EventServiceRelation, application_filters, None),
        (LogServiceRelation, application_filters, None),
        (AppServiceRelation, application_filters, None),
        (UriServiceRelation, application_filters, None),
        (ApdexServiceRelation, application_filters, None),
        (CodeRedefinedConfigRelation, application_filters, None),
        (StrategyTemplate, application_filters, None),
        (StrategyInstance, application_filters, None),
        (ProfileUploadRecord, application_filters, None),
        (TraceComparison, application_filters, None),
    ]

    if bk_biz_id is None:
        fetchers.append((ApmMetaConfig, None, None))
        return fetchers

    fetchers.extend(
        [
            (
                ApmMetaConfig,
                {"config_level": ApmMetaConfig.APPLICATION_LEVEL, "level_key__in": application_ids},
                None,
            ),
            (
                ApmMetaConfig,
                {"config_level": ApmMetaConfig.BK_BIZ_LEVEL, "level_key": str(bk_biz_id)},
                None,
            ),
            (
                ApmMetaConfig,
                {"config_level": ApmMetaConfig.SERVICE_LEVEL, "level_key__startswith": f"{bk_biz_id}-"},
                None,
            ),
        ]
    )
    return fetchers
