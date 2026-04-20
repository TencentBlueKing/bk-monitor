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

import re
import unittest

from django.test import TestCase

from apps.log_databus.handlers.grok.base import Grok, BUILTIN_PATTERNS
from apps.log_databus.handlers.grok.patterns import ALL_PATTERNS
from apps.log_databus.models import GrokInfo

from apps.log_databus.handlers.grok.handler import GrokHandler
from apps.log_databus.exceptions import (
    GrokCircularReferenceException,
    GrokReferencedException,
    GrokPatternNotFoundException,
    DuplicateGrokPatternException,
)

# 按模块分组导入，供 TestPerModulePatterns 使用
from apps.log_databus.handlers.grok.patterns.grok_patterns import PATTERNS as GROK_PATTERNS
from apps.log_databus.handlers.grok.patterns.aws import PATTERNS as AWS_PATTERNS
from apps.log_databus.handlers.grok.patterns.bacula import PATTERNS as BACULA_PATTERNS
from apps.log_databus.handlers.grok.patterns.bro import PATTERNS as BRO_PATTERNS
from apps.log_databus.handlers.grok.patterns.exim import PATTERNS as EXIM_PATTERNS
from apps.log_databus.handlers.grok.patterns.firewalls import PATTERNS as FIREWALLS_PATTERNS
from apps.log_databus.handlers.grok.patterns.haproxy import PATTERNS as HAPROXY_PATTERNS
from apps.log_databus.handlers.grok.patterns.java import PATTERNS as JAVA_PATTERNS
from apps.log_databus.handlers.grok.patterns.junos import PATTERNS as JUNOS_PATTERNS
from apps.log_databus.handlers.grok.patterns.linux_syslog import PATTERNS as LINUX_SYSLOG_PATTERNS
from apps.log_databus.handlers.grok.patterns.mcollective import PATTERNS as MCOLLECTIVE_PATTERNS
from apps.log_databus.handlers.grok.patterns.mcollective_patterns import PATTERNS as MCOLLECTIVE_PATTERNS_PATTERNS
from apps.log_databus.handlers.grok.patterns.mongodb import PATTERNS as MONGODB_PATTERNS
from apps.log_databus.handlers.grok.patterns.nagios import PATTERNS as NAGIOS_PATTERNS
from apps.log_databus.handlers.grok.patterns.postgresql import PATTERNS as POSTGRESQL_PATTERNS
from apps.log_databus.handlers.grok.patterns.rails import PATTERNS as RAILS_PATTERNS
from apps.log_databus.handlers.grok.patterns.redis import PATTERNS as REDIS_PATTERNS
from apps.log_databus.handlers.grok.patterns.ruby import PATTERNS as RUBY_PATTERNS


