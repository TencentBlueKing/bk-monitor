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


import time
from typing import Literal

import pytest
from django.test import TestCase
from django.utils import timezone

from bkmonitor.models import BCSCluster, BCSWorkload

pytestsmark = pytest.mark.django_db


def pytest_configure():
    TestCase.databases = {"default", "monitor_api"}


@pytest.fixture()
def create_bcs_cluster(db):
    BCSCluster(
        bk_biz_id=2,
        bcs_cluster_id="BCS-K8S-00000",
        name="蓝鲸7.0",
        area_name="",
        project_name="",
        environment="正式",
        updated_at=timezone.now(),
        node_count=18,
        cpu_usage_ratio=19.22,
        memory_usage_ratio=65.36,
        disk_usage_ratio=51.45,
        created_at=timezone.now(),
        status="RUNNING",
        monitor_status="success",
        last_synced_at=timezone.now(),
    ).save()


@pytest.fixture()
def create_namespaces():
    namespace_name = [
        "aiops-default",
        "apm-demo",
        "bcs-system",
        "bk-apigateway-dev",
        "bk-ci",
        "bk-iam-dev",
        "bk-jaeger",
        "bk-storage",
        "bk-user-rabbitmq",
        "bk-user-v3",
    ]
    for namespace in namespace_name:
        BCSWorkload(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            namespace=namespace,
            type="Deployment",
            name="bk-monitor-web",
            created_at=timezone.now(),
            last_synced_at=timezone.now(),
            pod_count=0,
        ).save()


def create_namespace(
    name: str,
    bk_biz_id: int = 2,
    bcs_cluster_id: str = "BCS-K8S-00000",
    type: Literal["Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"] = "Deployment",
    created_at=timezone.now(),
    last_synced_at=timezone.now(),
    pod_count=0,
):
    BCSWorkload(
        bk_biz_id=bk_biz_id,
        bcs_cluster_id=bcs_cluster_id,
        namespace=name,
        type=type,
        name=name,
        created_at=created_at,
        last_synced_at=last_synced_at,
        pod_count=pod_count,
    ).save()


@pytest.fixture()
def create_workloads():
    mock_data = [
        # namespace, type, name
        ["blueking", "Deployment", "bk-monitor-web"],
        ["default", "Deployment", "demo"],
        ["blueking", "Deployment", "bk-monitor-web-worker"],
        ["qzx", "NewType", "new-workload-name"],
    ]
    for item in mock_data:
        BCSWorkload(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            namespace=item[0],
            type=item[1],
            name=item[2],
            created_at=timezone.now(),
            last_synced_at=timezone.now(),
            pod_count=0,
        ).save()


@pytest.fixture()
def get_start_time() -> int:
    return int(time.mktime((timezone.now() - timezone.timedelta(days=1)).timetuple()))


@pytest.fixture()
def get_end_time() -> int:
    return int(time.mktime((timezone.now()).timetuple()))
