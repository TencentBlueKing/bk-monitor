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
from unittest.mock import patch, MagicMock

from apps.log_databus.handlers.grok.base import Grok, get_builtin_patterns
from apps.log_databus.handlers.grok.patterns import ALL_PATTERNS

from django.db import IntegrityError

from apps.log_databus.handlers.grok.handler import GrokHandler
from apps.log_databus.exceptions import (
    GrokCircularReferenceException,
    GrokReferencedException,
    GrokPatternNotFoundException,
    DuplicateGrokPatternException,
)

# 按模块分组导入，方便定位问题
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
        cls.builtin_map = get_builtin_patterns()

    def test_all_patterns_not_empty(self):
        """ALL_PATTERNS 不应为空"""
        self.assertGreater(len(self.all_patterns), 0, "ALL_PATTERNS 不应为空")

    def test_builtin_patterns_loaded(self):
        """get_builtin_patterns() 返回的字典不应为空"""
        self.assertGreater(len(self.builtin_map), 0, "内置模式字典不应为空")

    def test_all_patterns_have_required_fields(self):
        """每个模式必须包含 name 和 pattern 字段"""
        for p in self.all_patterns:
            self.assertIn("name", p, f"模式缺少 name 字段: {p}")
            self.assertIn("pattern", p, f"模式缺少 pattern 字段: {p}")
            # name 和 pattern 不应为空字符串
            self.assertTrue(p["name"].strip(), f"模式 name 不应为空: {p}")
            self.assertTrue(isinstance(p["pattern"], str), f"模式 pattern 应为字符串: {p}")

    def test_pattern_names_are_unique(self):
        """模式名称不应重复"""
        names = [p["name"] for p in self.all_patterns]
        duplicates = [name for name in names if names.count(name) > 1]
        self.assertEqual(len(duplicates), 0, f"存在重复的模式名称: {set(duplicates)}")

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
            len(self.all_patterns), total, f"ALL_PATTERNS 数量 ({len(self.all_patterns)}) 与各模块之和 ({total}) 不一致"
        )

    def test_builtin_map_count_matches_all_patterns(self):
        """get_builtin_patterns() 返回的字典条目数应等于 ALL_PATTERNS 数量（名称唯一前提下）"""
        self.assertEqual(
            len(self.builtin_map), len(self.all_patterns), "内置模式字典条目数与 ALL_PATTERNS 数量不一致，可能存在重名"
        )


class TestPatternRegexSyntax(unittest.TestCase):
    """
    测试所有内置模式的正则表达式语法是否合法。
    由于模式已改写为 RE2/标准 re 兼容语法，需要确保每个模式都能被 re 模块编译。
    分两层测试：
    1. 叶子模式（不含 %{...} 引用）直接编译
    2. 所有模式通过 Grok 类展开后编译
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.all_patterns = ALL_PATTERNS
        cls.builtin_map = get_builtin_patterns()

    def test_leaf_patterns_compile(self):
        """不含 %{...} 引用的叶子模式应能直接被 re.compile 编译"""
        grok_ref_re = re.compile(r"%{\w+")
        failed = []

        for p in self.all_patterns:
            name = p["name"]
            pattern = p["pattern"]
            # 跳过包含 Grok 引用的模式
            if grok_ref_re.search(pattern):
                continue
            try:
                re.compile(pattern)
            except re.error as e:
                failed.append({"name": name, "pattern": pattern, "error": str(e)})

        if failed:
            lines = ["以下叶子模式正则语法错误:"]
            for f in failed:
                lines.append(f"  - {f['name']}: pattern={f['pattern']!r}, error={f['error']}")
            self.fail("\n".join(lines))

    def test_all_patterns_compile_via_grok(self):
        """所有模式通过 Grok 类展开后应能成功编译（验证嵌套引用展开后的正则合法性）"""
        failed = []

        for p in self.all_patterns:
            name = p["name"]
            grok_expr = f"%{{{name}:value}}"
            try:
                Grok(grok_expr)
            except re.error as e:
                failed.append({"name": name, "error": f"正则编译错误: {e}"})
            except KeyError as e:
                failed.append({"name": name, "error": f"引用的模式不存在: {e}"})
            except Exception as e:
                failed.append({"name": name, "error": f"未知错误: {type(e).__name__}: {e}"})

        if failed:
            lines = ["以下模式通过 Grok 展开后编译失败:"]
            for f in failed:
                lines.append(f"  - {f['name']}: {f['error']}")
            self.fail("\n".join(lines))


class TestPatternSampleMatch(unittest.TestCase):
    """
    测试所有带 sample 字段的内置模式能否正确匹配其 sample 样例。
    使用 %{PATTERN_NAME:value} 形式构造 Grok 表达式，
    验证 sample 能被成功匹配并提取到 value 字段。
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.all_patterns = ALL_PATTERNS

    def test_all_patterns_with_sample_can_match(self):
        """遍历所有内置模式，对有 sample 字段的模式进行匹配测试"""
        failed = []

        for p in self.all_patterns:
            name = p["name"]
            sample = p.get("sample")
            if not sample:
                continue

            grok_expr = f"%{{{name}:value}}"
            try:
                grok = Grok(grok_expr)
                result = grok.match(sample)
            except Exception as e:
                failed.append({"name": name, "sample": sample, "error": str(e)})
                continue

            if result is None:
                failed.append({"name": name, "sample": sample, "error": "匹配返回 None"})
            elif "value" not in result:
                failed.append({"name": name, "sample": sample, "error": f"结果中缺少 value 字段: {result}"})

        if failed:
            lines = ["以下内置模式无法匹配其 sample:"]
            for f in failed:
                lines.append(f"  - {f['name']}: sample={f['sample']!r}, error={f['error']}")
            self.fail("\n".join(lines))

    def test_patterns_with_sample_match_exact_value(self):
        """
        对于叶子模式（不含 %{...} 引用），验证匹配结果的 value 字段
        应包含 sample 中的内容（search 模式下可能是子串匹配）
        """
        grok_ref_re = re.compile(r"%{\w+")
        failed = []

        for p in self.all_patterns:
            name = p["name"]
            sample = p.get("sample")
            pattern = p["pattern"]
            if not sample or grok_ref_re.search(pattern):
                continue

            grok_expr = f"%{{{name}:value}}"
            try:
                grok = Grok(grok_expr)
                result = grok.match(sample)
            except Exception:
                continue  # 编译/匹配错误已在其他测试中覆盖

            if result and "value" in result:
                # 匹配到的值应该是 sample 的子串
                self.assertIn(
                    result["value"], sample, f"模式 {name}: 匹配值 {result['value']!r} 不在 sample {sample!r} 中"
                )


