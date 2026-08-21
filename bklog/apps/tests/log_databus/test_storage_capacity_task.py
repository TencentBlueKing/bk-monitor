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

from django.test import TestCase, override_settings

from apps.log_databus.constants import (
    DORIS_CLUSTER_TYPE,
    REGISTERED_SYSTEM_DEFAULT,
    STORAGE_CLUSTER_TYPE,
)
from apps.log_databus.models import StorageUsed
from apps.log_databus.tasks.collector import get_doris_cluster_stats, sync_storage_capacity

BLUEKING_BIZ_ID = 2

ES_CLUSTER = {
    "cluster_type": STORAGE_CLUSTER_TYPE,
    "cluster_config": {
        "cluster_id": 101,
        "cluster_name": "es_public",
        "registered_system": REGISTERED_SYSTEM_DEFAULT,
        "custom_option": {},
    },
}

DORIS_PUBLIC_CLUSTER = {
    "cluster_type": DORIS_CLUSTER_TYPE,
    "cluster_config": {
        "cluster_id": 201,
        "cluster_name": "doris_public",
        "registered_system": REGISTERED_SYSTEM_DEFAULT,
        "custom_option": {},
    },
}

DORIS_PRIVATE_CLUSTER = {
    "cluster_type": DORIS_CLUSTER_TYPE,
    "cluster_config": {
        "cluster_id": 202,
        "cluster_name": "doris_private",
        "registered_system": "bkdata",
        "custom_option": {"bk_biz_id": 215},
    },
}


def build_doris_status(cluster_id, total_bytes=1000, used_bytes=250, tablet_count=1024):
    return {
        "cluster_id": cluster_id,
        "cluster_type": DORIS_CLUSTER_TYPE,
        "is_available": True,
        "capacity": {"total_bytes": total_bytes, "used_bytes": used_bytes, "available_bytes": total_bytes - used_bytes},
        "details": {"tablet_count": tablet_count, "data_used_bytes": used_bytes},
    }


@override_settings(BLUEKING_BK_BIZ_ID=BLUEKING_BIZ_ID)
class TestGetDorisClusterStats(TestCase):
    """doris 集群容量指标取数"""

    @patch("apps.log_databus.tasks.collector.TransferApi.get_cluster_status")
    def test_public_and_private_cluster_grouped_by_biz(self, mock_get_cluster_status):
        """公共集群按蓝鲸业务查询，私有集群按 custom_option 中的业务查询"""

        def _get_cluster_status(params, **kwargs):
            return [build_doris_status(cluster_id) for cluster_id in params["cluster_ids"]]

        mock_get_cluster_status.side_effect = _get_cluster_status

        stats = get_doris_cluster_stats([DORIS_PUBLIC_CLUSTER, DORIS_PRIVATE_CLUSTER])

        self.assertEqual(set(stats.keys()), {201, 202})
        queried_biz_ids = {call.args[0]["bk_biz_id"] for call in mock_get_cluster_status.call_args_list}
        self.assertEqual(queried_biz_ids, {BLUEKING_BIZ_ID, 215})

    @patch("apps.log_databus.tasks.collector.TransferApi.get_cluster_status")
    def test_capacity_and_tablet_count_mapping(self, mock_get_cluster_status):
        """使用率由 used_bytes/total_bytes 换算为百分比整数，tablet 数映射到索引数"""
        mock_get_cluster_status.return_value = [
            build_doris_status(201, total_bytes=1000, used_bytes=250, tablet_count=1024)
        ]

        stats = get_doris_cluster_stats([DORIS_PUBLIC_CLUSTER])

        self.assertEqual(stats[201], {"storage_usage": 25, "storage_total": 1000, "index_count": 1024})

    @patch("apps.log_databus.tasks.collector.TransferApi.get_cluster_status")
    def test_zero_or_missing_capacity_does_not_raise(self, mock_get_cluster_status):
        """总容量为 0 或字段缺失时不应抛除零异常"""
        mock_get_cluster_status.return_value = [
            build_doris_status(201, total_bytes=0, used_bytes=0, tablet_count=0),
            {"cluster_id": 202, "cluster_type": DORIS_CLUSTER_TYPE, "is_available": False},
        ]

        stats = get_doris_cluster_stats([DORIS_PUBLIC_CLUSTER])

        self.assertEqual(stats[201], {"storage_usage": 0, "storage_total": 0, "index_count": 0})
        self.assertEqual(stats[202], {"storage_usage": 0, "storage_total": 0, "index_count": 0})

    @patch("apps.log_databus.tasks.collector.TransferApi.get_cluster_status")
    def test_cluster_without_owner_biz_skipped(self, mock_get_cluster_status):
        """取不到归属业务的私有集群无法解析租户，直接跳过"""
        cluster = {
            "cluster_type": DORIS_CLUSTER_TYPE,
            "cluster_config": {"cluster_id": 203, "registered_system": "bkdata", "custom_option": {}},
        }

        stats = get_doris_cluster_stats([cluster])

        self.assertEqual(stats, {})
        mock_get_cluster_status.assert_not_called()

    @patch("apps.log_databus.tasks.collector.TransferApi.get_cluster_status")
    def test_invalid_owner_biz_skipped(self, mock_get_cluster_status):
        """归属业务无法转成数字时跳过该集群，不影响整体同步"""
        cluster = {
            "cluster_type": DORIS_CLUSTER_TYPE,
            "cluster_config": {
                "cluster_id": 204,
                "registered_system": "bkdata",
                "custom_option": {"bk_biz_id": "not-a-biz"},
            },
        }

        stats = get_doris_cluster_stats([cluster])

        self.assertEqual(stats, {})
        mock_get_cluster_status.assert_not_called()

    @patch("apps.log_databus.tasks.collector.TransferApi.get_cluster_status")
    def test_one_biz_failure_does_not_affect_others(self, mock_get_cluster_status):
        """某个业务查询失败时其余业务的集群仍应返回"""

        def _get_cluster_status(params, **kwargs):
            if params["bk_biz_id"] == BLUEKING_BIZ_ID:
                raise Exception("metadata unavailable")
            return [build_doris_status(cluster_id) for cluster_id in params["cluster_ids"]]

        mock_get_cluster_status.side_effect = _get_cluster_status

        stats = get_doris_cluster_stats([DORIS_PUBLIC_CLUSTER, DORIS_PRIVATE_CLUSTER])

        self.assertEqual(set(stats.keys()), {202})


