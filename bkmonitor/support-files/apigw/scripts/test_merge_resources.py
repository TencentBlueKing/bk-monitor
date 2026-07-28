#! /usr/bin/env python
"""merge_resources 的 operationId 唯一性校验测试。

apigateway 要求 operationId 全局唯一，重复会在部署阶段被网关以 `40002 校验失败`
拒绝，导致 migrate Job CrashLoopBackOff。这里在合并阶段就拦住该类回归。

脚本不是包模块，按文件路径动态加载，便于在任意 python 环境下独立运行：
    python support-files/apigw/scripts/test_merge_resources.py
"""

import importlib.util
from pathlib import Path

import pytest
import yaml

_SCRIPT = Path(__file__).with_name("merge_resources.py")
_spec = importlib.util.spec_from_file_location("merge_resources", _SCRIPT)
merge_resources = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(merge_resources)

check_unique_operation_ids = merge_resources.check_unique_operation_ids
merge_resources_func = merge_resources.merge_resources

_RESOURCES_DIR = _SCRIPT.parent.parent / "resources"
_ALERT_MCP_FILE = _RESOURCES_DIR / "internal/user/alert_mcp.yaml"
_ALERT_HANDLING_MCP_FILE = _RESOURCES_DIR / "internal/user/alert_handling_mcp.yaml"

_ALERT_QUERY_OPERATION_IDS = {
    "list_alerts",
    "get_alert_top_n",
    "get_strategy_snapshot",
    "get_strategy_detail",
    "get_alert_info",
    "get_alert_events",
    "get_alert_event_ts",
    "get_alert_event_tag_detail",
    "get_alert_k8s_target",
    "get_alert_host_target",
    "get_alert_traces",
    "get_alert_log_relations",
}
_ALERT_HANDLING_OPERATION_IDS = {
    "search_alarm_strategies",
    "get_alarm_strategy",
    "create_alarm_strategy",
    "update_alarm_strategy",
    "search_alarm_shields",
    "get_alarm_shield",
    "create_alarm_shield",
    "update_alarm_shield",
    "disable_alarm_shield",
    "search_alarm_notice_groups",
    "update_alarm_notice_group",
    "search_alarm_action_configs",
    "get_alarm_action_config",
    "update_alarm_action_config",
}


def _load_paths(file: Path) -> dict[str, dict]:
    return yaml.safe_load(file.read_text())["paths"]


def _operation_ids(paths: dict[str, dict]) -> set[str]:
    return {method_data["operationId"] for path_data in paths.values() for method_data in path_data.values()}


def test_check_unique_operation_ids_passes_on_unique():
    merged = {
        "/app/apm/calculate_by_range/": {"post": {"operationId": "calculate_by_range"}},
        "/mcp/calculate_by_range/": {"post": {"operationId": "apm_mcp_calculate_by_range"}},
    }
    # 不应抛出
    check_unique_operation_ids(merged)


def test_check_unique_operation_ids_raises_on_duplicate():
    merged = {
        "/app/apm/calculate_by_range/": {"post": {"operationId": "calculate_by_range"}},
        "/mcp/calculate_by_range/": {"post": {"operationId": "calculate_by_range"}},
    }
    with pytest.raises(ValueError, match="duplicate operationId 'calculate_by_range'"):
        check_unique_operation_ids(merged)


def test_check_unique_operation_ids_ignores_missing_operation_id():
    # 缺失 operationId 的方法不参与唯一性校验，不应误报
    merged = {
        "/a/": {"get": {}},
        "/b/": {"get": {}},
    }
    check_unique_operation_ids(merged)


def test_alert_mcp_resource_groups_are_disjoint():
    """告警查询与处置 MCP 必须保持独立，查询资源固定为当前 12 个。"""
    query_paths = _load_paths(_ALERT_MCP_FILE)
    handling_paths = _load_paths(_ALERT_HANDLING_MCP_FILE)

    assert len(query_paths) == 12
    assert _operation_ids(query_paths) == _ALERT_QUERY_OPERATION_IDS
    assert set(query_paths).isdisjoint(handling_paths)
    assert _operation_ids(query_paths).isdisjoint(_operation_ids(handling_paths))


def test_alert_handling_mcp_contract():
    """告警处置 MCP 必须精确包含 14 个资源并使用独立标签。"""
    paths = _load_paths(_ALERT_HANDLING_MCP_FILE)

    assert len(paths) == 14
    assert set(paths) == {f"/mcp/{operation_id}/" for operation_id in _ALERT_HANDLING_OPERATION_IDS}
    assert _operation_ids(paths) == _ALERT_HANDLING_OPERATION_IDS
    for path_data in paths.values():
        for method_data in path_data.values():
            assert method_data["tags"] == ["alert_handling_mcp"]


def test_repository_resources_have_unique_operation_ids():
    """仓库内现有 apigw 资源定义必须无重复 operationId（回归基线）。"""
    public_dirs = ["internal", "external"]
    verify_dirs = ["app", "user"]
    merged: dict[str, dict] = {}
    for public_dir in public_dirs:
        for verify_dir in verify_dirs:
            for file in _RESOURCES_DIR.glob(f"{public_dir}/{verify_dir}/*.yaml"):
                for path, path_data in _load_paths(file).items():
                    # 带上来源文件，避免同一路径被 dict.update 覆盖后漏检 operationId 冲突。
                    merged[f"{file.relative_to(_RESOURCES_DIR)}::{path}"] = path_data
    check_unique_operation_ids(merged)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
