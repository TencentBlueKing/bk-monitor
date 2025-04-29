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


import re
from typing import List

import pytest
from django.test import TestCase
from django.utils import timezone

from bkmonitor.models import BCSCluster, BCSContainer, BCSPod, BCSWorkload
from monitor_web.tests.new_k8s.test_resource import TestGetScenarioMetric

pytestsmark = pytest.mark.django_db


def pytest_configure():
    TestCase.databases = {"default", "monitor_api"}


@pytest.fixture()
def create_bcs_cluster():
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
def ensure_test_get_scenario_metric():
    test_instance = TestGetScenarioMetric()
    params = {k: v for k, v in zip(test_instance.argnames, test_instance.argvalues[0].values)}
    test_instance.test_with_metric(**params)


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


@pytest.fixture()
def create_workloads():
    BCSWorkload(
        bk_biz_id=2,
        bcs_cluster_id="BCS-K8S-00000",
        namespace="blueking",
        type="Deployment",
        name="bk-monitor-web",
        created_at=timezone.now(),
        last_synced_at=timezone.now(),
        pod_count=0,
    ).save()
    BCSWorkload(
        bk_biz_id=2,
        bcs_cluster_id="BCS-K8S-00000",
        namespace="default",
        type="Deployment",
        name="demo",
        created_at=timezone.now(),
        last_synced_at=timezone.now(),
        pod_count=0,
    ).save()
    BCSWorkload(
        bk_biz_id=2,
        bcs_cluster_id="BCS-K8S-00000",
        namespace="blueking",
        type="Deployment",
        name="bk-monitor-web-worker",
        created_at=timezone.now(),
        last_synced_at=timezone.now(),
        pod_count=0,
    ).save()


@pytest.fixture()
def create_pods():
    BCSPod(
        bk_biz_id=2,
        bcs_cluster_id="BCS-K8S-00000",
        namespace="blueking",
        name="bk-monitor-web-worker-784b79c9f-s9fhh",
        node_name="node-127-0-0-1",
        node_ip="127.0.0.1",
        workload_type="Deployment",
        workload_name="bk-monitor-web-worker",
        total_container_count=1,
        ready_container_count=1,
        pod_ip="127.0.0.1",
        restarts=0,
        created_at=timezone.now(),
        last_synced_at=timezone.now(),
    ).save()
    BCSPod(
        bk_biz_id=2,
        bcs_cluster_id="BCS-K8S-00000",
        namespace="default",
        name="bk-monitor-web-worker-784b79c9f-8lw9j",
        node_name="node-127-0-0-1",
        node_ip="127.0.0.1",
        workload_type="Deployment",
        workload_name="bk-monitor-web-worker",
        total_container_count=1,
        ready_container_count=1,
        pod_ip="127.0.0.1",
        restarts=0,
        created_at=timezone.now(),
        last_synced_at=timezone.now(),
    ).save()
    BCSPod(
        bk_biz_id=2,
        bcs_cluster_id="BCS-K8S-00000",
        namespace="blueking",
        name="bk-monitor-web-worker-resource-557cd688bd-c2q2c",
        node_name="node-127-0-0-1",
        node_ip="127.0.0.1",
        workload_type="Deployment",
        workload_name="bk-monitor-web-worker-resource",
        total_container_count=1,
        ready_container_count=1,
        pod_ip="127.0.0.1",
        restarts=0,
        created_at=timezone.now(),
        last_synced_at=timezone.now(),
    ).save()


@pytest.fixture()
def craete_containers():
    BCSContainer(
        bk_biz_id=2,
        bcs_cluster_id="BCS-K8S-00000",
        name="bk-monitor-web",
        namespace="blueking",
        pod_name="bk-monitor-web-579f6bf4bc-nmld9",
        workload_type="Deployment",
        workload_name="bk-monitor-web",
        node_ip="127.0.0.1",
        node_name="node-127-0-0-1",
        image="mirrors.tencent.com/build/blueking/bk-monitor:3.10.0-alpha.335",
        created_at=timezone.now(),
        last_synced_at=timezone.now(),
    ).save()
    BCSContainer(
        bk_biz_id=2,
        bcs_cluster_id="BCS-K8S-00000",
        name="bk-monitor-web",
        namespace="blueking",
        pod_name="bk-monitor-web-579f6bf4bc-qhmxk",
        workload_type="Deployment",
        workload_name="bk-monitor-web",
        node_ip="127.0.0.1",
        node_name="node-127-0-0-1",
        image="mirrors.tencent.com/build/blueking/bk-monitor:3.10.0-alpha.335",
        created_at=timezone.now(),
        last_synced_at=timezone.now(),
    ).save()
    BCSContainer(
        bk_biz_id=2,
        bcs_cluster_id="BCS-K8S-00000",
        name="bk-monitor-web",
        namespace="blueking",
        pod_name="bk-monitor-web-579f6bf4bc-qrzxv",
        workload_type="Deployment",
        workload_name="bk-monitor-web",
        node_ip="127.0.0.1",
        node_name="node-127-0-0-1",
        image="mirrors.tencent.com/build/blueking/bk-monitor:3.10.0-alpha.335",
        created_at=timezone.now(),
        last_synced_at=timezone.now(),
    ).save()


class BaseMetaPromQL:
    @staticmethod
    def build_argvalues(columns, promqls, promqls_with_interval) -> List[pytest.param]:
        argvalues = []

        for column, promql, promql_with_interval in zip(columns, promqls, promqls_with_interval):
            argvalues.append(pytest.param(column, promql, promql_with_interval, id=f"{column}"))

        return argvalues

    @staticmethod
    def build_argnames() -> List[str]:
        return ["column", "promql", "promql_with_interval"]

    def assert_meta_promql(self, meta, column, promql, promql_with_interval):
        assert hasattr(meta, f"meta_prom_with_{column}")
        result_promql: str = getattr(meta, f"meta_prom_with_{column}")
        assert re.sub(r'\n\s+', ' ', result_promql.strip()) == re.sub(r'\n\s+', ' ', promql.strip())

        # 判断带有时间间隔的 promql 语句
        meta.set_agg_interval(1669939200, 1669942800)
        result_promql: str = getattr(meta, f"meta_prom_with_{column}")
        assert re.sub(r'\n\s+', ' ', result_promql.strip()) == re.sub(r'\n\s+', ' ', promql_with_interval.strip())
