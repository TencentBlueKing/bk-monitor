"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

Pod 告警的目标解析：维度里没有 namespace 时，只在集群内能唯一确定 Pod 时补充 namespace 和 workload。
"""

from unittest import mock

import pytest
from django.utils import timezone

from alarm_backends.core.alert.adapter import MonitorEventAdapter
from bkmonitor.models import BCSPod
from constants.alert import EventTargetType, K8STargetType

pytestmark = pytest.mark.django_db

CLUSTER = "BCS-K8S-00000"
POD = "vmstorage-0"
CACHE_KEY = f"bcs_pod:{CLUSTER}:None:{POD}"


class FakeCache(dict):
    def set(self, key, value, timeout=None):
        self[key] = value


@pytest.fixture()
def redis_cache():
    cache = FakeCache()
    with mock.patch("bkmonitor.utils.dynamic_settings.redis_cache", cache):
        yield cache


def make_pod(namespace, workload_name):
    now = timezone.now()
    return BCSPod.objects.create(
        bk_biz_id=2,
        bcs_cluster_id=CLUSTER,
        name=POD,
        namespace=namespace,
        node_name="node-1",
        workload_type="StatefulSet",
        workload_name=workload_name,
        total_container_count=1,
        ready_container_count=1,
        images="",
        restarts=0,
        created_at=now,
        last_synced_at=now,
    )


def get_k8s_target(dimensions):
    return MonitorEventAdapter.get_k8s_target(dict(dimensions), bk_biz_id=2)


def test_unique_pod_adds_namespace_and_workload(redis_cache):
    make_pod("ns-a", "vmstorage-a")

    target_type, target, dimensions = get_k8s_target({"bcs_cluster_id": CLUSTER, "pod": POD})

    assert (target_type, target) == (K8STargetType.POD, POD)
    assert dimensions["__additional_dimensions"] == {
        "workload_kind": "StatefulSet",
        "workload_name": "vmstorage-a",
        "namespace": "ns-a",
    }
    assert CACHE_KEY in redis_cache


def test_same_pod_name_in_two_namespaces_adds_nothing(redis_cache):
    make_pod("ns-a", "vmstorage-a")
    make_pod("ns-b", "vmstorage-b")

    # 第二次仍查库判断：有歧义的结果不进缓存
    for _ in range(2):
        target_type, target, dimensions = get_k8s_target({"bcs_cluster_id": CLUSTER, "pod": POD})
        assert (target_type, target) == (K8STargetType.POD, POD)
        assert "__additional_dimensions" not in dimensions
    assert CACHE_KEY not in redis_cache


def test_pod_not_found_without_namespace_has_no_target(redis_cache):
    target_type, target, dimensions = get_k8s_target({"bcs_cluster_id": CLUSTER, "pod": POD})

    assert (target_type, target) == (EventTargetType.EMPTY, None)
    assert "__additional_dimensions" not in dimensions


def test_namespace_in_dimensions_selects_the_pod(redis_cache):
    make_pod("ns-a", "vmstorage-a")
    make_pod("ns-b", "vmstorage-b")

    target_type, target, dimensions = get_k8s_target({"bcs_cluster_id": CLUSTER, "pod": POD, "namespace": "ns-b"})

    assert (target_type, target) == (K8STargetType.POD, POD)
    assert dimensions["__additional_dimensions"] == {"workload_kind": "StatefulSet", "workload_name": "vmstorage-b"}


def test_lookup_without_redis_cache():
    make_pod("ns-a", "vmstorage-a")
    with mock.patch("bkmonitor.utils.dynamic_settings.redis_cache", None):
        assert BCSPod.get_instance_with_cache(name=POD, bcs_cluster_id=CLUSTER).namespace == "ns-a"

        make_pod("ns-b", "vmstorage-b")
        with pytest.raises(BCSPod.MultipleObjectsReturned):
            BCSPod.get_instance_with_cache(name=POD, bcs_cluster_id=CLUSTER)
        assert BCSPod.get_instance_with_cache(name=POD, bcs_cluster_id=CLUSTER, namespace="ns-b").namespace == "ns-b"
