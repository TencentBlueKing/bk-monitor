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
from core.drf_resource import api


def test_get_cluster_info_from_bcs_space(monkeypatch_get_space_detail, monkeypatch_get_clusters_by_space_uid):
    actual = api.kubernetes.get_cluster_info_from_bcs_space({"bk_biz_id": 0})
    assert actual == {}

    # 业务ID > 0 是没有共享集群的
    actual = api.kubernetes.get_cluster_info_from_bcs_space({"bk_biz_id": 2})
    assert actual == {}

    # 获取空间下的所有集群
    actual = api.kubernetes.get_cluster_info_from_bcs_space({"bk_biz_id": -3})
    expect = {
        'BCS-K8S-00000': {'cluster_type': 'single', 'namespace_list': []},
        'BCS-K8S-00002': {'cluster_type': 'shared', 'namespace_list': ['namespace_a', 'namespace_b']},
    }
    assert actual == expect

    # 获得空间下的共享集群
    actual = api.kubernetes.get_cluster_info_from_bcs_space({"bk_biz_id": -3, "shard_only": True})
    expect = {'BCS-K8S-00002': {'cluster_type': 'shared', 'namespace_list': ['namespace_a', 'namespace_b']}}
    assert actual == expect

    # 根据space_uid获得共享集群
    actual = api.kubernetes.get_cluster_info_from_bcs_space({"space_uid": "bkci__testprojectliu", "shard_only": True})
    assert actual == expect
