# -*- coding: utf-8 -*-
"""
V4 清洗规则单元测试

测试策略：快照全量比对。每个场景调用 build_log_v4_data_link，
将返回结果与 test_v4_clean_snapshots.py 中的 EXPECTED_* 常量做 assertEqual。

更新快照流程：
1. 修改清洗逻辑后运行 TestV4CleanSnapshotPrint.test_print_all_snapshots
2. 将输出（JSON→Python 语法转换后）替换 test_v4_clean_snapshots.py
3. 人工核对后运行全部测试确认通过
"""
from unittest import TestCase

from apps.log_databus.handlers.etl_storage.bk_log_text import BkLogTextEtlStorage
from apps.log_databus.handlers.etl_storage.bk_log_json import BkLogJsonEtlStorage
from apps.log_databus.handlers.etl_storage.bk_log_delimiter import BkLogDelimiterEtlStorage
from apps.log_databus.handlers.etl_storage.bk_log_regexp import BkLogRegexpEtlStorage

from apps.tests.log_databus.test_v4_clean_snapshots import (
    EXPECTED_TEXT_BASIC,
    EXPECTED_JSON_RETAIN_ORIGINAL,
    EXPECTED_JSON_ALIAS_DELETE_TIME,
    EXPECTED_JSON_EXTRA_AND_FAILURE,
    EXPECTED_DELIMITER_BASIC,
    EXPECTED_DELIMITER_DELETE_SKIP,
    EXPECTED_REGEXP_BASIC,
    EXPECTED_JSON_PATH_SEPARATOR,
    EXPECTED_JSON_ISO8601_TIME,
    EXPECTED_JSON_NON_JSON_RETAIN,
    EXPECTED_DELIMITER_TIME_FIELD,
    EXPECTED_JSON_EPOCH_MILLIS,
)
from apps.tests.log_databus.v4_clean.helpers import assert_v4_result_equal
from apps.tests.log_databus.v4_clean.testdata.built_in_configs import get_fresh_config


# ============================================================
# 场景 1：直接入库（text）— 基础
# ============================================================
class TestV4CleanText(TestCase):
    """直接入库（bk_log_text）V4 清洗规则测试"""

    def setUp(self):
        self.storage = BkLogTextEtlStorage()

    def test_basic_text(self):
        """场景1：直接入库 — 基础场景"""
        result = self.storage.build_log_v4_data_link([], {}, get_fresh_config())
        assert_v4_result_equal(self, result, EXPECTED_TEXT_BASIC, "场景1-直接入库")


