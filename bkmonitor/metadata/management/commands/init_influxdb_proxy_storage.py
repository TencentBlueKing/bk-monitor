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

from typing import Dict, Optional

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.db.models.query import QuerySet

from metadata import models


class Command(BaseCommand):
    """初始数据

    通过路由表、集群表组装关联信息
    """

    DEFAULT_SERVICE_NAME = "bkmonitorv3"

    def handle(self, *args, **options):
        # 如果存在记录，则认为已经初始化，不需要再次创建
        if models.InfluxDBProxyStorage.objects.first():
            self.stdout.write("records of InfluxDBProxyStorage has created")
            return
        # 查询路由表
        proxy_storage_list = models.InfluxDBStorage.objects.values(
            "storage_cluster_id", "proxy_cluster_name"
        ).distinct()
        if not proxy_storage_list:
            self.stdout.write("result table router is null")
            return
        # 查询集群信息
        proxy_cluster_list = models.ClusterInfo.objects.filter(cluster_type="influxdb").values(
            "cluster_id", "domain_name"
        )
        # 组装数据
        proxy_storage_map = {}
        for ps in proxy_storage_list:
            proxy_storage_map.setdefault(ps["storage_cluster_id"], []).append(ps["proxy_cluster_name"])

        # 创建记录
        created = self._bulk_create_proxy_storage(proxy_cluster_list, proxy_storage_map)
        self.stdout.write(self.style.SUCCESS("init influxdb proxy storage successfully"))

        # 更新路由表
        self._update_router_field(created)
        self.stdout.write(self.style.SUCCESS("update influxdb router field successfully"))

        # 增加一次推送
        models.InfluxDBProxyStorage.push()

        self.stdout.write(self.style.SUCCESS("init data successfully"))

    def _refine_service_name(self, domain_name: str) -> str:
        """获取 service name

        默认为以半角`.`分割后的第一个元素
        """
        splitted_data = domain_name.split(".")
        # 分割后的数组元素，至少有2个；如果小于2个，则为默认值
        if len(splitted_data) < 2:
            self.stdout.write(f"domain not split by '.', domain: {domain_name}")
            return self.DEFAULT_SERVICE_NAME

        # 否则，取第一个作为 service name
        return splitted_data[1]

    def _bulk_create_proxy_storage(self, proxy_cluster_list: QuerySet, proxy_storage_map: Dict) -> bool:
        record_list = []
        for pc in proxy_cluster_list:
            cluster_id = pc["cluster_id"]
            storage_cluster_name_list = proxy_storage_map.get(cluster_id)
            if not storage_cluster_name_list:
                self.stdout.write(f"cluster: {cluster_id}({pc['domain_name']}) not used")
                continue
            for c in storage_cluster_name_list:
                record_list.append(
                    models.InfluxDBProxyStorage(
                        creator="system",
                        updater="system",
                        proxy_cluster_id=cluster_id,
                        service_name=self._refine_service_name(pc["domain_name"]),
                        instance_cluster_name=c,
                    )
                )
        # 批量创建记录
        models.InfluxDBProxyStorage.objects.bulk_create(record_list)
        # 设置默认记录
        storage_cluster_id = models.ClusterInfo.objects.get(
            cluster_type=models.ClusterInfo.TYPE_INFLUXDB, is_default_cluster=True
        ).cluster_id
        influxdb_proxy_storage = models.InfluxDBProxyStorage.objects.filter(
            Q(instance_cluster_name=settings.INFLUXDB_DEFAULT_PROXY_CLUSTER_NAME)
            | Q(instance_cluster_name=settings.INFLUXDB_DEFAULT_PROXY_CLUSTER_NAME_FOR_K8S),
            proxy_cluster_id=storage_cluster_id,
        )
        # 默认值
        if not influxdb_proxy_storage:
            self.stderr.write(
                f"default record create failed, proxy_cluster_id: {storage_cluster_id},"
                f"instance_cluster_name: {settings.INFLUXDB_DEFAULT_PROXY_CLUSTER_NAME}"
            )
        influxdb_proxy_storage.update(is_default=True)
        return True

    def _update_router_field(self, created: Optional[bool] = True):
        # 如果`influxdb_proxy_storage`没有创建，则跳过
        if not created:
            return

        proxy_storages = models.InfluxDBProxyStorage.objects.values("id", "proxy_cluster_id", "instance_cluster_name")
        proxy_storage_map = {
            (f"{ps['proxy_cluster_id']}", f"{ps['instance_cluster_name']}"): ps["id"] for ps in proxy_storages
        }
        for ps, id in proxy_storage_map.items():
            router = models.InfluxDBStorage.objects.filter(storage_cluster_id=ps[0], proxy_cluster_name=ps[1])
            if not router.exists():
                self.stderr.write(f"proxy_cluster_id: {ps[0]}, instance_cluster: {ps[1]} not found router")
                continue
            router.update(influxdb_proxy_storage_id=id)
