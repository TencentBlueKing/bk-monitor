# -*- coding: utf-8 -*-
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
import json

from django.test import SimpleTestCase

from apps.log_desensitize.utils import (
    _estimate_json_depth,
    _get_sensitive_top_fields,
    _is_fail_closed,
    _MASKED_VALUE,
    _mask_sensitive_fields,
    merge_nested_data,
    path_aware_expand,
    restore_by_metadata,
)


class TestEstimateJsonDepth(SimpleTestCase):
    """_estimate_json_depth 单元测试"""

    def test_flat_object(self):
        """平坦 object：深度为 1"""
        self.assertEqual(_estimate_json_depth('{"a":1}'), 1)
        self.assertEqual(_estimate_json_depth('{"a":{"b":1}}'), 2)

    def test_nested_depth(self):
        """多层嵌套"""
        s = '{"a":{"b":{"c":{"d":1}}}}'
        self.assertEqual(_estimate_json_depth(s), 4)

    def test_string_braces_excluded(self):
        """字符串内的花括号不计入嵌套深度"""
        s = '{"a":"{not_counted}","b":{"c":1}}'
        # 最外层 + b.c 两层
        self.assertEqual(_estimate_json_depth(s), 2)

    def test_backslash_escape(self):
        """反斜杠转义正确处理（含连续反斜杠）"""
        # 字符串值为 "a\" 即 a\，末尾引号闭合
        s = '{"key":"a\\\\","nested":{"v":1}}'
        self.assertEqual(_estimate_json_depth(s), 2)

    def test_empty_object(self):
        """空 object"""
        self.assertEqual(_estimate_json_depth("{}"), 1)

    def test_string_with_braces(self):
        """纯字符串（无花括号）"""
        self.assertEqual(_estimate_json_depth('"hello"'), 0)

    def test_deep_recursion_prevention(self):
        """极深 JSON：扫描不爆炸"""
        s = '{"a":' * 5000 + '"x"' + '}' * 5000
        self.assertEqual(_estimate_json_depth(s), 5000)


