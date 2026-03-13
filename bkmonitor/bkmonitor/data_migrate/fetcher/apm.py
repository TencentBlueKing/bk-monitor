from apm.models import (
    ApdexConfig,
    ApmApplication,
    ApmInstanceDiscover,
    ApmMetricDimension,
    ApmTopoDiscoverRule,
    BcsClusterDefaultApplicationRelation,
    BkdataFlowConfig,
    CustomServiceConfig,
    DbConfig,
    EbpfApplicationConfig,
    LicenseConfig,
    LogDataSource,
    MetricDataSource,
    NormalTypeValueConfig,
    ProbeConfig,
    ProfileDataSource,
    ProfileService,
    QpsConfig,
    RemoteServiceDiscover,
    SamplerConfig,
    SubscriptionConfig,
    TraceDataSource,
)
from bkmonitor.data_migrate.fetcher.base import FetcherResultType


def get_apm_fetcher(bk_biz_id: int | None) -> list[FetcherResultType]:
    """
    获取 apm 模块迁移所需的 ORM 查询配置。

    这类表大部分都自带 ``bk_biz_id``，因此统一直接按业务过滤。
    ``DataLink``、``SubscriptionConfig`` 这类允许存在平台默认记录的表，
    在 ``bk_biz_id=None`` 时也会自然带出全局配置。
    """

    # 当 bk_biz_id 为 0 时，不返回任何数据
    if bk_biz_id == 0:
        return []

    filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}
    return [
        (ApmApplication, filters, None),
        (EbpfApplicationConfig, filters, None),
        (BcsClusterDefaultApplicationRelation, filters, None),
        (ProfileService, filters, None),
        (SubscriptionConfig, filters, None),
        (MetricDataSource, filters, None),
        (LogDataSource, filters, None),
        (TraceDataSource, filters, None),
        (ProfileDataSource, filters, None),
        # (DataLink, filters, None),
        (BkdataFlowConfig, filters, None),
        (ApmTopoDiscoverRule, filters, None),
        (ApmInstanceDiscover, filters, None),
        (ApmMetricDimension, filters, None),
        (RemoteServiceDiscover, filters, None),
        (ApdexConfig, filters, None),
        (SamplerConfig, filters, None),
        (CustomServiceConfig, filters, None),
        (NormalTypeValueConfig, filters, None),
        (QpsConfig, filters, None),
        (LicenseConfig, filters, None),
        (DbConfig, filters, None),
        (ProbeConfig, filters, None),
        # (RootEndpoint, filters, None),
        # (Endpoint, filters, None),
        # (TopoNode, filters, None),
        # (TopoRelation, filters, None),
        # (TopoInstance, filters, None),
        # (HostInstance, filters, None),
        # (RemoteServiceRelation, filters, None),
    ]
