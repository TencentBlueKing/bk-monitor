"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.log_databus.handlers.doris_cluster import DorisClusterHandler

BKBASE_TABLE_ID = "2_bklog_30_clustered"


def build_cluster_info(cluster_id: int, cluster_name: str, display_name: str = "") -> dict:
    return {
        "cluster_config": {
            "cluster_id": cluster_id,
            "cluster_name": cluster_name,
            "display_name": display_name or cluster_name,
        }
    }


@override_settings(
    # 用例依赖缓存真实生效（DummyCache 无法验证集群列表只请求一次），
    # 独立 LOCATION 保证 setUp 的 cache.clear() 不会波及其他用例
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "doris-cluster-handler-test",
        }
    }
)
class TestDorisClusterHandler(TestCase):
    """Doris 路由必须带上结果表实际所在的存储集群，否则 metadata 会落到默认集群上"""

    def setUp(self):
        super().setUp()
        cache.clear()

        bkdata_patcher = patch("apps.log_databus.handlers.doris_cluster.BkDataMetaApi")
        self.mock_bkdata_api = bkdata_patcher.start()
        self.addCleanup(bkdata_patcher.stop)
        self.mock_bkdata_api.result_tables.storages.return_value = {
            "doris": {"storage_cluster": {"id": 3, "cluster_name": "doris_cluster_1"}}
        }

        transfer_patcher = patch("apps.log_databus.handlers.doris_cluster.TransferApi")
        self.mock_transfer_api = transfer_patcher.start()
        self.addCleanup(transfer_patcher.stop)
        self.mock_transfer_api.get_cluster_info.return_value = [
            build_cluster_info(11, "doris_cluster_1"),
            build_cluster_info(12, "doris_cluster_2"),
        ]

    def test_get_cluster_id_by_bkbase_storage(self):
        """BkBase 上的集群名换算成日志平台的存储集群 ID"""
        self.assertEqual(DorisClusterHandler.get_cluster_id(BKBASE_TABLE_ID), 11)
        self.mock_bkdata_api.result_tables.storages.assert_called_once_with({"result_table_id": BKBASE_TABLE_ID})

    def test_get_cluster_id_by_display_name(self):
        """集群名不符合 metadata 命名规范时被改写，只有 display_name 保留 BkBase 原名"""
        self.mock_bkdata_api.result_tables.storages.return_value = {
            "doris": {"storage_cluster": {"cluster_name": "doris-cluster-3"}}
        }
        self.mock_transfer_api.get_cluster_info.return_value = [
            build_cluster_info(13, "auto_cluster_name_13", display_name="doris-cluster-3"),
        ]

        self.assertEqual(DorisClusterHandler.get_cluster_id(BKBASE_TABLE_ID), 13)

    def test_fallback_cluster_name_when_bkbase_storage_missing(self):
        """flow 刚创建时 BkBase 侧还查不到存储，此时回退到下发 flow 使用的集群名"""
        self.mock_bkdata_api.result_tables.storages.return_value = {}

        self.assertEqual(
            DorisClusterHandler.get_cluster_id(BKBASE_TABLE_ID, fallback_cluster_name="doris_cluster_2"), 12
        )

    def test_bkbase_storage_takes_precedence_over_fallback(self):
        """BkBase 上查得到存储时以实际集群为准"""
        self.assertEqual(
            DorisClusterHandler.get_cluster_id(BKBASE_TABLE_ID, fallback_cluster_name="doris_cluster_2"), 11
        )

    def test_no_cluster_name_at_all(self):
        """集群名完全无法确定时不查 metadata，直接返回 None"""
        self.mock_bkdata_api.result_tables.storages.return_value = {}

        self.assertIsNone(DorisClusterHandler.get_cluster_id(BKBASE_TABLE_ID))
        self.mock_transfer_api.get_cluster_info.assert_not_called()

    def test_cluster_not_registered_in_metadata(self):
        """BkBase 集群未登记到日志平台时返回 None，避免路由落到默认集群"""
        self.mock_transfer_api.get_cluster_info.return_value = [build_cluster_info(12, "doris_cluster_2")]

        self.assertIsNone(DorisClusterHandler.get_cluster_id(BKBASE_TABLE_ID))

    def test_bkbase_api_error_falls_back(self):
        """BkBase 接口异常时仍可用兜底集群名"""
        self.mock_bkdata_api.result_tables.storages.side_effect = Exception("bkbase error")

        self.assertEqual(
            DorisClusterHandler.get_cluster_id(BKBASE_TABLE_ID, fallback_cluster_name="doris_cluster_1"), 11
        )

    def test_metadata_api_error(self):
        """metadata 接口异常时返回 None，且不缓存空结果"""
        self.mock_transfer_api.get_cluster_info.side_effect = Exception("metadata error")

        self.assertIsNone(DorisClusterHandler.get_cluster_id(BKBASE_TABLE_ID))

        self.mock_transfer_api.get_cluster_info.side_effect = None
        self.assertEqual(DorisClusterHandler.get_cluster_id(BKBASE_TABLE_ID), 11)

    def test_empty_bkbase_table_id(self):
        """结果表为空时不查 BkBase"""
        self.assertIsNone(DorisClusterHandler.get_cluster_id(""))
        self.mock_bkdata_api.result_tables.storages.assert_not_called()

    def test_cluster_name_id_map_is_cached(self):
        """集群列表带缓存，注册路由不会反复请求 metadata"""
        DorisClusterHandler.get_cluster_id(BKBASE_TABLE_ID)
        DorisClusterHandler.get_cluster_id(BKBASE_TABLE_ID)

        self.mock_transfer_api.get_cluster_info.assert_called_once()

    def test_tenant_is_resolved_from_table_id(self):
        """租户由结果表前缀的业务换算，调用方不需要传"""
        with patch(
            "apps.log_databus.handlers.doris_cluster.Space.get_tenant_id", return_value="tenant_a"
        ) as mock_get_tenant_id:
            self.assertEqual(DorisClusterHandler.get_cluster_id("7_bklog_30_clustered"), 11)

        self.assertEqual(mock_get_tenant_id.call_args.kwargs["bk_biz_id"], 7)
        self.assertEqual(self.mock_transfer_api.get_cluster_info.call_args.kwargs["bk_tenant_id"], "tenant_a")

    def test_tenant_is_resolved_from_space_table_id(self):
        """非 BKCC 空间的结果表前缀是 space_{id}，换算成负数业务"""
        with patch(
            "apps.log_databus.handlers.doris_cluster.Space.get_tenant_id", return_value="tenant_a"
        ) as mock_get_tenant_id:
            DorisClusterHandler.get_cluster_id("space_5_bklog_30_clustered")

        self.assertEqual(mock_get_tenant_id.call_args.kwargs["bk_biz_id"], -5)

    def test_cluster_name_id_map_is_isolated_by_tenant(self):
        """不同租户的集群列表分开缓存，不能共用一份"""
        with patch("apps.log_databus.handlers.doris_cluster.Space.get_tenant_id", side_effect=["tenant_a", "tenant_b"]):
            DorisClusterHandler.get_cluster_id("7_bklog_30_clustered")
            DorisClusterHandler.get_cluster_id("8_bklog_30_clustered")

        self.assertEqual(self.mock_transfer_api.get_cluster_info.call_count, 2)
        self.assertEqual(
            [call.kwargs["bk_tenant_id"] for call in self.mock_transfer_api.get_cluster_info.call_args_list],
            ["tenant_a", "tenant_b"],
        )
