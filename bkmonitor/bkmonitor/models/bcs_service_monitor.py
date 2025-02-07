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

from bkmonitor.models import BCSBaseManager, BCSLabel, BCSMonitor
from core.drf_resource import api


class BCSServiceMonitorManager(BCSBaseManager):
    pass


class BCSServiceMonitor(BCSMonitor):
    # 资源复数名
    PLURAL = "ServiceMonitor"
    PLURALS = "servicemonitors"

    labels = models.ManyToManyField(BCSLabel, through="BCSServiceMonitorLabels", through_fields=("resource", "label"))

    objects = BCSServiceMonitorManager()

    class Meta:
        index_together = ["bk_biz_id", "bcs_cluster_id"]

    @classmethod
    def fetch_k8s_monitor_list_by_cluster(cls, params):
        bulk_request_params = [{"bcs_cluster_id": bcs_cluster_id} for bcs_cluster_id in params.keys()]
        api_resources = api.kubernetes.fetch_k8s_service_monitor_list_by_cluster.bulk_request(
            bulk_request_params, ignore_exceptions=True
        )
        return api_resources


class BCSServiceMonitorLabels(models.Model):
    id = models.BigAutoField(primary_key=True)
    resource = models.ForeignKey(BCSServiceMonitor, db_constraint=False, on_delete=models.CASCADE)
    label = models.ForeignKey(BCSLabel, db_constraint=False, on_delete=models.CASCADE)
    bcs_cluster_id = models.CharField(verbose_name="集群ID", max_length=128, db_index=True)
