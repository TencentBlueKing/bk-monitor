from django.db.models import Q

from metadata.models.bcs.cluster import BCSClusterInfo, BcsFederalClusterInfo
from metadata.models.bcs.resource import LogCollectorInfo, PodMonitorInfo, ServiceMonitorInfo
from monitor_web.data_migrate.fetcher.base import FetcherResultType


def get_metadata_bcs_fetcher(bk_biz_id: int | None) -> list[FetcherResultType]:
    """
    获取 Metadata 中 BCS 相关表。

    分层规则：
    - ``BCSClusterInfo`` 本身带业务字段，直接按 ``bk_biz_id`` 过滤
    - ``PodMonitorInfo`` / ``ServiceMonitorInfo`` / ``LogCollectorInfo`` 没有业务字段，
      因此通过业务下集群的 ``cluster_id`` 关联回查
    - ``BcsFederalClusterInfo`` 有租户字段但没有业务字段，因此先按业务下集群反查，
      再按这些集群的租户及联邦/宿主/子集群关系收敛
    """
    cluster_filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}
    cluster_queryset = BCSClusterInfo.objects.filter(**(cluster_filters or {}))
    cluster_ids = cluster_queryset.values_list("cluster_id", flat=True)

    if bk_biz_id is None:
        federal_cluster_filters = None
    else:
        federal_cluster_ids = BcsFederalClusterInfo.objects.filter(
            Q(fed_cluster_id__in=cluster_ids) | Q(host_cluster_id__in=cluster_ids) | Q(sub_cluster_id__in=cluster_ids),
            bk_tenant_id__in=cluster_queryset.values_list("bk_tenant_id", flat=True),
        ).values_list("id", flat=True)
        federal_cluster_filters = {"id__in": federal_cluster_ids}

    return [
        (BCSClusterInfo, cluster_filters, None),
        (BcsFederalClusterInfo, federal_cluster_filters, None),
        (ServiceMonitorInfo, {"cluster_id__in": cluster_ids}, None),
        (PodMonitorInfo, {"cluster_id__in": cluster_ids}, None),
        (LogCollectorInfo, {"cluster_id__in": cluster_ids}, None),
    ]
