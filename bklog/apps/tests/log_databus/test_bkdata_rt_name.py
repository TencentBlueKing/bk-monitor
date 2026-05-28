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

from apps.log_databus.utils.bkdata_rt_name import (
    BKDATA_RT_NAME_MAX_LEN,
    BKLOG_RT_NAME_PREFIX,
    collapse_underscores,
    make_bkdata_rt_name,
)


class TestCollapseUnderscores(TestCase):
    """覆盖 collapse_underscores 对各种连续下划线场景的处理.

    特别注意: 本 helper 只做合并连续下划线, 不做大小写 / 字符过滤 / 长度截断 /
    首字符校验. 这些场景留在调用方或将来再处理.
    """

    def test_consecutive_underscore_in_middle(self):
        # 中段含 `__`: 仅折叠为 `_`, 其它保持不变
        raw = "bklog_part_a__b_c"
        expected = "bklog_part_a_b_c"
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
            "bklog_part_a__b_c",
            "a__b___c____d",
            "__leading_and_trailing__",
            "MyApp__Log",
        ]:
            self.assertNotIn("__", collapse_underscores(raw))


class TestMakeBkdataRtName(TestCase):
    """覆盖 make_bkdata_rt_name 对 BKData 命名四条约束 (首字符字母 / 字符集 /
    禁止 __ / 长度 <= 50) 的处理.

    回归基线: 早期实现 ``f"bklog_{name_en}"[-50:]`` 在 name_en 较长时会把 ``bklog_``
    前缀尾截掉, 导致首字符变成下划线 / 数字, 触发 BKData 1500001. 本测试类显式覆盖
    那一类长度边界, 避免再次回归.
    """

    def test_short_name_keeps_full_prefix(self):
        # 短名字: 直接拼前缀, 不触发任何截断 / 折叠.
        self.assertEqual(make_bkdata_rt_name("foo"), "bklog_foo")

    def test_49_char_name_en_keeps_letter_first_char(self):
        # 长度 49 触发的核心边界: 老实现 ``f"bklog_{name_en}"[-50:]`` 在 name_en >= 45 字符
        # 时会把 ``bklog_`` 前缀尾截掉, 首字符落到 name_en 内部 -- 当截断点正好是 ``_``
        # 时就触发 BKData 1500001. 修复后必须以字母开头且长度 <= 50.
        name_en = "a" * 49
        self.assertEqual(len(name_en), 49)
        rt = make_bkdata_rt_name(name_en)
        self.assertEqual(rt, "bklog_" + "a" * 44)
        self.assertTrue(rt[0].isalpha())
        self.assertLessEqual(len(rt), BKDATA_RT_NAME_MAX_LEN)

    def test_double_underscore_in_name_en_collapsed(self):
        # name_en 含 ``__``: bklog 入参正则放行, 但 BKData 不接受, 必须折叠.
        name_en = "abc__def_" + "x" * 22  # 9 + 22 = 31, 折叠 __ 后保持长度
        rt = make_bkdata_rt_name(name_en)
        self.assertNotIn("__", rt)
        self.assertTrue(rt.startswith(BKLOG_RT_NAME_PREFIX))
        self.assertLessEqual(len(rt), BKDATA_RT_NAME_MAX_LEN)

    def test_name_en_starting_with_underscore_collapses_with_prefix(self):
        # 前缀 "bklog_" 末尾下划线 + name_en 首位下划线会拼出 ``__``, 必须折叠.
        rt = make_bkdata_rt_name("_foo")
        self.assertEqual(rt, "bklog_foo")
        self.assertNotIn("__", rt)

    def test_name_en_starting_with_digit_first_char_still_letter(self):
        # name_en 数字开头 (bklog 入参正则放行) 不会污染 result_table_name 首字符.
        rt = make_bkdata_rt_name("123abc")
        self.assertEqual(rt, "bklog_123abc")
        self.assertTrue(rt[0].isalpha())

    def test_name_en_max_length_upper_bound(self):
        # name_en = 50 字符 (bklog 入参 max_length=50): 截短到 50-6=44 后拼前缀.
        name_en = "a" * 50
        rt = make_bkdata_rt_name(name_en)
        self.assertEqual(rt, "bklog_" + "a" * 44)
        self.assertEqual(len(rt), BKDATA_RT_NAME_MAX_LEN)

    def test_name_en_far_longer_than_limit_truncated_safely(self):
        # 防御历史脏数据: name_en 远超长度上限, 截短到 max_len - prefix.
        name_en = "a" * 200
        rt = make_bkdata_rt_name(name_en)
        self.assertEqual(len(rt), BKDATA_RT_NAME_MAX_LEN)
        self.assertTrue(rt.startswith(BKLOG_RT_NAME_PREFIX))

    def test_first_char_is_always_letter_for_typical_inputs(self):
        # 穷举几种典型脏数据形态, 都必须保证首字符是字母.
        for name_en in [
            "_leading_underscore",
            "9digit_leading",
            "____",
            "a" * 60,
            "x__y__z",
            "VALID_UPPER",
            "a",  # 极短
        ]:
            rt = make_bkdata_rt_name(name_en)
            self.assertTrue(rt[0].isalpha(), f"first char must be letter for {name_en!r}, got {rt!r}")
            self.assertNotIn("__", rt)
            self.assertLessEqual(len(rt), BKDATA_RT_NAME_MAX_LEN)

    def test_idempotent(self):
        # make_bkdata_rt_name(make_bkdata_rt_name(x)) 不会因二次拼前缀而变形.
        name_en = "a" * 49
        once = make_bkdata_rt_name(name_en)
        # 再用 once 当 name_en 跑一遍 -- 仅验证函数自身的稳定性 (不会越跑越长).
        twice = make_bkdata_rt_name(once)
        self.assertLessEqual(len(twice), BKDATA_RT_NAME_MAX_LEN)
        self.assertTrue(twice[0].isalpha())
        self.assertNotIn("__", twice)

    def test_prefix_longer_than_max_len_returns_truncated_prefix(self):
        # 调用方姿势错误时不抛异常, 返回截断后的 prefix (能不能用是另一回事).
        rt = make_bkdata_rt_name("foo", prefix="x" * 60, max_len=BKDATA_RT_NAME_MAX_LEN)
        self.assertEqual(rt, "x" * BKDATA_RT_NAME_MAX_LEN)

    def test_custom_prefix_and_max_len(self):
        # 默认参数之外允许自定义 (虽然目前业务只用 bklog_ + 50, 但保持函数通用).
        rt = make_bkdata_rt_name("a" * 100, prefix="rt_", max_len=20)
        self.assertEqual(rt, "rt_" + "a" * 17)
        self.assertEqual(len(rt), 20)
