from rest_framework import serializers

from metadata.models.es_snapshot import EsSnapshot, EsSnapshotIndice, EsSnapshotRepository, EsSnapshotRestore

from .common import TenantPage, db_page, query


class Repositories(TenantPage):
    repository_name = serializers.CharField(required=False)
    cluster_id = serializers.IntegerField(required=False)


class Snapshots(TenantPage):
    repository_name = serializers.CharField(required=False)
    table_id = serializers.CharField(required=False)


class Indices(Snapshots):
    index_name = serializers.CharField(required=False)


class Restores(Snapshots):
    restore_id = serializers.IntegerField(min_value=1, required=False)


@query("log_archive.repository_list", "查询日志快照仓库及所属集群", Repositories)
def repositories(p):
    rows = EsSnapshotRepository.objects.filter(
        **{k: p[k] for k in ("bk_tenant_id", "repository_name", "cluster_id") if k in p}
    )
    return db_page(
        rows.order_by("repository_name").values(
            "repository_name",
            "alias",
            "cluster_id",
            "is_deleted",
            "creator",
            "last_modify_time",
        ),
        p,
    )


@query("log_archive.snapshot_list", "查询结果表的归档任务、保留期与状态", Snapshots)
def snapshots(p):
    rows = EsSnapshot.objects.filter(**{k: p[k] for k in ("bk_tenant_id", "table_id") if k in p})
    if "repository_name" in p:
        rows = rows.filter(target_snapshot_repository_name=p["repository_name"])
    return db_page(
        rows.order_by("-id").values(
            "table_id",
            "target_snapshot_repository_name",
            "snapshot_days",
            "status",
            "id",
            "last_modify_time",
        ),
        p,
    )


@query("log_archive.index_list", "查询已归档的物理索引、时间范围和容量", Indices)
def indices(p):
    rows = EsSnapshotIndice.objects.filter(
        **{k: p[k] for k in ("bk_tenant_id", "repository_name", "table_id", "index_name") if k in p}
    )
    return db_page(
        rows.order_by("-start_time", "-pk").values(
            "index_name",
            "snapshot_name",
            "table_id",
            "repository_name",
            "doc_count",
            "store_size",
            "cluster_id",
            "start_time",
            "end_time",
        ),
        p,
    )


@query("log_archive.restore_list", "查询回溯任务、已完成文档数及到期时间", Restores)
def restores(p):
    rows = EsSnapshotRestore.objects.filter(
        **{k: p[k] for k in ("bk_tenant_id", "repository_name", "table_id", "restore_id") if k in p}
    )
    return db_page(
        rows.order_by("-restore_id").values(
            "restore_id",
            "table_id",
            "repository_name",
            "complete_doc_count",
            "total_doc_count",
            "expired_time",
            "start_time",
            "end_time",
            "duration",
            "total_store_size",
            "is_deleted",
        ),
        p,
    )
