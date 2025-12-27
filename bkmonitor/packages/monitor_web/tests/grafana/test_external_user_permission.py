"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from django.http import HttpResponse
from django.utils import timezone

from bk_dataview.models import Dashboard
from bkmonitor.models.external_iam import ExternalPermission
from monitor_adapter.grafana.views import ApiProxyView, GrafanaSwitchOrgView

# 标记所有测试使用数据库
pytestmark = pytest.mark.django_db


# ==================== Fixtures ====================


@pytest.fixture
def bk_biz_id():
    """业务ID"""
    return 2


@pytest.fixture
def org_id(bk_biz_id):
    """Grafana 组织ID"""
    with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
        mock_get_org.return_value = {"id": 1, "name": str(bk_biz_id)}
        yield 1


@pytest.fixture
def external_user():
    """外部用户名"""
    return "external_user_001"


@pytest.fixture
def test_folder(db, org_id):
    """创建测试 folder"""
    folder = Dashboard.objects.create(
        org_id=org_id, uid="test_folder_uid", title="测试目录", is_folder=True, folder_id=0
    )
    yield folder
    folder.delete()


@pytest.fixture
def dashboard1(db, org_id, test_folder):
    """在 folder 下创建测试 dashboard 1"""
    dashboard = Dashboard.objects.create(
        org_id=org_id,
        uid="dashboard_uid_1",
        title="测试仪表盘1",
        folder_id=test_folder.id,
        is_folder=False,
    )
    yield dashboard
    dashboard.delete()


@pytest.fixture
def dashboard2(db, org_id, test_folder):
    """在 folder 下创建测试 dashboard 2"""
    dashboard = Dashboard.objects.create(
        org_id=org_id,
        uid="dashboard_uid_2",
        title="测试仪表盘2",
        folder_id=test_folder.id,
        is_folder=False,
    )
    yield dashboard
    dashboard.delete()


@pytest.fixture
def standalone_dashboard(db, org_id):
    """创建独立的 dashboard（不在 folder 中）"""
    dashboard = Dashboard.objects.create(
        org_id=org_id,
        uid="standalone_uid",
        title="独立仪表盘",
        folder_id=0,
        is_folder=False,
    )
    yield dashboard
    dashboard.delete()


@pytest.fixture
def external_permission_with_folder(db, bk_biz_id, external_user, org_id, test_folder):
    """创建包含 folder 权限的外部权限"""
    permission = ExternalPermission.objects.create(
        bk_biz_id=bk_biz_id,
        authorized_user=external_user,
        action_id="view_grafana",
        resources=[f"folder:{org_id}|{test_folder.id}"],
        expire_time=timezone.now() + timedelta(days=7),
    )
    yield permission
    permission.delete()


@pytest.fixture
def external_permission_with_dashboard(db, bk_biz_id, external_user, org_id, standalone_dashboard):
    """创建包含单个 dashboard 权限的外部权限"""
    permission = ExternalPermission.objects.create(
        bk_biz_id=bk_biz_id,
        authorized_user=external_user,
        action_id="view_grafana",
        resources=[f"{org_id}|{standalone_dashboard.uid}"],
        expire_time=timezone.now() + timedelta(days=7),
    )
    yield permission
    permission.delete()


@pytest.fixture
def external_permission_mixed(db, bk_biz_id, external_user, org_id, test_folder, standalone_dashboard):
    """创建混合权限（包含 folder 和 dashboard）"""
    permission = ExternalPermission.objects.create(
        bk_biz_id=bk_biz_id,
        authorized_user=external_user,
        action_id="view_grafana",
        resources=[
            f"folder:{org_id}|{test_folder.id}",
            f"{org_id}|{standalone_dashboard.uid}",
        ],
        expire_time=timezone.now() + timedelta(days=7),
    )
    yield permission
    permission.delete()


@pytest.fixture
def expired_permission(db, bk_biz_id, external_user, org_id, test_folder):
    """创建已过期的权限"""
    permission = ExternalPermission.objects.create(
        bk_biz_id=bk_biz_id,
        authorized_user=external_user,
        action_id="view_grafana",
        resources=[f"folder:{org_id}|{test_folder.id}"],
        expire_time=timezone.now() - timedelta(days=1),  # 已过期
    )
    yield permission
    permission.delete()


@pytest.fixture
def mock_request(bk_biz_id, external_user):
    """创建模拟的 request 对象"""
    request = Mock()
    request.org_name = str(bk_biz_id)
    request.external_user = external_user
    request.path = "/grafana/d/test_uid"
    return request


# ==================== Test Cases ====================