class TestGrokCoreMatch(unittest.TestCase):
    """测试 Grok 类的核心匹配功能"""

    def test_simple_pattern_match(self):
        """简单模式匹配"""
        grok = Grok("%{WORD:name}")
        result = grok.match("hello")
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "hello")

    def test_ip_v4_match(self):
        """IPv4 地址匹配"""
        grok = Grok("%{IPV4:ip}")
        result = grok.match("192.168.1.1")
        self.assertIsNotNone(result)
        self.assertEqual(result["ip"], "192.168.1.1")

    def test_ip_v6_match(self):
        """IPv6 地址匹配"""
        grok = Grok("%{IP:ip}")
        result = grok.match("::1")
        self.assertIsNotNone(result)
        self.assertIn("ip", result)

    def test_common_patterns_match_detail(self):
        """测试常用模式的匹配细节，验证提取的值是否正确"""
        test_cases = [
            ("IP", "192.168.1.1", "192.168.1.1"),
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
            ("MONTHNUM", "09", "09"),
            ("YEAR", "2024", "2024"),
        ]

        for pattern_name, sample, expected_value in test_cases:
            with self.subTest(pattern=pattern_name, sample=sample):
                grok = Grok(f"%{{{pattern_name}:value}}")
                result = grok.match(sample)
                self.assertIsNotNone(result, f"模式 {pattern_name} 无法匹配 sample: {sample!r}")
                self.assertEqual(
                    result.get("value"),
                    expected_value,
                    f"模式 {pattern_name} 匹配结果不符: 期望 {expected_value!r}, 实际 {result.get('value')!r}",
                )

    def test_no_match_returns_none(self):
        """不匹配时应返回 None"""
        grok = Grok("%{IP:ip_address}")
        result = grok.match("not_an_ip_address")
        self.assertIsNone(result)

    def test_match_in_longer_text(self):
        """在较长文本中搜索匹配（re.search 行为）"""
        grok = Grok("%{IP:ip}")
        result = grok.match("The server IP is 192.168.1.1 and it is running")
        self.assertIsNotNone(result)
        self.assertEqual(result["ip"], "192.168.1.1")

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
        self.assertIsInstance(result["value"], int)

    def test_no_type_conversion_default_string(self):
        """不指定类型时，值应为字符串"""
        grok = Grok("%{NUMBER:port}")
        result = grok.match("8080")
        self.assertIsNotNone(result)
        self.assertEqual(result["port"], "8080")
        self.assertIsInstance(result["port"], str)

    def test_multiple_type_conversions(self):
        """多字段同时进行类型转换"""
        grok = Grok("%{IP:ip} %{NUMBER:status:int} %{NUMBER:duration:float}")
        result = grok.match("192.168.1.1 200 1.234")
        self.assertIsNotNone(result)
        self.assertEqual(result["ip"], "192.168.1.1")
        self.assertEqual(result["status"], 200)
        self.assertIsInstance(result["status"], int)
        self.assertAlmostEqual(result["duration"], 1.234)
        self.assertIsInstance(result["duration"], float)


