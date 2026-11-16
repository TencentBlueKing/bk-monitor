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

from django.db.models import Q

from bkmonitor.models import BCSCluster
from bkmonitor.utils.kubernetes import BcsClusterType
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from core.drf_resource import api
from metadata.models import BcsFederalClusterInfo

NAMESPACED_RESOURCES = frozenset({"namespace", "workload", "pod", "container", "ingress", "service"})


def get_federated_resource_scope(bk_biz_id: int, bcs_cluster_id: str) -> Q | None:
    """Return a resource scope for a federation proxy, or None for an ordinary cluster."""
    tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
    members = dict(
        BcsFederalClusterInfo.objects.filter(
            bk_tenant_id=tenant_id, fed_cluster_id=bcs_cluster_id, is_deleted=False
        ).values_list("sub_cluster_id", "fed_namespaces")
    )
    if not members:
        return None

    clusters = dict(
        BCSCluster.objects.filter(bk_tenant_id=tenant_id, bcs_cluster_id__in=[bcs_cluster_id, *members]).values_list(
            "bcs_cluster_id", "bk_biz_id"
        )
    )
    scope = Q(pk__in=[])
    if bcs_cluster_id not in clusters:
        return scope

    authorized_namespaces = None
    if bk_biz_id < 0:
        space_clusters = api.kubernetes.get_cluster_info_from_bcs_space(bk_biz_id=bk_biz_id)
        if bcs_cluster_id not in space_clusters:
            return scope
        proxy = space_clusters[bcs_cluster_id]
        if proxy["cluster_type"] == BcsClusterType.SHARED:
            authorized_namespaces = set(proxy["namespace_list"])
    elif bk_biz_id <= 0 or clusters[bcs_cluster_id] != bk_biz_id:
        return scope

    # Access is granted through the proxy. A member need not be directly accessible
    # in this business or project; its owner is used only to locate physical rows.
    # Members with identical effective namespace lists can share one SQL predicate.
    members_by_namespaces = defaultdict(list)
    for member_id, namespaces in members.items():
        if member_id not in clusters:
            continue
        namespaces = {namespace for namespace in namespaces or () if namespace}
        if authorized_namespaces is not None:
            namespaces.intersection_update(authorized_namespaces)
        if namespaces:
            members_by_namespaces[(clusters[member_id], tuple(sorted(namespaces)))].append(member_id)

    for (owner_biz_id, namespaces), member_ids in members_by_namespaces.items():
        scope |= Q(bk_biz_id=owner_biz_id, bcs_cluster_id__in=member_ids, namespace__in=namespaces)
    return scope
