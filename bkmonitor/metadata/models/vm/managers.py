# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Optional

from django.db import models
from django.db.transaction import atomic

from metadata import config
from metadata.models.storage import ClusterInfo
from metadata.models.vm.constants import VM_RETENTION_TIME


class SpaceVMInfoManager(models.Manager):
    @atomic(config.DATABASE_CONNECTION_NAME)
    def create_record(
        self,
        space_type: str,
        space_id: str,
        vm_cluster_id: Optional[int] = None,
        vm_retention_time: Optional[str] = VM_RETENTION_TIME,
    ) -> models.Model:
        """创建记录

        :param space_type: 空间类型
        :param space_id: 空间 ID
        :param vm_cluster_id: vm 集群 ID
        :param vm_retention_time: 保留时间
        """
        # vm 集群 ID 为空时，获取默认的 vm 存储集群
        if not vm_cluster_id:
            vm_cluster_objs = ClusterInfo.objects.filter(cluster_type=ClusterInfo.TYPE_VM, is_default_cluster=True)
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
