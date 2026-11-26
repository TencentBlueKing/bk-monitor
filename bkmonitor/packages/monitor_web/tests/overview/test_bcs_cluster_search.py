"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace
from unittest import mock

from monitor_web.overview import search as overview_search
from monitor_web.overview.search import BCSClusterSearchItem

FOREIGN_BIZ_ID = 9999


def _cluster(bk_biz_id: int, name: str):
    return SimpleNamespace(bk_biz_id=bk_biz_id, name=name, bcs_cluster_id=f"BCS-K8S-{bk_biz_id}", space_uid="")


def test_cluster_search_excludes_unauthorized_business_when_filter_not_pushed_down():
    # 超过 20 个业务时不下推业务条件，数据库会返回所有名称匹配的集群
    allowed_biz_ids = list(range(1, 22))
    clusters = [_cluster(FOREIGN_BIZ_ID, "repro-cluster-foreign"), _cluster(1, "repro-cluster-allowed")]

    with (
        mock.patch.object(BCSClusterSearchItem, "_get_allowed_bk_biz_ids", return_value=allowed_biz_ids),
        mock.patch.object(BCSClusterSearchItem, "_get_biz_name", side_effect=str),
        mock.patch.object(overview_search.BCSCluster.objects, "filter", return_value=clusters),
    ):
        result = BCSClusterSearchItem.search(bk_tenant_id="system", username="tester", query="repro-cluster", limit=20)

    assert result is not None
    assert [(item["bk_biz_id"], item["name"]) for item in result[0]["items"]] == [(1, "repro-cluster-allowed")]
