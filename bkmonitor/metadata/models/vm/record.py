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
import logging
from typing import Dict, List, Optional

from django.db import models
from django.db.models.fields import DateTimeField

from metadata.models.common import BaseModel
from metadata.models.vm.constants import VM_RETENTION_TIME
from metadata.models.vm.managers import SpaceVMInfoManager

logger = logging.getLogger("metadata")


class AccessVMRecord(models.Model):
    BCS_CLUSTER_K8S = "bcs_cluster_k8s"
    BCS_CLUSTER_CUSTOM = "bcs_cluster_custom"
    USER_CUSTOM = "user_custom"
    ACCESS_VM = "access_vm"

    DATA_TYPE_CHOICES = (
        (BCS_CLUSTER_K8S, "BCS 集群k8s指标"),
        (BCS_CLUSTER_CUSTOM, "BCS 集群自定义指标"),
        (USER_CUSTOM, "用户自定义指标"),
        (ACCESS_VM, "接入 VM 指标"),
    )

    data_type = models.CharField("数据类型", max_length=32, choices=DATA_TYPE_CHOICES, default=BCS_CLUSTER_K8S)
    result_table_id = models.CharField("结果表ID", max_length=128, help_text="结果表ID")
    # 仅当 data_type 为bcs_cluster时才有值
    bcs_cluster_id = models.CharField("bcs集群ID", max_length=32, null=True, blank=True, help_text="bcs集群ID")
    storage_cluster_id = models.IntegerField("对接使用的storage域名", null=True, blank=True, help_text="对接使用的集群ID")
    # vm 对应的集群ID
    vm_cluster_id = models.IntegerField("集群ID", null=True, blank=True, help_text="因为查询 vm 集群已经统一，不需要再单独记录")
    bk_base_data_id = models.IntegerField("计算平台数据ID", help_text="计算平台数据ID")
    bk_base_data_name = models.CharField("计算平台数据名称", max_length=64, help_text="计算平台数据名称", default="")
    vm_result_table_id = models.CharField("VM 结果表rt", max_length=64, help_text="VM 结果表rt")
    remark = models.CharField("接入备注", max_length=256, null=True, blank=True, help_text="接入备注")

    class Meta:
        verbose_name = "接入VM记录表"
        verbose_name_plural = "接入VM记录表"

    @classmethod
    def refresh_vm_router(cls, table_id: Optional[str] = None):
        """刷新查询 vm 需要的路由"""
        logger.info("start refresh vm router")
        # 过滤到数据
        objs = cls.objects.values(
            "result_table_id", "storage_cluster_id", "vm_cluster_id", "bk_base_data_id", "vm_result_table_id"
        )
        if table_id is not None:
            objs = objs.filter(result_table_id=table_id)

        from metadata.models.constants import (
            INFLUXDB_KEY_PREFIX,
            QUERY_VM_STORAGE_ROUTER_KEY,
        )
        from metadata.models.influxdb_cluster import InfluxDBTool

        for obj in objs:
            table_id = obj["result_table_id"]
            try:
                db, measurement = table_id.split(".")
            except Exception:
                logger.error("table_id: %s not split by '.'", table_id)
                db, measurement = "", ""
            # 组装数据
            val = {
                "storageID": str(obj["storage_cluster_id"]),
                "table_id": table_id,
                "clusterName": "",
                "tagsKey": [],
                "db": db,
                "vm_rt": obj["vm_result_table_id"],
                "measurement": measurement,
                "retention_policies": {
                    "autogen": {
                        "is_default": True,
                        "resolution": 0,
                    },
                },
            }

            # 更新数据
            InfluxDBTool.push_to_redis(QUERY_VM_STORAGE_ROUTER_KEY, table_id, json.dumps(val), is_publish=False)
        # publish
        from metadata.utils.redis_tools import RedisTools

        RedisTools.publish(INFLUXDB_KEY_PREFIX, [QUERY_VM_STORAGE_ROUTER_KEY])

        logger.info("refresh vm router successfully")


class SpaceVMInfo(BaseModel):
    """空间接入 vm 信息"""

    space_type = models.CharField("空间类型英文名称", max_length=64)
    space_id = models.CharField("空间英文名称", max_length=128)
    vm_cluster_id = models.IntegerField("集群ID", help_text="关联 clusterinfo 表中存储的 vm 集群信息")
    vm_retention_time = models.CharField("保存时间", max_length=16, null=True, blank=True, default=VM_RETENTION_TIME)
    status = models.CharField("状态", max_length=16, null=True, blank=True)

    objects = SpaceVMInfoManager()

    class Meta:
        verbose_name = "空间接入 VM 信息"
        verbose_name_plural = "空间接入 VM 信息"

    def to_dict(self, fields: Optional[List] = None, exclude: Optional[List] = None) -> Dict:
        data = {}
        for f in self._meta.concrete_fields + self._meta.many_to_many:
            value = f.value_from_object(self)
            # 属性存在
            if fields and f.name not in fields:
                continue
            # 排除的属性
            if exclude and f.name in exclude:
                continue
            # 时间转换
            if isinstance(f, DateTimeField):
                value = value.strftime("%Y-%m-%d %H:%M:%S") if value else None

            data[f.name] = value

        return data
