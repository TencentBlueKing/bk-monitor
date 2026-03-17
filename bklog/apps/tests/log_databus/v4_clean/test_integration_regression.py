# -*- coding: utf-8 -*-
"""
回归测试：保留原 12 场景快照比对作为安全网
直接复用旧测试的逻辑和快照数据，确保重构不破坏既有行为。
"""
import copy
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

from apps.tests.log_databus.v4_clean.testdata.built_in_configs import get_fresh_config


class TestIntegrationRegression(TestCase):
    """
    原 12 场景快照全量比对回归测试。
    每个场景使用与旧 test_v4_clean.py 完全一致的输入，对比快照确保一致。
    """

    # ---- 场景 1：直接入库 ----
    def test_01_text_basic(self):
        storage = BkLogTextEtlStorage()
        result = storage.build_log_v4_data_link([], {}, get_fresh_config())
        self.assertEqual(result, EXPECTED_TEXT_BASIC)

    # ---- 场景 2：JSON 多字段 + 保留原文 ----
    def test_02_json_retain_original(self):
        storage = BkLogJsonEtlStorage()
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
        result = storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        self.assertEqual(result, EXPECTED_JSON_RETAIN_ORIGINAL)

    # ---- 场景 3：JSON 别名 + 删除 + 时间 ----
    def test_03_json_alias_delete_time(self):
        storage = BkLogJsonEtlStorage()
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
        result = storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        self.assertEqual(result, EXPECTED_JSON_ALIAS_DELETE_TIME)

    # ---- 场景 4：JSON ext_json + 解析失败 ----
    def test_04_json_extra_and_failure(self):
        storage = BkLogJsonEtlStorage()
        etl_params = {"retain_original_text": True, "retain_extra_json": True, "enable_retain_content": True}
        fields = [
            {"field_name": "level", "alias_name": "", "field_type": "string",
             "description": "日志级别", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
        ]
        result = storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        self.assertEqual(result, EXPECTED_JSON_EXTRA_AND_FAILURE)

    # ---- 场景 5：分隔符基础 ----
    def test_05_delimiter_basic(self):
        storage = BkLogDelimiterEtlStorage()
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
        result = storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        self.assertEqual(result, EXPECTED_DELIMITER_BASIC)

    # ---- 场景 6：分隔符删除 + 跳索引 ----
    def test_06_delimiter_delete_skip(self):
        storage = BkLogDelimiterEtlStorage()
        etl_params = {"separator": ",", "retain_original_text": False}
        fields = [
            {"field_name": "name", "alias_name": "", "field_type": "string", "field_index": 1,
             "is_analyzed": False, "is_dimension": True, "is_time": False, "is_delete": False, "option": {}},
            {"field_name": "unused", "alias_name": "", "field_type": "string", "field_index": 3,
             "is_analyzed": False, "is_dimension": False, "is_time": False, "is_delete": True, "option": {}},
            {"field_name": "value", "alias_name": "", "field_type": "int", "field_index": 5,
             "is_analyzed": False, "is_dimension": True, "is_time": False, "is_delete": False, "option": {}},
        ]
        result = storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        self.assertEqual(result, EXPECTED_DELIMITER_DELETE_SKIP)

    # ---- 场景 7：正则基础 ----
    def test_07_regexp_basic(self):
        storage = BkLogRegexpEtlStorage()
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
        result = storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        self.assertEqual(result, EXPECTED_REGEXP_BASIC)

    # ---- 场景 8：JSON path 正则 ----
    def test_08_json_path_separator(self):
        storage = BkLogJsonEtlStorage()
        etl_params = {"retain_original_text": False}
        fields = [
            {"field_name": "level", "alias_name": "", "field_type": "string",
             "is_analyzed": False, "is_dimension": True, "is_time": False,
             "is_delete": False, "option": {}},
        ]
        config = get_fresh_config()
        config["option"]["separator_configs"] = [
            {"separator_regexp": r"/data/logs/(?P<app_name>[^/]+)/(?P<log_type>[^/]+)\.log"}
        ]
        result = storage.build_log_v4_data_link(fields, etl_params, config)
        self.assertEqual(result, EXPECTED_JSON_PATH_SEPARATOR)

    # ---- 场景 9：JSON ISO8601 时间 ----
    def test_09_json_iso8601_time(self):
        storage = BkLogJsonEtlStorage()
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
        result = storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        self.assertEqual(result, EXPECTED_JSON_ISO8601_TIME)

    # ---- 场景 10：非 JSON 保留原文 ----
    def test_10_json_non_json_retain(self):
        storage = BkLogJsonEtlStorage()
        etl_params = {"retain_original_text": True, "enable_retain_content": True}
        fields = [
            {"field_name": "level", "alias_name": "", "field_type": "string",
             "description": "日志级别", "is_analyzed": False, "is_dimension": True,
             "is_time": False, "is_delete": False, "option": {}},
        ]
        result = storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        self.assertEqual(result, EXPECTED_JSON_NON_JSON_RETAIN)

    # ---- 场景 11：分隔符 + 时间字段 ----
    def test_11_delimiter_time_field(self):
        storage = BkLogDelimiterEtlStorage()
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
        result = storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        self.assertEqual(result, EXPECTED_DELIMITER_TIME_FIELD)

    # ---- 场景 12：JSON epoch_millis ----
    def test_12_json_epoch_millis(self):
        storage = BkLogJsonEtlStorage()
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
        result = storage.build_log_v4_data_link(fields, etl_params, get_fresh_config())
        self.assertEqual(result, EXPECTED_JSON_EPOCH_MILLIS)