class TestGrafanaSwitchOrgViewPermission:
    """测试 GrafanaSwitchOrgView 的权限检查功能"""

    def test_home_dashboard_always_allowed(self, mock_request, org_id):
        """测试 home dashboard 始终允许访问"""
        mock_request.path = "/grafana/d/home"

        with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
            mock_get_org.return_value = {"id": org_id}
            result = GrafanaSwitchOrgView.is_allowed_external_request(mock_request)

        assert result is True

    def test_no_org_name_allows_all(self, mock_request):
        """测试没有 org_name 时允许所有请求"""
        mock_request.org_name = None
        result = GrafanaSwitchOrgView.is_allowed_external_request(mock_request)
        assert result is True

    def test_non_dashboard_path_allows_all(self, mock_request, org_id):
        """测试非 dashboard 路径允许访问"""
        mock_request.path = "/grafana/api/datasources"

        with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
            mock_get_org.return_value = {"id": org_id}
            result = GrafanaSwitchOrgView.is_allowed_external_request(mock_request)

        assert result is True

    def test_folder_permission_expands_to_dashboards(
        self, mock_request, org_id, external_permission_with_folder, dashboard1, dashboard2
    ):
        """测试 folder 权限自动展开为其下所有 dashboard"""
        mock_request.path = f"/grafana/d/{dashboard1.uid}"

        with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
            mock_get_org.return_value = {"id": org_id}
            result = GrafanaSwitchOrgView.is_allowed_external_request(mock_request)

        assert result is True

        # 测试 folder 下的另一个 dashboard 也允许访问
        mock_request.path = f"/grafana/d/{dashboard2.uid}"
        with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
            mock_get_org.return_value = {"id": org_id}
            result = GrafanaSwitchOrgView.is_allowed_external_request(mock_request)

        assert result is True

    def test_dashboard_permission_allows_specific_dashboard(
        self, mock_request, org_id, external_permission_with_dashboard, standalone_dashboard
    ):
        """测试单个 dashboard 权限只允许访问该 dashboard"""
        mock_request.path = f"/grafana/d/{standalone_dashboard.uid}"

        with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
            mock_get_org.return_value = {"id": org_id}
            result = GrafanaSwitchOrgView.is_allowed_external_request(mock_request)

        assert result is True

    def test_no_permission_denies_access(self, mock_request, org_id, dashboard1):
        """测试没有权限时拒绝访问"""
        mock_request.path = f"/grafana/d/{dashboard1.uid}"

        with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
            mock_get_org.return_value = {"id": org_id}
            result = GrafanaSwitchOrgView.is_allowed_external_request(mock_request)

        assert result is False

    def test_expired_permission_denies_access(self, mock_request, org_id, expired_permission, dashboard1):
        """测试过期权限拒绝访问"""
        mock_request.path = f"/grafana/d/{dashboard1.uid}"

        with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
            mock_get_org.return_value = {"id": org_id}
            result = GrafanaSwitchOrgView.is_allowed_external_request(mock_request)

        assert result is False

    def test_mixed_permission_allows_all_resources(
        self, mock_request, org_id, external_permission_mixed, dashboard1, dashboard2, standalone_dashboard
    ):
        """测试混合权限（folder + dashboard）允许访问所有相关资源"""
        # 测试 folder 下的 dashboard
        mock_request.path = f"/grafana/d/{dashboard1.uid}"
        with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
            mock_get_org.return_value = {"id": org_id}
            result = GrafanaSwitchOrgView.is_allowed_external_request(mock_request)
        assert result is True

        # 测试独立的 dashboard
        mock_request.path = f"/grafana/d/{standalone_dashboard.uid}"
        with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
            mock_get_org.return_value = {"id": org_id}
            result = GrafanaSwitchOrgView.is_allowed_external_request(mock_request)
        assert result is True

    def test_dashboards_path_format(
        self, mock_request, org_id, external_permission_with_dashboard, standalone_dashboard
    ):
        """测试 /dashboards/ 路径格式的权限检查"""
        mock_request.path = f"/grafana/dashboards/f/{standalone_dashboard.uid}"

        with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
            mock_get_org.return_value = {"id": org_id}
            result = GrafanaSwitchOrgView.is_allowed_external_request(mock_request)

        assert result is True


