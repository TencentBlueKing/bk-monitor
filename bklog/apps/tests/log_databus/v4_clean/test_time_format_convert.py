# -*- coding: utf-8 -*-
"""
纯函数单元测试：EtlStorage._convert_v3_to_v4_time_format
覆盖 _convert_v3_to_v4_time_format 中所有 40+ 时间格式映射 + 未知格式回退。
"""
from unittest import TestCase

from apps.log_databus.handlers.etl_storage.base import EtlStorage


class TestConvertV3ToV4TimeFormat(TestCase):
    """测试 _convert_v3_to_v4_time_format 所有已定义的时间格式映射"""

    # (v3_format, expected_from_format, expected_zone)
    TIME_FORMAT_CASES = [
        # 标准日期时间
        ("yyyy-MM-dd HH:mm:ss", "%Y-%m-%d %H:%M:%S", 0),
        ("yyyy-MM-dd HH:mm:ss,SSS", "%Y-%m-%d %H:%M:%S,%3f", 0),
        ("yyyy-MM-dd HH:mm:ss.SSS", "%Y-%m-%d %H:%M:%S.%3f", 0),
        ("yyyy-MM-dd HH:mm:ss.SSSSSS", "%Y-%m-%d %H:%M:%S.%6f", 0),
        ("yy-MM-dd HH:mm:ss.SSSSSS", "%y-%m-%d %H:%M:%S.%6f", 0),
        ("yyyy-MM-ddTHH:mm:ss.SSSSSS", "%Y-%m-%dT%H:%M:%S.%6f", 0),
        ("yyyy-MM-dd+HH:mm:ss", "%Y-%m-%d+%H:%M:%S", 0),
        ("MM/dd/yyyy HH:mm:ss", "%m/%d/%Y %H:%M:%S", 0),
        ("yyyyMMddHHmmss", "%Y%m%d%H%M%S", 0),
        ("yyyyMMdd HHmmss", "%Y%m%d %H%M%S", 0),
        ("yyyyMMdd HHmmss.SSS", "%Y%m%d %H%M%S.%3f", 0),
        ("yyyyMMdd HH:mm:ss.SSSSSS", "%Y%m%d %H:%M:%S.%6f", 0),
        ("YYYYMMdd HH:mm:ss.SSSSSS", "%Y%m%d %H:%M:%S.%6f", 0),
        # 带时区的日期时间
        ("dd/MMM/yyyy:HH:mm:ss", "%d/%b/%Y:%H:%M:%S", 0),
        ("dd/MMM/yyyy:HH:mm:ssZ", "%d/%b/%Y:%H:%M:%S%:z", None),
        ("dd/MMM/yyyy:HH:mm:ss Z", "%d/%b/%Y:%H:%M:%S %:z", None),
        ("dd/MMM/yyyy:HH:mm:ssZZ", "%d/%b/%Y:%H:%M:%S%:z", None),
        ("dd/MMM/yyyy:HH:mm:ss ZZ", "%d/%b/%Y:%H:%M:%S %:z", None),
        # RFC/ISO
        ("rfc3339", "%+", None),
        ("ISO8601", "%+", None),
        # T分隔格式
        ("yyyy-MM-ddTHH:mm:ss", "%Y-%m-%dT%H:%M:%S", 0),
        ("yyyy-MM-ddTHH:mm:ss.SSS", "%Y-%m-%dT%H:%M:%S.%3f", 0),
        ("yyyyMMddTHHmmssZ", "%Y%m%dT%H%M%S%:z", None),
        ("yyyyMMddTHHmmss.SSSSSSZ", "%Y%m%dT%H%M%S.%6f%:z", None),
        ("yyyy-MM-ddTHH:mm:ss.SSSZ", "%Y-%m-%dT%H:%M:%S.%3f%:z", None),
        ("yyyy-MM-ddTHH:mm:ss.SSSSSSZ", "%Y-%m-%dT%H:%M:%S.%6fZ", None),
        ("YYYY-MM-DDTHH:mm:ss.SSSSSSZ", "%Y-%m-%dT%H:%M:%S.%6fZ", None),
        ("yyyy-MM-ddTHH:mm:ssZ", "%Y-%m-%dT%H:%M:%S%:z", None),
        ("yyyy-MM-ddTHH:mm:ss.SSSSSSZZ", "%Y-%m-%dT%H:%M:%S.%6f%:z", None),
        ("yyyy.MM.dd-HH.mm.ss:SSS", "%Y.%m.%d-%H.%M.%S:%3f", 0),
        # ES 内置名称
        ("date_hour_minute_second", "%Y-%m-%dT%H:%M:%S", 0),
        ("date_hour_minute_second_millis", "%Y-%m-%dT%H:%M:%S.%3f", 0),
        ("basic_date_time", "%Y%m%dT%H%M%S.%3f%z", None),
        ("basic_date_time_no_millis", "%Y%m%dT%H%M%S%z", None),
        ("basic_date_time_micros", "%Y%m%dT%H%M%S.%6f%z", None),
        ("strict_date_time", "%Y-%m-%dT%H:%M:%S.%3f%:z", None),
        ("strict_date_time_no_millis", "%Y-%m-%dT%H:%M:%S%:z", None),
        ("strict_date_time_micros", "%Y-%m-%dT%H:%M:%S.%6f%:z", None),
        # Unix 时间戳
        ("epoch_micros", "Unix Timestamp", None),
        ("Unix Time Stamp(milliseconds)", "Unix Timestamp", None),
        ("epoch_millis", "Unix Timestamp", None),
        ("epoch_second", "Unix Timestamp", None),
    ]

    def test_all_known_formats(self):
        """subTest 覆盖所有已定义的 V3 时间格式"""
        for v3_fmt, expected_format, expected_zone in self.TIME_FORMAT_CASES:
            with self.subTest(v3_format=v3_fmt):
                result = EtlStorage._convert_v3_to_v4_time_format(v3_fmt)
                self.assertEqual(result["from"]["format"], expected_format,
                                 f"format mismatch for {v3_fmt!r}")
                self.assertEqual(result["from"]["zone"], expected_zone,
                                 f"zone mismatch for {v3_fmt!r}")
                self.assertIsNone(result["interval_format"])
                self.assertEqual(result["to"], "millis")
                self.assertTrue(result["now_if_parse_failed"])

    def test_unknown_format_fallback(self):
        """未知格式应回退到默认 %Y-%m-%d %H:%M:%S"""
        result = EtlStorage._convert_v3_to_v4_time_format("xyz_unknown_format")
        self.assertEqual(result["from"]["format"], "%Y-%m-%d %H:%M:%S")
        self.assertEqual(result["from"]["zone"], 0)
        self.assertEqual(result["to"], "millis")
        self.assertTrue(result["now_if_parse_failed"])

    def test_empty_string_fallback(self):
        """空字符串应回退到默认"""
        result = EtlStorage._convert_v3_to_v4_time_format("")
        self.assertEqual(result["from"]["format"], "%Y-%m-%d %H:%M:%S")
