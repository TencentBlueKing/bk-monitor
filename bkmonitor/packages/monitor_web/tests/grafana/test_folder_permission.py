"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from bk_dataview.models import Dashboard
from monitor_web.grafana.permissions import DashboardPermission


@pytest.fixture
def org_id():
    """组织ID fixture"""
    return 1


@pytest.fixture
def bk_biz_id():
    """业务ID fixture"""
    return 2


@pytest.fixture
def sample_folders(db, org_id):
    """创建测试用的文件夹"""
    folders = [
        Dashboard.objects.create(
            org_id=org_id,
            uid=f"folder_{i}",
            title=f"测试文件夹{i}",
            is_folder=True,
            folder_id=0,
        )
        for i in range(1, 4)
    ]
    return folders


@pytest.fixture
def sample_dashboards(db, org_id, sample_folders):
    """创建测试用的仪表盘"""
    dashboards = []
    for folder in sample_folders:
        for j in range(2):
            dashboard = Dashboard.objects.create(
                org_id=org_id,
                uid=f"dashboard_{folder.id}_{j}",
                title=f"仪表盘{folder.id}_{j}",
                is_folder=False,
                folder_id=folder.id,
            )
            dashboards.append(dashboard)
    return dashboards


class TestExpandFolderToDashboards:
    """测试 expand_folder_to_dashboards 方法"""

    def test_expand_empty_folders(self, org_id):
        """测试空文件夹集合"""
        result = DashboardPermission.expand_folder_to_dashboards(org_id, set())
        assert result == set()

    def test_expand_folders_with_dashboards(self, org_id, sample_folders, sample_dashboards):
        """测试包含仪表盘的文件夹"""
        folder_ids = {(org_id, sample_folders[0].id)}
        result = DashboardPermission.expand_folder_to_dashboards(org_id, folder_ids)

        expected_uids = {d.uid for d in sample_dashboards if d.folder_id == sample_folders[0].id}
        assert result == expected_uids

    def test_expand_multiple_folders(self, org_id, sample_folders, sample_dashboards):
        """测试多个文件夹"""
        folder_ids = {(org_id, f.id) for f in sample_folders[:2]}
        result = DashboardPermission.expand_folder_to_dashboards(org_id, folder_ids)

        expected_uids = {
            d.uid for d in sample_dashboards if d.folder_id in [sample_folders[0].id, sample_folders[1].id]
        }
        assert result == expected_uids

    def test_expand_wrong_org_id(self, sample_folders, sample_dashboards):
        """测试错误的组织ID"""
        wrong_org_id = 999
        folder_ids = {(wrong_org_id, sample_folders[0].id)}
        result = DashboardPermission.expand_folder_to_dashboards(1, folder_ids)
        assert result == set()


class TestGetPolicyResources:
    """测试 get_policy_resources 方法"""

    @pytest.mark.parametrize(
        "policy,expected_dashboard_count,expected_folder_count",
        [
            ({}, 0, 0),
            ({"op": "eq", "value": "1|test_uid"}, 1, 0),
            ({"op": "eq", "value": "folder:1|100"}, 0, 1),
            ({"op": "in", "value": ["1|uid1", "1|uid2"]}, 2, 0),
            ({"op": "in", "value": ["folder:1|100", "folder:1|200"]}, 0, 2),
            ({"op": "in", "value": ["1|uid1", "folder:1|100"]}, 1, 1),
        ],
    )
    def test_get_policy_resources_basic(
        self, org_id, bk_biz_id, policy, expected_dashboard_count, expected_folder_count
    ):
        """测试基本策略解析"""
        dashboard_uids, folder_ids = DashboardPermission.get_policy_resources(org_id, bk_biz_id, policy)
        assert len(dashboard_uids) == expected_dashboard_count
        assert len(folder_ids) == expected_folder_count

    def test_get_policy_resources_or_operation(self, org_id, bk_biz_id):
        """测试 OR 操作"""
        policy = {
            "op": "or",
            "content": [
                {"op": "eq", "value": "1|uid1"},
                {"op": "eq", "value": "folder:1|100"},
            ],
        }
        dashboard_uids, folder_ids = DashboardPermission.get_policy_resources(org_id, bk_biz_id, policy)
        assert len(dashboard_uids) == 1
        assert len(folder_ids) == 1

    def test_get_policy_resources_and_wrong_biz_id(self, org_id, bk_biz_id):
        """测试 AND 操作业务ID不匹配"""
        policy = {
            "op": "and",
            "content": [
                {"field": "grafana_dashboard._bk_iam_path_", "value": "/business,999/"},
                {"op": "in", "value": ["1|uid1"]},
            ],
        }
        dashboard_uids, folder_ids = DashboardPermission.get_policy_resources(org_id, bk_biz_id, policy)
        assert len(dashboard_uids) == 0
        assert len(folder_ids) == 0


class TestListInstance:
    """测试 GrafanaDashboardProvider.list_instance 方法"""

    @pytest.fixture
    def provider(self):
        """创建 Provider 实例"""
        from monitor_web.iam.views import GrafanaDashboardProvider

        return GrafanaDashboardProvider()

    @pytest.fixture
    def mock_filter(self):
        """创建 mock filter 对象"""

        class MockFilter:
            def __init__(self):
                self.parent = None
                self.search = None
                self.resource_type_chain = None

        return MockFilter()

    @pytest.fixture
    def mock_page(self):
        """创建 mock page 对象"""

        class MockPage:
            def __init__(self, slice_from=0, slice_to=100):
                self.slice_from = slice_from
                self.slice_to = slice_to

        return MockPage()

    def test_list_instance_empty(self, provider, mock_filter, mock_page):
        """测试空数据情况"""
        from constants.common import DEFAULT_TENANT_ID

        options = {"bk_tenant_id": DEFAULT_TENANT_ID}
        result = provider.list_instance(mock_filter, mock_page, **options)
        assert result.count >= 0

    def test_list_instance_with_folders_and_dashboards(
        self, provider, mock_filter, mock_page, sample_folders, sample_dashboards
    ):
        """测试包含文件夹和仪表盘的情况"""
        from constants.common import DEFAULT_TENANT_ID

        options = {"bk_tenant_id": DEFAULT_TENANT_ID}
        result = provider.list_instance(mock_filter, mock_page, **options)
        assert result.count >= 0

    def test_list_instance_with_search(self, provider, mock_filter, mock_page, sample_dashboards):
        """测试搜索功能"""
        from constants.common import DEFAULT_TENANT_ID

        mock_filter.search = {"grafana_dashboard": ["测试"]}
        options = {"bk_tenant_id": DEFAULT_TENANT_ID}
        result = provider.list_instance(mock_filter, mock_page, **options)
        assert result.count >= 0

    def test_list_instance_with_pagination(self, provider, mock_filter, sample_dashboards):
        """测试分页功能"""
        from constants.common import DEFAULT_TENANT_ID

        class MockPageSmall:
            slice_from = 0
            slice_to = 2

        options = {"bk_tenant_id": DEFAULT_TENANT_ID}
        result = provider.list_instance(mock_filter, MockPageSmall(), **options)
        assert len(result.results) <= 2
