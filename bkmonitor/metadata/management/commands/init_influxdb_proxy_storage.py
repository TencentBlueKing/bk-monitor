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

import json
from typing import Dict, Optional

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.db.models.query import QuerySet
from django.db.utils import IntegrityError

from metadata import models


class Command(BaseCommand):
    """初始数据

    通过路由表、集群表组装关联信息
    """

    DEFAULT_SERVICE_NAME = "bkmonitorv3"

    def handle(self, *args, **options):
        # 查询路由表，忽略掉已经存在数据的记录
        proxy_storage_list = list(
            models.InfluxDBStorage.objects.filter(influxdb_proxy_storage_id=None)
            .values("storage_cluster_id", "proxy_cluster_name", "table_id")
            .distinct()
        )
        if not proxy_storage_list:
            self.stdout.write("not found null influxdb_proxy_storage_id records!")
            return
        # 查询集群信息
        proxy_cluster_list = models.ClusterInfo.objects.filter(cluster_type="influxdb").values(
            "cluster_id", "domain_name"
        )

        # 已经存在时，则忽略，否则创建
        # 过滤出已经存在的proxy和集群的关联关系的记录
        exist_data = [
            (obj["proxy_cluster_id"], obj["instance_cluster_name"])
            for obj in models.InfluxDBProxyStorage.objects.values("proxy_cluster_id", "instance_cluster_name")
        ]

        # 组装数据
        proxy_storage_map, table_id_list = {}, []
        for ps in proxy_storage_list:
            # 如果已经存在，则忽略
            if (ps["storage_cluster_id"], ps["proxy_cluster_name"]) in exist_data:
                table_id_list.append(ps["table_id"])
                continue
            proxy_storage_map.setdefault(ps["storage_cluster_id"], set()).add(ps["proxy_cluster_name"])

        if not proxy_storage_map:
            # 增加一个指定结果表的更新
            if table_id_list:
                self.stdout.write(f"table_id_list: {json.dumps(table_id_list)} need update proxy id")
                self._update_router_by_table_id(table_id_list=table_id_list)
            self.stdout.write("no new influxdb proxy and cluster create!")
            return

        # 创建记录
        try:
            self._bulk_create_proxy_storage(proxy_cluster_list, proxy_storage_map)
            self.stdout.write(self.style.SUCCESS("init influxdb proxy storage successfully"))
        except IntegrityError as e:
            self.stderr.write(f"bulk create proxy storage error, {e}")
            return

        # 更新路由表
        self._update_router_field()
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

    def _update_router_field(self):
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

    def _update_router_by_table_id(self, table_id_list: Optional[str] = None):
        """通过结果表更新路由"""
        if not table_id_list:
            return
        # 组装已经存在的 proxy 和集群实例的关系
        proxy_storage_map = {
            (ps["proxy_cluster_id"], ps["instance_cluster_name"]): ps["id"]
            for ps in models.InfluxDBProxyStorage.objects.values("id", "proxy_cluster_id", "instance_cluster_name")
        }
        objs = models.InfluxDBStorage.objects.filter(table_id__in=table_id_list)
        for obj in objs:
            key = (obj.storage_cluster_id, obj.proxy_cluster_name)
            influxdb_proxy_storage_id = proxy_storage_map.get(key)
            if not influxdb_proxy_storage_id:
                self.stdout.write(
                    "table_id: {}, storage_cluster_id: {}, cluster_id: {} not found".format(
                        obj.table_id, obj.storage_cluster_id, obj.proxy_cluster_name
                    )
                )
                continue
            obj.influxdb_proxy_storage_id = influxdb_proxy_storage_id
            obj.save(update_fields=["influxdb_proxy_storage_id"])
