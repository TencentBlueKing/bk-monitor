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
import copy
import difflib
import json
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


# ============================================================
# 公共 built_in_config
# ============================================================
BUILT_IN_CONFIG = {
    "option": {
        "es_unique_field_list": [
            "cloudId", "serverIp", "path", "gseIndex",
            "iterationIndex", "bk_host_id", "dtEventTimeStamp"
        ],
        "separator_node_source": "",
        "separator_node_action": "",
        "separator_node_name": "",
    },
    "fields": [
        {"field_name": "bk_host_id", "field_type": "float", "tag": "dimension",
         "alias_name": "bk_host_id", "description": "主机ID",
         "option": {"es_type": "integer"}},
        {"field_name": "__ext", "field_type": "object", "tag": "dimension",
         "alias_name": "ext", "description": "额外信息字段",
         "option": {"es_type": "object"}},
        {"field_name": "cloudId", "field_type": "float", "tag": "dimension",
         "alias_name": "cloudid", "description": "云区域ID",
         "option": {"es_type": "integer"}},
        {"field_name": "serverIp", "field_type": "string", "tag": "dimension",
         "alias_name": "ip", "description": "ip",
         "option": {"es_type": "keyword"}},
        {"field_name": "path", "field_type": "string", "tag": "dimension",
         "alias_name": "filename", "description": "日志路径",
         "option": {"es_type": "keyword"}},
        {"field_name": "gseIndex", "field_type": "float", "tag": "dimension",
         "alias_name": "gseindex", "description": "gse索引",
         "option": {"es_type": "long"}},
        {"field_name": "iterationIndex", "field_type": "float", "tag": "dimension",
         "alias_name": "iterationindex", "description": "迭代ID",
         "option": {"es_type": "integer"}, "flat_field": True},
    ],
    "time_field": {
        "field_name": "dtEventTimeStamp",
        "field_type": "timestamp",
        "alias_name": "utctime",
        "description": "数据时间",
        "tag": "timestamp",
        "option": {
            "time_zone": 8,
            "time_format": "yyyy-MM-dd HH:mm:ss",
            "es_type": "date",
            "es_format": "epoch_millis",
        },
    },
}


def _get_fresh_built_in_config():
    """每次测试都获取独立副本，避免测试间互相影响"""
    return copy.deepcopy(BUILT_IN_CONFIG)


def _rules_diff(actual, expected):
    """生成人类可读的规则差异"""
    actual_str = json.dumps(actual, indent=2, ensure_ascii=False, sort_keys=True)
    expected_str = json.dumps(expected, indent=2, ensure_ascii=False, sort_keys=True)
    diff = difflib.unified_diff(
        expected_str.splitlines(),
        actual_str.splitlines(),
        fromfile="expected",
        tofile="actual",
        lineterm="",
    )
    return "\n".join(diff)


def _assert_v4_result_equal(test_case, actual, expected, scenario_name=""):
    """全量比对 V4 清洗结果，失败时逐条定位差异"""
    actual_rules = actual["clean_rules"]
    expected_rules = expected["clean_rules"]

    # 先比规则数量
    test_case.assertEqual(
        len(actual_rules), len(expected_rules),
        f"[{scenario_name}] 规则数量不匹配: actual={len(actual_rules)}, expected={len(expected_rules)}\n"
        f"{_rules_diff(actual_rules, expected_rules)}"
    )

    # 逐条比对，精确定位差异
    for i, (a, e) in enumerate(zip(actual_rules, expected_rules)):
        test_case.assertEqual(
            a, e,
            f"[{scenario_name}] Rule[{i}] 不匹配:\n"
            f"  actual:   {json.dumps(a, ensure_ascii=False)}\n"
            f"  expected: {json.dumps(e, ensure_ascii=False)}"
        )

    # 比对 es_storage_config 和 doris_storage_config
    test_case.assertEqual(actual.get("es_storage_config"), expected.get("es_storage_config"),
                          f"[{scenario_name}] es_storage_config 不匹配")
    test_case.assertEqual(actual.get("doris_storage_config"), expected.get("doris_storage_config"),
                          f"[{scenario_name}] doris_storage_config 不匹配")


