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

from django.test import TestCase

from apps.log_databus.utils.bkdata_rt_name import collapse_underscores


class TestCollapseUnderscores(TestCase):
    """覆盖 collapse_underscores 对各种连续下划线场景的处理.

    特别注意: 本 helper 只做合并连续下划线, 不做大小写 / 字符过滤 / 长度截断 /
    首字符校验. 这些场景留在调用方或将来再处理.
    """

    def test_real_world_case_with_double_underscore(self):
        # 线上聚类接入失败的实际 case
        raw = "bklog_bcs_k8s_27019_bcs_test_env__log_hlmdw_path"
        expected = "bklog_bcs_k8s_27019_bcs_test_env_log_hlmdw_path"
        self.assertEqual(collapse_underscores(raw), expected)

    def test_multiple_consecutive_underscores(self):
        self.assertEqual(collapse_underscores("a__b___c____d"), "a_b_c_d")

    def test_no_consecutive_underscores_unchanged(self):
        self.assertEqual(collapse_underscores("no_double_underscore"), "no_double_underscore")

    def test_leading_and_trailing_double_underscores_only_merged(self):
        # 不去除首尾 _, 只合并
        self.assertEqual(
            collapse_underscores("__leading_and_trailing__"),
            "_leading_and_trailing_",
        )

    def test_empty_string(self):
        self.assertEqual(collapse_underscores(""), "")

    def test_uppercase_preserved(self):
        # 大小写不变, 仅合并 __
        self.assertEqual(collapse_underscores("MyApp__Log"), "MyApp_Log")

    def test_non_alphanumeric_chars_preserved(self):
        # 非 [A-Za-z0-9_] 字符不动, 只合并 __
        self.assertEqual(
            collapse_underscores("path.with-special__chars"),
            "path.with-special_chars",
        )

    def test_idempotent(self):
        # collapse_underscores(collapse_underscores(x)) == collapse_underscores(x)
        raw = "a__b___c____d__"
        once = collapse_underscores(raw)
        twice = collapse_underscores(once)
        self.assertEqual(once, twice)

    def test_result_never_contains_double_underscore(self):
        for raw in [
            "bklog_bcs_k8s_27019_bcs_test_env__log_hlmdw_path",
            "a__b___c____d",
            "__leading_and_trailing__",
            "MyApp__Log",
        ]:
            self.assertNotIn("__", collapse_underscores(raw))