class TestApiProxyViewFilterResource:
    """测试 ApiProxyView 的资源过滤功能"""

    def test_filter_dashboards_with_folder_permission(
        self, mock_request, org_id, external_permission_with_folder, dashboard1, dashboard2, standalone_dashboard
    ):
        """测试 folder 权限过滤 dashboard 列表"""
        view = ApiProxyView()

        # 模拟 Grafana API 返回的 dashboard 列表
        search_results = [
            {"type": "dash-db", "uid": dashboard1.uid, "title": "测试仪表盘1"},
            {"type": "dash-db", "uid": dashboard2.uid, "title": "测试仪表盘2"},
            {"type": "dash-db", "uid": standalone_dashboard.uid, "title": "独立仪表盘"},
            {"type": "dash-folder", "uid": "folder_uid", "title": "测试目录"},
        ]

        response = HttpResponse(json.dumps(search_results))

        with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
            mock_get_org.return_value = {"id": org_id}
            view.filter_external_resource(mock_request, response)

        # 解析过滤后的结果
        filtered_results = json.loads(response.content)

        # 应该只包含 folder 下的两个 dashboard
        assert len(filtered_results) == 2
        filtered_uids = {item["uid"] for item in filtered_results}
        assert dashboard1.uid in filtered_uids
        assert dashboard2.uid in filtered_uids
        assert standalone_dashboard.uid not in filtered_uids

    def test_filter_dashboards_with_dashboard_permission(
        self, mock_request, org_id, external_permission_with_dashboard, dashboard1, standalone_dashboard
    ):
        """测试单个 dashboard 权限过滤列表"""
        view = ApiProxyView()

        search_results = [
            {"type": "dash-db", "uid": dashboard1.uid, "title": "测试仪表盘1"},
            {"type": "dash-db", "uid": standalone_dashboard.uid, "title": "独立仪表盘"},
        ]

        response = HttpResponse(json.dumps(search_results))

        with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
            mock_get_org.return_value = {"id": org_id}
            view.filter_external_resource(mock_request, response)

        filtered_results = json.loads(response.content)

        # 应该只包含有权限的 dashboard
        assert len(filtered_results) == 1
        assert filtered_results[0]["uid"] == standalone_dashboard.uid

    def test_filter_removes_folders_from_results(
        self, mock_request, org_id, external_permission_with_folder, test_folder, dashboard1
    ):
        """测试过滤结果中不包含 folder（只保留 dashboard）"""
        view = ApiProxyView()

        search_results = [
            {"type": "dash-db", "uid": dashboard1.uid, "title": "测试仪表盘1"},
            {"type": "dash-folder", "uid": test_folder.uid, "title": "测试目录"},
        ]

        response = HttpResponse(json.dumps(search_results))

        with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
            mock_get_org.return_value = {"id": org_id}
            view.filter_external_resource(mock_request, response)

        filtered_results = json.loads(response.content)

        # 应该只包含 dashboard，不包含 folder
        assert len(filtered_results) == 1
        assert filtered_results[0]["type"] == "dash-db"
        assert filtered_results[0]["uid"] == dashboard1.uid

    def test_no_external_user_skips_filtering(self, org_id, dashboard1):
        """测试非外部用户不进行过滤"""
        view = ApiProxyView()
        request = Mock()
        request.org_name = "2"
        request.external_user = None  # 非外部用户

        search_results = [
            {"type": "dash-db", "uid": dashboard1.uid, "title": "测试仪表盘1"},
        ]

        response = HttpResponse(json.dumps(search_results))

        with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
            mock_get_org.return_value = {"id": org_id}
            view.filter_external_resource(request, response)

        # 结果应该保持不变
        filtered_results = json.loads(response.content)
        assert len(filtered_results) == 1
        assert filtered_results[0]["uid"] == dashboard1.uid

    def test_empty_permission_returns_empty_list(self, mock_request, org_id, dashboard1):
        """测试没有权限时返回空列表"""
        view = ApiProxyView()

        search_results = [
            {"type": "dash-db", "uid": dashboard1.uid, "title": "测试仪表盘1"},
        ]

        response = HttpResponse(json.dumps(search_results))

        with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
            mock_get_org.return_value = {"id": org_id}
            view.filter_external_resource(mock_request, response)

        filtered_results = json.loads(response.content)
        assert len(filtered_results) == 0


class TestResourceFormatCompatibility:
    """测试资源格式兼容性"""

    def test_dashboard_resource_with_org_id_prefix(
        self, mock_request, org_id, bk_biz_id, external_user, standalone_dashboard
    ):
        """测试带 org_id 前缀的 dashboard 资源格式"""
        # 创建带 org_id 前缀的权限
        permission = ExternalPermission.objects.create(
            bk_biz_id=bk_biz_id,
            authorized_user=external_user,
            action_id="view_grafana",
            resources=[f"{org_id}|{standalone_dashboard.uid}"],
            expire_time=timezone.now() + timedelta(days=7),
        )

        mock_request.path = f"/grafana/d/{standalone_dashboard.uid}"

        with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
            mock_get_org.return_value = {"id": org_id}
            result = GrafanaSwitchOrgView.is_allowed_external_request(mock_request)

        assert result is True
        permission.delete()

    def test_dashboard_resource_without_org_id_prefix(
        self, mock_request, org_id, bk_biz_id, external_user, standalone_dashboard
    ):
        """测试不带 org_id 前缀的 dashboard 资源格式（纯 uid）"""
        # 创建不带 org_id 前缀的权限
        permission = ExternalPermission.objects.create(
            bk_biz_id=bk_biz_id,
            authorized_user=external_user,
            action_id="view_grafana",
            resources=[standalone_dashboard.uid],  # 纯 uid 格式
            expire_time=timezone.now() + timedelta(days=7),
        )

        mock_request.path = f"/grafana/d/{standalone_dashboard.uid}"

        with patch("monitor_adapter.grafana.views.get_or_create_org") as mock_get_org:
            mock_get_org.return_value = {"id": org_id}
            result = GrafanaSwitchOrgView.is_allowed_external_request(mock_request)

        assert result is True
        permission.delete()
