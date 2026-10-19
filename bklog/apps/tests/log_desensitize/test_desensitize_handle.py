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

from django.test import SimpleTestCase, TestCase

from apps.log_desensitize.constants import DesensitizeOperator
from apps.log_desensitize.handlers.desensitize import DesensitizeHandler, DesensitizeRuleHandler
from apps.log_desensitize.utils import path_aware_expand, restore_by_metadata


class TestDesensitizeOperator(TestCase):
    """
    脱敏工厂单元测试
    """
    def test_transform_dict(self):
        param_1 = {
            "field_name": "test_field_1",
            "rule_id": 0,
            "operator": DesensitizeOperator.MASK_SHIELD.value,
            "params": {
                "preserve_head": 3,
                "preserve_tail": 3,
            },
            "match_pattern": "",
            "sort_index": 0
        }
        param_2 = {
            "field_name": "test_field_2",
            "rule_id": 0,
            "operator": DesensitizeOperator.TEXT_REPLACE.value,
            "params": {
                "template_string": "abc${partNum}defg",
            },
            "match_pattern": r"\d{3}(?P<partNum>\d{4})\d{4}",
            "sort_index": 1
        }

        text = {"test_field_1": "13234345678", "test_field_2": "13234345678"}
        desensitize_config_info = [param_1, param_2]

        result = DesensitizeHandler(desensitize_config_info=desensitize_config_info).transform_dict(text)

        self.assertEqual(result.get("test_field_1"), "132*****678")
        self.assertEqual(result.get("test_field_2"), "abc3434defg")

    def test_transform_dict_dotted_key(self):
        """dotted key 嵌套字段脱敏：transform_dict 能匹配展开后的 dotted path"""
        config = {
            "field_name": "body.player.id",
            "rule_id": 0,
            "operator": DesensitizeOperator.MASK_SHIELD.value,
            "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
            "match_pattern": "",
            "sort_index": 0,
        }
        text = {"body.player.id": "12345"}
        result = DesensitizeHandler(desensitize_config_info=[config]).transform_dict(text)

        self.assertEqual(result.get("body.player.id"), "1***5")


class TestPreviewConsistency(TestCase):
    """预览与查询一致性测试"""

    def test_preview_flattened_subpath(self):
        """预览能正确处理 flattened 子路径"""
        logs = [{"body": {"player": {"id": "12345"}}}]
        field_configs = [
            {
                "field_name": "body.player.id",
                "rules": [
                    {
                        "rule_id": 0,
                        "operator": DesensitizeOperator.MASK_SHIELD.value,
                        "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
                        "match_pattern": "",
                    }
                ],
            }
        ]
        text_fields = []

        result = DesensitizeRuleHandler.preview(logs, field_configs, text_fields)

        self.assertIn("body.player.id", result)
        self.assertEqual(result["body.player.id"][0], "1***5")

    def test_preview_json_string_subpath(self):
        """预览能正确处理 JSON 字符串子路径"""
        logs = [{"body": '{"player":{"id":"12345"},"server":{"ip":"10.0.0.1"}}'}]
        field_configs = [
            {
                "field_name": "body.player.id",
                "rules": [
                    {
                        "rule_id": 0,
                        "operator": DesensitizeOperator.MASK_SHIELD.value,
                        "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
                        "match_pattern": "",
                    }
                ],
            }
        ]
        text_fields = []

        result = DesensitizeRuleHandler.preview(logs, field_configs, text_fields)

        self.assertIn("body.player.id", result)
        self.assertEqual(result["body.player.id"][0], "1***5")
        # preview 只返回配置字段（body.player.id）的值，不返回中间路径（body）
        self.assertNotIn("body", result)

    def test_preview_with_text_fields(self):
        """预览带 text_fields 时，子路径脱敏仍正确返回"""
        logs = [{"body": {"player": {"id": "12345"}}, "log": "player id 12345"}]
        field_configs = [
            {
                "field_name": "body.player.id",
                "rules": [
                    {
                        "rule_id": 0,
                        "operator": DesensitizeOperator.MASK_SHIELD.value,
                        "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
                        "match_pattern": "",
                    }
                ],
            },
        ]
        text_fields = ["log"]

        result = DesensitizeRuleHandler.preview(logs, field_configs, text_fields)

        # 子路径脱敏结果正确返回
        self.assertIn("body.player.id", result)
        self.assertEqual(result["body.player.id"][0], "1***5")

    def test_expand_restore_consistency(self):
        """展开-脱敏-还原与直接查询结果一致（普通 object）"""
        original = {"body": {"player": {"id": "12345"}}}
        paths = ["body.player.id"]

        # 模拟查询链路
        expanded, metadata = path_aware_expand(original, paths)
        config = {
            "field_name": "body.player.id",
            "rule_id": 0,
            "operator": DesensitizeOperator.MASK_SHIELD.value,
            "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
            "match_pattern": "",
            "sort_index": 0,
        }
        handler = DesensitizeHandler(desensitize_config_info=[config])
        desensitized = handler.transform_dict(expanded)
        restored = restore_by_metadata(desensitized, metadata)

        # 结果应为嵌套 dict，且值被脱敏
        self.assertIsInstance(restored["body"], dict)
        self.assertEqual(restored["body"]["player"]["id"], "1***5")

    def test_expand_restore_consistency_json_string(self):
        """展开-脱敏-还原完整回路：JSON 字符串数据还原为字符串"""
        original = {"body": '{"player":{"id":"12345"},"server":{"ip":"10.0.0.1"}}'}
        paths = ["body.player.id"]

        # 模拟查询链路
        expanded, metadata = path_aware_expand(original, paths)
        config = {
            "field_name": "body.player.id",
            "rule_id": 0,
            "operator": DesensitizeOperator.MASK_SHIELD.value,
            "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
            "match_pattern": "",
            "sort_index": 0,
        }
        handler = DesensitizeHandler(desensitize_config_info=[config])
        desensitized = handler.transform_dict(expanded)
        restored = restore_by_metadata(desensitized, metadata)

        # 结果应为 JSON 字符串，且内部值被脱敏
        self.assertIsInstance(restored["body"], str)
        parsed = json.loads(restored["body"])
        self.assertEqual(parsed["player"]["id"], "1***5")
        # 未配置脱敏的字段保持原值
        self.assertEqual(parsed["server"]["ip"], "10.0.0.1")

    def test_preview_consistency_with_query_result(self):
        """预览结果与查询链路（展开-脱敏-还原）结果一致"""
        original = {"body": {"player": {"id": "12345"}}}
        paths = ["body.player.id"]
        config = {
            "field_name": "body.player.id",
            "rule_id": 0,
            "operator": DesensitizeOperator.MASK_SHIELD.value,
            "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
            "match_pattern": "",
            "sort_index": 0,
        }

        # 预览方式
        preview_configs = [
            {
                "field_name": "body.player.id",
                "rules": [
                    {
                        "rule_id": 0,
                        "operator": DesensitizeOperator.MASK_SHIELD.value,
                        "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
                        "match_pattern": "",
                    }
                ],
            }
        ]
        preview_result = DesensitizeRuleHandler.preview(
            [original], preview_configs, []
        )
        preview_value = preview_result["body.player.id"][0]

        # 查询链路方式
        handler = DesensitizeHandler(desensitize_config_info=[config])
        expanded, metadata = path_aware_expand(original, paths)
        desensitized = handler.transform_dict(expanded)
        restored = restore_by_metadata(desensitized, metadata)
        query_value = restored["body"]["player"]["id"]

        # 两者应一致
        self.assertEqual(preview_value, query_value)
        self.assertEqual(preview_value, "1***5")