@override_settings(BLUEKING_BK_BIZ_ID=BLUEKING_BIZ_ID)
class TestSyncStorageCapacity(TestCase):
    """周期任务同步 ES 与 doris 集群容量"""

    def setUp(self):
        StorageUsed.objects.all().delete()

    @patch("apps.log_databus.tasks.collector.get_all_biz_storage_capacity", return_value={})
    @patch("apps.log_databus.tasks.collector.count_storage_indices", return_value=88)
    @patch("apps.log_databus.tasks.collector.get_storage_usage_and_all", return_value=(66, 2000))
    @patch("apps.log_databus.tasks.collector.TransferApi.get_cluster_status")
    @patch("apps.log_databus.tasks.collector.TransferApi.get_cluster_info")
    def test_es_and_doris_cluster_both_recorded(
        self,
        mock_get_cluster_info,
        mock_get_cluster_status,
        mock_get_storage_usage_and_all,
        mock_count_storage_indices,
        mock_get_all_biz_storage_capacity,
    ):
        """ES 与 doris 集群都应写出集群级记录，且 doris 不触发 ES 的 _cat 查询"""

        def _get_cluster_info(params):
            if params["cluster_type"] == DORIS_CLUSTER_TYPE:
                return [DORIS_PUBLIC_CLUSTER]
            return [ES_CLUSTER]

        mock_get_cluster_info.side_effect = _get_cluster_info
        mock_get_cluster_status.return_value = [
            build_doris_status(201, total_bytes=4000, used_bytes=1000, tablet_count=512)
        ]

        sync_storage_capacity()

        es_record = StorageUsed.objects.get(bk_biz_id=StorageUsed.CLUSTER_INFO_BIZ_ID, storage_cluster_id=101)
        self.assertEqual((es_record.storage_usage, es_record.storage_total, es_record.index_count), (66, 2000, 88))

        doris_record = StorageUsed.objects.get(bk_biz_id=StorageUsed.CLUSTER_INFO_BIZ_ID, storage_cluster_id=201)
        self.assertEqual(
            (doris_record.storage_usage, doris_record.storage_total, doris_record.index_count), (25, 4000, 512)
        )

        # doris 集群不走 ES 的 _cat 路由，两个 ES 取数函数各自只被 ES 集群调用一次
        self.assertEqual(mock_get_storage_usage_and_all.call_count, 1)
        self.assertEqual(mock_count_storage_indices.call_count, 1)

    @patch("apps.log_databus.tasks.collector.get_biz_storage_capacity", return_value=1.5)
    @patch("apps.log_databus.tasks.collector.get_all_biz_storage_capacity", return_value={})
    @patch("apps.log_databus.tasks.collector.count_storage_indices", return_value=0)
    @patch("apps.log_databus.tasks.collector.get_storage_usage_and_all", return_value=(0, 0))
    @patch("apps.log_databus.tasks.collector.TransferApi.get_cluster_status")
    @patch("apps.log_databus.tasks.collector.TransferApi.get_cluster_info")
    def test_doris_cluster_skips_biz_level_record(
        self,
        mock_get_cluster_info,
        mock_get_cluster_status,
        mock_get_storage_usage_and_all,
        mock_count_storage_indices,
        mock_get_all_biz_storage_capacity,
        mock_get_biz_storage_capacity,
    ):
        """doris 按业务的用量无等价接口，只写集群级记录"""

        def _get_cluster_info(params):
            if params["cluster_type"] == DORIS_CLUSTER_TYPE:
                return [DORIS_PRIVATE_CLUSTER]
            return []

        mock_get_cluster_info.side_effect = _get_cluster_info
        mock_get_cluster_status.return_value = [build_doris_status(202)]

        sync_storage_capacity()

        self.assertEqual(StorageUsed.objects.filter(storage_cluster_id=202).count(), 1)
        self.assertTrue(
            StorageUsed.objects.filter(
                storage_cluster_id=202, bk_biz_id=StorageUsed.CLUSTER_INFO_BIZ_ID
            ).exists()
        )
        mock_get_biz_storage_capacity.assert_not_called()
        mock_get_all_biz_storage_capacity.assert_not_called()

    @patch("apps.log_databus.tasks.collector.get_all_biz_storage_capacity", return_value={})
    @patch("apps.log_databus.tasks.collector.count_storage_indices", return_value=88)
    @patch("apps.log_databus.tasks.collector.get_storage_usage_and_all", return_value=(66, 2000))
    @patch("apps.log_databus.tasks.collector.TransferApi.get_cluster_info")
    def test_doris_query_failure_does_not_break_es_sync(
        self,
        mock_get_cluster_info,
        mock_get_storage_usage_and_all,
        mock_count_storage_indices,
        mock_get_all_biz_storage_capacity,
    ):
        """metadata 查询 doris 集群列表失败时，ES 集群同步不受影响"""

        def _get_cluster_info(params):
            if params["cluster_type"] == DORIS_CLUSTER_TYPE:
                raise Exception("metadata unavailable")
            return [ES_CLUSTER]

        mock_get_cluster_info.side_effect = _get_cluster_info

        sync_storage_capacity()

        self.assertTrue(StorageUsed.objects.filter(storage_cluster_id=101).exists())

    @patch("apps.log_databus.tasks.collector.get_all_biz_storage_capacity", return_value={})
    @patch("apps.log_databus.tasks.collector.count_storage_indices", return_value=0)
    @patch("apps.log_databus.tasks.collector.get_storage_usage_and_all", return_value=(0, 0))
    @patch("apps.log_databus.tasks.collector.TransferApi.get_cluster_status", return_value=[])
    @patch("apps.log_databus.tasks.collector.TransferApi.get_cluster_info")
    def test_doris_cluster_without_stats_skipped(
        self,
        mock_get_cluster_info,
        mock_get_cluster_status,
        mock_get_storage_usage_and_all,
        mock_count_storage_indices,
        mock_get_all_biz_storage_capacity,
    ):
        """metadata 未返回状态的 doris 集群不写记录，避免把已有指标刷成 0"""

        def _get_cluster_info(params):
            if params["cluster_type"] == DORIS_CLUSTER_TYPE:
                return [DORIS_PUBLIC_CLUSTER]
            return [ES_CLUSTER]

        mock_get_cluster_info.side_effect = _get_cluster_info

        sync_storage_capacity()

        self.assertFalse(StorageUsed.objects.filter(storage_cluster_id=201).exists())
        self.assertTrue(StorageUsed.objects.filter(storage_cluster_id=101).exists())
