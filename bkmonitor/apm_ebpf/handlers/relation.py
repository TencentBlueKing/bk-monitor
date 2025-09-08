"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import itertools
import operator

from django.conf import settings
from django.db.models import Q
from django.utils.datetime_safe import datetime

from apm_ebpf.apps import logger
from apm_ebpf.models import ClusterRelation
from bkm_space.api import SpaceApi
from bkmonitor.utils import group_by
from core.drf_resource import api
from core.errors.bkmonitor.space import SpaceNotFound
from metadata.models.space.constants import SPACE_UID_HYPHEN, SpaceTypes


class RelationHandler:
    @classmethod
    def find_clusters(cls):
        """
        BCS集群发现
        """
        clusters = []
        project_id_mapping = {}
        for tenant in api.bk_login.list_tenant():
            bk_tenant_id = tenant["id"]
            projects = api.bcs.get_projects(kind="k8s", bk_tenant_id=bk_tenant_id)
            project_id_mapping.update(group_by(projects, operator.itemgetter("project_id")))
            clusters.extend(api.bcs_cluster_manager.get_project_k8s_non_shared_clusters(bk_tenant_id=bk_tenant_id))

        cluster_mapping = group_by(clusters, operator.itemgetter("cluster_id"))
        logger.info(f"[RelationHandler] found: {len(cluster_mapping)} k8s clusters")

        # 兼容特殊集群和业务映射配置
        if settings.DEBUGGING_BCS_CLUSTER_ID_MAPPING_BIZ_ID:
            items = settings.DEBUGGING_BCS_CLUSTER_ID_MAPPING_BIZ_ID.split(",")
            for item in items:
                mapping = item.split(":")
                if len(mapping) != 2:
                    continue

                special_cluster_id, special_biz_id = mapping[0], mapping[1]
                if special_cluster_id in cluster_mapping:
                    project_id = cluster_mapping[special_cluster_id][0]["project_id"]
                    cluster_mapping[special_cluster_id] = [
                        {"project_id": project_id, "cluster_id": special_cluster_id, "bk_biz_id": special_biz_id},
                    ]

        add_keys = []
        update_ids = []
        not_exist_ids = []

        for cluster_id, items in cluster_mapping.items():
            exists_mappings = group_by(
                ClusterRelation.objects.filter(cluster_id=cluster_id),
                lambda i: (str(i.related_bk_biz_id), str(i.bk_biz_id), i.project_id, i.cluster_id),
            )

            for item in items:
                # 创建集群<->业务关联 此条件下related_bk_biz_id == bk_biz_id
                biz_key = (str(item["bk_biz_id"]), str(item["bk_biz_id"]), item["project_id"], item["cluster_id"])
                if biz_key in exists_mappings:
                    update_ids.extend([i.id for i in exists_mappings[biz_key]])
                    del exists_mappings[biz_key]
                else:
                    add_keys.append(biz_key)

                # 创建集群<->容器项目关联 此条件下需要获取容器项目的业务id(非space_uid)
                if item["project_id"] in project_id_mapping:
                    space_biz_id = cls._get_cluster_bk_biz_id(
                        project_id_mapping[item["project_id"]][0].get("project_code")
                    )
                    if space_biz_id:
                        space_key = (str(item["bk_biz_id"]), str(space_biz_id), item["project_id"], item["cluster_id"])
                        if space_key in exists_mappings:
                            update_ids.extend([i.id for i in exists_mappings[space_key]])
                            del exists_mappings[space_key]
                        else:
                            add_keys.append(space_key)

            not_exist_ids += [i.id for i in list(itertools.chain(*exists_mappings.values()))]

        ClusterRelation.objects.filter(id__in=update_ids).update(last_check_time=datetime.now())
        _, c = ClusterRelation.objects.filter(Q(id__in=not_exist_ids) | ~Q(id__in=update_ids)).delete()
        ClusterRelation.objects.bulk_create(
            [
                ClusterRelation(
                    related_bk_biz_id=i[0],
                    bk_biz_id=i[1],
                    project_id=i[2],
                    cluster_id=i[3],
                    last_check_time=datetime.now(),
                )
                for i in add_keys
            ]
        )
        logger.info(
            f"[find_cluster] relaton found finished. "
            f"add: {len(add_keys)}, "
            f"update: {len(update_ids)}, "
            f"delete: {sum(c.values())}"
        )

    @classmethod
    def _get_cluster_bk_biz_id(cls, project_code):
        """获取BCS项目在监控创建的容器项目空间的业务id"""

        if not project_code:
            return None

        space_uid = f"{SpaceTypes.BKCI.value}{SPACE_UID_HYPHEN}{project_code}"
        try:
            return SpaceApi.get_space_detail(space_uid=space_uid).bk_biz_id
        except SpaceNotFound as e:
            logger.warning(f"try to get bk_biz_id of project_code: {project_code}, but found: {e}")
            return None

    @classmethod
    def list_biz_ids(cls, cluster_id):
        """
        根据集群ID获取关联的业务ID列表
        """
        return list(
            ClusterRelation.objects.filter(cluster_id=cluster_id).values_list("bk_biz_id", flat=True).distinct()
        )
