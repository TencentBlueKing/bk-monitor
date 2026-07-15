"""StorageClusterRecord history shared by ESStorage and DorisStorage admin RPCs."""

import copy
from typing import Any

from core.drf_resource.exceptions import CustomException
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


def resolve_runtime_storage_cluster(
    storage: Any,
    bk_tenant_id: str,
    storage_cluster_id: Any,
    expected_cluster_type: str,
) -> Any:
    """Resolve and validate the cluster used by a one-off read-only runtime query."""

    current_cluster_id = storage.storage_cluster_id
    if storage_cluster_id in (None, ""):
        target_cluster_id = current_cluster_id
    else:
        if isinstance(storage_cluster_id, bool) or not isinstance(storage_cluster_id, int | str):
            raise CustomException(message="storage_cluster_id 必须是整数")
        try:
            target_cluster_id = int(storage_cluster_id)
        except (TypeError, ValueError) as error:
            raise CustomException(message="storage_cluster_id 必须是整数") from error

    try:
        cluster = models.ClusterInfo.objects.get(
            bk_tenant_id=bk_tenant_id,
            cluster_id=target_cluster_id,
            cluster_type=expected_cluster_type,
        )
    except models.ClusterInfo.DoesNotExist as error:
        raise CustomException(
            message=(
                f"存储集群不存在、租户不匹配或类型不是 {expected_cluster_type}: storage_cluster_id={target_cluster_id}"
            )
        ) from error

    # The current storage model is the source of truth for the current cluster. This
    # also keeps old records usable when their initial StorageClusterRecord is absent.
    if target_cluster_id == current_cluster_id:
        return cluster

    history_table_id = resolve_storage_history_table_id(storage)
    if not models.StorageClusterRecord.objects.filter(
        bk_tenant_id=bk_tenant_id,
        table_id=history_table_id,
        cluster_id=target_cluster_id,
    ).exists():
        raise CustomException(
            message=(
                "storage_cluster_id 不属于当前实体表的历史存储集群: "
                f"table_id={history_table_id}, storage_cluster_id={target_cluster_id}"
            )
        )
    return cluster


def clone_storage_with_runtime_cluster(storage: Any, cluster: Any) -> Any:
    """Return an unsaved model clone whose client resolves to the selected cluster."""

    runtime_storage = copy.copy(storage)
    runtime_storage.storage_cluster_id = cluster.cluster_id
    runtime_storage._cluster = cluster
    return runtime_storage


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
