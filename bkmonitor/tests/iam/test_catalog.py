"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import MagicMock, patch

from bkmonitor.iam.adapters.catalog import (
    GrafanaRef,
    fetch_instance_info,
    list_instances,
    parse_grafana_instance_id,
    parse_iam_path,
)


# ============================================================================
# parse_grafana_instance_id
# ============================================================================


class TestParseGrafanaInstanceId:
    def test_folder_format(self):
        ref = parse_grafana_instance_id("folder:14|7")
        assert ref == GrafanaRef(kind="folder", org_id=14, folder_id=7)

    def test_dashboard_org_uid_format(self):
        ref = parse_grafana_instance_id("14|f0ImroNIz")
        assert ref == GrafanaRef(kind="dashboard", org_id=14, uid="f0ImroNIz")

    def test_dashboard_pure_uid_format(self):
        ref = parse_grafana_instance_id("f0ImroNIz")
        assert ref == GrafanaRef(kind="dashboard", uid="f0ImroNIz")

    def test_non_numeric_org_head_falls_back_to_uid(self):
        # 历史兼容：头段不是数字时，整体按纯 uid 处理
        ref = parse_grafana_instance_id("abc|def")
        assert ref == GrafanaRef(kind="dashboard", uid="abc|def")

    def test_invalid_folder_format(self):
        assert parse_grafana_instance_id("folder:abc|7") is None
        assert parse_grafana_instance_id("folder:14|xyz") is None
        assert parse_grafana_instance_id("folder:14") is None

    def test_empty(self):
        assert parse_grafana_instance_id("") is None
        assert parse_grafana_instance_id(None) is None


# ============================================================================
# parse_iam_path
# ============================================================================


class TestParseIamPath:
    def test_single_segment(self):
        assert parse_iam_path("/space,2/") == [{"type": "space", "id": "2"}]

    def test_multi_segment(self):
        result = parse_iam_path("/space,2/apm_application,3/")
        assert result == [{"type": "space", "id": "2"}, {"type": "apm_application", "id": "3"}]

    def test_empty(self):
        assert parse_iam_path("") == []
        assert parse_iam_path("/") == []
        assert parse_iam_path(None) == []

    def test_no_trailing_slash(self):
        assert parse_iam_path("/space,2") == [{"type": "space", "id": "2"}]


# ============================================================================
# list_instances / fetch_instance_info 分派
# ============================================================================


class TestDispatch:
    def test_unknown_type(self):
        assert list_instances("unknown_rt", {}, {}) == {"count": 0, "results": []}
        assert fetch_instance_info("unknown_rt", ["1"], []) == []


# ============================================================================
# apm / rum 目录查询（同时返回 display_name=app_alias 与 name=app_name）
# ============================================================================


class TestApmCatalog:
    def test_fetch_apm_returns_display_and_name(self):
        row = MagicMock()
        row.pk = 390
        row.app_alias = "我的APM"
        row.app_name = "my_apm_app"
        row.bk_biz_id = 2
        qs = MagicMock()
        qs.__iter__.return_value = iter([row])
        with patch("apm_web.models.Application.objects.filter", return_value=qs) as m_filter:
            result = fetch_instance_info("apm_application", ["390"], ["display_name", "name", "_bk_iam_path_"])
        assert result == [{"id": "390", "display_name": "我的APM", "name": "my_apm_app", "_bk_iam_path_": "/space,2/"}]
        m_filter.assert_called_once_with(pk__in=[390], bk_tenant_id="system")

    def test_fetch_apm_skips_non_numeric_ids(self):
        with patch("apm_web.models.Application.objects.filter") as m_filter:
            result = fetch_instance_info("apm_application", ["not-a-number"], [])
        assert result == []
        m_filter.assert_not_called()

    def test_list_apm_parent_filter_and_pagination(self):
        rows = [MagicMock() for _ in range(2)]
        for i, row in enumerate(rows):
            row.pk = 390 + i
            row.app_alias = f"alias-{i}"
            row.app_name = f"app-{i}"
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.count.return_value = 2
        qs.__getitem__.return_value = rows
        with patch("apm_web.models.Application.objects.filter", return_value=qs):
            result = list_instances(
                "apm_application",
                {"parent": {"type": "space", "id": "2"}},
                {"page": 1, "page_size": 10},
            )
        assert result["count"] == 2
        assert result["results"] == [
            {"id": "390", "display_name": "alias-0", "name": "app-0"},
            {"id": "391", "display_name": "alias-1", "name": "app-1"},
        ]


class TestRumCatalog:
    def test_fetch_rum_returns_display_and_name(self):
        row = MagicMock()
        row.pk = 11
        row.app_alias = "我的RUM"
        row.app_name = "my_rum_app"
        row.bk_biz_id = -42
        qs = MagicMock()
        qs.__iter__.return_value = iter([row])
        with patch("rum_web.models.application.Application.objects.filter", return_value=qs):
            result = fetch_instance_info("rum_application", ["11"], ["name", "_bk_iam_path_"])
        assert result == [{"id": "11", "display_name": "我的RUM", "name": "my_rum_app", "_bk_iam_path_": "/space,-42/"}]


# ============================================================================
# grafana 目录查询（三种 ID 格式）
# ============================================================================


