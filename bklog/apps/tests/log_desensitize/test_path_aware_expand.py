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
    path_aware_expand,
    restore_by_metadata,
)


class TestEstimateJsonDepth(SimpleTestCase):
    """_estimate_json_depth 单元测试（纯内存）"""

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
    """path_aware_expand 单元测试（纯内存，无需数据库）"""

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

    # ------------------------------------------------------------------
    # P0-2: 极深 JSON 不触发 RecursionError（预扫描保护）
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # P0-1: JSON 字符串带空白能正确解析
    # ------------------------------------------------------------------

    def test_json_string_with_whitespace_and_configured_path(self):
        """带空白的 JSON 字符串 + 子路径规则：正确解析脱敏"""
        data = {"body": '  {"secret":"CLEAR"}  '}
        paths = ["body.secret"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertIn("body.secret", expanded)
        self.assertEqual(expanded["body.secret"], "CLEAR")
        self.assertEqual(metadata["body"]["type"], "json_string")

    # ------------------------------------------------------------------
    # P0-3: 带点号真实 key 不崩溃
    # ------------------------------------------------------------------

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

    def test_dotted_key_conflict_restore_scalar_lost(self):
        """点号 key 冲突后还原：子树优先，标量确定性丢失并记录 error

        这是已文档化的已知限制（点号同时作为路径分隔符和 key 名）。
        展开阶段保留两个值，还原阶段子树优先，标量 "scalar" 被丢弃。
        """
        data = {"body": '{"a":"scalar","a.b":"secret"}'}
        paths = ["body.a.b"]
        expanded, metadata = path_aware_expand(data, paths)

        with self.assertLogs("apps.log_desensitize.utils", level="ERROR") as cm:
            restored = restore_by_metadata(expanded, metadata)

        self.assertIsInstance(restored["body"], str)
        parsed = json.loads(restored["body"])
        # 子树优先：a.b 还原为嵌套 {"a": {"b": "secret"}}，标量 "scalar" 丢失
        self.assertEqual(parsed, {"a": {"b": "secret"}})
        # 必须记录 error 日志，避免静默丢失
        self.assertTrue(
            any("path conflict" in msg for msg in cm.output),
            "expected a path conflict error log, got: {}".format(cm.output),
        )


class TestRestoreByMetadata(SimpleTestCase):
    """restore_by_metadata 单元测试（纯内存，无需数据库）"""

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

    def test_restore_dict_preserves_key_order(self):
        """缺失场景 4 补充：dict 类型还原时 key 顺序保持"""
        expanded = {"body.c": "3", "body.a": "1", "body.b": "2"}
        metadata = {"body": {"type": "dict"}}
        restored = restore_by_metadata(expanded, metadata)

        self.assertIsInstance(restored["body"], dict)
        # key 顺序应保持
        self.assertEqual(list(restored["body"].keys()), ["c", "a", "b"])
