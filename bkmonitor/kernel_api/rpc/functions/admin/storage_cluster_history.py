"""StorageClusterRecord history shared by ESStorage and DorisStorage admin RPCs."""

from typing import Any

from kernel_api.rpc.functions.admin.common import serialize_model
from metadata import models

STORAGE_CLUSTER_RECORD_FIELDS = [
    "table_id",
    "cluster_id",
    "is_current",
    "is_deleted",
    "enable_time",
    "disable_time",
    "delete_time",
    "creator",
    "create_time",
]
CLUSTER_SUMMARY_FIELDS = ["cluster_id", "cluster_name", "display_name", "cluster_type"]


def resolve_storage_history_table_id(storage: Any) -> str:
    """Virtual storages share the entity table's storage migration history."""

    return storage.origin_table_id or storage.table_id


def build_storage_cluster_records(storage: Any, bk_tenant_id: str) -> list[dict[str, Any]]:
    record_table_id = resolve_storage_history_table_id(storage)
    records = list(
        models.StorageClusterRecord.objects.filter(
            bk_tenant_id=bk_tenant_id,
            table_id=record_table_id,
        ).order_by("-create_time")
    )
    clusters = models.ClusterInfo.objects.filter(
        bk_tenant_id=bk_tenant_id,
        cluster_id__in=[record.cluster_id for record in records],
    )
    cluster_map = {cluster.cluster_id: cluster for cluster in clusters}
    return [serialize_storage_cluster_record(record, cluster_map.get(record.cluster_id)) for record in records]


def serialize_storage_cluster_record(record: Any, cluster: Any | None) -> dict[str, Any]:
    item = serialize_model(record, STORAGE_CLUSTER_RECORD_FIELDS)
    item["cluster"] = serialize_model(cluster, CLUSTER_SUMMARY_FIELDS) if cluster is not None else None
    item["storage_type"] = storage_type_from_cluster(cluster)
    return item


def storage_type_from_cluster(cluster: Any | None) -> str:
    cluster_type = getattr(cluster, "cluster_type", None)
    if cluster_type == models.ClusterInfo.TYPE_ES:
        return "es"
    if cluster_type == models.ClusterInfo.TYPE_DORIS:
        return "doris"
    return "unknown"
