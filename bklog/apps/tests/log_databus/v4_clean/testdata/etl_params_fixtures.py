# -*- coding: utf-8 -*-
"""
V4 清洗规则测试 — etl_params 预定义组合
"""

EMPTY_PARAMS = {}

JSON_RETAIN_ORIGINAL = {"retain_original_text": True, "retain_extra_json": False}
JSON_RETAIN_EXTRA = {"retain_original_text": True, "retain_extra_json": True, "enable_retain_content": True}
JSON_NO_RETAIN = {"retain_original_text": False}
JSON_ENABLE_RETAIN_CONTENT = {"retain_original_text": True, "enable_retain_content": True}

DELIMITER_BASIC = {"separator": "|", "retain_original_text": True}
DELIMITER_COMMA = {"separator": ",", "retain_original_text": False}

REGEXP_BASIC = {
    "separator_regexp": r"(?P<request_ip>[\d\.]+)\s+-\s+-\s+\[(?P<request_time>[^\]]+)\]\s+\"(?P<method>\w+)",
    "retain_original_text": True,
}
