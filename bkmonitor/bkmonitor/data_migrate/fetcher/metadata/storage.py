from collections.abc import Sequence

from bkmonitor.data_migrate.fetcher.base import FetcherResultType
from metadata.models.es_snapshot import EsSnapshot, EsSnapshotIndice
from metadata.models.result_table import ESFieldQueryAliasOption
from metadata.models.storage import DorisStorage, ESStorage, KafkaStorage, StorageClusterRecord


def _normalize_table_ids(table_ids: Sequence[str] | None) -> list[str]:
    """将 table_id 输入规范化为列表。"""
    return list(table_ids or [])


def _normalize_cluster_ids(cluster_ids: Sequence[int] | None) -> list[int]:
    """将 cluster_id 输入规范化为列表。"""
    return list(cluster_ids or [])


def get_metadata_cluster_info_fetcher(cluster_ids: Sequence[int] | None) -> list[FetcherResultType]:
    """
    获取 Metadata 中存储集群信息。

    ``ClusterInfo`` 独立于具体 ``table_id`` 迁移，因此单独提供一个入口。
    ``ClusterConfig`` 当前先不导出。
    """
    # normalized_cluster_ids = _normalize_cluster_ids(cluster_ids)
    # filters = {"cluster_id__in": normalized_cluster_ids} if normalized_cluster_ids else None
    return [
        # (ClusterInfo, filters, None),
        # ClusterConfig 先不迁移，等集群注册配置是否需要跟随迁移进一步确认后再恢复。
        # cluster_queryset = ClusterInfo.objects.filter(**filters) if filters else ClusterInfo.objects.all()
        # cluster_names = cluster_queryset.values_list("cluster_name", flat=True)
        # cluster_tenant_ids = cluster_queryset.values_list("bk_tenant_id", flat=True)
        # cluster_kinds = []
        # cluster_types = set(cluster_queryset.values_list("cluster_type", flat=True))
        # if ClusterInfo.TYPE_ES in cluster_types:
        #     cluster_kinds.append(DataLinkKind.ELASTICSEARCH.value)
        # if ClusterInfo.TYPE_VM in cluster_types:
        #     cluster_kinds.append(DataLinkKind.VMSTORAGE.value)
        # if "doris" in cluster_types:
        #     cluster_kinds.append(DataLinkKind.DORIS.value)
        # if "kafka" in cluster_types:
        #     cluster_kinds.append(DataLinkKind.KAFKACHANNEL.value)
        # cluster_config_filters = None
        # if filters is not None:
        #     cluster_config_filters = {
        #         "name__in": cluster_names,
        #         "bk_tenant_id__in": cluster_tenant_ids,
        #         "kind__in": cluster_kinds,
        #     }
        # (ClusterConfig, cluster_config_filters, None),
    ]


def get_metadata_storage_by_table_ids_fetcher(table_ids: Sequence[str] | None) -> list[FetcherResultType]:
    """
    按 table_ids 获取 Metadata 中存储与 ES 快照相关表。

    收敛规则：
    - ``ESStorage`` 同时兼容 ``table_id`` 和 ``origin_table_id`` 命中
    - 其余存储表直接按 ``table_id`` / ``result_table_id`` 过滤
    - ``EsSnapshotRepository`` 通过该批 ``table_id`` 对应快照配置反查仓库名
    """
    normalized_table_ids = _normalize_table_ids(table_ids)
    es_storage_ids = list(ESStorage.objects.filter(table_id__in=normalized_table_ids).values_list("id", flat=True))
    es_storage_ids += list(
        ESStorage.objects.filter(origin_table_id__in=normalized_table_ids).values_list("id", flat=True)
    )

    snapshot_repo_names = list(
        EsSnapshot.objects.filter(table_id__in=normalized_table_ids).values_list(
            "target_snapshot_repository_name", flat=True
        )
    )
    snapshot_repo_names += list(
        EsSnapshotIndice.objects.filter(table_id__in=normalized_table_ids).values_list("repository_name", flat=True)
    )

    return [
        (ESStorage, {"id__in": es_storage_ids}, None),
        # AccessVMRecord 先不迁移，等结果表与 VM 接入关系进一步确认后再恢复。
        # (AccessVMRecord, {"result_table_id__in": normalized_table_ids}, None),
        (KafkaStorage, {"table_id__in": normalized_table_ids}, None),
        (DorisStorage, {"table_id__in": normalized_table_ids}, None),
        (StorageClusterRecord, {"table_id__in": normalized_table_ids, "is_current": True}, None),
        (ESFieldQueryAliasOption, {"table_id__in": normalized_table_ids}, None),
        # (EsSnapshot, {"table_id__in": normalized_table_ids}, None),
        # (EsSnapshotIndice, {"table_id__in": normalized_table_ids}, None),
        # (EsSnapshotRepository, {"repository_name__in": snapshot_repo_names}, None),
        # (EsSnapshotRestore, {"table_id__in": normalized_table_ids}, None),
    ]
