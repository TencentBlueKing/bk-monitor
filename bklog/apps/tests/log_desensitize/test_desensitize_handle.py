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
from apps.log_desensitize.utils import (
    JSON_LEAF_MAX_DEPTH,
    TEXT_FIELD_MASKED_VALUE,
    DesensitizeHit,
    expand_nested_data,
    sync_text_fields,
)

IP_PATTERN = r"\d{1,3}(?:\.\d{1,3}){3}"


CLIENT_JSON = (
    '{"ip":"10.20.30.40","port":12345,"user_agent":"user-agent-test0/1.2.3",'
    '"location":{"city":"北京市","country":"CN","district":"海淀区","province":"北京市"}}'
)
LOG_TEXT = (
    'request done {"client":{"ip":"10.20.30.40","port":12345,"user_agent":"user-agent-test0/1.2.3",'
    '"location":{"country":"CN","province":"北京市","city":"北京市","district":"海淀区"}}} status=200'
)


def build_config(field_name, operator, params, match_pattern="", sort_index=0):
    """
    构造一条不绑定规则 ID 的字段脱敏配置
    """
    return {
        "field_name": field_name,
        "rule_id": 0,
        "operator": operator,
        "params": params,
        "match_pattern": match_pattern,
        "sort_index": sort_index,
    }


def replace_config(field_name, template, match_pattern=""):
    """
    文本替换配置；match_pattern 为空时为整字段规则
    """
    return build_config(
        field_name,
        DesensitizeOperator.TEXT_REPLACE.value,
        {"template_string": template},
        match_pattern,
    )


def mask_all_config(field_name):
    """
    整字段全部掩码配置
    """
    params = {"preserve_head": 0, "preserve_tail": 0, "replace_mark": "*"}
    return build_config(field_name, DesensitizeOperator.MASK_SHIELD.value, params)


def run_sync(configs, log, text_fields=("log",)):
    """
    按检索链路的顺序执行：展开 -> 字段脱敏（记录命中）-> 原文同步
    """
    handler = DesensitizeHandler(configs)
    hits = []
    result = handler.transform_dict(expand_nested_data(log), hits=hits)
    return sync_text_fields(result, list(text_fields), hits, handler, index_set_id=1)


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


class TestFieldRuleMatching(SimpleTestCase):
    """
    transform_dict 字段匹配：完全相同的字段名优先，否则按最长上级字段匹配
    """

    def test_nested_parent_rule_matches_leaf(self):
        handler = DesensitizeHandler([replace_config("__ext_json.data", "[M]")])
        result = handler.transform_dict({"__ext_json.data.phone": "13800001111", "other": "keep"})
        self.assertEqual(result, {"__ext_json.data.phone": "[M]", "other": "keep"})

    def test_longest_parent_rule_wins(self):
        handler = DesensitizeHandler(
            [replace_config("__ext_json", "[TOP]"), replace_config("__ext_json.data", "[DATA]")]
        )
        result = handler.transform_dict({"__ext_json.data.x": "a", "__ext_json.other": "b"})
        self.assertEqual(result, {"__ext_json.data.x": "[DATA]", "__ext_json.other": "[TOP]"})

    def test_top_level_rule_no_regression(self):
        handler = DesensitizeHandler([replace_config("__ext", "[M]")])
        result = handler.transform_dict({"__ext.a.b": "value", "serverIp": "10.0.0.1"})
        self.assertEqual(result, {"__ext.a.b": "[M]", "serverIp": "10.0.0.1"})

    def test_exact_rule_preferred(self):
        handler = DesensitizeHandler([replace_config("a.b", "[AB]"), replace_config("a", "[A]")])
        result = handler.transform_dict({"a.b": "1", "a.c": "2"})
        self.assertEqual(result, {"a.b": "[AB]", "a.c": "[A]"})

    def test_prefix_matched_by_segment(self):
        handler = DesensitizeHandler([replace_config("__ext_json.data", "[M]")])
        result = handler.transform_dict({"__ext_json.database.x": "keep"})
        self.assertEqual(result, {"__ext_json.database.x": "keep"})

    def test_agg_dimensions_with_str_keys(self):
        """Grafana 聚合维度以字符串 key 传入，仍需脱敏"""
        handler = DesensitizeHandler(
            [replace_config("serverIp", "[IP]", IP_PATTERN), replace_config("__ext_json.data", "[M]")]
        )
        result = handler.transform_dict({"serverIp": "10.0.0.1", "__ext_json.data.phone": "13800001111"})
        self.assertEqual(result, {"serverIp": "[IP]", "__ext_json.data.phone": "[M]"})


