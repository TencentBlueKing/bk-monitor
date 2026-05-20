"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT

AST 守卫测试：bkm_cli/*.py（排除 platform_source.py 与 platform_catalog/*）
不得有 api.<x>.<y>(...) 形态的 Call 节点。
"""

from __future__ import annotations

import os
import textwrap

from kernel_api.rpc.functions.bkm_cli.platform_catalog._lint import (
    scan_bkm_cli_for_violations,
    scan_file_for_api_calls,
)


def test_scan_finds_api_call(tmp_path):
    src = tmp_path / "strategy.py"
    src.write_text(
        textwrap.dedent(
            """
            import api  # type: ignore
            def f():
                return api.cmdb.get_host_by_ip(bk_biz_id=1, ips=[])
            """
        )
    )
    violations = scan_file_for_api_calls(str(src))
    assert len(violations) == 1
    assert "api.cmdb.get_host_by_ip" in violations[0][1]


def test_scan_ignores_type_import(tmp_path):
    src = tmp_path / "cache.py"
    src.write_text(
        textwrap.dedent(
            """
            from api.cmdb.define import Host

            def f():
                x = Host()
                return x
            """
        )
    )
    violations = scan_file_for_api_calls(str(src))
    assert violations == []


def test_scan_ignores_module_import(tmp_path):
    src = tmp_path / "x.py"
    src.write_text("import api  # type: ignore\nfrom api.cmdb import define  # type: ignore\n")
    violations = scan_file_for_api_calls(str(src))
    assert violations == []


def test_scan_bkm_cli_dir_allows_platform_source(tmp_path):
    bkm_cli = tmp_path / "bkm_cli"
    bkm_cli.mkdir()
    (bkm_cli / "platform_source.py").write_text("import api  # type: ignore\napi.cmdb.get_host_by_ip(bk_biz_id=1)\n")
    (bkm_cli / "strategy.py").write_text("import api  # type: ignore\napi.cmdb.get_host_by_ip(bk_biz_id=1)\n")
    catalog = bkm_cli / "platform_catalog"
    catalog.mkdir()
    (catalog / "cmdb.py").write_text("import api  # type: ignore\napi.cmdb.get_host_by_ip(bk_biz_id=1)\n")
    violations = scan_bkm_cli_for_violations(str(bkm_cli))
    paths = [v[0] for v in violations]
    # strategy.py 违规
    assert any("strategy.py" in p for p in paths)
    # platform_source.py 与 platform_catalog/* 放行
    assert not any("platform_source.py" in p for p in paths)
    assert not any("platform_catalog" in p for p in paths)


def test_real_bkm_cli_directory_passes():
    """现状 bkm_cli/*（不含 platform_source.py 与 platform_catalog/）不应有 api.<x>.<y>(...) 违规。"""
    bkm_cli_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "functions", "bkm_cli"))
    violations = scan_bkm_cli_for_violations(bkm_cli_dir)
    assert violations == [], f"existing bkm_cli/* has api.* Call violations: {violations}"


def test_known_bypasses_documented(tmp_path):
    """锁定 AST 守卫的已知边界——以下写法能绕过 _is_api_call，需 PR 评审兜底。

    出现新的合法绕过场景时，请显式更新本测试明示边界，而不是悄悄改 _lint.py 把它过掉。
    """
    src = tmp_path / "evil.py"
    src.write_text(
        textwrap.dedent(
            """
            import api  # type: ignore

            # bypass 1: getattr 间接取域
            getattr(api, "cmdb").get_host_by_ip(bk_biz_id=1)

            # bypass 2: 起别名后调用
            alias = api
            alias.cmdb.get_host_by_ip(bk_biz_id=1)

            # bypass 3: from-import 后直接调
            from api import cmdb  # type: ignore
            cmdb.get_host_by_ip(bk_biz_id=1)

            # bypass 4: from-import 取 Resource 类再实例化调用
            from api.cmdb import default as cmdb_default  # type: ignore
            cmdb_default.GetHostByIP()(bk_biz_id=1)
            """
        )
    )
    violations = scan_file_for_api_calls(str(src))
    assert violations == [], (
        "AST 守卫只匹配 api.<x>.<y>(...) Call 形态；如果想拦上述绕过，请扩展 _is_api_call 并同步更新本测试。"
    )