# ============================================================
# 场景 2~4, 8：JSON 清洗
# ============================================================
class TestV4CleanJson(TestCase):
    """JSON 清洗（bk_log_json）V4 清洗规则测试"""

    def setUp(self):
        self.storage = BkLogJsonEtlStorage()

    def test_json_basic_with_retain_original_text(self):
        """场景2：JSON 清洗 — 多字段 + 保留原文"""
        etl_params = {"retain_original_text": True, "retain_extra_json": False}
        fields = [
            {"field_name": "user", "alias_name": "", "field_type": "string",
             "description": "用户名", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
            {"field_name": "status_code", "alias_name": "", "field_type": "int",
             "description": "状态码", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
            {"field_name": "message", "alias_name": "", "field_type": "string",
             "description": "日志内容", "is_analyzed": True, "is_dimension": False,
             "is_time": False, "is_delete": False, "option": {}},
        ]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        assert_v4_result_equal(self, result, EXPECTED_JSON_RETAIN_ORIGINAL, "场景2-JSON多字段+保留原文")

    def test_json_alias_and_delete_and_time_field(self):
        """场景3：JSON 清洗 — 别名 + 删除字段 + 用户时间字段"""
        etl_params = {"retain_original_text": False}
        fields = [
            {"field_name": "src_ip", "alias_name": "client_ip", "field_type": "string",
             "description": "来源IP", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
            {"field_name": "log_time", "alias_name": "", "field_type": "string",
             "description": "日志时间", "is_analyzed": False, "is_dimension": True,
             "is_time": True, "is_delete": False,
             "option": {"time_zone": 8, "time_format": "yyyy-MM-dd HH:mm:ss"}},
            {"field_name": "debug_info", "alias_name": "", "field_type": "string",
             "description": "调试信息", "is_analyzed": False, "is_dimension": False,
             "is_time": False, "is_delete": True, "option": {}},
        ]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        assert_v4_result_equal(self, result, EXPECTED_JSON_ALIAS_DELETE_TIME, "场景3-JSON别名+删除+时间")

    def test_json_retain_extra_json_and_enable_retain_content(self):
        """场景4：JSON 清洗 — retain_extra_json + enable_retain_content（保留清洗失败日志）"""
        etl_params = {"retain_original_text": True, "retain_extra_json": True, "enable_retain_content": True}
        fields = [
            {"field_name": "level", "alias_name": "", "field_type": "string",
             "description": "日志级别", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
        ]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        assert_v4_result_equal(self, result, EXPECTED_JSON_EXTRA_AND_FAILURE, "场景4-JSON-ext_json+解析失败")

    def test_json_with_path_separator_configs(self):
        """场景8：JSON 清洗 — 含 path 正则提取"""
        etl_params = {"retain_original_text": False}
        fields = [
            {"field_name": "level", "alias_name": "", "field_type": "string",
             "is_analyzed": False, "is_dimension": True, "is_time": False,
             "is_delete": False, "option": {}},
        ]
        built_in_config = get_fresh_config()
        built_in_config["option"]["separator_configs"] = [
            {"separator_regexp": r"/data/logs/(?P<app_name>[^/]+)/(?P<log_type>[^/]+)\.log"}
        ]
        result = self.storage.build_log_v4_data_link(fields, etl_params, built_in_config)
        assert_v4_result_equal(self, result, EXPECTED_JSON_PATH_SEPARATOR, "场景8-JSON-path正则")


# ============================================================
# 场景 5~6：分隔符清洗
# ============================================================
class TestV4CleanDelimiter(TestCase):
    """分隔符清洗（bk_log_delimiter）V4 清洗规则测试"""

    def setUp(self):
        self.storage = BkLogDelimiterEtlStorage()

    def test_delimiter_basic(self):
        """场景5：分隔符清洗 — 基础"""
        etl_params = {"separator": "|", "retain_original_text": True}
        fields = [
            {"field_name": "ip", "alias_name": "", "field_type": "string", "field_index": 1,
             "description": "IP地址", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
            {"field_name": "method", "alias_name": "", "field_type": "string", "field_index": 2,
             "description": "请求方法", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
            {"field_name": "cost", "alias_name": "", "field_type": "double", "field_index": 3,
             "description": "耗时", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
        ]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        assert_v4_result_equal(self, result, EXPECTED_DELIMITER_BASIC, "场景5-分隔符基础")

    def test_delimiter_with_delete_and_skip_index(self):
        """场景6：分隔符清洗 — 含删除字段 + 跳过索引"""
        etl_params = {"separator": ",", "retain_original_text": False}
        fields = [
            {"field_name": "name", "alias_name": "", "field_type": "string", "field_index": 1,
             "is_analyzed": False, "is_dimension": True, "is_time": False, "is_delete": False, "option": {}},
            {"field_name": "unused", "alias_name": "", "field_type": "string", "field_index": 3,
             "is_analyzed": False, "is_dimension": False, "is_time": False, "is_delete": True, "option": {}},
            {"field_name": "value", "alias_name": "", "field_type": "int", "field_index": 5,
             "is_analyzed": False, "is_dimension": True, "is_time": False, "is_delete": False, "option": {}},
        ]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        assert_v4_result_equal(self, result, EXPECTED_DELIMITER_DELETE_SKIP, "场景6-分隔符删除+跳索引")


# ============================================================
# 场景 7：正则清洗
# ============================================================
class TestV4CleanRegexp(TestCase):
    """正则清洗（bk_log_regexp）V4 清洗规则测试"""

    def setUp(self):
        self.storage = BkLogRegexpEtlStorage()

    def test_regexp_basic(self):
        r"""场景7：正则清洗 — 基础"""
        etl_params = {
            "separator_regexp": r"(?P<request_ip>[\d\.]+)\s+-\s+-\s+\[(?P<request_time>[^\]]+)\]\s+\"(?P<method>\w+)",
            "retain_original_text": True,
        }
        fields = [
            {"field_name": "request_ip", "alias_name": "", "field_type": "string",
             "description": "请求IP", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
            {"field_name": "request_time", "alias_name": "", "field_type": "string",
             "description": "请求时间", "is_analyzed": False, "is_dimension": True,
             "is_time": True, "is_delete": False,
             "option": {"time_zone": 8, "time_format": "dd/MMM/yyyy:HH:mm:ss Z"}},
            {"field_name": "method", "alias_name": "", "field_type": "string",
             "description": "HTTP方法", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
        ]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        assert_v4_result_equal(self, result, EXPECTED_REGEXP_BASIC, "场景7-正则基础")


# ============================================================
# 场景 9, 10, 12：新增 JSON 清洗场景
# ============================================================
class TestV4CleanJsonNew(TestCase):
    """新增 JSON 清洗场景测试"""

    def setUp(self):
        self.storage = BkLogJsonEtlStorage()

    def test_json_iso8601_time_field(self):
        """场景9：JSON + 自定义时间格式 (ISO8601 带时区 yyyy-MM-ddTHH:mm:ss.SSSZ)"""
        etl_params = {"retain_original_text": False}
        fields = [
            {"field_name": "timestamp", "alias_name": "", "field_type": "string",
             "description": "ISO8601时间戳", "is_analyzed": False, "is_dimension": True,
             "is_time": True, "is_delete": False,
             "option": {"time_zone": 8, "time_format": "yyyy-MM-ddTHH:mm:ss.SSSZ"}},
            {"field_name": "action", "alias_name": "", "field_type": "string",
             "description": "操作", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
        ]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        assert_v4_result_equal(self, result, EXPECTED_JSON_ISO8601_TIME, "场景9-JSON-ISO8601时间")

    def test_json_non_json_retain_content(self):
        """场景10：JSON + enable_retain_content + 非 JSON 日志"""
        etl_params = {"retain_original_text": True, "enable_retain_content": True}
        fields = [
            {"field_name": "level", "alias_name": "", "field_type": "string",
             "description": "日志级别", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
        ]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        assert_v4_result_equal(self, result, EXPECTED_JSON_NON_JSON_RETAIN, "场景10-非JSON保留原文")

    def test_json_epoch_millis_time_field(self):
        """场景12：JSON + epoch_millis 时间格式"""
        etl_params = {"retain_original_text": False}
        fields = [
            {"field_name": "ts", "alias_name": "", "field_type": "long",
             "description": "毫秒时间戳", "is_analyzed": False, "is_dimension": True,
             "is_time": True, "is_delete": False,
             "option": {"time_zone": 0, "time_format": "epoch_millis"}},
            {"field_name": "event", "alias_name": "", "field_type": "string",
             "description": "事件", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
        ]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        assert_v4_result_equal(self, result, EXPECTED_JSON_EPOCH_MILLIS, "场景12-JSON-epoch_millis")


# ============================================================
# 场景 11：新增分隔符清洗场景
# ============================================================
class TestV4CleanDelimiterNew(TestCase):
    """新增分隔符清洗场景测试"""

    def setUp(self):
        self.storage = BkLogDelimiterEtlStorage()

    def test_delimiter_with_time_field(self):
        """场景11：分隔符 + 自定义时间字段"""
        etl_params = {"separator": "|", "retain_original_text": True}
        fields = [
            {"field_name": "host", "alias_name": "", "field_type": "string", "field_index": 1,
             "description": "主机名", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
            {"field_name": "log_time", "alias_name": "", "field_type": "string", "field_index": 2,
             "description": "日志时间", "is_analyzed": False, "is_dimension": True,
             "is_time": True, "is_delete": False,
             "option": {"time_zone": 8, "time_format": "yyyy-MM-dd HH:mm:ss"}},
            {"field_name": "level", "alias_name": "", "field_type": "string", "field_index": 3,
             "description": "日志级别", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
            {"field_name": "msg", "alias_name": "", "field_type": "string", "field_index": 4,
             "description": "消息", "is_analyzed": True, "is_dimension": False,
             "is_time": False, "is_delete": False, "option": {}},
        ]
        result = self.storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        assert_v4_result_equal(self, result, EXPECTED_DELIMITER_TIME_FIELD, "场景11-分隔符+时间字段")
