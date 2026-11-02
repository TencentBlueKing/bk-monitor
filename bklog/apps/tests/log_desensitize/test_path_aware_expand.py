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
        self.assertEqual(_estimate_json_depth('{"a":1}'), 1)
        self.assertEqual(_estimate_json_depth('{"a":{"b":1}}'), 2)

    def test_nested_depth(self):
        s = '{"a":{"b":{"c":{"d":1}}}}'
        self.assertEqual(_estimate_json_depth(s), 4)

    def test_string_braces_excluded(self):
        s = '{"a":"{not_counted}","b":{"c":1}}'
        self.assertEqual(_estimate_json_depth(s), 2)

    def test_backslash_escape(self):
        s = '{"key":"a\\\\","nested":{"v":1}}'
        self.assertEqual(_estimate_json_depth(s), 2)

    def test_empty_object(self):
        self.assertEqual(_estimate_json_depth("{}"), 1)

    def test_string_with_braces(self):
        self.assertEqual(_estimate_json_depth('"hello"'), 0)

    def test_deep_recursion_prevention(self):
        s = '{"a":' * 5000 + '"x"' + '}' * 5000
        self.assertEqual(_estimate_json_depth(s), 5000)


class TestPathAwareExpand(SimpleTestCase):
    """path_aware_expand 单元测试（tuple key）"""

    def test_normal_object_nested(self):
        """普通 object 嵌套：正常展开为 tuple key"""
        data = {"body": {"player": {"id": "123"}, "server": {"ip": "10.0.0.1"}}}
        paths = ["body.player.id", "body.server.ip"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded[("body", "player", "id")], "123")
        self.assertEqual(expanded[("body", "server", "ip")], "10.0.0.1")
        self.assertEqual(metadata[("body",)]["type"], "dict")

    def test_flattened_object(self):
        """flattened 对象（ES 返回对象形态）：正常展开"""
        data = {"body": {"player": {"id": "456"}}}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded[("body", "player", "id")], "456")
        self.assertEqual(metadata[("body",)]["type"], "dict")

    def test_json_string_object(self):
        """JSON 字符串 object：解析后展开，元数据标记为 json_string"""
        data = {"body": '{"player":{"id":"789"},"server":{"ip":"10.0.0.2"}}'}
        paths = ["body.player.id", "body.server.ip"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded[("body", "player", "id")], "789")
        self.assertEqual(expanded[("body", "server", "ip")], "10.0.0.2")
        self.assertEqual(metadata[("body",)]["type"], "json_string")

    def test_json_string_not_in_configured_path(self):
        """JSON 字符串但不在配置路径祖先中：不解析，保持原值"""
        data = {"body": '{"player":{"id":"111"}}', "other": "value"}
        paths = ["other"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded[("body",)], '{"player":{"id":"111"}}')
        self.assertEqual(expanded[("other",)], "value")
        self.assertNotIn(("body", "player", "id"), expanded)

    def test_empty_configured_paths(self):
        """无配置路径：仅展开普通 dict，不解析 JSON 字符串"""
        data = {"body": {"player": {"id": "222"}}, "extra": '{"nested":"value"}'}
        expanded, metadata = path_aware_expand(data, [])

        self.assertEqual(expanded[("body", "player", "id")], "222")
        self.assertEqual(expanded[("extra",)], '{"nested":"value"}')
        self.assertNotEqual(metadata.get(("extra",), {}).get("type"), "json_string")

    def test_null_value(self):
        """空值：正常展开"""
        data = {"body": {"player": {"id": None}}}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertIsNone(expanded[("body", "player", "id")])

    def test_json_parse_failure(self):
        """JSON 解析失败且存在子路径规则：fail-closed 整体遮罩"""
        data = {"body": '{"player":{"id":invalid_json}}'}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded[("body",)], "***MASKED***")
        self.assertEqual(metadata[("body",)]["type"], "scalar")

    def test_json_parse_failure_without_subpath_rules(self):
        """JSON 解析失败但无子路径规则：保持原值"""
        data = {"body": '{"player":{"id":invalid_json}}'}
        paths = ["other.field"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded[("body",)], '{"player":{"id":invalid_json}}')
        self.assertEqual(metadata[("body",)]["type"], "scalar")

    def test_json_string_with_whitespace(self):
        """JSON 字符串首尾带空白：strip 后仍能正确解析并展开"""
        data = {"body": '  {"player":{"id":"789"}}  '}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded[("body", "player", "id")], "789")
        self.assertEqual(metadata[("body",)]["type"], "json_string")

    def test_json_string_scalar_result(self):
        """JSON 字符串解析结果为标量（非 object）：保持原值"""
        data = {"body": "[1, 2, 3]"}
        paths = ["body"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded[("body",)], "[1, 2, 3]")

    def test_array_value_not_expanded(self):
        """数组值：不展开元素"""
        data = {"body": {"players": [{"id": "1"}, {"id": "2"}]}}
        paths = ["body.players"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded[("body", "players")], [{"id": "1"}, {"id": "2"}])

    def test_max_depth_exceeded_without_rules(self):
        """超深嵌套 + 无子路径规则：深度 > max_depth 的子树作为原子值保留"""
        data = {}
        current = data
        for i in range(15):
            current["level"] = {}
            current["leaf"] = "value_{}".format(i)
            current = current["level"]

        paths = ["leaf"]
        expanded, __ = path_aware_expand(data, paths, max_depth=10)

        for i in range(11):
            key = ("leaf",) if i == 0 else ("level",) * i + ("leaf",)
            self.assertIn(key, expanded)
            self.assertEqual(expanded[key], "value_{}".format(i))

        deep_level_key = ("level",) * 11
        self.assertIn(deep_level_key, expanded)
        self.assertIsInstance(expanded[deep_level_key], dict)
        self.assertIn("leaf", expanded[deep_level_key])

    def test_max_depth_exceeded_with_subpath_rules(self):
        """超深嵌套 + 子路径规则在深度下限上：遮罩"""
        data = {}
        current = data
        for i in range(15):
            current["level"] = {}
            current["leaf"] = "value_{}".format(i)
            current = current["level"]

        paths = ["{}.leaf".format(".".join(["level"] * 12))]
        expanded, __ = path_aware_expand(data, paths, max_depth=10)

        deep_level_key = ("level",) * 11
        self.assertIn(deep_level_key, expanded)
        self.assertEqual(expanded[deep_level_key], "***MASKED***")

    def test_max_json_bytes_exceeded_with_subpath(self):
        """超大 JSON 字符串 + 存在子路径规则：fail-closed 整体遮罩"""
        large_json = '{"player":{"id":"' + "x" * 70000 + '"}}'
        data = {"body": large_json}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(data, paths, max_json_bytes=65536)

        self.assertEqual(expanded[("body",)], "***MASKED***")
        self.assertEqual(metadata[("body",)]["type"], "scalar")

    def test_max_json_bytes_exceeded_without_subpath(self):
        """超大 JSON 字符串 + 无子路径规则：保持原值"""
        large_json = '{"player":{"id":"' + "x" * 70000 + '"}}'
        data = {"body": large_json}
        paths = ["other.field"]
        expanded, metadata = path_aware_expand(data, paths, max_json_bytes=65536)

        self.assertEqual(expanded[("body",)], large_json)
        self.assertNotIn(("body", "player", "id"), expanded)

    def test_scalar_value(self):
        """标量值：直接赋值"""
        data = {"message": "hello", "count": 42}
        paths = ["message"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded[("message",)], "hello")
        self.assertEqual(expanded[("count",)], 42)
        self.assertEqual(metadata[("message",)]["type"], "scalar")

    def test_mixed_scenario(self):
        """混合场景：普通 object + JSON 字符串 + 标量"""
        data = {
            "user": {"name": "alice", "age": 30},
            "session": '{"token":"abc123","expires":"2026-01-01"}',
            "status": 200,
        }
        paths = ["user.name", "session.token"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded[("user", "name")], "alice")
        self.assertEqual(expanded[("user", "age")], 30)
        self.assertEqual(expanded[("session", "token")], "abc123")
        self.assertEqual(expanded[("session", "expires")], "2026-01-01")
        self.assertEqual(expanded[("status",)], 200)
        self.assertEqual(metadata[("user",)]["type"], "dict")
        self.assertEqual(metadata[("session",)]["type"], "json_string")
        self.assertEqual(metadata[("status",)]["type"], "scalar")

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

        self.assertEqual(expanded, {("body", "inner", "deep"): "value"})
        self.assertNotIn(("body", "inner"), expanded)
        self.assertEqual(metadata[("body",)]["type"], "json_string")

    def test_configured_paths_partial_match(self):
        """配置路径只指定部分子字段：dict 类型无条件递归展开所有子字段"""
        data = {"body": {"player": {"id": "123", "name": "alice"}}}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded[("body", "player", "id")], "123")
        self.assertEqual(expanded[("body", "player", "name")], "alice")

    def test_deep_json_no_recursion_error(self):
        """极深 JSON 字符串（1100 层嵌套）不触发 RecursionError，fail-closed 遮罩"""
        malicious_json = '{"a":' * 1100 + '"secret"' + '}' * 1100
        data = {"body": malicious_json}
        paths = ["body.secret"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded[("body",)], "***MASKED***")

    def test_deep_json_no_recursion_error_without_rules(self):
        """极深 JSON + 无子路径规则：保持原值"""
        malicious_json = '{"a":' * 1100 + '"secret"' + '}' * 1100
        data = {"body": malicious_json}
        paths = ["other.field"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertEqual(expanded[("body",)], malicious_json)

    def test_json_string_with_whitespace_and_configured_path(self):
        """带空白的 JSON 字符串 + 子路径规则：正确解析脱敏"""
        data = {"body": '  {"secret":"CLEAR"}  '}
        paths = ["body.secret"]
        expanded, metadata = path_aware_expand(data, paths)

        self.assertIn(("body", "secret"), expanded)
        self.assertEqual(expanded[("body", "secret")], "CLEAR")
        self.assertEqual(metadata[("body",)]["type"], "json_string")


class TestPathTokenNoAmbiguity(SimpleTestCase):
    """path token 彻底消除 dotted string 歧义"""

    def test_literal_dotted_key_and_nested_dict_no_conflict(self):
        """字面 key 与嵌套 dict 不冲突，两个值都保留（展开阶段）"""
        data = {"body": {"a": {"b": "NESTED"}, "a.b": "LITERAL"}}
        expanded, metadata = path_aware_expand(data, ["body.a.b"])

        # tuple key 下两个路径不同，两个值都保留
        self.assertEqual(expanded[("body", "a", "b")], "NESTED")
        self.assertEqual(expanded[("body", "a.b")], "LITERAL")

    def test_reverse_order_both_preserved(self):
        """调换 key 顺序：两个值仍然都保留（展开阶段）"""
        data = {"body": {"a.b": "LITERAL", "a": {"b": "NESTED"}}}
        expanded, metadata = path_aware_expand(data, ["body.a.b"])

        self.assertEqual(expanded[("body", "a.b")], "LITERAL")
        self.assertEqual(expanded[("body", "a", "b")], "NESTED")

    def test_literal_key_json_value_fail_closed(self):
        """字面 key 内嵌 JSON + split 解释命中配置 → fail-closed"""
        data = {"body": '{"a.b":"{\\"secret\\":\\"CLEAR\\"}"}'}
        expanded, metadata = path_aware_expand(data, ["body.a.b.secret"])

        self.assertEqual(expanded[("body", "a.b")], _MASKED_VALUE)

    def test_literal_key_json_value_no_config_no_mask(self):
        """字面 key 内嵌 JSON + split 解释不命中配置 → 保持原值"""
        data = {"body": '{"a.b":"{\\"secret\\":\\"CLEAR\\"}"}'}
        expanded, metadata = path_aware_expand(data, ["body.other.field"])

        self.assertEqual(expanded[("body", "a.b")], '{"secret":"CLEAR"}')

    def test_es_flattened_still_works(self):
        """ES-flattened 顶层 dotted key 正常展开"""
        data = {"__ext_json.deployment.pod.name": "secret"}
        expanded, metadata = path_aware_expand(data, ["__ext_json.deployment.pod.name"])

        self.assertEqual(expanded[("__ext_json", "deployment", "pod", "name")], "secret")

    def test_restore_preserves_literal_dotted_key(self):
        """还原后字面点号 key 保持原样（展开+还原阶段，不涉及脱敏）"""
        data = {"body": {"a": {"b": "NESTED"}, "a.b": "LITERAL"}}
        expanded, metadata = path_aware_expand(data, ["body.a.b"])
        restored = restore_by_metadata(expanded, metadata)

        # body 还原为 dict，包含 "a"（嵌套）和 "a.b"（字面 key）
        self.assertIsInstance(restored["body"], dict)
        self.assertEqual(restored["body"]["a"]["b"], "NESTED")
        self.assertEqual(restored["body"]["a.b"], "LITERAL")


class TestRestoreByMetadata(SimpleTestCase):
    """restore_by_metadata 单元测试（tuple key）"""

    def test_restore_dict_type(self):
        """dict 类型：还原为嵌套 dict"""
        expanded = {("body", "player", "id"): "123", ("body", "server", "ip"): "10.0.0.1"}
        metadata = {("body",): {"type": "dict"}}
        restored = restore_by_metadata(expanded, metadata)

        self.assertEqual(restored["body"]["player"]["id"], "123")
        self.assertEqual(restored["body"]["server"]["ip"], "10.0.0.1")
        self.assertIsInstance(restored["body"], dict)

    def test_restore_json_string_type(self):
        """json_string 类型：还原为 JSON 字符串"""
        expanded = {("body", "player", "id"): "456", ("body", "server", "ip"): "10.0.0.2"}
        metadata = {("body",): {"type": "json_string"}}
        restored = restore_by_metadata(expanded, metadata)

        self.assertIsInstance(restored["body"], str)
        parsed = json.loads(restored["body"])
        self.assertEqual(parsed["player"]["id"], "456")
        self.assertEqual(parsed["server"]["ip"], "10.0.0.2")

    def test_restore_scalar_type(self):
        """scalar 类型：直接赋值"""
        expanded = {("message",): "hello", ("count",): 42}
        metadata = {("message",): {"type": "scalar"}, ("count",): {"type": "scalar"}}
        restored = restore_by_metadata(expanded, metadata)

        self.assertEqual(restored["message"], "hello")
        self.assertEqual(restored["count"], 42)

    def test_restore_single_scalar(self):
        """单个顶层标量：直接赋值，不被构建为嵌套 dict"""
        expanded = {("count",): 42}
        metadata = {("count",): {"type": "scalar"}}
        restored = restore_by_metadata(expanded, metadata)

        self.assertEqual(restored["count"], 42)
        self.assertNotIsInstance(restored["count"], dict)

    def test_mixed_restore(self):
        """混合类型还原"""
        expanded = {
            ("user", "name"): "alice",
            ("user", "age"): 30,
            ("session", "token"): "abc",
            ("status",): 200,
        }
        metadata = {
            ("user",): {"type": "dict"},
            ("session",): {"type": "json_string"},
            ("status",): {"type": "scalar"},
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
        expanded[("body", "player", "id")] = "***"
        restored = restore_by_metadata(expanded, metadata)

        self.assertEqual(restored["body"]["player"]["id"], "***")
        self.assertIsInstance(restored["body"], dict)

    def test_expand_restore_roundtrip_json_string(self):
        """展开-还原完整回路：JSON 字符串数据还原为字符串"""
        original = {"body": '{"player":{"id":"456"}}'}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(original, paths)
        expanded[("body", "player", "id")] = "***"
        restored = restore_by_metadata(expanded, metadata)

        self.assertIsInstance(restored["body"], str)
        parsed = json.loads(restored["body"])
        self.assertEqual(parsed["player"]["id"], "***")

    def test_restore_default_metadata(self):
        """无元数据时默认按 dict 处理（多段 tuple key 兜底折叠）"""
        expanded = {("body", "player", "id"): "789"}
        metadata = {}
        restored = restore_by_metadata(expanded, metadata)

        self.assertEqual(restored["body"]["player"]["id"], "789")

    def test_restore_json_string_preserves_unconfigured_fields(self):
        """JSON 字符串还原时，未配置脱敏的字段保持原值"""
        expanded = {("body", "player", "id"): "***", ("body", "server", "ip"): "10.0.0.1"}
        metadata = {("body",): {"type": "json_string"}}
        restored = restore_by_metadata(expanded, metadata)

        parsed = json.loads(restored["body"])
        self.assertEqual(parsed["player"]["id"], "***")
        self.assertEqual(parsed["server"]["ip"], "10.0.0.1")

    def test_restore_json_string_preserves_key_order(self):
        """restore_by_metadata 对 JSON 字符串内 key 顺序保持"""
        expanded = {("body", "zebra"): "z_value", ("body", "apple"): "a_value", ("body", "mango"): "m_value"}
        metadata = {("body",): {"type": "json_string"}}
        restored = restore_by_metadata(expanded, metadata)

        self.assertIsInstance(restored["body"], str)
        parsed = json.loads(restored["body"])
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
    """_mask_sensitive_fields 公共函数测试（兼容 tuple key 和 string key）"""

    def test_masks_only_sensitive_fields_tuple_key(self):
        """仅遮罩敏感字段（tuple key），保留其他字段"""
        log = {("body",): "secret_data", ("message",): "hello", ("ts",): 123}
        result = _mask_sensitive_fields(log, {"body"})
        self.assertEqual(result[("body",)], _MASKED_VALUE)
        self.assertEqual(result[("message",)], "hello")
        self.assertEqual(result[("ts",)], 123)

    def test_masks_nested_tuple_key(self):
        """嵌套 tuple key 的顶层前缀匹配"""
        log = {("body", "player", "id"): "123", ("message",): "hello"}
        result = _mask_sensitive_fields(log, {"body"})
        self.assertEqual(result[("body", "player", "id")], _MASKED_VALUE)
        self.assertEqual(result[("message",)], "hello")

    def test_masks_string_key_compat(self):
        """兼容 string key（merge_nested_data 失败时的原始格式）"""
        log = {"body": "secret_data", "message": "hello"}
        result = _mask_sensitive_fields(log, {"body"})
        self.assertEqual(result["body"], _MASKED_VALUE)
        self.assertEqual(result["message"], "hello")

    def test_empty_sensitive_fields(self):
        """空敏感字段集合：不做任何遮罩"""
        log = {("a",): "value"}
        result = _mask_sensitive_fields(log, set())
        self.assertEqual(result, {("a",): "value"})


class TestIsFailClosed(SimpleTestCase):
    """_is_fail_closed 公共函数测试"""

    def test_detects_masked_value(self):
        """检测到 _MASKED_VALUE 返回 True"""
        log = {("body",): _MASKED_VALUE, ("other",): "value"}
        metadata = {("body",): {"type": "scalar"}, ("other",): {"type": "scalar"}}
        self.assertTrue(_is_fail_closed(log, metadata))

    def test_no_masked_value(self):
        """无 _MASKED_VALUE 返回 False"""
        log = {("body",): "normal", ("other",): "value"}
        metadata = {("body",): {"type": "scalar"}, ("other",): {"type": "scalar"}}
        self.assertFalse(_is_fail_closed(log, metadata))

    def test_empty_metadata(self):
        """空元数据返回 False"""
        self.assertFalse(_is_fail_closed({("a",): 1}, {}))

    def test_restore_dict_preserves_key_order(self):
        """dict 类型还原时 key 顺序保持"""
        expanded = {("body", "c"): "3", ("body", "a"): "1", ("body", "b"): "2"}
        metadata = {("body",): {"type": "dict"}}
        restored = restore_by_metadata(expanded, metadata)

        self.assertIsInstance(restored["body"], dict)
        self.assertEqual(list(restored["body"].keys()), ["c", "a", "b"])
