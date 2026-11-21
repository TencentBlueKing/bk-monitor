"""可独立调用的只读检查和集群注册；不初始化租户、不修改默认集群。"""

from django.conf import settings

from core.drf_resource import api
from metadata.models import ClusterInfo, DataSource
from metadata.models.data_link.constants import DataLinkKind
from metadata.models.data_link.data_link_configs import ClusterConfig
from metadata.utils.gse import KafkaGseSyncer


def check_settings():
    return {
        "single_tenant": not settings.ENABLE_MULTI_TENANT_MODE,
        "v4_enabled": settings.ENABLE_V2_VM_DATA_LINK,
        "data_bk_biz_id": settings.DEFAULT_BKDATA_BIZ_ID,
    }


def check_cluster_registration(cluster_ids=None, *, bk_tenant_id="system"):
    """查询 BKBase 实际资源，不以本地 registered_to_bkbase 代替远端状态。None=全部支持集群。"""
    clusters = ClusterInfo.objects.filter(
        bk_tenant_id=bk_tenant_id, cluster_type__in=ClusterConfig.CLUSTER_TYPE_TO_KIND_MAP
    )
    if cluster_ids is not None:
        clusters = clusters.filter(cluster_id__in=cluster_ids)
    inventories = {}
    result = []
    for cluster in clusters.order_by("cluster_id"):
        kind = ClusterConfig.CLUSTER_TYPE_TO_KIND_MAP[cluster.cluster_type]
        namespaces = {}
        for namespace in ClusterConfig.KIND_TO_NAMESPACES_MAP[kind]:
            key = (namespace, kind)
            if key not in inventories:
                inventories[key] = {
                    item["metadata"]["name"]: item
                    for item in api.bkdata.list_data_link(
                        bk_tenant_id=bk_tenant_id, namespace=namespace, kind=DataLinkKind.get_choice_value(kind)
                    )
                }
            item = inventories[key].get(cluster.cluster_name)
            namespaces[namespace] = {"registered": item is not None, "status": item.get("status") if item else None}
        result.append(
            {"cluster_id": cluster.cluster_id, "cluster_name": cluster.cluster_name, "namespaces": namespaces}
        )
    return result


def register_kafka_to_gse(cluster_ids, *, bk_tenant_id="system"):
    """显式注册选定 Kafka；与 BKBase 注册分开调用。"""
    result = []
    for cluster_id in dict.fromkeys(cluster_ids):
        cluster = ClusterInfo.objects.get(
            bk_tenant_id=bk_tenant_id, cluster_id=cluster_id, cluster_type=ClusterInfo.TYPE_KAFKA
        )
        KafkaGseSyncer.register_to_gse(mq_cluster=cluster)
        result.append(cluster_id)
    return result


def register_clusters(cluster_ids, *, namespaces=None, bk_tenant_id="system"):
    """重复 apply 同名集群，不改默认集群；Kafka 必须先有 GSE streamToId。"""
    if namespaces == []:
        return []
    result = []
    for cluster_id in dict.fromkeys(cluster_ids):
        cluster = ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_id=cluster_id)
        ClusterConfig.sync_cluster_config(cluster, sync_namespaces=namespaces)
        result.append(cluster_id)
    return result


def check_data_sources(data_ids=None, *, bk_tenant_id="system"):
    sources = DataSource.objects.filter(bk_tenant_id=bk_tenant_id)
    if data_ids is not None:
        sources = sources.filter(bk_data_id__in=data_ids)
    result = []
    for source in sources.order_by("bk_data_id"):
        result.append(
            {
                "data_id": source.bk_data_id,
                "enabled": source.is_enable,
                "etl_config": source.etl_config,
                "created_from": source.created_from,
                "mq_cluster_id": source.mq_cluster_id,
                "topic": source.mq_config.topic,
            }
        )
    return result
