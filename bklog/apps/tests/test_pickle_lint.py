"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

# 仓库级 lint 守门：禁止在 safe_unpickle.py 之外直接调用 pickle / cloudpickle 反序列化。
#
# 背景：AIOPS 模型文件来自跨信任域的 BkData 接口，反序列化必须经过受限 Unpickler +
# schema 校验（safe_unpickle.safe_loads + validate_model_content）。若直接 pickle.loads(...)
# 等于把 CVE-2024-aiops-rce 防御链旁路掉。本测试用 AST 静态扫描 bklog/ 下所有 .py，
# 命中即失败，并提示开发者改走 AiopsModelHandler.pickle_decode 唯一入口。

import ast
import pathlib

from django.test import SimpleTestCase

# 禁止的形态：X.Y(...)
_FORBIDDEN_CALLS: frozenset[tuple[str, str]] = frozenset(
    {
        ("pickle", "loads"),
        ("pickle", "load"),
        ("pickle", "Unpickler"),
        ("cloudpickle", "loads"),
        ("cloudpickle", "load"),
        ("cloudpickle", "Unpickler"),
    }
)

# 白名单：唯一允许的封装入口
_ALLOWED_FILES: frozenset[str] = frozenset(
    {
        "apps/log_clustering/handlers/aiops/aiops_model/safe_unpickle.py",
    }
)

# 跳过的目录（与 bklog/.flake8 的 exclude 对齐 + 测试代码自身）
_SKIP_PREFIXES: tuple[str, ...] = (
    "blueapps/",
    "blueking/",
    "version_log/",
    "bk_dataview/",
    "pipeline/",
    "config/",
    "sites/",
    "static/",
)


def _is_test_file(rel_path: str) -> bool:
    """测试代码允许使用 pickle.loads/dumps 构造测试 payload。"""
    parts = pathlib.PurePosixPath(rel_path).parts
    if "tests" in parts:
        return True
    return parts[-1].startswith("test_")


def _scan_file(py_path: pathlib.Path) -> list[tuple[int, str]]:
    """返回 [(lineno, "module.attr"), ...]，命中禁列表的调用点。"""
    try:
        source = py_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        # 形态：X.Y(...) 且 X 是裸 Name
        value = func.value
        if not isinstance(value, ast.Name):
            continue
        pair = (value.id, func.attr)
        if pair in _FORBIDDEN_CALLS:
            hits.append((node.lineno, f"{pair[0]}.{pair[1]}"))
    return hits


class PickleLintTests(SimpleTestCase):
    """禁止 pickle.loads / cloudpickle.loads 等在 safe_unpickle 之外被直接调用。"""

    def test_no_direct_pickle_load_outside_safe_unpickle(self):
        bklog_root = pathlib.Path(__file__).resolve().parents[2]
        self.assertTrue(
            (bklog_root / "manage.py").exists(),
            f"unexpected bklog root resolved: {bklog_root}",
        )

        violations: list[str] = []
        for py in bklog_root.rglob("*.py"):
            rel = py.relative_to(bklog_root).as_posix()
            if rel in _ALLOWED_FILES:
                continue
            if any(rel.startswith(p) for p in _SKIP_PREFIXES):
                continue
            if _is_test_file(rel):
                continue
            for lineno, call in _scan_file(py):
                violations.append(f"{rel}:{lineno}  {call}(...)")

        msg = (
            "禁止在 safe_unpickle.py 之外直接调用 pickle / cloudpickle 反序列化。\n"
            "所有 AIOPS 模型文件反序列化必须走 AiopsModelHandler.pickle_decode -> safe_loads。\n"
            "命中位置：\n  " + "\n  ".join(violations)
        )
        self.assertEqual(violations, [], msg)
