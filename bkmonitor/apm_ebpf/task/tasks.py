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
from apm_ebpf.handlers.bk_collector import BkCollectorInstaller
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
    定时寻找安装 DeepFlow / bk-collector的集群
    """
    logger.info(f"[discover_cron] start")

    cluster_mapping = ClusterRelation.all_cluster_ids()
    logger.info(f"[discover_cron] start to discover deepflow and bk-collector in {len(cluster_mapping)} clusters")

    deepflow_checker = DeepflowInstaller.generator()
    collector_checker = BkCollectorInstaller.generator()
    for cluster_id, related_bk_biz_ids in cluster_mapping.items():
        related_bk_biz_ids = list(related_bk_biz_ids)
        next(deepflow_checker)(cluster_id=cluster_id).check_installed()
        next(collector_checker)(cluster_id=cluster_id, related_bk_biz_ids=related_bk_biz_ids).check_installed()

    # [1] 为安装了 deepflow 的集群安装仪表盘
    install_grafana.delay()
    # [2] 为安装了 bk-collector 的集群创建默认应用 && 下发配置 !!!具体实现交给 apm.tasks 模块处理
    logger.info(f"[discover_cron] end")


def cluster_discover_cron():
    """
    定时发现所有集群
    """
    RelationHandler.find_clusters()
    logger.info(f"[cluster_discover_cron] end.")
