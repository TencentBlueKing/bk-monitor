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

from django.db import models

from metadata.models.storage import ClusterInfo


class BkBaseResultTable(models.Model):
    """
    计算平台结果表
    """

    data_link_name = models.CharField(verbose_name="链路名称", max_length=255)
    bkbase_data_name = models.CharField(verbose_name="计算平台数据源名称", max_length=128)
    bkbase_table_id = models.IntegerField(verbose_name="计算平台结果表ID", null=True, blank=True)
    storage_type = models.CharField(
        "存储类型", max_length=32, choices=ClusterInfo.CLUSTER_TYPE_CHOICES, default=ClusterInfo.TYPE_VM
    )
    storage_cluster_id = models.CharField("存储集群ID", max_length=32)
    monitor_table_id = models.CharField("监控平台结果表ID", max_length=128)

    class Meta:
        verbose_name = "接入计算平台记录表"
        verbose_name_plural = "接入计算平台记录表"
