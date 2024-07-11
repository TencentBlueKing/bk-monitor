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

from typing import List, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from metadata import models
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis


class Command(BaseCommand):
    help = "switch vm cluster"

    def handle(self, *args, **options):
        data = self.validate(**options)
        objs, vm_cluster_id = data["objs"], data["dst_vm_cluster_id"]
        updated_count = objs.count()
        objs.update(vm_cluster_id=vm_cluster_id)
        # 更新路由信息
        SpaceTableIDRedis().push_table_id_detail(table_id_list=[obj.result_table_id for obj in objs], is_publish=True)
        self.stdout.write(self.style.SUCCESS(f"switch vm cluster success, {updated_count} records updated."))

    def add_arguments(self, parser):
        parser.add_argument("--src_vm_names", required=False, help="要切换的 vm 集群名称，多个以半角逗号分隔")
        parser.add_argument("--src_vm_ids", required=False, help="要切换的 vm 集群 id，多个以半角逗号分隔")
        parser.add_argument("--data_ids", required=False, help="要切换的数据源ID，多个以半角逗号分隔")
        parser.add_argument("--dst_vm_id", required=False, help="目标 vm 集群 id")
        parser.add_argument("--dst_vm_name", required=False, help="目标 vm 集群 id")

    def validate(self, **options):
        """校验参数存在"""
        src_vm_names, src_vm_ids, data_ids = (
            options.get("src_vm_names"),
            options.get("src_vm_ids"),
            options.get("data_ids"),
        )
        dst_vm_id, dst_vm_name = options.get("dst_vm_id"), options.get("dst_vm_name")
        if not (src_vm_names or src_vm_ids or data_ids):
            raise CommandError("need one params[src_vm_names]|[src_vm_ids]|[data_ids]")
        if not (dst_vm_id or dst_vm_name):
            raise CommandError("need one params[dst_vm_id]|[dst_vm_name]")
        dst_vm_cluster_id = self.get_dst_vm_cluster_id(dst_vm_id, dst_vm_name)
        # 过滤对应的 vm 记录
        objs = self.filter_vm_records(src_vm_names=src_vm_names, src_vm_ids=src_vm_ids, data_ids=data_ids)
        if not objs:
            raise CommandError("not found record by src_vm_names or src_vm_ids or data_ids")
        return {
            "objs": objs,
            "dst_vm_cluster_id": dst_vm_cluster_id,
        }

    def filter_vm_records(
        self, src_vm_names: Optional[str] = None, src_vm_ids: Optional[str] = None, data_ids: Optional[str] = None
    ) -> List:
        """过滤集群或者数据源对应的结果表记录"""
        # 按照参数场景进行操作，返回创建的vm记录
        if data_ids:
            data_ids = data_ids.split(",")
            table_id_list = list(
                models.DataSourceResultTable.objects.filter(bk_data_id__in=data_ids).values_list("table_id", flat=True)
            )
            return models.AccessVMRecord.objects.filter(result_table_id__in=table_id_list)

        if src_vm_ids:
            src_vm_ids = [int(id) for id in src_vm_ids.split(",")]
            return models.AccessVMRecord.objects.filter(vm_cluster_id__in=src_vm_ids)

        src_vm_names = src_vm_names.split(",")
        cluster_id_list = models.ClusterInfo.objects.filter(cluster_name__in=src_vm_names).values_list(
            "cluster_id", flat=True
        )
        return models.AccessVMRecord.objects.filter(vm_cluster_id__in=cluster_id_list)

    def get_dst_vm_cluster_id(self, dst_vm_id: Optional[str] = None, dst_vm_name: Optional[str] = None) -> int:
        """过滤要切换的vm集群ID"""
        filter_params = Q()
        if dst_vm_id:
            filter_params |= Q(cluster_id=int(dst_vm_id))
        if dst_vm_name:
            filter_params |= Q(cluster_name=dst_vm_name)
        obj = models.ClusterInfo.objects.filter(filter_params).first()
        if not obj:
            raise CommandError("not found record by dst_vm_id or dst_vm_name")
        return obj.cluster_id
