# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from api.bcs.tasks import (
    sync_bcs_cluster_to_db,
    sync_bcs_node,
    sync_bcs_pod,
    sync_bcs_pod_monitor,
    sync_bcs_service,
    sync_bcs_service_monitor,
    sync_bcs_workload,
)

"""
主动同步指定集群信息

python manage.py sync_bcs_to_db --bcs_cluster_id=BCS-K8S-00000
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--bcs_cluster_id", help="bcs cluster id")

    def handle(self, bcs_cluster_id, **kwargs):
        print("start sync cluster list to db")
        # 同步全量集群列表
        sync_bcs_cluster_to_db()
        print(f"[workload] start sync {bcs_cluster_id} to db")
        sync_bcs_workload(bcs_cluster_id)
        print(f"[service] start sync {bcs_cluster_id} to db")
        sync_bcs_service(bcs_cluster_id)
        print(f"[pod&container] start sync {bcs_cluster_id} to db")
        sync_bcs_pod(bcs_cluster_id)
        print(f"[node] start sync {bcs_cluster_id} to db")
        sync_bcs_node(bcs_cluster_id)
        print(f"[service monitor] start sync {bcs_cluster_id} to db")
        sync_bcs_service_monitor(bcs_cluster_id)
        print(f"[pod monitor] start sync {bcs_cluster_id} to db")
        sync_bcs_pod_monitor(bcs_cluster_id)
        print(f"finish sync {bcs_cluster_id} to db")
