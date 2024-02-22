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
import datetime

from alarm_backends.service.scheduler.app import app
from apm_ebpf.apps import logger
from apm_ebpf.handlers.deepflow import DeepflowHandler, DeepflowInstaller
from apm_ebpf.handlers.relation import RelationHandler
from apm_ebpf.models import ClusterRelation


@app.task(ignore_result=True, queue="celery_cron")
def install_grafana():
    """
    为有效集群安装grafana仪表盘
    """
    logger.info(f"[GrafanaInstaller] start at {datetime.datetime.now()}")
    DeepflowHandler.install_grafana()
    logger.info(f"[GrafanaInstaller] end at {datetime.datetime.now()}")


def ebpf_discover_cron():
    """
    定时寻找安装DeepFlow的集群
    """
    logger.info(f"[ebpf_discover_cron] start")

    cluster_ids = ClusterRelation.all_cluster_ids()
    logger.info(f"[ebpf_discover_cron] start to discover deepflow in {len(cluster_ids)} clusters")
    for cluster_id in cluster_ids:
        DeepflowInstaller(cluster_id).check_installed()

    install_grafana.delay()
    logger.info(f"[ebpf_discover_cron] end")


def cluster_discover_cron():
    """
    定时发现所有集群
    """
    RelationHandler.find_clusters()
    logger.info(f"[cluster_discover_cron] end.")
