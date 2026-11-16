"""按场景读取动态配置的默认集群。"""

from django.conf import settings


def get_scene_default_cluster(
    scene: str, storage_type: str, bk_tenant_id: str, default: int | None = None
) -> int | None:
    """按租户和标准 ClusterType 查找场景集群，查不到时沿用原默认逻辑。"""
    from metadata.models.storage import ClusterInfo

    cluster_id = settings.SCENE_DEFAULT_STORAGE_CLUSTERS.get(bk_tenant_id, {}).get(scene, {}).get(storage_type)
    if (
        cluster_id is not None
        and ClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id, cluster_type=storage_type, cluster_id=cluster_id
        ).exists()
    ):
        return cluster_id
    return default