class TestGrokCompositePatterns(unittest.TestCase):
    """测试组合模式匹配（多个内置模式组合使用）"""

    def test_composite_ip_method_path_status(self):
        """IP + 方法 + 路径 + 状态码"""
        grok = Grok("%{IP:client} %{WORD:method} %{URIPATHPARAM:request} %{NUMBER:status:int}")
        result = grok.match("192.168.1.1 GET /api/v1/users?page=1 200")
        self.assertIsNotNone(result)
        self.assertEqual(result["client"], "192.168.1.1")
        self.assertEqual(result["method"], "GET")
        self.assertEqual(result["request"], "/api/v1/users?page=1")
        self.assertEqual(result["status"], 200)

    def test_syslog_timestamp_match(self):
        """Syslog 时间戳匹配"""
        grok = Grok("%{SYSLOGTIMESTAMP:timestamp}")
        result = grok.match("Mar 15 14:30:59")
        self.assertIsNotNone(result)
        self.assertIn("timestamp", result)

    def test_timestamp_iso8601_match(self):
        """ISO8601 时间戳匹配"""
        grok = Grok("%{TIMESTAMP_ISO8601:ts}")
        result = grok.match("2024-03-15T14:30:59+08:00")
        self.assertIsNotNone(result)
        self.assertIn("ts", result)

    def test_httpdate_match(self):
        """HTTP 日期格式匹配"""
        grok = Grok("%{HTTPDATE:timestamp}")
        result = grok.match("15/Mar/2024:14:30:59 +0800")
        self.assertIsNotNone(result)
        self.assertIn("timestamp", result)

    def test_common_apache_log(self):
        """Apache Common 日志格式匹配"""
        grok = Grok("%{COMMONAPACHELOG}")
        log_line = '192.168.1.1 - frank [15/Mar/2024:14:30:59 +0800] "GET /api/v1/users HTTP/1.1" 200 1234'
        result = grok.match(log_line)
        self.assertIsNotNone(result, f"COMMONAPACHELOG 无法匹配: {log_line!r}")

    def test_java_stacktrace_part(self):
        """Java 堆栈跟踪行匹配"""
        grok = Grok("%{JAVASTACKTRACEPART}")
        line = "at com.example.service.UserService.getUserById(UserService.java:42)"
        result = grok.match(line)
        self.assertIsNotNone(result, f"JAVASTACKTRACEPART 无法匹配: {line!r}")

    def test_hostport_match(self):
        """主机名:端口匹配"""
        grok = Grok("%{HOSTPORT:hp}")
        result = grok.match("www.example.com:8080")
        self.assertIsNotNone(result)
        self.assertIn("hp", result)

    def test_uri_match(self):
        """完整 URI 匹配"""
        grok = Grok("%{URI:url}")
        result = grok.match("https://www.example.com/api/v1/users?page=1")
        self.assertIsNotNone(result)
        self.assertIn("url", result)

    def test_path_unix_match(self):
        """Unix 路径匹配"""
        grok = Grok("%{UNIXPATH:path}")
        result = grok.match("/var/log/syslog")
        self.assertIsNotNone(result)
        self.assertEqual(result["path"], "/var/log/syslog")

    def test_quotedstring_match(self):
        """带引号字符串匹配"""
        grok = Grok("%{QUOTEDSTRING:qs}")
        result = grok.match('"hello world"')
        self.assertIsNotNone(result)
        self.assertIn("qs", result)

    def test_mac_address_match(self):
        """MAC 地址匹配"""
        grok = Grok("%{MAC:mac}")
        # 通用格式
        result = grok.match("0a:1b:2c:3d:4e:5f")
        self.assertIsNotNone(result)
        self.assertIn("mac", result)


class TestGrokCustomPatterns(unittest.TestCase):
    """测试自定义模式功能"""

    def test_custom_pattern_basic(self):
        """自定义模式基本使用"""
        custom = {"MY_STATUS": r"OK|FAIL|WARN"}
        grok = Grok("%{MY_STATUS:status}", custom_patterns=custom)

        result = grok.match("OK")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "OK")

        result = grok.match("FAIL")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "FAIL")

        result = grok.match("UNKNOWN")
        self.assertIsNone(result)

    def test_custom_pattern_override_builtin(self):
        """自定义模式可以覆盖内置模式"""
        # 覆盖 WORD 模式为只匹配大写字母
        custom = {"WORD": r"[A-Z]+"}
        grok = Grok("%{WORD:w}", custom_patterns=custom)

        result = grok.match("HELLO")
        self.assertIsNotNone(result)
        self.assertEqual(result["w"], "HELLO")

        result = grok.match("hello")
        self.assertIsNone(result)

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
        result = grok.match("")
        self.assertIsNone(result)

    def test_special_characters_in_input(self):
        """输入包含特殊字符"""
        grok = Grok("%{GREEDYDATA:data}")
        result = grok.match("hello [world] (test) {foo} $bar ^baz")
        self.assertIsNotNone(result)

    def test_multiline_input_no_match_by_default(self):
        """默认情况下 . 不匹配换行符，GREEDYDATA 不跨行"""
        grok = Grok("^%{GREEDYDATA:line}$")
        result = grok.match("line1\nline2")
        # re.search 会在 line1 或 line2 上匹配
        # 具体行为取决于 re 引擎，这里只验证不会异常
        # GREEDYDATA 是 .* 不含 DOTALL，所以只匹配单行
        if result:
            self.assertNotIn("\n", result.get("line", ""))

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

    def test_grok_regex_obj_accessible(self):
        """Grok 实例的 regex_obj 属性应可访问且为编译后的正则对象"""
        grok = Grok("%{WORD:w}")
        self.assertIsInstance(grok.regex_obj, re.Pattern)

    def test_grok_pattern_attribute(self):
        """Grok 实例的 pattern 属性应保留原始模式字符串"""
        pattern = "%{IP:ip} %{WORD:method}"
        grok = Grok(pattern)
        self.assertEqual(grok.pattern, pattern)


