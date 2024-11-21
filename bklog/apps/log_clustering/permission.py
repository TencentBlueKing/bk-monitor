from typing import List

from django.conf import settings

from apps.iam.handlers.actions import ActionMeta
from apps.iam.handlers.drf import InstanceActionPermission
from apps.iam.handlers.resources import ResourceMeta
from apps.log_clustering.models import ClusteringConfig


class PatternPermission(InstanceActionPermission):
    """
    关联其他资源的权限检查
    """

    def __init__(self, actions: List[ActionMeta], resource_meta: ResourceMeta):
        super(PatternPermission, self).__init__(actions, resource_meta)

    def has_permission(self, request, view):
        # 跳过权限校验
        if settings.IGNORE_IAM_PERMISSION:
            return True
        instance_id = view.kwargs[self.get_look_url_kwarg(view)]
        if instance_id.startswith("flow-"):
            # 通过 dataflow id 查询 pattern
            flow_id = instance_id[len("flow-") :]
            clustering_config = ClusteringConfig.get_by_flow_id(flow_id)
            instance_id = clustering_config.index_set_id
        resource = self.resource_meta.create_instance(instance_id)
        self.resources = [resource]
        return super(InstanceActionPermission, self).has_permission(request, view)
