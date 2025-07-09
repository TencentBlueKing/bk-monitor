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

import pytest

from monitor_web.k8s.core.filters import (
    ClusterFilter,
    DefaultContainerFilter,
    NamespaceFilter,
    SpaceFilter,
    load_resource_filter,
)
from monitor_web.k8s.core.meta import (
    FilterCollection,
    K8sContainerMeta,
    K8sIngressMeta,
    K8sNamespaceMeta,
    K8sPodMeta,
    K8sServiceMeta,
    K8sWorkloadMeta,
    load_resource_meta,
)


@pytest.mark.parametrize(
    ["resource_type", "meta_class"],
    [
        # ["node", K8sNodeMeta],  # 目前暂不可用
        ["container", K8sContainerMeta],
        ["container_name", K8sContainerMeta],
        ["pod", K8sPodMeta],
        ["pod_name", K8sPodMeta],
        ["workload", K8sWorkloadMeta],
        ["namespace", K8sNamespaceMeta],
        ["ingress", K8sIngressMeta],
        ["service", K8sServiceMeta],
        ["other", type(None)],
    ],
)
def test_load_resource_meta(resource_type, meta_class):
    meta = load_resource_meta(resource_type, 2, "BCS-K8S-00000")
    assert isinstance(meta, meta_class)


class TestFilterCollection:
    def test_add_and_remove_filter(self):
        meta = load_resource_meta("pod", 2, "BCS-K8S-00000")
        filter: FilterCollection = meta.filter
        default_filters_keys = [
            "bcs_cluster_idbcs_cluster_id['BCS-K8S-00000']",
            "bk_biz_idbk_biz_id['2']",
            "container_excludecontainer_name['']",
        ]
        assert list(filter.filters.keys()) == default_filters_keys
        assert isinstance(filter.filters[default_filters_keys[0]], ClusterFilter)
        assert isinstance(filter.filters[default_filters_keys[1]], SpaceFilter)
        assert isinstance(filter.filters[default_filters_keys[2]], DefaultContainerFilter)

        namespace_filter = load_resource_filter("namespace", "blueking")
        filter.add(namespace_filter)
        assert len(filter.filters) == 4
        assert isinstance(filter.filters[namespace_filter.filter_uid], NamespaceFilter)

        filter.remove(namespace_filter)
        assert len(filter.filters) == 3

    def test_filter_queryset(self):
        meta = load_resource_meta("pod", 2, "BCS-K8S-00000")
        query_orm = """SELECT
            `bkmonitor_bcspod`.`id`,
            `bkmonitor_bcspod`.`bk_biz_id`,
            `bkmonitor_bcspod`.`bcs_cluster_id`,
            `bkmonitor_bcspod`.`name`,
            `bkmonitor_bcspod`.`namespace`,
            `bkmonitor_bcspod`.`workload_type`,
            `bkmonitor_bcspod`.`workload_name`
        FROM
            `bkmonitor_bcspod`
        WHERE
            (`bkmonitor_bcspod`.`bcs_cluster_id` = BCS-K8S-00000
                AND `bkmonitor_bcspod`.`bk_biz_id` = 2)
        ORDER BY
            `bkmonitor_bcspod`.`id` ASC"""
        assert str(meta.filter.filter_queryset.query) == re.sub(r"\n\s+", " ", query_orm)
