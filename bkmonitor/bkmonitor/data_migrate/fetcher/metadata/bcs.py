from django.db.models import Q

from bkmonitor.data_migrate.fetcher.base import FetcherResultType
from metadata.models.bcs.cluster import BCSClusterInfo, BcsFederalClusterInfo
from metadata.models.bcs.resource import LogCollectorInfo, PodMonitorInfo, ServiceMonitorInfo


def get_metadata_bcs_fetcher(bk_biz_id: int | None) -> list[FetcherResultType]:
    """
    获取 Metadata 中 BCS 相关表。

    分层规则：
    - ``BCSClusterInfo`` 本身带业务字段，直接按 ``bk_biz_id`` 过滤
    - ``PodMonitorInfo`` / ``ServiceMonitorInfo`` / ``LogCollectorInfo`` 没有业务字段，
      因此通过业务下集群的 ``cluster_id`` 关联回查
    - ``BcsFederalClusterInfo`` 没有业务字段，但会引用集群 ID，
      因此按联邦/宿主/子集群任一命中业务下集群来收敛
    """
    cluster_filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}
    cluster_ids = BCSClusterInfo.objects.filter(**(cluster_filters or {})).values_list("cluster_id", flat=True)

    if bk_biz_id is None:
        federal_cluster_filters = None
    else:
        federal_cluster_ids = BcsFederalClusterInfo.objects.filter(
            Q(fed_cluster_id__in=cluster_ids) | Q(host_cluster_id__in=cluster_ids) | Q(sub_cluster_id__in=cluster_ids)
        ).values_list("id", flat=True)
        federal_cluster_filters = {"id__in": federal_cluster_ids}

    return [
        (BCSClusterInfo, cluster_filters, None),
        (BcsFederalClusterInfo, federal_cluster_filters, None),
        (ServiceMonitorInfo, {"cluster_id__in": cluster_ids}, None),
        (PodMonitorInfo, {"cluster_id__in": cluster_ids}, None),
        (LogCollectorInfo, {"cluster_id__in": cluster_ids}, None),
    ]
