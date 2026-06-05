"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

from django.test import TestCase

from constants.common import DEFAULT_TENANT_ID
from monitor_web.models.custom_report import CustomEventGroup
from monitor_web.strategies.metric_list_cache import CustomEventCacheManager


def make_event_group(event_group_id, bk_data_id, bk_biz_id, name):
    """构造 metadata query_event_group 返回的事件分组结构"""
    return {
        "event_group_id": event_group_id,
        "bk_data_id": bk_data_id,
        "bk_biz_id": bk_biz_id,
        "event_group_name": name,
        "table_id": f"bkmonitor_event_{bk_data_id}",
        "label": "application_check",
        "event_info_list": [
            {"event_name": "test_event", "dimension_list": ["target"], "event_id": 1},
        ],
    }


class TestCustomEventCacheManagerPlatformGroup(TestCase):
    """平台级自定义事件分组的缓存产出行为"""

    OWNER_BIZ = 10001
    OTHER_BIZ = 10002

    def setUp(self):  # NOCC:invalid-name(设计如此:)
        CustomEventGroup.objects.all().delete()
        # 平台级分组：EventGroup 挂归属业务（PR #8907 之后的形态）
        CustomEventGroup.objects.create(
            bk_event_group_id=101,
            bk_data_id=201,
            bk_biz_id=self.OWNER_BIZ,
            name="platform_group",
            scenario="application_check",
            type="custom_event",
            is_platform=True,
        )
        # 普通分组：仅归属业务可见
        CustomEventGroup.objects.create(
            bk_event_group_id=102,
            bk_data_id=202,
            bk_biz_id=self.OWNER_BIZ,
            name="normal_group",
            scenario="application_check",
            type="custom_event",
            is_platform=False,
        )
        # 存量平台级分组：EventGroup 挂 0（PR #8907 之前的形态）
        CustomEventGroup.objects.create(
            bk_event_group_id=103,
            bk_data_id=203,
            bk_biz_id=self.OWNER_BIZ,
            name="legacy_platform_group",
            scenario="application_check",
            type="custom_event",
            is_platform=True,
        )

        self.metadata_groups = {
            101: make_event_group(101, 201, self.OWNER_BIZ, "platform_group"),
            102: make_event_group(102, 202, self.OWNER_BIZ, "normal_group"),
            103: make_event_group(103, 203, 0, "legacy_platform_group"),
        }

        def fake_query_event_group(bk_tenant_id=None, bk_biz_id=None, bk_data_ids=None, **kwargs):
            if bk_data_ids:
                return [dict(group) for group in self.metadata_groups.values() if group["bk_data_id"] in bk_data_ids]
            return [dict(group) for group in self.metadata_groups.values() if group["bk_biz_id"] == bk_biz_id]

        self.query_event_group_patcher = mock.patch("core.drf_resource.api.metadata.query_event_group")
        mocked_query_event_group = self.query_event_group_patcher.start()
        mocked_query_event_group.request.refresh.side_effect = fake_query_event_group
        self.mocked_query_event_group = mocked_query_event_group

        self.k8s_patcher = mock.patch("core.drf_resource.api.kubernetes.fetch_k8s_cluster_list", return_value=[])
        self.k8s_patcher.start()

    def tearDown(self):  # NOCC:invalid-name(设计如此:)
        self.query_event_group_patcher.stop()
        self.k8s_patcher.stop()
        CustomEventGroup.objects.all().delete()

    def get_custom_tables(self, bk_biz_id):
        manager = CustomEventCacheManager(bk_tenant_id=DEFAULT_TENANT_ID, bk_biz_id=bk_biz_id)
        return [table for table in manager.get_tables() if table["event_group_id"] != 0]

    def test_owner_biz_skips_platform_group(self):
        """归属业务任务：平台级分组跳过（由 biz=0 任务产出），普通分组正常产出"""
        tables = self.get_custom_tables(self.OWNER_BIZ)
        group_ids = [table["event_group_id"] for table in tables]
        self.assertEqual(group_ids, [102])
        self.assertEqual(tables[0]["bk_biz_id"], self.OWNER_BIZ)

    def test_biz_0_yields_platform_group_with_biz_0(self):
        """biz=0 任务：补拉平台级分组且缓存业务改写为 0，存量挂 0 的分组不重复产出"""
        tables = self.get_custom_tables(0)
        group_ids = sorted(table["event_group_id"] for table in tables)
        self.assertEqual(group_ids, [101, 103])
        for table in tables:
            self.assertEqual(table["bk_biz_id"], 0)
        # 每个分组只产出一次
        self.assertEqual(len(group_ids), len(set(group_ids)))

    def test_other_biz_has_no_custom_group(self):
        """非归属业务任务：不产出任何自定义事件分组（可见性由缓存行 bk_biz_id=0 提供）"""
        tables = self.get_custom_tables(self.OTHER_BIZ)
        self.assertEqual(tables, [])

    def test_no_platform_group_skips_supplement_query(self):
        """无平台级分组时，biz=0 任务不应发起 bk_data_ids 补拉（空列表会导致全量返回）"""
        CustomEventGroup.objects.filter(is_platform=True).update(is_platform=False)
        self.get_custom_tables(0)
        for call in self.mocked_query_event_group.request.refresh.call_args_list:
            self.assertNotIn("bk_data_ids", call.kwargs)

    def test_owner_biz_k8s_loop_does_not_resurrect_platform_group(self):
        """归属业务任务：平台级分组名即使命中集群 ID，也不经 k8s 事件循环重新产出"""
        self.metadata_groups[101]["event_group_name"] = "platform_group_BCS-K8S-12345"
        cluster = {"cluster_id": "BCS-K8S-12345", "name": "test-cluster", "bk_biz_id": self.OWNER_BIZ}
        with (
            mock.patch("core.drf_resource.api.kubernetes.fetch_k8s_cluster_list", return_value=[cluster]),
            mock.patch("core.drf_resource.api.kubernetes.fetch_bcs_cluster_alert_enabled_id_list", return_value=[]),
        ):
            tables = self.get_custom_tables(self.OWNER_BIZ)
        group_ids = [table["event_group_id"] for table in tables]
        self.assertEqual(group_ids, [102])

    def test_bkci_related_biz_platform_group_not_resurrected(self):
        """BKCI 空间任务：关联业务的平台级分组不经 k8s 名称匹配产出，普通分组不受影响"""
        neg_biz = -100
        self.metadata_groups[101]["event_group_name"] = "platform_group_BCS-K8S-12345"
        self.metadata_groups[102]["event_group_name"] = "normal_group_BCS-K8S-12345"
        cluster = {"cluster_id": "BCS-K8S-12345", "name": "test-cluster", "bk_biz_id": neg_biz}
        related_space = mock.Mock(bk_biz_id=self.OWNER_BIZ)
        with (
            mock.patch(
                "monitor_web.strategies.metric_list_cache.bk_biz_id_to_space_uid", return_value="bkci__testproj"
            ),
            mock.patch(
                "monitor_web.strategies.metric_list_cache.SpaceApi.get_related_space", return_value=related_space
            ),
            mock.patch("core.drf_resource.api.kubernetes.fetch_k8s_cluster_list", return_value=[cluster]),
            mock.patch("core.drf_resource.api.kubernetes.fetch_bcs_cluster_alert_enabled_id_list", return_value=[]),
        ):
            tables = self.get_custom_tables(neg_biz)
        group_ids = [table["event_group_id"] for table in tables]
        self.assertEqual(group_ids, [102])
        self.assertEqual(tables[0]["bk_biz_id"], neg_biz)
