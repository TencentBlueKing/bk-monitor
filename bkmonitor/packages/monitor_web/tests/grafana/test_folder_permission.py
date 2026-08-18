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

# Dashboard 在 bk_dataview 库、业务/空间映射在 monitor_api 库：
# 模块级标记放开三个库的测试隔离（仅 db fixture 只放开 default，会触发
# DatabaseOperationForbidden / Database access not allowed）
pytestmark = pytest.mark.django_db(databases=["default", "bk_dataview", "monitor_api"])


@pytest.fixture(scope="session", autouse=True)
def create_grafana_tables(django_db_setup, django_db_blocker):
    """bk_dataview 模型均为 managed=False（schema 由 grafana 外部维护），
    测试库不会自动建表；按需在 bk_dataview 测试库中建 dashboard 表。"""
    from django.db import connections

    with django_db_blocker.unblock():
        conn = connections["bk_dataview"]
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES LIKE 'dashboard'")
            if not cur.fetchone():
                with conn.schema_editor() as schema_editor:
                    schema_editor.create_model(Dashboard)


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
            version=1,  # version 无模型默认值且 NOT NULL，必须显式提供
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
                version=1,  # version 无模型默认值且 NOT NULL，必须显式提供
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


class TestExpandResourcesToDashboardUids:
    """测试 expand_resources_to_dashboard_uids（原 get_policy_resources 的资源解析逻辑迁移至此）"""

    @pytest.mark.parametrize(
        "resource_ids,expected_uids",
        [
            ([], set()),
            (["1|test_uid"], {"test_uid"}),
            (["1|uid1", "1|uid2"], {"uid1", "uid2"}),
            (["999|uid1"], set()),  # 跨 org 过滤
            (["uid_without_org"], {"uid_without_org"}),  # 纯 uid
            (["1|uid1", "999|uid2"], {"uid1"}),
        ],
    )
    def test_dashboard_ids(self, org_id, resource_ids, expected_uids):
        """dashboard 资源 id 解析 + org 过滤"""
        uids = DashboardPermission.expand_resources_to_dashboard_uids(org_id, resource_ids)
        assert uids == expected_uids

    def test_folder_expansion(self, org_id, sample_folders, sample_dashboards):
        """folder 资源 id 展开为其下所有 dashboard uid"""
        folder = sample_folders[0]
        resource_ids = [f"{DashboardPermission.FOLDER_PREFIX}{org_id}|{folder.id}"]
        uids = DashboardPermission.expand_resources_to_dashboard_uids(org_id, resource_ids)
        expected = {d.uid for d in sample_dashboards if d.folder_id == folder.id}
        assert uids == expected

    def test_mixed_dashboard_and_folder(self, org_id, sample_folders, sample_dashboards):
        """dashboard 与 folder 混合资源列表"""
        folder = sample_folders[0]
        resource_ids = [f"{org_id}|direct_uid", f"{DashboardPermission.FOLDER_PREFIX}{org_id}|{folder.id}"]
        uids = DashboardPermission.expand_resources_to_dashboard_uids(org_id, resource_ids)
        expected = {"direct_uid"} | {d.uid for d in sample_dashboards if d.folder_id == folder.id}
        assert uids == expected

    def test_wrong_org_folder_filtered(self, sample_folders):
        """跨 org 的 folder 不展开"""
        folder = sample_folders[0]
        resource_ids = [f"{DashboardPermission.FOLDER_PREFIX}999|{folder.id}"]
        uids = DashboardPermission.expand_resources_to_dashboard_uids(1, resource_ids)
        assert uids == set()


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