# ============================================================
# 场景 1：直接入库（text）— 基础
# ============================================================
class TestV4CleanText(TestCase):
    """直接入库（bk_log_text）V4 清洗规则测试"""

    def setUp(self):
        self.storage = BkLogTextEtlStorage()

    def test_basic_text(self):
        """场景1：直接入库 — 基础场景"""
        result = self.storage.build_log_v4_data_link([], {}, _get_fresh_built_in_config())
        _assert_v4_result_equal(self, result, EXPECTED_TEXT_BASIC, "场景1-直接入库")


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
        result = self.storage.build_log_v4_data_link(fields, etl_params, _get_fresh_built_in_config())
        _assert_v4_result_equal(self, result, EXPECTED_JSON_RETAIN_ORIGINAL, "场景2-JSON多字段+保留原文")

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
        result = self.storage.build_log_v4_data_link(fields, etl_params, _get_fresh_built_in_config())
        _assert_v4_result_equal(self, result, EXPECTED_JSON_ALIAS_DELETE_TIME, "场景3-JSON别名+删除+时间")

    def test_json_retain_extra_json_and_enable_retain_content(self):
        """场景4：JSON 清洗 — retain_extra_json + enable_retain_content（保留清洗失败日志）"""
        etl_params = {"retain_original_text": True, "retain_extra_json": True, "enable_retain_content": True}
        fields = [
            {"field_name": "level", "alias_name": "", "field_type": "string",
             "description": "日志级别", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
        ]
        result = self.storage.build_log_v4_data_link(fields, etl_params, _get_fresh_built_in_config())
        _assert_v4_result_equal(self, result, EXPECTED_JSON_EXTRA_AND_FAILURE, "场景4-JSON-ext_json+解析失败")

    def test_json_with_path_separator_configs(self):
        """场景8：JSON 清洗 — 含 path 正则提取（从 etl_params 传入，模拟真实调用链）"""
        etl_params = {
            "retain_original_text": False,
            "path_regexp": r"/data/logs/(?P<app_name>[^/]+)/(?P<log_type>[^/]+)\.log",
        }
        fields = [
            {"field_name": "level", "alias_name": "", "field_type": "string",
             "is_analyzed": False, "is_dimension": True, "is_time": False,
             "is_delete": False, "option": {}},
        ]
        result = self.storage.build_log_v4_data_link(fields, etl_params, _get_fresh_built_in_config())
        _assert_v4_result_equal(self, result, EXPECTED_JSON_PATH_SEPARATOR, "场景8-JSON-path正则")


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
        result = self.storage.build_log_v4_data_link(fields, etl_params, _get_fresh_built_in_config())
        _assert_v4_result_equal(self, result, EXPECTED_DELIMITER_BASIC, "场景5-分隔符基础")

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
        result = self.storage.build_log_v4_data_link(fields, etl_params, _get_fresh_built_in_config())
        _assert_v4_result_equal(self, result, EXPECTED_DELIMITER_DELETE_SKIP, "场景6-分隔符删除+跳索引")


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
        result = self.storage.build_log_v4_data_link(fields, etl_params, _get_fresh_built_in_config())
        _assert_v4_result_equal(self, result, EXPECTED_REGEXP_BASIC, "场景7-正则基础")


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
        result = self.storage.build_log_v4_data_link(fields, etl_params, _get_fresh_built_in_config())
        _assert_v4_result_equal(self, result, EXPECTED_JSON_ISO8601_TIME, "场景9-JSON-ISO8601时间")

    def test_json_non_json_retain_content(self):
        """场景10：JSON + enable_retain_content + 非 JSON 日志"""
        etl_params = {"retain_original_text": True, "enable_retain_content": True}
        fields = [
            {"field_name": "level", "alias_name": "", "field_type": "string",
             "description": "日志级别", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
        ]
        result = self.storage.build_log_v4_data_link(fields, etl_params, _get_fresh_built_in_config())
        _assert_v4_result_equal(self, result, EXPECTED_JSON_NON_JSON_RETAIN, "场景10-非JSON保留原文")

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
        result = self.storage.build_log_v4_data_link(fields, etl_params, _get_fresh_built_in_config())
        _assert_v4_result_equal(self, result, EXPECTED_JSON_EPOCH_MILLIS, "场景12-JSON-epoch_millis")


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
        result = self.storage.build_log_v4_data_link(fields, etl_params, _get_fresh_built_in_config())
        _assert_v4_result_equal(self, result, EXPECTED_DELIMITER_TIME_FIELD, "场景11-分隔符+时间字段")