class TestTransformHits(SimpleTestCase):
    """
    transform_dict 记录实际发生的替换
    """

    def test_without_hits_output_unchanged(self):
        configs = [replace_config("ip", "[IP]", IP_PATTERN)]
        result = DesensitizeHandler(configs).transform_dict({"ip": "client 10.20.30.40 ok"})
        self.assertEqual(result, {"ip": "client [IP] ok"})

    def test_hits_record_regex_fragment(self):
        handler = DesensitizeHandler([replace_config("ip", "[IP]", IP_PATTERN)])
        hits = []
        handler.transform_dict({"ip": "client 10.20.30.40 ok"}, hits=hits)
        expected_hit = DesensitizeHit(
            field="ip",
            value="client 10.20.30.40 ok",
            src="10.20.30.40",
            masked="[IP]",
            rules=handler.field_rule_mapping["ip"],
            is_whole=False,
        )
        self.assertEqual(hits, [expected_hit])

    def test_hits_record_whole_value(self):
        handler = DesensitizeHandler([replace_config("ip", "[IP]")])
        hits = []
        handler.transform_dict({"ip": "10.20.30.40"}, hits=hits)
        self.assertEqual([(hit.src, hit.masked, hit.is_whole) for hit in hits], [("10.20.30.40", "[IP]", True)])

    def test_hits_skip_unchanged_value(self):
        params = {"preserve_head": 2, "preserve_tail": 2, "replace_mark": "*"}
        handler = DesensitizeHandler([build_config("code", DesensitizeOperator.MASK_SHIELD.value, params)])
        hits = []
        result = handler.transform_dict({"code": "abc"}, hits=hits)
        self.assertEqual(result, {"code": "abc"})
        self.assertEqual(hits, [])


class TestSyncTextFields(SimpleTestCase):
    """
    原文字段同步：按命中子串替换、整字段规则的 JSON 叶子回退与 fail-closed
    """

    def test_regex_fragment_synced_when_key_order_differs(self):
        result = run_sync(
            [replace_config("__ext_json.http.client", "[IP]", IP_PATTERN)],
            {"__ext_json": {"http": {"client": CLIENT_JSON}}, "log": LOG_TEXT},
        )
        self.assertEqual(result["__ext_json.http.client"], CLIENT_JSON.replace("10.20.30.40", "[IP]"))
        self.assertEqual(result["log"], LOG_TEXT.replace("10.20.30.40", "[IP]"))

    def test_longer_fragment_replaced_first(self):
        result = run_sync(
            [replace_config("ip", "[IP]"), replace_config("suffix", "[S]")],
            {"ip": "10.20.30.40", "suffix": "13.88", "log": "ip=10.20.30.40 tail=13.88"},
        )
        self.assertEqual(result["log"], "ip=[IP] tail=[S]")

    def test_non_string_text_field_skipped(self):
        configs = [replace_config("ip", "[IP]")]
        self.assertEqual(run_sync(configs, {"ip": "10.20.30.40", "log": None})["log"], None)
        self.assertEqual(run_sync(configs, {"ip": "10.20.30.40", "log": ["10.20.30.40"]})["log"], ["10.20.30.40"])

    def test_escaped_fragment_synced(self):
        result = run_sync(
            [replace_config("path", "[P]"), replace_config("city", "[C]")],
            {
                "path": "/api/v1/user",
                "city": "北京市",
                "log": '{"path":"\\/api\\/v1\\/user","city":"\\u5317\\u4eac\\u5e02"}',
            },
        )
        self.assertEqual(result["log"], '{"path":"[P]","city":"[C]"}')

    def test_text_field_own_hits_ignored(self):
        hit = DesensitizeHit(field="log", value="abc", src="abc", masked="[X]", rules=[], is_whole=False)
        result = sync_text_fields({"log": "abc"}, ["log"], [hit], DesensitizeHandler([]))
        self.assertEqual(result, {"log": "abc"})

    def test_whole_value_found_replaced_directly(self):
        value = '{"ip":"10.20.30.40"}'
        result = run_sync(
            [replace_config("__ext_json.http.client", "[CLIENT]")],
            {"__ext_json": {"http": {"client": value}}, "log": f"x {value} y"},
        )
        self.assertEqual(result["log"], "x [CLIENT] y")

    def test_whole_plain_value_absent_keeps_text(self):
        with self.assertNoLogs("apps.log_desensitize.utils", level="WARNING"):
            result = run_sync([replace_config("serverIp", "[IP]")], {"serverIp": "10.0.0.1", "log": "hello world"})
        self.assertEqual(result["log"], "hello world")

    def test_whole_json_parse_failed_fail_closed(self):
        with self.assertLogs("apps.log_desensitize.utils", level="WARNING") as captured:
            result = run_sync(
                [replace_config("client", "[CLIENT]")],
                {"client": '{"ip":"10.20.30.40"', "log": "x 10.20.30.40"},
            )
        self.assertEqual(result["log"], TEXT_FIELD_MASKED_VALUE)
        self.assertEqual(len(captured.output), 1)
        self.assertIn("reason=json_parse_failed", captured.output[0])
        self.assertIn("source_field=client", captured.output[0])
        self.assertNotIn("10.20.30.40", captured.output[0])

    def test_whole_deep_json_fail_closed(self):
        """嵌套超过 JSON_LEAF_MAX_DEPTH：不依赖解释器递归上限，确定性 fail-closed"""
        depth = JSON_LEAF_MAX_DEPTH + 100
        deep_value = '{"a":' * depth + "1" + "}" * depth
        with self.assertLogs("apps.log_desensitize.utils", level="WARNING") as captured:
            result = run_sync([replace_config("client", "[CLIENT]")], {"client": deep_value, "log": "a 1"})
        self.assertEqual(result["log"], TEXT_FIELD_MASKED_VALUE)
        self.assertIn("reason=json_too_deep", captured.output[0])

    def test_whole_json_within_depth_limit_replaced(self):
        depth = JSON_LEAF_MAX_DEPTH - 1
        deep_value = '{"a":' * depth + '"secret"' + "}" * depth
        result = run_sync([mask_all_config("client")], {"client": deep_value, "log": "token secret end"})
        self.assertEqual(result["log"], "token ****** end")

    def test_whole_json_leaves_all_found(self):
        result = run_sync(
            [mask_all_config("__ext_json.http.client")],
            {"__ext_json": {"http": {"client": CLIENT_JSON}}, "log": LOG_TEXT},
        )
        self.assertEqual(result["__ext_json.http.client"], "*" * len(CLIENT_JSON))
        self.assertEqual(
            result["log"],
            'request done {"client":{"ip":"***********","port":*****,"user_agent":"**********************",'
            '"location":{"country":"**","province":"***","city":"***","district":"***"}}} status=200',
        )

    def test_whole_json_leaves_partial_fail_closed(self):
        with self.assertLogs("apps.log_desensitize.utils", level="WARNING") as captured:
            result = run_sync(
                [replace_config("client", "[CLIENT]")],
                {"client": '{"ip":"10.20.30.40","token":"abc123"}', "log": "client ip 10.20.30.40"},
            )
        self.assertEqual(result["log"], TEXT_FIELD_MASKED_VALUE)
        self.assertIn("reason=partial_leaf_not_found", captured.output[0])

    def test_whole_json_leaves_none_found_keeps_text(self):
        result = run_sync([replace_config("client", "[CLIENT]")], {"client": '{"ip":"10.20.30.40"}', "log": "hello"})
        self.assertEqual(result["log"], "hello")

    def test_number_and_bool_leaves(self):
        result = run_sync(
            [mask_all_config("client")],
            {"client": '{"port":12345,"ok":true}', "log": "port=12345 ok=true"},
        )
        self.assertEqual(result["log"], "port=***** ok=****")

    def test_list_value_whole_rule(self):
        result = run_sync([mask_all_config("phones")], {"phones": ["13800001111"], "log": '{"phones":["13800001111"]}'})
        self.assertEqual(result["log"], '{"phones":' + "*" * len("['13800001111']") + "}")