class TestPerModulePatterns(unittest.TestCase):
    """
    按模块逐一测试每个 patterns 文件中的模式。
    确保每个模块的模式都能通过 Grok 展开并编译，且带 sample 的模式能匹配。
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


class TestGrokDateTimePatterns(unittest.TestCase):
    """专门测试日期时间相关模式的匹配"""

    def test_time_match(self):
        """TIME 模式匹配"""
        grok = Grok("%{TIME:time}")
        for sample in ["14:30:59", "00:00:00", "23:59:59"]:
            with self.subTest(sample=sample):
                result = grok.match(sample)
                self.assertIsNotNone(result, f"TIME 无法匹配: {sample!r}")

    def test_date_us_match(self):
        """DATE_US 模式匹配"""
        grok = Grok("%{DATE_US:date}")
        result = grok.match("03/15/2024")
        self.assertIsNotNone(result)

    def test_date_eu_match(self):
        """DATE_EU 模式匹配"""
        grok = Grok("%{DATE_EU:date}")
        result = grok.match("15.03.2024")
        self.assertIsNotNone(result)

    def test_iso8601_timezone_match(self):
        """ISO8601_TIMEZONE 模式匹配"""
        grok = Grok("%{ISO8601_TIMEZONE:tz}")
        for sample in ["+08:00", "-0500", "Z"]:
            with self.subTest(sample=sample):
                result = grok.match(sample)
                self.assertIsNotNone(result, f"ISO8601_TIMEZONE 无法匹配: {sample!r}")

    def test_datestamp_rfc822_match(self):
        """DATESTAMP_RFC822 模式匹配"""
        grok = Grok("%{DATESTAMP_RFC822:ts}")
        result = grok.match("Mon Jan 15 2024 14:30:59 UTC")
        self.assertIsNotNone(result)

    def test_datestamp_eventlog_match(self):
        """DATESTAMP_EVENTLOG 模式匹配"""
        grok = Grok("%{DATESTAMP_EVENTLOG:ts}")
        result = grok.match("20240315143059")
        self.assertIsNotNone(result)


class TestGrokLogLevelPatterns(unittest.TestCase):
    """测试日志级别模式的各种变体"""

    def test_loglevel_variants(self):
        """LOGLEVEL 应匹配各种大小写和缩写形式"""
        grok = Grok("%{LOGLEVEL:level}")
        levels = [
            "DEBUG",
            "debug",
            "Debug",
            "INFO",
            "info",
            "Info",
            "WARN",
            "warn",
            "Warn",
            "WARNING",
            "warning",
            "Warning",
            "ERROR",
            "error",
            "Error",
            "ERR",
            "err",
            "FATAL",
            "fatal",
            "Fatal",
            "TRACE",
            "trace",
            "Trace",
            "NOTICE",
            "notice",
            "ALERT",
            "alert",
            "CRITICAL",
            "critical",
            "SEVERE",
            "severe",
            "EMERGENCY",
            "emergency",
        ]
        for level in levels:
            with self.subTest(level=level):
                result = grok.match(level)
                self.assertIsNotNone(result, f"LOGLEVEL 无法匹配: {level!r}")


class TestExtractPatternReferences(unittest.TestCase):
    """测试 GrokHandler._extract_pattern_references 静态方法"""

    def test_simple_reference(self):
        """提取简单引用"""
        refs = GrokHandler._extract_pattern_references("%{IP:ip}")
        self.assertEqual(refs, {"IP"})

    def test_multiple_references(self):
        """提取多个引用"""
        refs = GrokHandler._extract_pattern_references("%{IP:ip} %{WORD:method} %{NUMBER:status}")
        self.assertEqual(refs, {"IP", "WORD", "NUMBER"})

    def test_reference_without_field_name(self):
        """提取不带字段名的引用"""
        refs = GrokHandler._extract_pattern_references("%{IP} %{WORD}")
        self.assertEqual(refs, {"IP", "WORD"})

    def test_reference_with_type(self):
        """提取带类型的引用"""
        refs = GrokHandler._extract_pattern_references("%{NUMBER:port:int} %{NUMBER:ratio:float}")
        self.assertEqual(refs, {"NUMBER"})

    def test_no_references(self):
        """无引用时返回空集合"""
        refs = GrokHandler._extract_pattern_references(r"[a-z]+\d+")
        self.assertEqual(refs, set())

    def test_duplicate_references(self):
        """重复引用应去重"""
        refs = GrokHandler._extract_pattern_references("%{IP:src_ip} %{IP:dst_ip}")
        self.assertEqual(refs, {"IP"})

    def test_mixed_format_references(self):
        """混合格式引用"""
        refs = GrokHandler._extract_pattern_references("%{IP:ip} %{WORD} %{NUMBER:port:int}")
        self.assertEqual(refs, {"IP", "WORD", "NUMBER"})


class TestDetectCircularReference(unittest.TestCase):
    """测试 GrokHandler.detect_circular_reference 类方法"""

    def test_no_circular_reference(self):
        """无循环引用"""
        patterns_map = {
            "A": "%{B} %{C}",
            "B": r"\d+",
            "C": r"[a-z]+",
        }
        has_cycle, cycle_path = GrokHandler.detect_circular_reference("A", patterns_map)
        self.assertFalse(has_cycle)
        self.assertEqual(cycle_path, [])

    def test_direct_circular_reference(self):
        """直接循环引用 A -> A"""
        patterns_map = {
            "A": "%{A}",
        }
        has_cycle, cycle_path = GrokHandler.detect_circular_reference("A", patterns_map)
        self.assertTrue(has_cycle)
        self.assertIn("A", cycle_path)

    def test_indirect_circular_reference(self):
        """间接循环引用 A -> B -> C -> A"""
        patterns_map = {
            "A": "%{B}",
            "B": "%{C}",
            "C": "%{A}",
        }
        has_cycle, cycle_path = GrokHandler.detect_circular_reference("A", patterns_map)
        self.assertTrue(has_cycle)
        # 循环路径应包含 A, B, C
        self.assertIn("A", cycle_path)

    def test_reference_to_nonexistent_pattern(self):
        """引用不存在的模式（内置模式）不应报循环"""
        patterns_map = {
            "A": "%{IP} %{B}",
            "B": r"\d+",
        }
        has_cycle, cycle_path = GrokHandler.detect_circular_reference("A", patterns_map)
        self.assertFalse(has_cycle)

    def test_diamond_dependency_no_cycle(self):
        """菱形依赖不应误报为循环"""
        patterns_map = {
            "A": "%{B} %{C}",
            "B": "%{D}",
            "C": "%{D}",
            "D": r"\d+",
        }
        has_cycle, cycle_path = GrokHandler.detect_circular_reference("A", patterns_map)
        self.assertFalse(has_cycle)

    def test_long_chain_no_cycle(self):
        """长链依赖无循环"""
        patterns_map = {
            "A": "%{B}",
            "B": "%{C}",
            "C": "%{D}",
            "D": "%{E}",
            "E": r"\d+",
        }
        has_cycle, cycle_path = GrokHandler.detect_circular_reference("A", patterns_map)
        self.assertFalse(has_cycle)

    def test_long_chain_with_cycle(self):
        """长链依赖有循环"""
        patterns_map = {
            "A": "%{B}",
            "B": "%{C}",
            "C": "%{D}",
            "D": "%{E}",
            "E": "%{B}",  # 回到 B
        }
        has_cycle, cycle_path = GrokHandler.detect_circular_reference("A", patterns_map)
        self.assertTrue(has_cycle)

    def test_empty_patterns_map(self):
        """空模式字典"""
        has_cycle, cycle_path = GrokHandler.detect_circular_reference("A", {})
        self.assertFalse(has_cycle)
        self.assertEqual(cycle_path, [])

    def test_pattern_with_no_references(self):
        """模式不包含引用"""
        patterns_map = {
            "A": r"\d+",
        }
        has_cycle, cycle_path = GrokHandler.detect_circular_reference("A", patterns_map)
        self.assertFalse(has_cycle)


class TestGrokHandlerWithMockDB(unittest.TestCase):
    """
    测试 GrokHandler 中需要数据库交互的方法。
    使用 unittest.mock 模拟 GrokInfo 模型的数据库操作。
    """

    def setUp(self):
        self.handler = GrokHandler(bk_biz_id=100)

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_get_custom_patterns_map(self, mock_grok_info):
        """获取自定义模式字典"""
        mock_grok_info.objects.filter.return_value.values.return_value = [
            {"name": "MY_PATTERN", "pattern": r"\d+"},
            {"name": "MY_STATUS", "pattern": r"OK|FAIL"},
        ]
        result = self.handler.get_custom_patterns_map()
        self.assertEqual(result, {"MY_PATTERN": r"\d+", "MY_STATUS": r"OK|FAIL"})
        mock_grok_info.objects.filter.assert_called_once_with(bk_biz_id=100)

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_get_all_pattern_names(self, mock_grok_info):
        """获取所有模式名称"""
        mock_grok_info.objects.filter.return_value.values_list.return_value = ["IP", "WORD", "MY_PATTERN"]
        result = self.handler.get_all_pattern_names()
        self.assertEqual(result, ["IP", "WORD", "MY_PATTERN"])

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_validate_references_exist_success(self, mock_grok_info):
        """验证引用存在 - 成功"""
        mock_grok_info.objects.filter.return_value.values_list.return_value = ["IP", "WORD", "NUMBER"]
        # 不应抛出异常
        self.handler.validate_references_exist("%{IP:ip} %{WORD:method}")

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_validate_references_exist_failure(self, mock_grok_info):
        """验证引用存在 - 失败（引用不存在的模式）"""
        mock_grok_info.objects.filter.return_value.values_list.return_value = ["IP", "WORD"]
        with self.assertRaises(GrokPatternNotFoundException):
            self.handler.validate_references_exist("%{IP:ip} %{NONEXISTENT:value}")

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_validate_circular_reference_no_cycle(self, mock_grok_info):
        """验证循环引用 - 无循环"""
        mock_grok_info.objects.filter.return_value.values.return_value = [
            {"name": "MY_A", "pattern": r"\d+"},
        ]
        # 不应抛出异常
        self.handler.validate_circular_reference("MY_B", "%{MY_A}")

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_validate_circular_reference_with_cycle(self, mock_grok_info):
        """验证循环引用 - 有循环"""
        mock_grok_info.objects.filter.return_value.values.return_value = [
            {"name": "MY_A", "pattern": "%{MY_B}"},
        ]
        with self.assertRaises(GrokCircularReferenceException):
            self.handler.validate_circular_reference("MY_B", "%{MY_A}")

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_create_grok_info_success(self, mock_grok_info):
        """创建 Grok 模式 - 成功"""
        # mock validate_references_exist
        mock_grok_info.objects.filter.return_value.values_list.return_value = ["IP", "WORD"]
        # mock validate_circular_reference
        mock_grok_info.objects.filter.return_value.values.return_value = []
        # mock create
        mock_created = MagicMock()
        mock_created.id = 42
        mock_grok_info.objects.create.return_value = mock_created

        result = self.handler.create_grok_info(
            {
                "name": "MY_LOG",
                "pattern": "%{IP:ip} %{WORD:method}",
                "sample": "192.168.1.1 GET",
                "description": "自定义日志模式",
            }
        )
        self.assertEqual(result, {"id": 42})

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_create_grok_info_duplicate(self, mock_grok_info):
        """创建 Grok 模式 - 名称重复"""
        mock_grok_info.objects.filter.return_value.values_list.return_value = ["IP"]
        mock_grok_info.objects.filter.return_value.values.return_value = []
        mock_grok_info.objects.create.side_effect = IntegrityError("duplicate")

        with self.assertRaises(DuplicateGrokPatternException):
            self.handler.create_grok_info(
                {
                    "name": "IP",
                    "pattern": r"\d+\.\d+\.\d+\.\d+",
                }
            )

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_update_grok_info(self, mock_grok_info):
        """更新 Grok 模式"""
        # mock validate_references_exist
        mock_grok_info.objects.filter.return_value.values_list.return_value = ["IP", "WORD"]
        # mock get grok_info
        mock_grok_obj = MagicMock()
        mock_grok_obj.name = "MY_LOG"
        mock_grok_info.objects.filter.return_value.first.return_value = mock_grok_obj
        # mock validate_circular_reference
        mock_grok_info.objects.filter.return_value.values.return_value = []

        self.handler.update_grok_info(
            {
                "id": 1,
                "pattern": "%{IP:ip}",
                "sample": "192.168.1.1",
                "description": "更新后的描述",
            }
        )
        mock_grok_obj.save.assert_called_once()

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_delete_grok_info_success(self, mock_grok_info):
        """删除 Grok 模式 - 成功（无引用）"""
        mock_grok_obj = MagicMock()
        mock_grok_obj.is_builtin = False
        mock_grok_obj.name = "MY_LOG"
        mock_grok_obj.bk_biz_id = 100
        mock_grok_info.objects.filter.return_value.first.return_value = mock_grok_obj
        # 无其他模式引用
        mock_grok_info.objects.filter.return_value.all.return_value = []

        GrokHandler.delete_grok_info(1)
        mock_grok_obj.delete.assert_called_once()

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_delete_grok_info_builtin_noop(self, mock_grok_info):
        """删除内置 Grok 模式 - 不执行删除"""
        mock_grok_obj = MagicMock()
        mock_grok_obj.is_builtin = True
        mock_grok_info.objects.filter.return_value.first.return_value = mock_grok_obj

        GrokHandler.delete_grok_info(1)
        mock_grok_obj.delete.assert_not_called()

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_delete_grok_info_referenced(self, mock_grok_info):
        """删除被引用的 Grok 模式 - 抛出异常"""
        mock_grok_obj = MagicMock()
        mock_grok_obj.is_builtin = False
        mock_grok_obj.name = "MY_BASE"
        mock_grok_obj.bk_biz_id = 100
        mock_grok_info.objects.filter.return_value.first.return_value = mock_grok_obj

        # 有其他模式引用了 MY_BASE
        referencing_grok = MagicMock()
        referencing_grok.name = "MY_LOG"
        referencing_grok.pattern = "%{MY_BASE:base} %{WORD:extra}"
        mock_grok_info.objects.filter.return_value.all.return_value = [referencing_grok]

        with self.assertRaises(GrokReferencedException):
            GrokHandler.delete_grok_info(1)

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_delete_grok_info_not_found(self, mock_grok_info):
        """删除不存在的 Grok 模式 - 静默返回"""
        mock_grok_info.objects.filter.return_value.first.return_value = None
        # 不应抛出异常
        GrokHandler.delete_grok_info(999)

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_get_updated_by_list(self, mock_grok_info):
        """获取更新人列表"""
        mock_grok_info.objects.filter.return_value.values_list.return_value.distinct.return_value = [
            "admin",
            "user1",
            "user2",
        ]
        result = GrokHandler.get_updated_by_list(100)
        self.assertEqual(result, ["admin", "user1", "user2"])

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_list_grok_info_basic(self, mock_grok_info):
        """列表查询 - 基本查询"""
        mock_qs = MagicMock()
        mock_qs.count.return_value = 2
        mock_grok_info.objects.filter.return_value.order_by.return_value.values.return_value = mock_qs

        result = GrokHandler.list_grok_info({"bk_biz_id": 100})
        self.assertEqual(result["total"], 2)

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_list_grok_info_with_keyword(self, mock_grok_info):
        """列表查询 - 带关键字过滤"""
        mock_qs = MagicMock()
        mock_qs.count.return_value = 1
        mock_grok_info.objects.filter.return_value.order_by.return_value.values.return_value = mock_qs

        result = GrokHandler.list_grok_info({"bk_biz_id": 100, "keyword": "IP"})
        self.assertEqual(result["total"], 1)


class TestGrokHandlerDebug(unittest.TestCase):
    """测试 GrokHandler.debug 方法"""

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_debug_with_builtin_pattern(self, mock_grok_info):
        """调试内置模式"""
        # mock validate_references_exist
        mock_grok_info.objects.filter.return_value.values_list.return_value = ["IP", "WORD"]
        # mock get_custom_patterns_map
        mock_grok_info.objects.filter.return_value.values.return_value = []

        handler = GrokHandler(bk_biz_id=100)
        result = handler.debug(
            {
                "pattern": "%{IP:ip} %{WORD:method}",
                "sample": "192.168.1.1 GET /api/v1/users",
            }
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["ip"], "192.168.1.1")
        self.assertEqual(result["method"], "GET")

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_debug_with_custom_pattern(self, mock_grok_info):
        """调试自定义模式"""
        mock_grok_info.objects.filter.return_value.values_list.return_value = ["IP", "MY_STATUS"]
        mock_grok_info.objects.filter.return_value.values.return_value = [
            {"name": "MY_STATUS", "pattern": r"OK|FAIL|WARN"},
        ]

        handler = GrokHandler(bk_biz_id=100)
        result = handler.debug(
            {
                "pattern": "%{IP:ip} %{MY_STATUS:status}",
                "sample": "192.168.1.1 OK",
            }
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["ip"], "192.168.1.1")
        self.assertEqual(result["status"], "OK")

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_debug_no_match(self, mock_grok_info):
        """调试 - 不匹配"""
        mock_grok_info.objects.filter.return_value.values_list.return_value = ["IP"]
        mock_grok_info.objects.filter.return_value.values.return_value = []

        handler = GrokHandler(bk_biz_id=100)
        result = handler.debug(
            {
                "pattern": "%{IP:ip}",
                "sample": "not_an_ip",
            }
        )
        self.assertIsNone(result)

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_debug_returns_matched_field(self, mock_grok_info):
        """调试结果应包含 _matched 字段（整个表达式匹配到的原文片段）"""
        mock_grok_info.objects.filter.return_value.values_list.return_value = ["IP", "WORD"]
        mock_grok_info.objects.filter.return_value.values.return_value = []

        handler = GrokHandler(bk_biz_id=100)
        result = handler.debug(
            {
                "pattern": "%{IP:ip} %{WORD:method}",
                "sample": "prefix 192.168.1.1 GET suffix",
            }
        )
        self.assertIsNotNone(result)
        self.assertIn("_matched", result)
        self.assertEqual(result["_matched"], "192.168.1.1 GET")


class TestGrokHandlerGrokToRegex(unittest.TestCase):
    """测试 GrokHandler.grok_to_regex 方法"""

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_grok_to_regex_basic(self, mock_grok_info):
        """基本 Grok 转正则"""
        mock_grok_info.objects.filter.return_value.values_list.return_value = ["IP", "WORD"]
        mock_grok_info.objects.filter.return_value.values.return_value = []

        handler = GrokHandler(bk_biz_id=100)
        regex = handler.grok_to_regex("%{IP:ip} %{WORD:method}")
        self.assertIsInstance(regex, str)
        # 结果应该是合法的正则表达式
        compiled = re.compile(regex)
        match = compiled.search("192.168.1.1 GET")
        self.assertIsNotNone(match)
        self.assertEqual(match.group("ip"), "192.168.1.1")
        self.assertEqual(match.group("method"), "GET")

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_grok_to_regex_with_custom_pattern(self, mock_grok_info):
        """带自定义模式的 Grok 转正则"""
        mock_grok_info.objects.filter.return_value.values_list.return_value = ["IP", "MY_STATUS"]
        mock_grok_info.objects.filter.return_value.values.return_value = [
            {"name": "MY_STATUS", "pattern": r"OK|FAIL"},
        ]

        handler = GrokHandler(bk_biz_id=100)
        regex = handler.grok_to_regex("%{IP:ip} %{MY_STATUS:status}")
        compiled = re.compile(regex)
        match = compiled.search("192.168.1.1 OK")
        self.assertIsNotNone(match)
        self.assertEqual(match.group("status"), "OK")

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_grok_to_regex_no_grok_references(self, mock_grok_info):
        """纯正则表达式（无 Grok 引用）"""
        mock_grok_info.objects.filter.return_value.values_list.return_value = []
        mock_grok_info.objects.filter.return_value.values.return_value = []

        handler = GrokHandler(bk_biz_id=100)
        regex = handler.grok_to_regex(r"(?P<num>\d+)")
        self.assertEqual(regex, r"(?P<num>\d+)")


class TestGrokHandlerReplaceCustomPatterns(unittest.TestCase):
    """测试 GrokHandler.replace_custom_patterns 方法"""

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_replace_custom_patterns_basic(self, mock_grok_info):
        """替换自定义模式，保留内置模式"""
        mock_grok_info.objects.filter.return_value.values_list.return_value = ["IP", "MY_STATUS"]
        mock_grok_info.objects.filter.return_value.values.return_value = [
            {"name": "MY_STATUS", "pattern": r"OK|FAIL"},
        ]

        handler = GrokHandler(bk_biz_id=100)
        result = handler.replace_custom_patterns("%{IP:ip} %{MY_STATUS:status}")
        # IP 是内置模式，应保留原样
        self.assertIn("%{IP:ip}", result)
        # MY_STATUS 是自定义模式，应被替换为正则
        self.assertNotIn("%{MY_STATUS", result)
        self.assertIn("OK|FAIL", result)

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_replace_custom_patterns_no_custom(self, mock_grok_info):
        """无自定义模式时，表达式不变"""
        mock_grok_info.objects.filter.return_value.values_list.return_value = ["IP", "WORD"]
        mock_grok_info.objects.filter.return_value.values.return_value = []

        handler = GrokHandler(bk_biz_id=100)
        pattern = "%{IP:ip} %{WORD:method}"
        result = handler.replace_custom_patterns(pattern)
        self.assertEqual(result, pattern)

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_replace_custom_patterns_nested(self, mock_grok_info):
        """嵌套自定义模式应被递归替换"""
        mock_grok_info.objects.filter.return_value.values_list.return_value = ["IP", "MY_OUTER", "MY_INNER"]
        mock_grok_info.objects.filter.return_value.values.return_value = [
            {"name": "MY_INNER", "pattern": r"\d{3}"},
            {"name": "MY_OUTER", "pattern": r"CODE-%{MY_INNER}"},
        ]

        handler = GrokHandler(bk_biz_id=100)
        result = handler.replace_custom_patterns("%{MY_OUTER:code}")
        # MY_OUTER 和 MY_INNER 都应被替换
        self.assertNotIn("%{MY_OUTER", result)
        self.assertNotIn("%{MY_INNER", result)
        self.assertIn(r"\d{3}", result)

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_replace_custom_patterns_without_field_name(self, mock_grok_info):
        """替换不带字段名的自定义模式"""
        mock_grok_info.objects.filter.return_value.values_list.return_value = ["IP", "MY_SEP"]
        mock_grok_info.objects.filter.return_value.values.return_value = [
            {"name": "MY_SEP", "pattern": r"\s*-\s*"},
        ]

        handler = GrokHandler(bk_biz_id=100)
        result = handler.replace_custom_patterns("%{IP:ip}%{MY_SEP}%{IP:ip2}")
        # MY_SEP 应被替换
        self.assertNotIn("%{MY_SEP}", result)
        # IP 应保留
        self.assertIn("%{IP:ip}", result)

    @patch("apps.log_databus.handlers.grok.handler.GrokInfo")
    def test_replace_custom_patterns_with_type(self, mock_grok_info):
        """替换带类型的自定义模式"""
        mock_grok_info.objects.filter.return_value.values_list.return_value = ["MY_NUM"]
        mock_grok_info.objects.filter.return_value.values.return_value = [
            {"name": "MY_NUM", "pattern": r"\d+"},
        ]

        handler = GrokHandler(bk_biz_id=100)
        result = handler.replace_custom_patterns("%{MY_NUM:port:int}")
        # MY_NUM 应被替换，字段名保留
        self.assertNotIn("%{MY_NUM", result)
        self.assertIn("port", result)


if __name__ == "__main__":
    unittest.main()
