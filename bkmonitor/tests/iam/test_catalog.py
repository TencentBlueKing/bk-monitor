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

from bkmonitor.iam.handlers.catalog import (
    GrafanaRef,
    fetch_instance_info,
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


def test_resource_resolution_uses_native_provider_query():
    from iam.resource.provider import ListResult

    expected = [{"id": "42", "name": "application", "_bk_iam_path_": "/space,3/"}]
    provider = MagicMock()
    provider.fetch_instance_info.return_value = ListResult(expected, 1)
    with patch("bkmonitor.iam.handlers.catalog.get_resource_provider", return_value=provider) as lookup:
        result = fetch_instance_info("apm_application", ["42"], ["name", "_bk_iam_path_"], "tenant-a")
    assert result == expected
    lookup.assert_called_once_with("apm_application")
    filters = provider.fetch_instance_info.call_args.args[0]
    assert filters.ids == ["42"]
    assert filters.attrs == ["name", "_bk_iam_path_"]
    assert provider.fetch_instance_info.call_args.kwargs == {
        "bk_tenant_id": "tenant-a", "include_resource_metadata": True
    }
