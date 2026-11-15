"""按场景读取动态配置的默认集群。"""

from django.conf import settings


def get_scene_default_cluster(scene: str, storage_type: str, default: int | None = None) -> int | None:
    """返回 ClusterInfo ID；未配置或为 null 时沿用调用方的默认值。"""
    cluster_id = settings.SCENE_DEFAULT_STORAGE_CLUSTERS.get(scene, {}).get(storage_type)
    return default if cluster_id is None else cluster_id
