# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from collections import defaultdict

from django.db import models

from apm_ebpf.constants import WorkloadType


class DeepflowWorkload(models.Model):
    bk_biz_id = models.IntegerField("业务id")
    cluster_id = models.CharField("集群ID", max_length=128)
    namespace = models.CharField("命名空间", max_length=255)
    name = models.CharField("名称", max_length=255)
    # content格式为特定内容, 需要通过 @WorkloadContent 进行访问
    content = models.JSONField("特定配置内容")
    type = models.CharField("workload类型", max_length=32, choices=WorkloadType.choices)
    is_normal = models.BooleanField("是否正常")
    last_check_time = models.DateTimeField("最后检查日期")
    create_at = models.DateTimeField("创建时间", auto_now_add=True)
    update_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "deepflow集群管理表"


class ClusterRelation(models.Model):
    related_bk_biz_id = models.IntegerField("集群关联的BKCC业务id")
    bk_biz_id = models.IntegerField("监控的容器项目业务ID 可能为负数")
    cluster_id = models.CharField("集群ID", max_length=128)
    project_id = models.CharField("BCS项目ID", max_length=128)
    last_check_time = models.DateTimeField("最近检查日期")
    create_at = models.DateTimeField("创建时间", auto_now_add=True)
    update_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "BCS集群关联信息表"

    @classmethod
    def all_cluster_ids(cls):
        res = defaultdict(set)
        for i in ClusterRelation.objects.all():
            # 正常来说集群只会关联一个 CC 业务 这里写松一点
            res[i.cluster_id].add(i.related_bk_biz_id)
        return res


class DeepflowDashboardRecord(models.Model):
    bk_biz_id = models.IntegerField("监控的容器项目业务ID 可能为负数")
    name = models.CharField("仪表盘名称", max_length=526)

    class Meta:
        verbose_name = "deepflow仪表盘安装记录"
