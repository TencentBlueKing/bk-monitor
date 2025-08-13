"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from django.db import models

from metadata.models.data_link.constants import DataLinkResourceStatus
from metadata.models.storage import ClusterInfo

logger = logging.getLogger("metadata")


# ------------------------------------------------------ #
# ------------------ BkBase相关暂不修改 ------------------ #
# ------------------------------------------------------ #


class BkBaseResultTable(models.Model):
    """
    计算平台结果表
    data_link_name作为唯一主键，
    Note：新接入的链路，data_link_name和bkbase_data_name相同，都是根据数据源的data_name拼接而成，V3->V4迁移场景下不同
    除bkbase_table_id外，其余均为声明式字段，bkbase_table_id相当于链路status的一部分
    """

    STATUS_CHOICES = (
        (DataLinkResourceStatus.INITIALIZING.value, "初始化中"),
        (DataLinkResourceStatus.CREATING.value, "创建中"),
        (DataLinkResourceStatus.PENDING.value, "等待中"),
        (DataLinkResourceStatus.OK.value, "已就绪"),
    )

    # 在V3->V4迁移场景中，data_link_name和bkbase_data_name不一定相同，故需设计为分别全局唯一
    data_link_name = models.CharField(
        verbose_name="链路名称", max_length=255, primary_key=True, db_index=True, unique=True
    )
    bkbase_data_name = models.CharField(
        verbose_name="计算平台数据源名称", max_length=128, unique=True, null=True, blank=True
    )
    storage_type = models.CharField(
        "存储类型", max_length=32, choices=ClusterInfo.CLUSTER_TYPE_CHOICES, default=ClusterInfo.TYPE_VM
    )  # 存储类型
    monitor_table_id = models.CharField(verbose_name="监控平台结果表ID", max_length=128)

    # 回填信息
    storage_cluster_id = models.IntegerField(verbose_name="存储集群ID", null=True, blank=True)
    create_time = models.DateTimeField(verbose_name="创建时间", auto_now_add=True)
    last_modify_time = models.DateTimeField(verbose_name="最后更新时间", auto_now=True)
    status = models.CharField(
        verbose_name="状态", max_length=64, choices=STATUS_CHOICES, default=DataLinkResourceStatus.INITIALIZING.value
    )

    # 计算平台结果表ID，只有在实际创建后才进行赋值
    bkbase_table_id = models.CharField(verbose_name="计算平台结果表ID", max_length=128, null=True, blank=True)
    # 计算平台结果表名称，通常作为databus、vmstorage、vmstoragebinding等的name
    bkbase_rt_name = models.CharField(
        verbose_name="计算平台结果表名称", max_length=128, unique=True, null=True, blank=True
    )
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")

    class Meta:
        verbose_name = "接入计算平台记录表"
        verbose_name_plural = "接入计算平台记录表"

    @property
    def component_id(self):
        """
        计算平台指标查询用ID
        """
        from metadata.models.data_link.data_link_configs import DataBusConfig

        try:
            databus_config_ins = DataBusConfig.objects.get(name=self.bkbase_rt_name)
            return databus_config_ins.namespace + "-" + databus_config_ins.name
        except DataBusConfig.DoesNotExist:
            logger.error("data_link->[%s],do not have databus->[%s]", self.data_link_name, self.bkbase_rt_name)
            return None