class TestPatternDataIntegrity(unittest.TestCase):
    """测试模式数据完整性：字段、名称唯一性、ALL_PATTERNS 聚合正确性"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.all_patterns = ALL_PATTERNS
        cls.builtin_map = BUILTIN_PATTERNS

    def test_all_patterns_not_empty(self):
        """ALL_PATTERNS 不应为空"""
        self.assertGreater(len(self.all_patterns), 0, "ALL_PATTERNS 不应为空")

    def test_all_patterns_have_required_fields(self):
        """每个模式必须包含 name 和 pattern 字段，且不为空"""
        for p in self.all_patterns:
            self.assertIn("name", p, f"模式缺少 name 字段: {p}")
            self.assertIn("pattern", p, f"模式缺少 pattern 字段: {p}")
            self.assertTrue(p["name"].strip(), f"模式 name 不应为空: {p}")
            self.assertIsInstance(p["pattern"], str, f"模式 pattern 应为字符串: {p}")

    def test_pattern_names_are_unique(self):
        """模式名称不应重复，且 BUILTIN_PATTERNS 字典条目数应与 ALL_PATTERNS 一致"""
        names = [p["name"] for p in self.all_patterns]
        duplicates = [name for name in names if names.count(name) > 1]
        self.assertEqual(len(duplicates), 0, f"存在重复的模式名称: {set(duplicates)}")
        # 名称唯一时，字典条目数应一致
        self.assertEqual(len(self.builtin_map), len(self.all_patterns))

    def test_all_patterns_count_matches_sum_of_modules(self):
        """ALL_PATTERNS 的总数应等于各模块模式数之和"""
        module_patterns = [
            GROK_PATTERNS,
            AWS_PATTERNS,
            BACULA_PATTERNS,
            BRO_PATTERNS,
            EXIM_PATTERNS,
            FIREWALLS_PATTERNS,
            HAPROXY_PATTERNS,
            JAVA_PATTERNS,
            JUNOS_PATTERNS,
            LINUX_SYSLOG_PATTERNS,
            MCOLLECTIVE_PATTERNS,
            MCOLLECTIVE_PATTERNS_PATTERNS,
            MONGODB_PATTERNS,
            NAGIOS_PATTERNS,
            POSTGRESQL_PATTERNS,
            RAILS_PATTERNS,
            REDIS_PATTERNS,
            RUBY_PATTERNS,
        ]
        total = sum(len(m) for m in module_patterns)
        self.assertEqual(
            len(self.all_patterns),
            total,
            f"ALL_PATTERNS 数量 ({len(self.all_patterns)}) 与各模块之和 ({total}) 不一致",
        )


class TestPerModulePatterns(unittest.TestCase):
    """
    按模块逐一测试每个 patterns 文件中的模式。
    确保每个模式都能通过 Grok 展开并编译，且带 sample 的模式能匹配。
    此测试已覆盖正则语法合法性和 sample 匹配，无需单独的 RegexSyntax / SampleMatch 测试类。
    """

    MODULE_PATTERNS = {
        "grok_patterns": GROK_PATTERNS,
        "aws": AWS_PATTERNS,
        "bacula": BACULA_PATTERNS,
        "bro": BRO_PATTERNS,
        "exim": EXIM_PATTERNS,
        "firewalls": FIREWALLS_PATTERNS,
        "haproxy": HAPROXY_PATTERNS,
        "java": JAVA_PATTERNS,
        "junos": JUNOS_PATTERNS,
        "linux_syslog": LINUX_SYSLOG_PATTERNS,
        "mcollective": MCOLLECTIVE_PATTERNS,
        "mcollective_patterns": MCOLLECTIVE_PATTERNS_PATTERNS,
        "mongodb": MONGODB_PATTERNS,
        "nagios": NAGIOS_PATTERNS,
        "postgresql": POSTGRESQL_PATTERNS,
        "rails": RAILS_PATTERNS,
        "redis": REDIS_PATTERNS,
        "ruby": RUBY_PATTERNS,
    }

    def test_each_module_patterns_compile_and_match(self):
        """逐模块测试：每个模式能编译，带 sample 的能匹配"""
        all_failures = {}

        for module_name, patterns in self.MODULE_PATTERNS.items():
            module_failures = []
            for p in patterns:
                name = p["name"]
                sample = p.get("sample")
                grok_expr = f"%{{{name}:value}}"

                # 测试编译
                try:
                    grok = Grok(grok_expr)
                except Exception as e:
                    module_failures.append(f"  编译失败 - {name}: {e}")
                    continue

                # 测试匹配（仅对有 sample 的模式）
                if sample:
                    try:
                        result = grok.match(sample)
                        if result is None:
                            module_failures.append(f"  匹配失败 - {name}: sample={sample!r} 返回 None")
                        elif "value" not in result:
                            module_failures.append(f"  匹配失败 - {name}: 结果缺少 value 字段, result={result}")
                    except Exception as e:
                        module_failures.append(f"  匹配异常 - {name}: sample={sample!r}, error={e}")

            if module_failures:
                all_failures[module_name] = module_failures

        if all_failures:
            lines = ["以下模块存在问题:"]
            for module_name, failures in all_failures.items():
                lines.append(f"\n[{module_name}]")
                lines.extend(failures)
            self.fail("\n".join(lines))


class TestGrokCoreMatch(unittest.TestCase):
    """测试 Grok 类的核心匹配功能"""

    def test_common_patterns_match_detail(self):
        """测试常用模式的匹配细节，验证提取的值是否正确"""
        test_cases = [
            ("IP", "192.168.1.1", "192.168.1.1"),
            ("IP", "::1", "::1"),
            ("WORD", "hello", "hello"),
            ("INT", "-42", "-42"),
            ("NUMBER", "3.14", "3.14"),
            ("POSINT", "42", "42"),
            ("EMAILADDRESS", "user.name@example.com", "user.name@example.com"),
            ("USERNAME", "john.doe-01", "john.doe-01"),
            ("NOTSPACE", "no-spaces-here", "no-spaces-here"),
            ("BASE16NUM", "0x1A3F", "0x1A3F"),
            ("UUID", "550e8400-e29b-41d4-a716-446655440000", "550e8400-e29b-41d4-a716-446655440000"),
            ("HOSTNAME", "www.example.com", "www.example.com"),
            ("LOGLEVEL", "ERROR", "ERROR"),
            ("UNIXPATH", "/var/log/syslog", "/var/log/syslog"),
        ]

        for pattern_name, sample, expected_value in test_cases:
            with self.subTest(pattern=pattern_name, sample=sample):
                grok = Grok(f"%{{{pattern_name}:value}}")
                result = grok.match(sample)
                self.assertIsNotNone(result, f"模式 {pattern_name} 无法匹配 sample: {sample!r}")
                self.assertEqual(result.get("value"), expected_value)

    def test_no_match_returns_none(self):
        """不匹配时应返回 None"""
        grok = Grok("%{IP:ip_address}")
        result = grok.match("not_an_ip_address")
        self.assertIsNone(result)

    def test_pattern_without_field_name(self):
        """不带字段名的模式（非捕获组）不应出现在结果中"""
        grok = Grok("%{WORD} %{NUMBER:num}")
        result = grok.match("hello 42")
        self.assertIsNotNone(result)
        self.assertNotIn("WORD", result)
        self.assertEqual(result["num"], "42")

    def test_multiple_fields_extraction(self):
        """多字段提取"""
        grok = Grok("%{WORD:method} %{URIPATHPARAM:request} %{NUMBER:status}")
        result = grok.match("GET /api/v1/users?page=1 200")
        self.assertIsNotNone(result)
        self.assertEqual(result["method"], "GET")
        self.assertEqual(result["request"], "/api/v1/users?page=1")
        self.assertEqual(result["status"], "200")


class TestGrokTypeConversion(unittest.TestCase):
    """测试 Grok 类的类型转换功能"""

    def test_int_conversion(self):
        """int 类型转换"""
        grok = Grok("%{NUMBER:port:int}")
        result = grok.match("8080")
        self.assertIsNotNone(result)
        self.assertEqual(result["port"], 8080)
        self.assertIsInstance(result["port"], int)

    def test_float_conversion(self):
        """float 类型转换"""
        grok = Grok("%{NUMBER:ratio:float}")
        result = grok.match("3.14")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["ratio"], 3.14)
        self.assertIsInstance(result["ratio"], float)

    def test_int_conversion_negative(self):
        """负整数类型转换"""
        grok = Grok("%{INT:value:int}")
        result = grok.match("-100")
        self.assertIsNotNone(result)
        self.assertEqual(result["value"], -100)

    def test_no_type_conversion_default_string(self):
        """不指定类型时，值应为字符串"""
        grok = Grok("%{NUMBER:port}")
        result = grok.match("8080")
        self.assertIsNotNone(result)
        self.assertIsInstance(result["port"], str)

    def test_multiple_type_conversions(self):
        """多字段同时进行类型转换"""
        grok = Grok("%{IP:ip} %{NUMBER:status:int} %{NUMBER:duration:float}")
        result = grok.match("192.168.1.1 200 1.234")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], 200)
        self.assertAlmostEqual(result["duration"], 1.234)


class TestGrokCustomPatterns(unittest.TestCase):
    """测试自定义模式功能"""

    def test_custom_pattern_basic(self):
        """自定义模式基本使用"""
        custom = {"MY_STATUS": r"OK|FAIL|WARN"}
        grok = Grok("%{MY_STATUS:status}", custom_patterns=custom)

        self.assertEqual(grok.match("OK")["status"], "OK")
        self.assertEqual(grok.match("FAIL")["status"], "FAIL")
        self.assertIsNone(grok.match("UNKNOWN"))

    def test_custom_pattern_override_builtin(self):
        """自定义模式可以覆盖内置模式"""
        custom = {"WORD": r"[A-Z]+"}
        grok = Grok("%{WORD:w}", custom_patterns=custom)

        self.assertIsNotNone(grok.match("HELLO"))
        self.assertIsNone(grok.match("hello"))

    def test_nested_custom_patterns(self):
        """嵌套自定义模式"""
        custom = {
            "INNER_NUM": r"\d{3}",
            "OUTER_CODE": r"CODE-%{INNER_NUM}",
        }
        grok = Grok("%{OUTER_CODE:code}", custom_patterns=custom)
        result = grok.match("CODE-123")
        self.assertIsNotNone(result)
        self.assertEqual(result["code"], "CODE-123")

    def test_custom_pattern_with_builtin_reference(self):
        """自定义模式中引用内置模式"""
        custom = {"MY_LOG": r"%{IP:ip} %{LOGLEVEL:level} %{GREEDYDATA:msg}"}
        grok = Grok("%{MY_LOG:log}", custom_patterns=custom)
        result = grok.match("192.168.1.1 ERROR something went wrong")
        self.assertIsNotNone(result)
        self.assertEqual(result["ip"], "192.168.1.1")
        self.assertEqual(result["level"], "ERROR")


class TestGrokEdgeCases(unittest.TestCase):
    """测试边界情况"""

    def test_unknown_pattern_raises_key_error(self):
        """引用不存在的模式时应抛出 KeyError"""
        with self.assertRaises(KeyError):
            Grok("%{NONEXISTENT_PATTERN:value}")

    def test_empty_string_match(self):
        """空字符串匹配 - GREEDYDATA 可以匹配空字符串"""
        grok = Grok("%{GREEDYDATA:data}")
        result = grok.match("")
        self.assertIsNotNone(result)
        self.assertEqual(result["data"], "")

    def test_empty_string_no_match(self):
        """空字符串不匹配需要内容的模式"""
        grok = Grok("%{WORD:w}")
        self.assertIsNone(grok.match(""))

    def test_special_characters_in_input(self):
        """输入包含特殊字符"""
        grok = Grok("%{GREEDYDATA:data}")
        result = grok.match("hello [world] (test) {foo} $bar ^baz")
        self.assertIsNotNone(result)

    def test_unicode_input(self):
        """Unicode 输入"""
        grok = Grok("%{GREEDYDATA:data}")
        result = grok.match("你好世界 こんにちは мир")
        self.assertIsNotNone(result)
        self.assertIn("你好世界", result["data"])

    def test_very_long_input(self):
        """较长输入不应导致异常"""
        grok = Grok("%{IP:ip} %{GREEDYDATA:rest}")
        long_text = "192.168.1.1 " + "x" * 10000
        result = grok.match(long_text)
        self.assertIsNotNone(result)
        self.assertEqual(result["ip"], "192.168.1.1")

    def test_grok_regex_obj_and_pattern(self):
        """Grok 实例的 regex_obj 和 pattern 属性应正确"""
        pattern = "%{IP:ip} %{WORD:method}"
        grok = Grok(pattern)
        self.assertIsInstance(grok.regex_obj, re.Pattern)
        self.assertEqual(grok.pattern, pattern)


class TestExtractPatternReferences(unittest.TestCase):
    """测试 GrokHandler._extract_pattern_references 静态方法"""

    def test_extract_references(self):
        """提取各种格式的引用"""
        # 简单引用
        self.assertEqual(GrokHandler._extract_pattern_references("%{IP:ip}"), {"IP"})
        # 多个引用
        self.assertEqual(
            GrokHandler._extract_pattern_references("%{IP:ip} %{WORD:method} %{NUMBER:status}"),
            {"IP", "WORD", "NUMBER"},
        )
        # 不带字段名
        self.assertEqual(GrokHandler._extract_pattern_references("%{IP} %{WORD}"), {"IP", "WORD"})
        # 带类型
        self.assertEqual(GrokHandler._extract_pattern_references("%{NUMBER:port:int}"), {"NUMBER"})
        # 无引用
        self.assertEqual(GrokHandler._extract_pattern_references(r"[a-z]+\d+"), set())
        # 重复引用应去重
        self.assertEqual(GrokHandler._extract_pattern_references("%{IP:src_ip} %{IP:dst_ip}"), {"IP"})


class TestDetectCircularReference(unittest.TestCase):
    """测试 GrokHandler.detect_circular_reference 类方法"""

    def test_no_circular_reference(self):
        """无循环引用（含菱形依赖）"""
        patterns_map = {
            "A": "%{B} %{C}",
            "B": "%{D}",
            "C": "%{D}",
            "D": r"\d+",
        }
        has_cycle, _ = GrokHandler.detect_circular_reference("A", patterns_map)
        self.assertFalse(has_cycle)

    def test_direct_circular_reference(self):
        """直接循环引用 A -> A"""
        has_cycle, cycle_path = GrokHandler.detect_circular_reference("A", {"A": "%{A}"})
        self.assertTrue(has_cycle)
        self.assertIn("A", cycle_path)

    def test_indirect_circular_reference(self):
        """间接循环引用 A -> B -> C -> A"""
        patterns_map = {"A": "%{B}", "B": "%{C}", "C": "%{A}"}
        has_cycle, cycle_path = GrokHandler.detect_circular_reference("A", patterns_map)
        self.assertTrue(has_cycle)
        self.assertIn("A", cycle_path)

    def test_long_chain_with_cycle(self):
        """长链依赖有循环 A -> B -> C -> D -> E -> B"""
        patterns_map = {"A": "%{B}", "B": "%{C}", "C": "%{D}", "D": "%{E}", "E": "%{B}"}
        has_cycle, _ = GrokHandler.detect_circular_reference("A", patterns_map)
        self.assertTrue(has_cycle)

    def test_reference_to_nonexistent_pattern(self):
        """引用不存在的模式（内置模式）不应报循环"""
        has_cycle, _ = GrokHandler.detect_circular_reference("A", {"A": "%{IP} %{B}", "B": r"\d+"})
        self.assertFalse(has_cycle)

    def test_empty_patterns_map(self):
        """空模式字典"""
        has_cycle, cycle_path = GrokHandler.detect_circular_reference("A", {})
        self.assertFalse(has_cycle)
        self.assertEqual(cycle_path, [])


class TestGrokHandlerWithDB(TestCase):
    """
    测试 GrokHandler 中需要数据库交互的方法。
    使用 Django TestCase 操作真实数据库，每个测试方法自动回滚事务。
    注意：内置模式已通过 migration 0048 预置到数据库中，无需手动创建。
    """

    def setUp(self):
        self.handler = GrokHandler(bk_biz_id=100)
        # 预置自定义模式（内置模式已通过 migration 预置）
        GrokInfo.objects.create(bk_biz_id=100, name="MY_PATTERN", pattern=r"\d+", is_builtin=False)
        GrokInfo.objects.create(bk_biz_id=100, name="MY_STATUS", pattern=r"OK|FAIL", is_builtin=False)

    # ---- get / list 方法 ----

    def test_get_custom_patterns_map(self):
        """获取自定义模式字典"""
        result = self.handler.get_custom_patterns_map()
        self.assertEqual(result, {"MY_PATTERN": r"\d+", "MY_STATUS": r"OK|FAIL"})

    def test_get_all_pattern_names(self):
        """获取所有模式名称（包含内置和自定义）"""
        result = self.handler.get_all_pattern_names()
        self.assertIn("IP", result)
        self.assertIn("MY_PATTERN", result)

    def test_list_grok_info_basic(self):
        """列表查询 - 基本查询"""
        result = GrokHandler.list_grok_info({"bk_biz_id": 100})
        builtin_count = GrokInfo.objects.filter(is_builtin=True).count()
        self.assertEqual(result["total"], builtin_count + 2)
        self.assertEqual(len(result["list"]), result["total"])

    def test_list_grok_info_with_keyword(self):
        """列表查询 - 带关键字过滤"""
        result = GrokHandler.list_grok_info({"bk_biz_id": 100, "keyword": "MY_PATTERN"})
        names = [item["name"] for item in result["list"]]
        self.assertIn("MY_PATTERN", names)

    def test_list_grok_info_filter_builtin_and_custom(self):
        """列表查询 - 按 is_builtin 过滤"""
        builtin_result = GrokHandler.list_grok_info({"bk_biz_id": 100, "is_builtin": True})
        for item in builtin_result["list"]:
            self.assertTrue(item["is_builtin"])

        custom_result = GrokHandler.list_grok_info({"bk_biz_id": 100, "is_builtin": False})
        for item in custom_result["list"]:
            self.assertFalse(item["is_builtin"])

    def test_list_grok_info_with_pagination(self):
        """列表查询 - 分页"""
        result = GrokHandler.list_grok_info({"bk_biz_id": 100, "page": 1, "pagesize": 2})
        self.assertGreater(result["total"], 2)
        self.assertEqual(len(result["list"]), 2)

    def test_get_updated_by_list(self):
        """获取更新人列表"""
        GrokInfo.objects.filter(bk_biz_id=100).update(updated_by="admin")
        result = GrokHandler.get_updated_by_list(100)
        self.assertIn("admin", result)

    # ---- 验证方法 ----

    def test_validate_references_exist(self):
        """验证引用存在 - 成功和失败"""
        self.handler.validate_references_exist("%{IP:ip} %{WORD:method}")
        with self.assertRaises(GrokPatternNotFoundException):
            self.handler.validate_references_exist("%{IP:ip} %{NONEXISTENT:value}")

    def test_validate_circular_reference(self):
        """验证循环引用 - 无循环和有循环"""
        GrokInfo.objects.create(bk_biz_id=100, name="MY_A", pattern=r"\d+", is_builtin=False)
        self.handler.validate_circular_reference("MY_B", "%{MY_A}")

        GrokInfo.objects.filter(name="MY_A", bk_biz_id=100).update(pattern="%{MY_B}")
        with self.assertRaises(GrokCircularReferenceException):
            self.handler.validate_circular_reference("MY_B", "%{MY_A}")

    # ---- CRUD 方法 ----

    def test_create_grok_info_success(self):
        """创建 Grok 模式 - 成功"""
        result = self.handler.create_grok_info(
            {
                "name": "MY_LOG",
                "pattern": "%{IP:ip} %{WORD:method}",
                "sample": "192.168.1.1 GET",
                "description": "自定义日志模式",
            }
        )
        grok = GrokInfo.objects.get(id=result["id"])
        self.assertEqual(grok.name, "MY_LOG")
        self.assertEqual(grok.bk_biz_id, 100)

    def test_create_grok_info_duplicate(self):
        """创建 Grok 模式 - 名称重复"""
        with self.assertRaises(DuplicateGrokPatternException):
            self.handler.create_grok_info({"name": "MY_PATTERN", "pattern": r"\d+"})

    def test_update_grok_info(self):
        """更新 Grok 模式"""
        grok = GrokInfo.objects.create(
            bk_biz_id=100,
            name="MY_LOG",
            pattern="%{IP:ip}",
            is_builtin=False,
            sample="old_sample",
            description="旧描述",
        )
        self.handler.update_grok_info(
            {"id": grok.id, "pattern": "%{IP:ip} %{WORD:method}", "sample": "192.168.1.1 GET", "description": "新描述"}
        )
        grok.refresh_from_db()
        self.assertEqual(grok.pattern, "%{IP:ip} %{WORD:method}")
        self.assertEqual(grok.description, "新描述")

    def test_delete_grok_info_success(self):
        """删除 Grok 模式 - 成功（无引用）"""
        grok = GrokInfo.objects.create(bk_biz_id=100, name="MY_LOG", pattern="%{IP:ip}", is_builtin=False)
        GrokHandler.delete_grok_info(grok.id)
        self.assertFalse(GrokInfo.objects.filter(id=grok.id).exists())

    def test_delete_grok_info_builtin_noop(self):
        """删除内置 Grok 模式 - 不执行删除"""
        builtin_grok = GrokInfo.objects.get(name="IP", is_builtin=True)
        GrokHandler.delete_grok_info(builtin_grok.id)
        self.assertTrue(GrokInfo.objects.filter(id=builtin_grok.id).exists())

    def test_delete_grok_info_referenced(self):
        """删除被引用的 Grok 模式 - 抛出异常"""
        base = GrokInfo.objects.create(bk_biz_id=100, name="MY_BASE", pattern=r"\d+", is_builtin=False)
        GrokInfo.objects.create(bk_biz_id=100, name="MY_LOG", pattern="%{MY_BASE:base}", is_builtin=False)
        with self.assertRaises(GrokReferencedException):
            GrokHandler.delete_grok_info(base.id)
        self.assertTrue(GrokInfo.objects.filter(id=base.id).exists())

    def test_delete_grok_info_not_found(self):
        """删除不存在的 Grok 模式 - 静默返回"""
        GrokHandler.delete_grok_info(99999)

    def test_create_and_delete_lifecycle(self):
        """完整生命周期：创建 -> 查询 -> 删除"""
        result = self.handler.create_grok_info(
            {"name": "LIFECYCLE_TEST", "pattern": r"\d+", "sample": "123", "description": "生命周期测试"}
        )
        grok_id = result["id"]
        self.assertTrue(GrokInfo.objects.filter(id=grok_id).exists())
        GrokHandler.delete_grok_info(grok_id)
        self.assertFalse(GrokInfo.objects.filter(id=grok_id).exists())

    # ---- debug 方法 ----

    def test_debug_with_builtin_pattern(self):
        """调试内置模式"""
        result = self.handler.debug({"pattern": "%{IP:ip} %{WORD:method}", "sample": "192.168.1.1 GET /api/v1/users"})
        self.assertIsNotNone(result)
        self.assertEqual(result["ip"], "192.168.1.1")
        self.assertEqual(result["method"], "GET")

    def test_debug_with_custom_pattern(self):
        """调试自定义模式"""
        result = self.handler.debug({"pattern": "%{IP:ip} %{MY_STATUS:status}", "sample": "192.168.1.1 OK"})
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "OK")

    def test_debug_no_match(self):
        """调试 - 不匹配"""
        result = self.handler.debug({"pattern": "%{IP:ip}", "sample": "not_an_ip"})
        self.assertIsNone(result)

    def test_debug_returns_matched_field(self):
        """调试结果应包含 _matched 字段"""
        result = self.handler.debug({"pattern": "%{IP:ip} %{WORD:method}", "sample": "prefix 192.168.1.1 GET suffix"})
        self.assertIsNotNone(result)
        self.assertEqual(result["_matched"], "192.168.1.1 GET")

    # ---- grok_to_regex 方法 ----

    def test_grok_to_regex_basic(self):
        """基本 Grok 转正则"""
        regex = self.handler.grok_to_regex("%{IP:ip} %{WORD:method}")
        match = re.compile(regex).search("192.168.1.1 GET")
        self.assertIsNotNone(match)
        self.assertEqual(match.group("ip"), "192.168.1.1")

    def test_grok_to_regex_with_custom_pattern(self):
        """带自定义模式的 Grok 转正则"""
        regex = self.handler.grok_to_regex("%{IP:ip} %{MY_STATUS:status}")
        match = re.compile(regex).search("192.168.1.1 OK")
        self.assertIsNotNone(match)
        self.assertEqual(match.group("status"), "OK")

    def test_grok_to_regex_no_grok_references(self):
        """纯正则表达式（无 Grok 引用）"""
        regex = self.handler.grok_to_regex(r"(?P<num>\d+)")
        self.assertEqual(regex, r"(?P<num>\d+)")

    # ---- replace_custom_patterns 方法 ----

    def test_replace_custom_patterns_basic(self):
        """替换自定义模式，保留内置模式"""
        result = self.handler.replace_custom_patterns("%{IP:ip} %{MY_STATUS:status}")
        self.assertIn("%{IP:ip}", result)
        self.assertNotIn("%{MY_STATUS", result)
        self.assertIn("OK|FAIL", result)

    def test_replace_custom_patterns_no_custom(self):
        """无自定义模式时，表达式不变"""
        pattern = "%{IP:ip} %{WORD:method}"
        self.assertEqual(self.handler.replace_custom_patterns(pattern), pattern)

    def test_replace_custom_patterns_nested(self):
        """嵌套自定义模式应被递归替换"""
        GrokInfo.objects.create(bk_biz_id=100, name="MY_INNER", pattern=r"\d{3}", is_builtin=False)
        GrokInfo.objects.create(bk_biz_id=100, name="MY_OUTER", pattern=r"CODE-%{MY_INNER}", is_builtin=False)

        result = self.handler.replace_custom_patterns("%{MY_OUTER:code}")
        self.assertNotIn("%{MY_OUTER", result)
        self.assertNotIn("%{MY_INNER", result)
        self.assertIn(r"\d{3}", result)

    def test_replace_custom_patterns_with_type(self):
        """替换带类型的自定义模式"""
        result = self.handler.replace_custom_patterns("%{MY_PATTERN:port:int}")
        self.assertNotIn("%{MY_PATTERN", result)
        self.assertIn("port", result)


if __name__ == "__main__":
    unittest.main()
