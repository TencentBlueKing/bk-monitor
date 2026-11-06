"""BKBase VM 查询集群的本地只读镜像。"""

from typing import Any

from django.db import models

from metadata.models.data_link.constants import BKBASE_NAMESPACE_BK_MONITOR, DataLinkKind


class VmQueryClusterConfig(models.Model):
    """保存查询集群及其覆盖的 storage 名称，不参与链路下发。"""

    kind = DataLinkKind.VMQUERYCLUSTER.value

    bk_tenant_id = models.CharField("租户ID", max_length=256)
    namespace = models.CharField("命名空间", max_length=64, default=BKBASE_NAMESPACE_BK_MONITOR)
    name = models.CharField("资源名称", max_length=255)
    cluster_name = models.CharField("查询集群名称", max_length=255)
    cluster_domain = models.CharField("查询集群域名", max_length=255)
    num_replicas = models.PositiveIntegerField("副本数")
    monitor_storage_clusters = models.JSONField("关联的 VM storage 名称", default=list)
    k8s_cluster = models.CharField("K8s 集群", max_length=255)
    k8s_namespace = models.CharField("K8s 命名空间", max_length=255)
    version = models.CharField("版本", max_length=255)
    status = models.CharField("状态", max_length=64, default="", blank=True)
    last_synced_at = models.DateTimeField("最后成功同步时间", null=True, blank=True)
    origin_config = models.JSONField("原始配置", default=dict)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "VM 查询集群配置"
        verbose_name_plural = verbose_name
        unique_together = (("bk_tenant_id", "namespace", "name"),)

    @property
    def component_config(self) -> dict[str, Any] | None:
        """查询 BKBase 中该资源的实时配置。"""
        from metadata.models.data_link.service import get_data_link_component_config

        return get_data_link_component_config(
            bk_tenant_id=self.bk_tenant_id,
            kind=self.kind,
            namespace=self.namespace,
            component_name=self.name,
        )
