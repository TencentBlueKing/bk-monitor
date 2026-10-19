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

from apps.log_desensitize.utils import path_aware_expand, restore_by_metadata


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
        """JSON 解析失败（形似 JSON 但内容非法）：保持原字符串值"""
        data = {"body": '{"player":{"id":invalid_json}}'}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(data, paths)

        # 形似 JSON object 但解析失败，应保持原值
        self.assertEqual(expanded["body"], '{"player":{"id":invalid_json}}')

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

    def test_max_depth_exceeded(self):
        """超深嵌套：超过 max_depth 后停止展开，深层 key 不存在于 expanded 中"""
        data = {}
        current = data
        for i in range(15):
            current["level"] = {}
            current["leaf"] = "value_{}".format(i)
            current = current["level"]

        paths = ["{}leaf".format("level." * 15)]
        expanded, __ = path_aware_expand(data, paths, max_depth=10)

        # depth 0-10（≤ max_depth）的 leaf 应出现在 expanded 中
        for i in range(11):
            key = "leaf" if i == 0 else "{}.leaf".format(".".join(["level"] * i))
            self.assertIn(key, expanded)
            self.assertEqual(expanded[key], "value_{}".format(i))

        # depth 11+（> max_depth）的 leaf 不应出现
        deep_key = "leaf" if 11 == 0 else "{}.leaf".format(".".join(["level"] * 11))
        self.assertNotIn(deep_key, expanded)

    def test_max_json_bytes_exceeded(self):
        """超大 JSON 字符串：超过 max_json_bytes 后跳过解析"""
        large_json = '{"player":{"id":"' + "x" * 70000 + '"}}'
        data = {"body": large_json}
        paths = ["body.player.id"]
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
