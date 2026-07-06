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

from constants.mcp import (
    MCP_SERVER_SUFFIX_TO_PERMISSION_ACTION,
    OPERATION_MCP_PERMISSION_ACTION,
    extract_mcp_server_suffix,
    get_mcp_permission_action_by_server_name,
)


class TestExtractMcpServerSuffix:
    """覆盖 `extract_mcp_server_suffix` 在各种 server name 形态下的解析行为。"""

    @pytest.mark.parametrize(
        "server_name,expected_suffix",
        [
            # 1) 不同网关前缀
            ("bkmonitorv3-prod-dashboard-edit", "dashboard-edit"),
            ("bk-monitor-prod-profiling-query", "profiling-query"),
            # 2) 不同 stage
            ("bkmonitorv3-stage-dashboard-edit", "dashboard-edit"),
            ("bkmonitorv3-stag-dashboard-edit", "dashboard-edit"),
            # 3) 单段后缀
            ("bkmonitorv3-prod-alarm", "alarm"),
            ("bkmonitorv3-prod-event", "event"),
            # 4) 多段后缀
            ("bkmonitorv3-prod-apm-trace", "apm-trace"),
            ("bkmonitorv3-prod-dashboard-ascode", "dashboard-ascode"),
        ],
    )
    def test_valid_names(self, server_name, expected_suffix):
        assert extract_mcp_server_suffix(server_name) == expected_suffix

    @pytest.mark.parametrize(
        "server_name",
        [
            "",
            "foo",
            "foo-prod",  # 缺 suffix
            "bkmonitorv3-test-dashboard-edit",  # 未知 stage
            "bkmonitorv3-dashboard-edit",  # 没有 stage 段
        ],
    )
    def test_invalid_names_return_empty(self, server_name):
        assert extract_mcp_server_suffix(server_name) == ""

    @pytest.mark.parametrize(
        "server_name,expected_suffix",
        [
            # 5) 大小写：解析前会统一 lower，必须能匹配字典
            ("BKMonitorV3-Prod-Dashboard-Edit", "dashboard-edit"),
            ("BK-MONITOR-PROD-PROFILING-QUERY", "profiling-query"),
        ],
    )
    def test_case_insensitive_parsing(self, server_name, expected_suffix):
        """大小写不敏感解析后，结果必须为小写以匹配后缀字典。"""
        assert extract_mcp_server_suffix(server_name) == expected_suffix

    @pytest.mark.parametrize(
        "server_name,expected_suffix",
        [
            # 6) 贪婪歧义边界：取 *最先* 出现的 stage 关键字
            #    （旧实现 `.+` 贪婪会取最后一个，新实现非贪婪取最先）
            ("bk-monitor-stage-prod-dashboard-edit", "prod-dashboard-edit"),
            # 7) 后缀本身叫 `prod`（合法但不在映射表里）
            ("bkmonitorv3-prod-prod", "prod"),
        ],
    )
    def test_greedy_edge_cases(self, server_name, expected_suffix):
        assert extract_mcp_server_suffix(server_name) == expected_suffix


class TestGetMcpPermissionActionByServerName:
    """覆盖 `get_mcp_permission_action_by_server_name` 的端到端映射结果。"""

    @pytest.mark.parametrize(
        "server_name,expected_action",
        [
            ("bkmonitorv3-prod-dashboard-edit", "using_dashboard_mcp"),
            ("bk-monitor-prod-profiling-query", "using_apm_mcp"),
            ("bkmonitorv3-stage-log-query", "using_log_mcp"),
            ("BKMonitorV3-Prod-Dashboard-Edit", "using_dashboard_mcp"),  # 大小写不敏感
            ("bkmonitorv3-prod-operation", "using_operation_mcp"),  # 运营数据 MCP
        ],
    )
    def test_known_actions(self, server_name, expected_action):
        assert get_mcp_permission_action_by_server_name(server_name) == expected_action

    def test_operation_action_constant_matches_mapping(self):
        """运营 MCP 权限动作常量必须与映射表一致，避免鉴权收敛逻辑因常量漂移而失效。"""
        assert OPERATION_MCP_PERMISSION_ACTION == "using_operation_mcp"
        assert MCP_SERVER_SUFFIX_TO_PERMISSION_ACTION["operation"] == OPERATION_MCP_PERMISSION_ACTION

    @pytest.mark.parametrize(
        "server_name",
        [
            "",  # 空
            "foo",  # 完全非法
            "foo-prod-bar",  # 解析得到后缀但不在映射里
            "bkmonitorv3-test-dashboard-edit",  # 未知 stage
            "bkmonitorv3-prod-unknown-tool",  # 已知格式但未注册的后缀
        ],
    )
    def test_unknown_returns_empty(self, server_name):
        assert get_mcp_permission_action_by_server_name(server_name) == ""

    def test_every_mapping_key_is_resolvable(self):
        """保护性测试：映射表里的每个 key，使用 `<apigw>-prod-<key>` 必须能解析回该 key。

        这能在以后给字典加新的 key（比如不小心引入大写或空格）时立刻报错，
        避免 `MCP_SERVER_SUFFIX_TO_PERMISSION_ACTION` 与正则约束彼此漂移。
        """
        for suffix, expected_action in MCP_SERVER_SUFFIX_TO_PERMISSION_ACTION.items():
            server_name = f"bk-monitor-prod-{suffix}"
            assert extract_mcp_server_suffix(server_name) == suffix, suffix
            assert get_mcp_permission_action_by_server_name(server_name) == expected_action, suffix
