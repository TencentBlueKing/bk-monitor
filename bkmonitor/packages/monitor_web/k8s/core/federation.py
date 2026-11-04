"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations under the License.
"""

from collections import defaultdict
from dataclasses import dataclass

from django.db.models import Q

from bkmonitor.models import BCSCluster
from bkmonitor.utils.kubernetes import BcsClusterType
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from core.drf_resource import api
from metadata.models import BcsFederalClusterInfo

NAMESPACED_RESOURCES = frozenset({"namespace", "workload", "pod", "container", "ingress", "service"})


@dataclass(frozen=True)
class FederatedResourceScope:
    resources: Q
    history_namespaces: tuple[str, ...] = ()


def get_federated_resource_scope(bk_biz_id: int, bcs_cluster_id: str) -> FederatedResourceScope | None:
    """Return a resource scope for a federation proxy, or None for an ordinary cluster."""
    tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
    members = dict(
        BcsFederalClusterInfo.objects.filter(
            bk_tenant_id=tenant_id, fed_cluster_id=bcs_cluster_id, is_deleted=False
        ).values_list("sub_cluster_id", "fed_namespaces")
    )
    if not members:
        return None

    clusters = BCSCluster.objects.filter(bk_tenant_id=tenant_id, bcs_cluster_id__in=[bcs_cluster_id, *members])
    scope = Q(pk__in=[])
    space_clusters = None
    if bk_biz_id < 0:
        space_clusters = api.kubernetes.get_cluster_info_from_bcs_space(bk_biz_id=bk_biz_id)
        if bcs_cluster_id not in space_clusters:
            return FederatedResourceScope(scope)
    elif bk_biz_id > 0:
        clusters = clusters.filter(bk_biz_id=bk_biz_id)
    else:
        return FederatedResourceScope(scope)

    visible_clusters = dict(clusters.values_list("bcs_cluster_id", "bk_biz_id"))
    if bcs_cluster_id not in visible_clusters:
        return FederatedResourceScope(scope)

    # Members with identical effective namespace lists can share one SQL predicate.
    members_by_namespaces = defaultdict(list)
    visible_namespaces = set()
    hidden_namespaces = set()
    for member_id, namespaces in members.items():
        member_namespaces = {namespace for namespace in namespaces or () if namespace}
        if member_id not in visible_clusters:
            hidden_namespaces.update(member_namespaces)
            continue
        namespaces = member_namespaces.copy()
        if space_clusters is not None:
            if member_id not in space_clusters:
                hidden_namespaces.update(member_namespaces)
                continue
            for cluster_id in (bcs_cluster_id, member_id):
                cluster = space_clusters[cluster_id]
                if cluster["cluster_type"] == BcsClusterType.SHARED:
                    namespaces.intersection_update(cluster["namespace_list"])
        if namespaces:
            members_by_namespaces[(visible_clusters[member_id], tuple(sorted(namespaces)))].append(member_id)
        visible_namespaces.update(namespaces)
        hidden_namespaces.update(member_namespaces - namespaces)

    for (owner_biz_id, namespaces), member_ids in members_by_namespaces.items():
        scope |= Q(bk_biz_id=owner_biz_id, bcs_cluster_id__in=member_ids, namespace__in=namespaces)
    # Proxy metrics no longer carry the original cluster ID. Include history only
    # when all members contributing to a namespace are visible in this space.
    return FederatedResourceScope(scope, tuple(sorted(visible_namespaces - hidden_namespaces)))