class TestPathAwareExpandRoundtrip(SimpleTestCase):
    """path_aware_expand + restore_by_metadata 回路测试（纯内存）"""

    def test_dict_roundtrip_preserves_structure(self):
        """dict 类型回路：展开-脱敏-还原后结构不变"""
        original = {"body": {"player": {"id": "123", "name": "alice"}}}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(original, paths)

        # 脱敏只修改配置路径的值
        expanded["body.player.id"] = "***"
        restored = restore_by_metadata(expanded, metadata)

        self.assertIsInstance(restored["body"], dict)
        self.assertEqual(restored["body"]["player"]["id"], "***")
        self.assertEqual(restored["body"]["player"]["name"], "alice")

    def test_json_string_roundtrip_preserves_structure(self):
        """JSON 字符串回路：展开-脱敏-还原后结构不变"""
        original = {"body": '{"player":{"id":"123","name":"alice"}}'}
        paths = ["body.player.id"]
        expanded, metadata = path_aware_expand(original, paths)

        # 脱敏只修改配置路径的值
        expanded["body.player.id"] = "***"
        restored = restore_by_metadata(expanded, metadata)

        self.assertIsInstance(restored["body"], str)
        parsed = json.loads(restored["body"])
        self.assertEqual(parsed["player"]["id"], "***")
        self.assertEqual(parsed["player"]["name"], "alice")