class TestPathAwareExpand(SimpleTestCase):
    """path_aware_expand 单元测试"""

    def test_normal_object_nested(self):
        """普通 object 嵌套：正常展开为 dotted path"""
        data = {"body": {"player": {"id": "123"}, "server": {"ip": "10.0.0.1"}}}
        paths = ["body.player.id", "body.server.ip"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded["body.player.id"], "123")
        self.assertEqual(expanded["body.server.ip"], "10.0.0.1")
        self.assertEqual(metadata["body"]["type"], "dict")

    def test_flattened_object(self):
        """flattened 对象（ES 返回对象形态）：正常展开"""
        data = {"body": {"player": {"id": "456"}}}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded["body.player.id"], "456")
        self.assertEqual(metadata["body"]["type"], "dict")

    def test_json_string_object(self):
        """JSON 字符串 object：解析后展开，元数据标记为 json_string"""
        data = {"body": '{"player":{"id":"789"},"server":{"ip":"10.0.0.2"}}'}
        paths = ["body.player.id", "body.server.ip"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded["body.player.id"], "789")
        self.assertEqual(expanded["body.server.ip"], "10.0.0.2")
        self.assertEqual(metadata["body"]["type"], "json_string")

    def test_json_string_not_in_configured_path(self):
        """JSON 字符串但不在配置路径祖先中：不解析，保持原值"""
        data = {"body": '{"player":{"id":"111"}}', "other": "value"}
        paths = ["other"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded["body"], '{"player":{"id":"111"}}')
        self.assertEqual(expanded["other"], "value")
        self.assertNotIn("body.player.id", expanded)

    def test_empty_configured_paths(self):
        """无配置路径：仅展开普通 dict，不解析 JSON 字符串"""
        data = {"body": {"player": {"id": "222"}}, "extra": '{"nested":"value"}'}
        expanded, metadata = path_aware_expand(data, [])

        self.assertEqual(expanded["body.player.id"], "222")
        self.assertEqual(expanded["extra"], '{"nested":"value"}')
        # 无配置路径时不应有 json_string 类型元数据
        self.assertNotEqual(metadata.get("extra", {}).get("type"), "json_string")

    def test_null_value(self):
        """空值：正常展开"""
        data = {"body": {"player": {"id": None}}}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertIsNone(expanded["body.player.id"])

    def test_json_parse_failure(self):
        """JSON 解析失败且存在子路径规则：fail-closed 整体遮罩"""
        data = {"body": '{"player":{"id":invalid_json}}'}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(data, paths)

        # 该字段存在子路径规则（body.player.id），无法解析时必须 fail-closed
        self.assertEqual(expanded["body"], "***MASKED***")
        self.assertEqual(metadata["body"]["type"], "scalar")

    def test_json_parse_failure_without_subpath_rules(self):
        """JSON 解析失败但无子路径规则：保持原值（无泄露风险）"""
        data = {"body": '{"player":{"id":invalid_json}}'}
        paths = ["other.field"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded["body"], '{"player":{"id":invalid_json}}')
        self.assertEqual(metadata["body"]["type"], "scalar")

    def test_json_string_with_whitespace(self):
        """JSON 字符串首尾带空白：strip 后仍能正确解析并展开"""
        data = {"body": '  {"player":{"id":"789"}}  '}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded["body.player.id"], "789")
        self.assertEqual(metadata["body"]["type"], "json_string")

    def test_json_string_scalar_result(self):
        """JSON 字符串解析结果为标量（非 object）：保持原值"""
        data = {"body": "[1, 2, 3]"}
        paths = ["body"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded["body"], "[1, 2, 3]")

    def test_array_value_not_expanded(self):
        """数组值：不展开元素"""
        data = {"body": {"players": [{"id": "1"}, {"id": "2"}]}}
        paths = ["body.players"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded["body.players"], [{"id": "1"}, {"id": "2"}])

    def test_max_depth_exceeded_without_rules(self):
        """超深嵌套 + 无子路径规则：深度 > max_depth 的子树作为原子值保留，不丢失（P1-1）"""
        data = {}
        current = data
        for i in range(15):
            current["level"] = {}
            current["leaf"] = "value_{}".format(i)
            current = current["level"]

        # 配置路径在浅层，不涉及深层字段
        paths = ["leaf"]
        expanded, __ = path_aware_expand(data, paths, max_depth=10)

        # depth 0-10 的 leaf 应出现在 expanded 中
        for i in range(11):
            key = "leaf" if i == 0 else "{}.leaf".format(".".join(["level"] * i))
            self.assertIn(key, expanded)
            self.assertEqual(expanded[key], "value_{}".format(i))

        # depth 11 的 level 子树作为原子值保留（含 depth 11+ 内容）
        deep_level_key = ".".join(["level"] * 11)
        self.assertIn(deep_level_key, expanded)
        self.assertIsInstance(expanded[deep_level_key], dict)
        self.assertIn("leaf", expanded[deep_level_key])

    def test_max_depth_exceeded_with_subpath_rules(self):
        """超深嵌套 + 子路径规则在深度下限上：深度 > max_depth 且命中子路径时遮罩（P1-1）"""
        data = {}
        current = data
        for i in range(15):
            current["level"] = {}
            current["leaf"] = "value_{}".format(i)
            current = current["level"]

        # 配置路径在深层（depth 12 的 leaf），超过 max_depth=10
        paths = ["{}.leaf".format(".".join(["level"] * 12))]
        expanded, __ = path_aware_expand(data, paths, max_depth=10)

        # depth 11 的 level 字段有子路径规则且超限 → 遮罩
        deep_level_key = ".".join(["level"] * 11)
        self.assertIn(deep_level_key, expanded)
        self.assertEqual(expanded[deep_level_key], "***MASKED***")

    def test_max_json_bytes_exceeded_with_subpath(self):
        """超大 JSON 字符串 + 存在子路径规则：fail-closed 整体遮罩"""
        large_json = '{"player":{"id":"' + "x" * 70000 + '"}}'
        data = {"body": large_json}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(data, paths, max_json_bytes=65536)

        self.assertEqual(expanded["body"], "***MASKED***")
        self.assertEqual(metadata["body"]["type"], "scalar")

    def test_max_json_bytes_exceeded_without_subpath(self):
        """超大 JSON 字符串 + 无子路径规则：保持原值（无泄露风险）"""
        large_json = '{"player":{"id":"' + "x" * 70000 + '"}}'
        data = {"body": large_json}
        paths = ["other.field"]
        expanded, metadata = path_aware_expand(data, paths, max_json_bytes=65536)

        self.assertEqual(expanded["body"], large_json)
        self.assertNotIn("body.player.id", expanded)

    def test_scalar_value(self):
        """标量值：直接赋值"""
        data = {"message": "hello", "count": 42}
        paths = ["message"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded["message"], "hello")
        self.assertEqual(expanded["count"], 42)
        self.assertEqual(metadata["message"]["type"], "scalar")

    def test_mixed_scenario(self):
        """混合场景：普通 object + JSON 字符串 + 标量"""
        data = {
            "user": {"name": "alice", "age": 30},
            "session": '{"token":"abc123","expires":"2026-01-01"}',
            "status": 200,
        }
        paths = ["user.name", "session.token"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded["user.name"], "alice")
        self.assertEqual(expanded["user.age"], 30)
        self.assertEqual(expanded["session.token"], "abc123")
        self.assertEqual(expanded["session.expires"], "2026-01-01")
        self.assertEqual(expanded["status"], 200)
        self.assertEqual(metadata["user"]["type"], "dict")
        self.assertEqual(metadata["session"]["type"], "json_string")
        self.assertEqual(metadata["status"]["type"], "scalar")

    def test_empty_dict_input(self):
        """空 dict 输入：返回空 expanded 和空 metadata"""
        data = {}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded, {})
        self.assertEqual(metadata, {})

    def test_nested_json_string(self):
        """多层 JSON 字符串嵌套：JSON in JSON 递归解析"""
        data = {"body": '{"inner": "{\\"deep\\": \\"value\\"}"}'}
        paths = ["body.inner.deep"]
        expanded, metadata = path_aware_expand(data, paths)

        # body 解析后 inner 仍是 JSON 字符串，且 body.inner 属祖先路径，应被再次解析
        self.assertEqual(expanded, {"body.inner.deep": "value"})
        # 中间层 body.inner 已被完全展开，不应作为叶子保留
        self.assertNotIn("body.inner", expanded)
        # 顶层 body 的原始容器类型应记录为 json_string
        self.assertEqual(metadata["body"]["type"], "json_string")

    def test_configured_paths_partial_match(self):
        """配置路径只指定部分子字段：dict 类型无条件递归展开所有子字段"""
        data = {"body": {"player": {"id": "123", "name": "alice"}}}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(data, paths)

        # 配置路径被展开
        self.assertEqual(expanded["body.player.id"], "123")
        # dict 类型的子字段无条件递归展开（即使 name 不在配置路径中）
        self.assertEqual(expanded["body.player.name"], "alice")

    def test_deep_json_no_recursion_error(self):
        """极深 JSON 字符串（1100 层嵌套）不触发 RecursionError，fail-closed 遮罩"""

        malicious_json = '{"a":' * 1100 + '"secret"' + '}' * 1100
        data = {"body": malicious_json}
        paths = ["body.secret"]
        expanded, metadata = path_aware_expand(data, paths)

        # 预扫描拦截深度超标 → fail-closed
        self.assertEqual(expanded["body"], "***MASKED***")

    def test_deep_json_no_recursion_error_without_rules(self):
        """极深 JSON + 无子路径规则：保持原值"""
        malicious_json = '{"a":' * 1100 + '"secret"' + '}' * 1100
        data = {"body": malicious_json}
        paths = ["other.field"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded["body"], malicious_json)

    def test_json_string_with_whitespace_and_configured_path(self):
        """带空白的 JSON 字符串 + 子路径规则：正确解析脱敏"""
        data = {"body": '  {"secret":"CLEAR"}  '}
        paths = ["body.secret"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertIn("body.secret", expanded)
        self.assertEqual(expanded["body.secret"], "CLEAR")
        self.assertEqual(metadata["body"]["type"], "json_string")

    def test_dotted_key_conflict_no_crash(self):
        """包含点号的真实 key 与路径冲突时不崩溃（安全网）"""
        # JSON 字符串内同时有 a 和 a.b 两个 key
        data = {"body": '{"a":"scalar","a.b":"secret"}'}
        paths = ["body.a.b"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertIn("body.a", expanded)
        self.assertIn("body.a.b", expanded)
        # 展开阶段两个值都保留
        self.assertEqual(expanded["body.a"], "scalar")
        self.assertEqual(expanded["body.a.b"], "secret")

    def test_json_literal_dot_key_preserved_in_restore(self):
        """Review 原例：JSON 内字面点号 key 与普通 key 共存，两者都必须保留

        ``body='{"a":"scalar","a.b":"secret"}'``，配置 ``body.a.b``。
        其中 ``"a"`` 是普通 key，``"a.b"`` 是字面点号 key（点号是键名的一部分）。
        修复前：``_build_nested_dict`` 盲分 ``body.a.b``，把标量 ``"scalar"`` 覆盖丢失。
        修复后：metadata 记录 ``segments``，``body.a.b`` 的 segments 为 ``("body", "a.b")``
        （``a.b`` 是单段），还原时不再盲分，两个值都完整保留，无需 error 日志。
        """
        data = {"body": '{"a":"scalar","a.b":"secret"}'}
        paths = ["body.a.b"]
        expanded, metadata = path_aware_expand(data, paths)

        # 展开阶段：两个平级标量，不冲突
        self.assertEqual(expanded, {"body.a": "scalar", "body.a.b": "secret"})
        # metadata 必须记录 segments：字面 key "body.a.b" segments 含 2 段
        self.assertEqual(
            metadata["body.a.b"].get("segments"),
            ("body", "a.b"),
            "body.a.b 的 segments 应为 ('body', 'a.b')，其中 'a.b' 是单段（字面键名）",
        )
        self.assertEqual(
            metadata["body.a"].get("segments"),
            ("body", "a"),
            "body.a 的 segments 应为 ('body', 'a')——普通 key",
        )

        # 还原阶段：不再有冲突，两个值都保留，不产生 error 日志
        with self.assertNoLogs("apps.log_desensitize.utils", level="ERROR"):
            restored = restore_by_metadata(expanded, metadata)

        self.assertIsInstance(restored["body"], str)
        parsed = json.loads(restored["body"])
        # 精确断言：普通 key "a" 与字面 key "a.b" 都完整保留
        self.assertEqual(parsed, {"a": "scalar", "a.b": "secret"})

    def test_json_literal_dot_key_nested_child_preserved(self):
        """JSON 内字面点号 key 自身还嵌套子对象：结构完整还原"""
        data = {"body": '{"a.b": {"c": "val"}}'}
        paths = ["body.a.b.c"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(
            metadata["body.a.b"].get("segments"),
            ("body", "a.b"),
        )
        self.assertEqual(expanded, {"body.a.b.c": "val"})

        restored = restore_by_metadata(expanded, metadata)
        parsed = json.loads(restored["body"])
        # 字面 key "a.b" 保持为一层键名，其下嵌套 "c"
        self.assertEqual(parsed, {"a.b": {"c": "val"}})

    def test_json_literal_dot_key_multiple_levels(self):
        """JSON 内多层字面点号 key（"x.y" 与 "x.y.z" 共存）：全部保留"""
        data = {"body": '{"x.y": "v1", "x.y.z": "v2"}'}
        # 配置一个不相关的祖先路径，触发 body 的 JSON 解析
        paths = ["body.x.y"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(metadata["body.x.y"].get("segments"), ("body", "x.y"))
        self.assertEqual(metadata["body.x.y.z"].get("segments"), ("body", "x.y.z"))

        restored = restore_by_metadata(expanded, metadata)
        parsed = json.loads(restored["body"])
        # 两个字面 key 都作为独立键名保留
        self.assertEqual(parsed, {"x.y": "v1", "x.y.z": "v2"})

    def test_json_literal_key_does_not_break_es_flattened(self):
        """字面 key 修复不影响 ES-flattened 顶层 dotted key 的 re-nest 行为"""
        data = {"__ext_json.deployment.pod.name": "secret"}
        paths = ["__ext_json.deployment.pod.name"]
        expanded, metadata = path_aware_expand(data, paths)

        # 顶层 key（非 JSON 解析来源）的 segments 按点号正常 split
        self.assertEqual(
            metadata["__ext_json.deployment.pod.name"].get("segments"),
            ("__ext_json", "deployment", "pod", "name"),
        )
        restored = restore_by_metadata(expanded, metadata)
        # ES-flattened dotted key 仍按路径分隔符正常 re-nest
        self.assertEqual(restored, {"__ext_json": {"deployment": {"pod": {"name": "secret"}}}})

    def test_json_literal_key_mixed_with_nested_object(self):
        """JSON 内字面点号 key 与普通嵌套对象共存，还原后语义不混淆"""
        # "a.b" 是字面 key(标量)，"a" 是普通 key(对象)
        data = {"body": '{"a": {"c": "v1"}, "a.b": "v2"}'}
        paths = ["body.a.c", "body.a.b"]
        expanded, metadata = path_aware_expand(data, paths)

        # 字面 key "body.a.b" 的 segments 含 "a.b" 单段
        self.assertEqual(metadata["body.a.b"].get("segments"), ("body", "a.b"))
        # 普通 key 按点号 split
        self.assertEqual(metadata["body.a.c"].get("segments"), ("body", "a", "c"))

        restored = restore_by_metadata(expanded, metadata)
        parsed = json.loads(restored["body"])
        # "a.b" 作为独立键名，"a" 作为嵌套对象，互不干扰
        self.assertEqual(parsed, {"a": {"c": "v1"}, "a.b": "v2"})

    def test_expand_stage_conflict_dict_vs_dotted_key(self):
        """展开阶段冲突：JSON 同时含 a(dict) 与 a.b(scalar)，dict 先迭代

        两者计算出相同的 current_path "body.a.b"，展开阶段必须检测冲突、
        确定性保留先迭代的值，并记录 error（不能静默覆盖）。
        """
        data = {"body": '{"a": {"b": "dict_value"}, "a.b": "scalar_value"}'}
        paths = ["body.a.b"]

        with self.assertLogs("apps.log_desensitize.utils", level="ERROR") as cm:
            expanded, metadata = path_aware_expand(data, paths)

        # 确定性保留先迭代的 dict 值
        self.assertEqual(expanded["body.a.b"], "dict_value")
        # 必须记录冲突 error，避免静默覆盖
        self.assertTrue(
            any("dotted-key conflict" in msg for msg in cm.output),
            "expected a dotted-key conflict error log, got: {}".format(cm.output),
        )

    def test_expand_stage_conflict_dotted_key_first(self):
        """展开阶段冲突：JSON 同时含 a.b(scalar) 与 a(dict)，scalar 先迭代

        与上一用例顺序相反，确定性保留先迭代的 scalar 值，并记录 error。
        """
        data = {"body": '{"a.b": "scalar_value", "a": {"b": "dict_value"}}'}
        paths = ["body.a.b"]

        with self.assertLogs("apps.log_desensitize.utils", level="ERROR") as cm:
            expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded["body.a.b"], "scalar_value")
        self.assertTrue(
            any("dotted-key conflict" in msg for msg in cm.output),
            "expected a dotted-key conflict error log, got: {}".format(cm.output),
        )

    def test_expand_stage_conflict_restore_no_crash(self):
        """展开阶段冲突后还原不崩溃，且不静默丢数据"""
        data = {"body": '{"a": {"b": "dict_value"}, "a.b": "scalar_value"}'}
        paths = ["body.a.b"]

        with self.assertLogs("apps.log_desensitize.utils", level="ERROR"):
            expanded, metadata = path_aware_expand(data, paths)
            restored = restore_by_metadata(expanded, metadata)

        # 还原结果结构合法（不崩溃），body 仍为 JSON 字符串
        self.assertIsInstance(restored["body"], str)
        parsed = json.loads(restored["body"])
        # 保留先迭代的 dict 值
        self.assertEqual(parsed, {"a": {"b": "dict_value"}})


class TestRestoreByMetadata(SimpleTestCase):
    """restore_by_metadata 单元测试"""

    def test_restore_dict_type(self):
        """dict 类型：还原为嵌套 dict"""
        expanded = {"body.player.id": "123", "body.server.ip": "10.0.0.1"}
        metadata = {"body": {"type": "dict"}}
        restored = restore_by_metadata(expanded, metadata)

        self.assertEqual(restored["body"]["player"]["id"], "123")
        self.assertEqual(restored["body"]["server"]["ip"], "10.0.0.1")
        self.assertIsInstance(restored["body"], dict)

    def test_restore_json_string_type(self):
        """json_string 类型：还原为 JSON 字符串"""
        expanded = {"body.player.id": "456", "body.server.ip": "10.0.0.2"}
        metadata = {"body": {"type": "json_string"}}
        restored = restore_by_metadata(expanded, metadata)

        self.assertIsInstance(restored["body"], str)
        parsed = json.loads(restored["body"])
        self.assertEqual(parsed["player"]["id"], "456")
        self.assertEqual(parsed["server"]["ip"], "10.0.0.2")

    def test_restore_scalar_type(self):
        """scalar 类型：直接赋值"""
        expanded = {"message": "hello", "count": 42}
        metadata = {"message": {"type": "scalar"}, "count": {"type": "scalar"}}
        restored = restore_by_metadata(expanded, metadata)

        self.assertEqual(restored["message"], "hello")
        self.assertEqual(restored["count"], 42)

    def test_restore_single_scalar(self):
        """单个顶层标量：直接赋值，不被构建为嵌套 dict"""
        expanded = {"count": 42}
        metadata = {"count": {"type": "scalar"}}
        restored = restore_by_metadata(expanded, metadata)

        self.assertEqual(restored["count"], 42)
        self.assertNotIsInstance(restored["count"], dict)

    def test_mixed_restore(self):
        """混合类型还原"""
        expanded = {
            "user.name": "alice",
            "user.age": 30,
            "session.token": "abc",
            "status": 200,
        }
        metadata = {
            "user": {"type": "dict"},
            "session": {"type": "json_string"},
            "status": {"type": "scalar"},
        }
        restored = restore_by_metadata(expanded, metadata)

        self.assertEqual(restored["user"]["name"], "alice")
        self.assertEqual(restored["user"]["age"], 30)
        self.assertIsInstance(restored["session"], str)
        parsed = json.loads(restored["session"])
        self.assertEqual(parsed["token"], "abc")
        self.assertEqual(restored["status"], 200)

    def test_expand_restore_roundtrip(self):
        """展开-还原完整回路：普通 object 数据不变"""
        original = {"body": {"player": {"id": "123"}}}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(original, paths)
        # 模拟脱敏：修改值
        expanded["body.player.id"] = "***"
        restored = restore_by_metadata(expanded, metadata)

        self.assertEqual(restored["body"]["player"]["id"], "***")
        self.assertIsInstance(restored["body"], dict)

    def test_expand_restore_roundtrip_json_string(self):
        """展开-还原完整回路：JSON 字符串数据还原为字符串"""
        original = {"body": '{"player":{"id":"456"}}'}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(original, paths)
        # 模拟脱敏：修改值
        expanded["body.player.id"] = "***"
        restored = restore_by_metadata(expanded, metadata)

        self.assertIsInstance(restored["body"], str)
        parsed = json.loads(restored["body"])
        self.assertEqual(parsed["player"]["id"], "***")

    def test_restore_default_metadata(self):
        """无元数据时默认按 dict 处理"""
        expanded = {"body.player.id": "789"}
        metadata = {}
        restored = restore_by_metadata(expanded, metadata)

        self.assertEqual(restored["body"]["player"]["id"], "789")

    def test_restore_json_string_preserves_unconfigured_fields(self):
        """JSON 字符串还原时，未配置脱敏的字段保持原值"""
        expanded = {"body.player.id": "***", "body.server.ip": "10.0.0.1"}
        metadata = {"body": {"type": "json_string"}}
        restored = restore_by_metadata(expanded, metadata)

        parsed = json.loads(restored["body"])
        self.assertEqual(parsed["player"]["id"], "***")
        self.assertEqual(parsed["server"]["ip"], "10.0.0.1")

    def test_restore_json_string_preserves_key_order(self):
        """缺失场景 4：restore_by_metadata 对 JSON 字符串内 key 顺序保持。

        验证还原后的 JSON 字符串中 key 顺序与 expanded_data 中的插入顺序一致，
        确保 json.dumps 不会随机打乱字段顺序。
        """
        expanded = {"body.zebra": "z_value", "body.apple": "a_value", "body.mango": "m_value"}
        metadata = {"body": {"type": "json_string"}}
        restored = restore_by_metadata(expanded, metadata)

        self.assertIsInstance(restored["body"], str)
        parsed = json.loads(restored["body"])
        # key 顺序应保持与 expanded_data 插入顺序一致
        self.assertEqual(list(parsed.keys()), ["zebra", "apple", "mango"])


class TestMergeNestedDataConflict(SimpleTestCase):
    """merge_nested_data 冲突防御测试"""

    def test_scalar_then_subtree_no_crash(self):
        """先标量后子树：不崩溃，子树优先，标量丢失"""
        result = merge_nested_data({"body.a": "scalar", "body.a.b": "secret"})
        self.assertEqual(result, {"body": {"a": {"b": "secret"}}})

    def test_subtree_then_scalar_no_crash(self):
        """先子树后标量：不崩溃，子树优先，标量不写入"""
        result = merge_nested_data({"body.a.b": "secret", "body.a": "scalar"})
        self.assertEqual(result, {"body": {"a": {"b": "secret"}}})

    def test_conflict_logs_error_with_details(self):
        """冲突时记录 error 日志，包含 key 名"""
        with self.assertLogs("apps.log_desensitize.utils", level="ERROR") as cm:
            merge_nested_data({"body.a": "scalar", "body.a.b": "secret"})
        self.assertTrue(
            any("path conflict" in msg and "body.a" in msg for msg in cm.output),
            "expected conflict error log with key name, got: {}".format(cm.output),
        )

    def test_normal_flattened_no_conflict(self):
        """正常 flattened 数据无冲突：行为不变"""
        result = merge_nested_data({"body.player.id": "123", "body.player.name": "test"})
        self.assertEqual(result, {"body": {"player": {"id": "123", "name": "test"}}})

    def test_empty_dict(self):
        """空 dict 输入：返回空 dict"""
        self.assertEqual(merge_nested_data({}), {})


class TestGetSensitiveTopFields(SimpleTestCase):
    """_get_sensitive_top_fields 公共函数测试"""

    def test_nested_path_extracts_top_prefix(self):
        """嵌套路径提取顶层前缀"""
        result = _get_sensitive_top_fields([{"field_name": "body.player.id"}], [], [])
        self.assertEqual(result, {"body"})

    def test_text_fields_included(self):
        """text_fields 字段纳入遮罩范围"""
        result = _get_sensitive_top_fields([], [], ["log"])
        self.assertEqual(result, {"log"})

    def test_mixed_sources(self):
        """多来源合并"""
        result = _get_sensitive_top_fields(
            [{"field_name": "body.player.id"}, {"field_name": "message"}],
            [{"field_name": "log"}],
            ["log", "raw_data"],
        )
        self.assertEqual(result, {"body", "message", "log", "raw_data"})

    def test_empty_inputs(self):
        """空输入返回空集合"""
        result = _get_sensitive_top_fields([], [], [])
        self.assertEqual(result, set())

    def test_none_inputs(self):
        """None 输入返回空集合"""
        result = _get_sensitive_top_fields(None, None, None)
        self.assertEqual(result, set())


class TestMaskSensitiveFields(SimpleTestCase):
    """_mask_sensitive_fields 公共函数测试"""

    def test_masks_only_sensitive_fields(self):
        """仅遮罩敏感字段，保留其他字段"""
        log = {"body": "secret_data", "message": "hello", "ts": 123}
        result = _mask_sensitive_fields(log, {"body"})
        self.assertEqual(result["body"], _MASKED_VALUE)
        self.assertEqual(result["message"], "hello")
        self.assertEqual(result["ts"], 123)

    def test_preserves_field_names(self):
        """保留原始字段名结构"""
        log = {"a": 1, "b": 2, "c": 3}
        result = _mask_sensitive_fields(log, {"b"})
        self.assertEqual(set(result.keys()), {"a", "b", "c"})

    def test_empty_sensitive_fields(self):
        """空敏感字段集合：不做任何遮罩"""
        log = {"a": "value"}
        result = _mask_sensitive_fields(log, set())
        self.assertEqual(result, {"a": "value"})


class TestIsFailClosed(SimpleTestCase):
    """_is_fail_closed 公共函数测试"""

    def test_detects_masked_value(self):
        """检测到 _MASKED_VALUE 返回 True"""
        log = {"body": _MASKED_VALUE, "other": "value"}
        metadata = {"body": {"type": "scalar"}, "other": {"type": "scalar"}}
        self.assertTrue(_is_fail_closed(log, metadata))

    def test_no_masked_value(self):
        """无 _MASKED_VALUE 返回 False"""
        log = {"body": "normal", "other": "value"}
        metadata = {"body": {"type": "scalar"}, "other": {"type": "scalar"}}
        self.assertFalse(_is_fail_closed(log, metadata))

    def test_empty_metadata(self):
        """空元数据返回 False"""
        self.assertFalse(_is_fail_closed({"a": 1}, {}))

    def test_restore_dict_preserves_key_order(self):
        """缺失场景 4 补充：dict 类型还原时 key 顺序保持"""
        expanded = {"body.c": "3", "body.a": "1", "body.b": "2"}
        metadata = {"body": {"type": "dict"}}
        restored = restore_by_metadata(expanded, metadata)

        self.assertIsInstance(restored["body"], dict)
        # key 顺序应保持
        self.assertEqual(list(restored["body"].keys()), ["c", "a", "b"])