class TestPreviewConsistency(SimpleTestCase):
    """
    预览与检索链路使用同一套字段匹配和原文同步逻辑
    """

    @staticmethod
    def _rules(template, match_pattern=""):
        return [{"operator": DesensitizeOperator.TEXT_REPLACE.value, "params": {"template_string": template},
                 "match_pattern": match_pattern}]

    def test_preview_nested_json_string_and_text_field(self):
        result = DesensitizeRuleHandler.preview(
            logs=[{"__ext_json": {"http": {"client": CLIENT_JSON}}, "log": LOG_TEXT}],
            field_configs=[{"field_name": "__ext_json.http.client", "rules": self._rules("[IP]", IP_PATTERN)}],
            text_fields=["log"],
        )
        self.assertEqual(
            result,
            {
                "__ext_json.http.client": [CLIENT_JSON.replace("10.20.30.40", "[IP]")],
                "log": [LOG_TEXT.replace("10.20.30.40", "[IP]")],
            },
        )

    def test_preview_object_parent_returns_json(self):
        result = DesensitizeRuleHandler.preview(
            logs=[{"__ext_json": {"data": {"phone": "13800001111", "lv": 5}}}],
            field_configs=[{"field_name": "__ext_json.data", "rules": self._rules("[PHONE]", r"1\d{10}")}],
            text_fields=[],
        )
        expected = json.dumps({"phone": "[PHONE]", "lv": "5"}, ensure_ascii=False)
        self.assertEqual(result, {"__ext_json.data": [expected]})

    def test_preview_missing_field_returns_none(self):
        result = DesensitizeRuleHandler.preview(
            logs=[{"x": 1}],
            field_configs=[{"field_name": "ip", "rules": self._rules("[IP]", IP_PATTERN)}],
            text_fields=[],
        )
        self.assertEqual(result, {"ip": [None]})