def _space_queryset():
    """模拟 Space.objects.filter(...) 返回的空间列表（bkcc 空间，space_id=2）。"""
    space = MagicMock()
    space.space_type_id = "bkcc"
    space.space_id = "2"
    space.id = 99
    qs = MagicMock()
    qs.__iter__.return_value = iter([space])
    return qs


def _org_filter(**kwargs):
    qs = MagicMock()
    if "name__in" in kwargs:
        # _get_valid_org_ids：按空间名反查合法 org id 集合
        qs.values_list.return_value = [14]
    else:
        # _fetch_grafana：按 org id 批量查 org（org.name 即 bk_biz_id）
        org = MagicMock()
        org.id = 14
        org.name = "2"
        qs.__iter__.return_value = iter([org])
    return qs


def _dashboard_filter(**kwargs):
    qs = MagicMock()
    qs.filter.return_value = qs
    if kwargs.get("id__in") == {7}:
        folder = MagicMock()
        folder.id = 7
        folder.org_id = 14
        folder.title = "运维大盘"
        qs.__iter__.return_value = iter([folder])
    elif kwargs.get("uid__in") == {"uidX"}:
        dash = MagicMock()
        dash.uid = "uidX"
        dash.org_id = 14
        dash.folder_id = 0
        dash.title = "大盘"
        qs.__iter__.return_value = iter([dash])
    elif kwargs.get("is_folder"):
        # list_grafana 的 folders / folder_titles 查询
        folder = MagicMock()
        folder.org_id = 14
        folder.id = 7
        folder.title = "运维大盘"
        qs.__iter__.return_value = iter([folder])
    else:
        # list_grafana 的 dashboards 查询
        dash = MagicMock()
        dash.org_id = 14
        dash.uid = "uidX"
        dash.folder_id = 7
        dash.title = "大盘"
        qs.__iter__.return_value = iter([dash])
    return qs


class TestGrafanaCatalog:
    def test_fetch_grafana_supports_three_formats(self):
        with (
            patch("metadata.models.Space.objects.filter", return_value=_space_queryset()),
            patch("bk_dataview.models.Org.objects.filter", side_effect=_org_filter),
            patch("bk_dataview.models.Dashboard.objects.filter", side_effect=_dashboard_filter),
        ):
            result = fetch_instance_info(
                "grafana_dashboard",
                ["folder:14|7", "14|uidX", "uidX"],
                ["display_name", "_bk_iam_path_"],
            )
        assert result == [
            {"id": "folder:14|7", "display_name": "[目录] 运维大盘", "_bk_iam_path_": "/space,2/"},
            {"id": "14|uidX", "display_name": "[仪表盘] General/大盘", "_bk_iam_path_": "/space,2/"},
            {"id": "uidX", "display_name": "[仪表盘] General/大盘", "_bk_iam_path_": "/space,2/"},
        ]

    def test_fetch_grafana_skips_invalid_ids(self):
        with (
            patch("metadata.models.Space.objects.filter", return_value=_space_queryset()),
            patch("bk_dataview.models.Org.objects.filter", side_effect=_org_filter),
            patch("bk_dataview.models.Dashboard.objects.filter") as m_dash_filter,
        ):
            result = fetch_instance_info("grafana_dashboard", ["folder:bad", ""], [])
        assert result == []
        # 全部 ID 解析失败时，不发起任何 Dashboard 查询
        m_dash_filter.assert_not_called()

    def test_fetch_grafana_query_count_independent_of_id_count(self):
        """批量优化：查询次数与 ID 数量无关（Dashboard ≤3 次、Org ≤2 次）。"""
        with (
            patch("metadata.models.Space.objects.filter", return_value=_space_queryset()),
            patch("bk_dataview.models.Org.objects.filter", side_effect=_org_filter) as m_org_filter,
            patch("bk_dataview.models.Dashboard.objects.filter", side_effect=_dashboard_filter) as m_dash_filter,
        ):
            ids = ["folder:14|7"] + [f"14|dash-{i}" for i in range(20)] + ["14|uidX"]
            result = fetch_instance_info("grafana_dashboard", ids, ["display_name", "_bk_iam_path_"])
        assert len(result) == 2
        # Dashboard 查询：folders + dashboards + folder_titles 最多 3 次
        assert m_dash_filter.call_count <= 3
        # Org 查询：valid_org_ids + 批量 org 名 最多 2 次
        assert m_org_filter.call_count <= 2

    def test_list_grafana_by_parent(self):
        with (
            patch("metadata.models.Space.objects.filter", return_value=_space_queryset()),
            patch("bk_dataview.models.Org.objects.filter", side_effect=_org_filter),
            patch("bk_dataview.models.Dashboard.objects.filter", side_effect=_dashboard_filter) as m_dash_filter,
            patch("bk_dataview.api.get_org_by_name", return_value={"id": 14}),
        ):
            result = list_instances(
                "grafana_dashboard",
                {"parent": {"type": "space", "id": "2"}},
                {"page": 1, "page_size": 10},
            )
        assert result["count"] == 2
        assert result["results"] == [
            {"id": "folder:14|7", "display_name": "[目录] 运维大盘"},
            {"id": "14|uidX", "display_name": "[仪表盘] 运维大盘/大盘"},
        ]
        # 收窄优化：folders 只查一次（枚举 + 目录名映射共用），dashboards 一次
        assert m_dash_filter.call_count == 2
