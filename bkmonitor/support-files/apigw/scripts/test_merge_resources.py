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


def test_repository_resources_have_unique_operation_ids():
    """仓库内现有 apigw 资源定义必须无重复 operationId（回归基线）。"""
    public_dirs = ["internal", "external"]
    verify_dirs = ["app", "user"]
    merged: dict[str, dict] = {}
    for public_dir in public_dirs:
        for verify_dir in verify_dirs:
            for file in _RESOURCES_DIR.glob(f"{public_dir}/{verify_dir}/*.yaml"):
                merged.update(yaml.safe_load(file.read_text())["paths"])
    check_unique_operation_ids(merged)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
