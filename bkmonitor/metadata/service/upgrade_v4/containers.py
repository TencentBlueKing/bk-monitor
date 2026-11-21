"""按集群全部或局部准备容器指标/事件；不重新下发采集。"""

from metadata import models
from metadata.service.upgrade_v4.common import run_batch
from metadata.service.upgrade_v4.events import migrate_event
from metadata.service.upgrade_v4.metrics import migrate_metric


def migrate_containers(
    cluster_ids=None,
    *,
    vm_cluster_name=None,
    metrics=True,
    events=True,
    bk_biz_ids=None,
    bk_tenant_id="system",
    **route_options,
):
    clusters = models.BCSClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id).exclude(
        status=models.BCSClusterInfo.CLUSTER_STATUS_DELETED
    )
    if cluster_ids is not None:
        clusters = clusters.filter(cluster_id__in=cluster_ids)
    if bk_biz_ids is not None:
        clusters = clusters.filter(bk_biz_id__in=bk_biz_ids)
    items = {}
    for cluster in clusters.order_by("cluster_id"):
        if metrics:
            for data_id in (cluster.K8sMetricDataID, cluster.CustomMetricDataID):
                if data_id:
                    items[data_id] = ("metric", cluster.cluster_id)
        if events:
            for data_id in (cluster.K8sEventDataID, cluster.CustomEventDataID):
                if data_id:
                    items[data_id] = ("event", cluster.cluster_id)

    def migrate(data_id):
        kind, cluster_id = items[data_id]
        if kind == "event":
            return migrate_event(data_id, bk_tenant_id=bk_tenant_id)
        if models.BcsFederalClusterInfo.is_federal_cluster(cluster_id, bk_tenant_id=bk_tenant_id):
            raise ValueError("联邦入口集群使用专用拓扑链路，不作为普通容器指标升级")
        return migrate_metric(
            data_id, vm_cluster_name=vm_cluster_name, bcs_cluster_id=cluster_id, bk_tenant_id=bk_tenant_id
        )

    return run_batch(items, migrate, bk_tenant_id=bk_tenant_id, **route_options)