class TestPreviewFalsyValues(TestCase):
    """
    验证 preview 方法修复后对 falsy 值的正确处理。

    修复前: `restored_result.get(_field_name)` 对 0/False/"" 返回 falsy，
    导致回退到 result.get(_field_name) 取到错误值。
    修复后: `_field_name in restored_result` 仅判断 key 是否存在。

    注意：对于 dotted path（如 body.player.id），key 不会出现在 restored_result 中
    （因为 restore_by_metadata 产出嵌套结构），所以修复前后行为一致。
    修复真正影响的场景是顶层字段（无点号）且值为 falsy 的情况。
    """

    def test_preview_top_level_zero_value(self):
        """preview 中顶层字段脱敏后值为 '0' 时正确返回"""
        logs = [{"count": 0}]
        field_configs = [
            {
                "field_name": "count",
                "rules": [
                    {
                        "rule_id": 0,
                        "operator": DesensitizeOperator.MASK_SHIELD.value,
                        "params": {"preserve_head": 0, "preserve_tail": 0, "replace_mark": "*"},
                        "match_pattern": "",
                    }
                ],
            }
        ]

        result = DesensitizeRuleHandler.preview(logs, field_configs, [])

        # count=0 → transform_dict 转为 "0" → mask_shield(preserve 0+0) 替换全部 → "*"
        self.assertIn("count", result)
        self.assertEqual(result["count"][0], "*")

    def test_preview_top_level_none_value(self):
        """preview 中顶层字段值为 None 时，transform_dict 转为空字符串后脱敏"""
        logs = [{"note": None}]
        field_configs = [
            {
                "field_name": "note",
                "rules": [
                    {
                        "rule_id": 0,
                        "operator": DesensitizeOperator.MASK_SHIELD.value,
                        "params": {"preserve_head": 0, "preserve_tail": 0, "replace_mark": "#"},
                        "match_pattern": "",
                    }
                ],
            }
        ]

        result = DesensitizeRuleHandler.preview(logs, field_configs, [])

        # None → transform_dict 中 str_value="" → mask_shield("") 返回 ""
        # restore_by_metadata: scalar 类型，sub_items.get("note")=""
        # "note" in restored_result → True, str("")=""
        self.assertIn("note", result)
        self.assertEqual(result["note"][0], "")

    def test_preview_dotted_path_falsy_value(self):
        """preview 中 dotted path 字段值为 0 时，通过 result.get 回退正确取值"""
        logs = [{"body": {"player": {"level": 0}}}]
        field_configs = [
            {
                "field_name": "body.player.level",
                "rules": [
                    {
                        "rule_id": 0,
                        "operator": DesensitizeOperator.MASK_SHIELD.value,
                        "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
                        "match_pattern": "",
                    }
                ],
            }
        ]

        result = DesensitizeRuleHandler.preview(logs, field_configs, [])

        # dotted path 在 restored_result（嵌套结构）中不存在，走 result.get 分支
        self.assertIn("body.player.level", result)
        # "0" len=1, preserve 1+1=2>=1, 不脱敏返回原值 "0"
        self.assertEqual(result["body.player.level"][0], "0")

    def test_preview_dotted_path_boolean_false(self):
        """preview 中 dotted path 字段值为 False 时正确返回"""
        logs = [{"body": {"player": {"online": False}}}]
        field_configs = [
            {
                "field_name": "body.player.online",
                "rules": [
                    {
                        "rule_id": 0,
                        "operator": DesensitizeOperator.MASK_SHIELD.value,
                        "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
                        "match_pattern": "",
                    }
                ],
            }
        ]

        result = DesensitizeRuleHandler.preview(logs, field_configs, [])

        self.assertIn("body.player.online", result)
        # False → "False" len=5, preserve 1+1=2<5, 脱敏: "F***e"
        self.assertEqual(result["body.player.online"][0], "F***e")

    def test_preview_normal_string_not_affected(self):
        """preview 中正常字符串值不受修复影响"""
        logs = [{"body": {"player": {"id": "12345"}}}]
        field_configs = [
            {
                "field_name": "body.player.id",
                "rules": [
                    {
                        "rule_id": 0,
                        "operator": DesensitizeOperator.MASK_SHIELD.value,
                        "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
                        "match_pattern": "",
                    }
                ],
            }
        ]

        result = DesensitizeRuleHandler.preview(logs, field_configs, [])

        self.assertEqual(result["body.player.id"][0], "1***5")


class TestRestoreByMetadataFalsyValues(SimpleTestCase):
    """验证 restore_by_metadata 对 falsy 值的正确还原（纯内存）"""

    def test_restore_json_string_with_zero(self):
        """JSON 字符串还原：内部数值 0 正确保留"""
        expanded = {"body.player.level": 0}
        metadata = {"body": {"type": "json_string"}}
        restored = restore_by_metadata(expanded, metadata)

        self.assertIsInstance(restored["body"], str)
        parsed = json.loads(restored["body"])
        self.assertEqual(parsed["player"]["level"], 0)

    def test_restore_dict_with_false(self):
        """dict 类型还原：布尔值 False 正确保留"""
        expanded = {"body.player.online": False}
        metadata = {"body": {"type": "dict"}}
        restored = restore_by_metadata(expanded, metadata)

        self.assertIsInstance(restored["body"], dict)
        self.assertFalse(restored["body"]["player"]["online"])

    def test_restore_dict_with_none(self):
        """dict 类型还原：None 值正确保留"""
        expanded = {"body.player.note": None}
        metadata = {"body": {"type": "dict"}}
        restored = restore_by_metadata(expanded, metadata)

        self.assertIsNone(restored["body"]["player"]["note"])

    def test_restore_json_string_with_empty_string(self):
        """JSON 字符串还原：内部空字符串正确保留"""
        expanded = {"body.player.name": ""}
        metadata = {"body": {"type": "json_string"}}
        restored = restore_by_metadata(expanded, metadata)

        self.assertIsInstance(restored["body"], str)
        parsed = json.loads(restored["body"])
        self.assertEqual(parsed["player"]["name"], "")
