"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import Mock, patch

from monitor_web.grafana.resources.manage import GetDashboardList, StarDashboard, UnstarDashboard


def test_external_user_filters_starred_dashboard_list():
    """external 用户查询收藏仪表盘时，不返回无权限的收藏项。"""
    request = Mock()
    request.external_user = "external_user_001"
    request.user = Mock(username="authorizer")
    search_results = [
        {
            "id": 1,
            "uid": "leaked_uid",
            "title": "无权限收藏仪表盘",
            "isStarred": True,
            "url": "/d/leaked_uid",
            "uri": "db/leaked_uid",
            "tags": [],
        },
        {
            "id": 2,
            "uid": "allowed_uid",
            "title": "有权限收藏仪表盘",
            "isStarred": True,
            "url": "/d/allowed_uid",
            "uri": "db/allowed_uid",
            "tags": [],
        },
    ]

    with (
        patch("monitor_web.grafana.resources.manage.get_request", return_value=request),
        patch("monitor_web.grafana.resources.manage.get_or_create_org", return_value={"id": 1}),
        patch("monitor_web.grafana.resources.manage.DashboardPermission.has_permission") as mock_has_permission,
        patch("monitor_web.grafana.resources.manage.api.grafana.search_folder_or_dashboard") as mock_search,
    ):
        mock_has_permission.return_value = (True, None, {"allowed_uid": Mock()})
        mock_search.return_value = {"result": True, "data": search_results}
        result = GetDashboardList().perform_request({"bk_biz_id": 2, "is_report": False, "is_starred": True})

    assert [dashboard["uid"] for dashboard in result] == ["allowed_uid"]
    mock_has_permission.assert_called_once_with(request, None, 2, force_check=True)
    mock_search.assert_called_once_with(type="dash-db", org_id=1, username="external_external_user_001", starred="true")


def test_external_user_star_dashboard_uses_external_grafana_user():
    """external 用户收藏仪表盘时，写入 external 专属 Grafana 用户。"""
    request = Mock()
    request.external_user = "external_user_001"
    request.user = Mock(username="authorizer")

    with (
        patch("monitor_web.grafana.resources.manage.get_request", return_value=request),
        patch("monitor_web.grafana.resources.manage.get_or_create_org", return_value={"id": 1}),
        patch("monitor_web.grafana.resources.manage.api.grafana.star_dashboard") as mock_star_dashboard,
    ):
        StarDashboard().perform_request({"bk_biz_id": 2, "dashboard_id": "100"})

    mock_star_dashboard.assert_called_once_with(org_id=1, id="100", username="external_external_user_001")


def test_external_user_unstar_dashboard_uses_external_grafana_user():
    """external 用户取消收藏仪表盘时，写入 external 专属 Grafana 用户。"""
    request = Mock()
    request.external_user = "external_user_001"
    request.user = Mock(username="authorizer")

    with (
        patch("monitor_web.grafana.resources.manage.get_request", return_value=request),
        patch("monitor_web.grafana.resources.manage.get_or_create_org", return_value={"id": 1}),
        patch("monitor_web.grafana.resources.manage.api.grafana.unstar_dashboard") as mock_unstar_dashboard,
    ):
        UnstarDashboard().perform_request({"bk_biz_id": 2, "dashboard_id": "100"})

    mock_unstar_dashboard.assert_called_once_with(org_id=1, id="100", username="external_external_user_001")
