from django.db import models
from django.db.transaction import atomic

from bk_monitor_base.metadata import config
from bk_monitor_base.metadata.models.storage import ClusterInfo
from bk_monitor_base.metadata.models.vm.constants import VM_RETENTION_TIME
from bk_monitor_base.metadata.utils.tenant import space_uid_to_bk_tenant_id


class SpaceVMInfoManager(models.Manager):
    @atomic(config.DATABASE_CONNECTION_NAME)
    def create_record(
        self,
        space_type: str,
        space_id: str,
        vm_cluster_id: int | None = None,
        vm_retention_time: str | None = VM_RETENTION_TIME,
    ) -> models.Model:
        """创建记录

        :param space_type: 空间类型
        :param space_id: 空间 ID
        :param vm_cluster_id: vm 集群 ID
        :param vm_retention_time: 保留时间
        """
        bk_tenant_id = space_uid_to_bk_tenant_id(f"{space_type}__{space_id}")
        # vm 集群 ID 为空时，获取默认的 vm 存储集群
        if not vm_cluster_id:
            vm_cluster_objs = ClusterInfo.objects.filter(
                bk_tenant_id=bk_tenant_id, cluster_type=ClusterInfo.TYPE_VM, is_default_cluster=True
            )
            if not vm_cluster_objs.exists():
                raise ValueError(f"cluster_type: {ClusterInfo.TYPE_VM} not found default cluster")
            # 获取集群 ID
            vm_cluster_id = vm_cluster_objs.first().cluster_id

        # 创建集群
        return self.create(
            space_type=space_type,
            space_id=space_id,
            vm_cluster_id=vm_cluster_id,
            vm_retention_time=vm_retention_time,
        )
