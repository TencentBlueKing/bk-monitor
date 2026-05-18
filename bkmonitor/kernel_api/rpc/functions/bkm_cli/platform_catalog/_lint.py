"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT

AST 守卫：除 platform_source.py 与 platform_catalog/* 外，bkm_cli/* 模块不得有
api.<domain>.<func>(...) 形态的 Call 节点。类型 import（如 `from api.cmdb.define import Host`）
不算违规——它不是 Call 节点。
"""

from __future__ import annotations

import ast
import os
from pathlib import Path


def _is_api_call(node: ast.AST) -> bool:
    """判断节点是否为 api.<x>.<y>(...) 形态的 Call。"""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not isinstance(func, ast.Attribute):
        return False
    if not isinstance(func.value, ast.Attribute):
        return False
    if not isinstance(func.value.value, ast.Name):
        return False
    return func.value.value.id == "api"


def scan_file_for_api_calls(file_path: str) -> list[tuple[int, str]]:
    """返回 [(lineno, snippet)] 列表。"""
    try:
        with open(file_path, encoding="utf-8") as f:
            source = f.read()
    except OSError:
        return []
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return []
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if _is_api_call(node):
            try:
                snippet = ast.unparse(node).splitlines()[0]
            except (AttributeError, TypeError):
                snippet = "<api call>"
            violations.append((node.lineno, snippet))
    return violations


def scan_bkm_cli_for_violations(bkm_cli_dir: str) -> list[tuple[str, int, str]]:
    """扫描整个 bkm_cli 目录，排除 platform_source.py 与 platform_catalog/*。

    返回 [(relpath, lineno, snippet)]。
    """
    bkm_cli_path = Path(bkm_cli_dir).resolve()
    catalog_path = bkm_cli_path / "platform_catalog"
    violations: list[tuple[str, int, str]] = []
    for root, _dirs, files in os.walk(bkm_cli_path):
        root_path = Path(root).resolve()
        try:
            root_path.relative_to(catalog_path)
            continue
        except ValueError:
            pass
        for name in files:
            if not name.endswith(".py"):
                continue
            if name == "platform_source.py" and root_path == bkm_cli_path:
                continue
            file_path = root_path / name
            for lineno, snippet in scan_file_for_api_calls(str(file_path)):
                violations.append((str(file_path.relative_to(bkm_cli_path)), lineno, snippet))
    return violations
