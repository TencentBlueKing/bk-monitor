"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings
from django.utils.datetime_safe import datetime

from apm_ebpf.apps import logger
from apm_ebpf.models import ClusterRelation
from bkm_space.api import SpaceApi
from core.errors.bkmonitor.space import SpaceNotFound
from metadata.models.space import Space, SpaceResource
from metadata.models.space.constants import SPACE_UID_HYPHEN, SpaceTypes


class RelationHandler:
    @classmethod
    def find_clusters(cls):
        """
        BCS集群发现（完全基于 Space 和 SpaceResource）
        """
        special_cluster_mapping = cls._get_special_cluster_biz_mapping()

        # 1) 从 BKCI 空间绑定的 BCS 资源中拿项目维度（cluster_id 等）
        bcs_resources = list(
            SpaceResource.objects.filter(
                space_type_id=SpaceTypes.BKCI.value,
                resource_type=SpaceTypes.BCS.value,
            ).values("space_id", "dimension_values")
        )
        project_codes = list({r["space_id"] for r in bcs_resources})
        # 2) project_code(space_id) -> project_id(space_code)
        project_code_to_project_id = {
            i["space_id"]: i["space_code"]
            for i in Space.objects.filter(
                space_type_id=SpaceTypes.BKCI.value,
                space_id__in=project_codes,
            ).values("space_id", "space_code")
        }
        logger.info(f"[RelationHandler] found: {len(project_codes)} bkci projects from metadata")

        # 3) project_code -> 关联 BKCC 业务（related_bk_biz_id），一个 project_code 只关联一个业务
        project_code_to_related_biz_id = {}
        for item in SpaceResource.objects.filter(
            space_type_id=SpaceTypes.BKCI.value,
            resource_type=SpaceTypes.BKCC.value,
            space_id__in=project_codes,
        ).values("space_id", "resource_id"):
            project_code = item["space_id"]
            resource_id = item["resource_id"]
            if not resource_id:
                continue
            project_code_to_related_biz_id[project_code] = str(resource_id)

        # 4) 组装目标关系键:
        #    (related_bk_biz_id, bk_biz_id, project_id, cluster_id)
        #    其中 bk_biz_id 既包含 BKCC 自身，也包含 BKCI 空间对应的负数业务ID
        desired_keys = set()
        for resource in bcs_resources:
            project_code = resource["space_id"]
            project_id = project_code_to_project_id.get(project_code)
            related_biz_id = project_code_to_related_biz_id.get(project_code)
            if not project_id or not related_biz_id:
                continue

            space_biz_id = cls._get_cluster_bk_biz_id(project_code)

            # dimension_values 中每个元素可对应一个集群
            for dimension in resource["dimension_values"] or []:
                cluster_id = dimension.get("cluster_id")
                if not cluster_id:
                    continue
                current_related_biz_id = related_biz_id
                # 如果 cluster_id 在特殊映射中，则使用特殊映射
                if cluster_id in special_cluster_mapping:
                    current_related_biz_id = special_cluster_mapping[cluster_id]

                # 关系一：集群 <-> 业务
                desired_keys.add((str(current_related_biz_id), str(current_related_biz_id), project_id, cluster_id))
                if space_biz_id:
                    # 关系二：集群 <-> 容器项目空间（负数业务ID）
                    desired_keys.add((str(current_related_biz_id), str(space_biz_id), project_id, cluster_id))

        # 5) 与现存关系做差集，计算增删改
        existing_relations = list(
            ClusterRelation.objects.values("id", "related_bk_biz_id", "bk_biz_id", "project_id", "cluster_id")
        )
        existing_mapping = {}
        for relation in existing_relations:
            key = (
                str(relation["related_bk_biz_id"]),
                str(relation["bk_biz_id"]),
                relation["project_id"],
                relation["cluster_id"],
            )
            existing_mapping.setdefault(key, []).append(relation["id"])

        add_keys = list(desired_keys - set(existing_mapping.keys()))
        update_ids = []
        delete_ids = []
        for key, ids in existing_mapping.items():
            if key in desired_keys:
                update_ids.extend(ids)
            else:
                delete_ids.extend(ids)

        ClusterRelation.objects.filter(id__in=update_ids).update(last_check_time=datetime.now())
        _, c = ClusterRelation.objects.filter(id__in=delete_ids).delete()
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
    def _get_special_cluster_biz_mapping(cls):
        mapping = {}
        if not settings.DEBUGGING_BCS_CLUSTER_ID_MAPPING_BIZ_ID:
            return mapping
        for item in settings.DEBUGGING_BCS_CLUSTER_ID_MAPPING_BIZ_ID.split(","):
            pair = item.split(":")
            if len(pair) != 2:
                continue
            mapping[pair[0]] = pair[1]
        return mapping

    @classmethod
    def list_biz_ids(cls, cluster_id):
        """
        根据集群ID获取关联的业务ID列表
        """
        return list(
            ClusterRelation.objects.filter(cluster_id=cluster_id).values_list("bk_biz_id", flat=True).distinct()
        )
