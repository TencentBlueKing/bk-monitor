from django.db.models import Q

from apm_ebpf.models import ClusterRelation, DeepflowDashboardRecord, DeepflowWorkload
from monitor_web.data_migrate.fetcher.base import FetcherResultType


def get_apm_ebpf_fetcher(bk_biz_id: int | None) -> list[FetcherResultType]:
    """
    获取 apm_ebpf 相关表。

    ``DeepflowWorkload`` 和 ``DeepflowDashboardRecord`` 直接按业务过滤；
    ``ClusterRelation`` 同时连接两侧业务，因此按两个业务字段任一命中来收敛。
    """
    direct_filters = None if bk_biz_id is None else {"bk_biz_id": bk_biz_id}
    cluster_relation_filters = None
    if bk_biz_id is not None:
        cluster_relation_ids = ClusterRelation.objects.filter(
            Q(bk_biz_id=bk_biz_id) | Q(related_bk_biz_id=bk_biz_id)
        ).values_list("id", flat=True)
        cluster_relation_filters = {"id__in": cluster_relation_ids}

    return [
        (DeepflowWorkload, direct_filters, None),
        (ClusterRelation, cluster_relation_filters, None),
        (DeepflowDashboardRecord, direct_filters, None),
    ]
