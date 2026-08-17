"""
清洗失败标记 __parse_failure 行为测试

关键约束：__parse_failure 只由 record_parse_failure 决定，不与 retain_original_text 联动。

原因：分隔符 / 正则在 V3 与 V4 两条链路上都没有丢弃失败记录的能力——
V3 的 TransformMapBySeparator / TransformMapByRegexp 恒返回 nil error；
V4 的 split_str / regex 算子没有 error_strategy（只有 json_de 有）。
因此失败记录必然入库，若此时把 __parse_failure 一起抹掉，就会退化成
「字段全空且无法判断失败原因」的数据，比保留标记更糟。
"""

from unittest import TestCase

from apps.log_databus.constants import PARSE_FAILURE_FIELD
from apps.log_databus.handlers.etl_storage.bk_log_delimiter import BkLogDelimiterEtlStorage
from apps.log_databus.handlers.etl_storage.bk_log_regexp import BkLogRegexpEtlStorage
from apps.tests.log_databus.v4_clean.helpers import assert_rule_absent
from apps.tests.log_databus.v4_clean.testdata.built_in_configs import build_test_field_list, get_fresh_config
from apps.tests.log_databus.v4_clean.testdata.field_fixtures import make_field

CASES = [
    ("delimiter", BkLogDelimiterEtlStorage, {"separator": "|"}, {"field_index": 1}),
    ("regexp", BkLogRegexpEtlStorage, {"separator_regexp": r"(?P<level>\w+)"}, {}),
]


class TestParseFailureResultTableField(TestCase):
    """结果表字段列表（V3 / V4 共用）中的 __parse_failure"""

    def test_kept_when_original_text_disabled(self):
        """未保留原文时结果表仍应声明 __parse_failure，否则 V3 失败记录无法诊断"""
        for name, storage_cls, extra, field_kwargs in CASES:
            with self.subTest(etl_type=name):
                etl_params = {**extra, "retain_original_text": False, "record_parse_failure": True}
                fields = [make_field("level", **field_kwargs)]
                rt_fields = storage_cls().get_result_table_fields(fields, etl_params, get_fresh_config())
                self.assertIn(PARSE_FAILURE_FIELD, [f["field_name"] for f in rt_fields["fields"]])

    def test_absent_when_not_requested(self):
        """未开启 record_parse_failure 时不声明该字段"""
        for name, storage_cls, extra, field_kwargs in CASES:
            with self.subTest(etl_type=name):
                etl_params = {**extra, "retain_original_text": True}
                fields = [make_field("level", **field_kwargs)]
                rt_fields = storage_cls().get_result_table_fields(fields, etl_params, get_fresh_config())
                self.assertNotIn(PARSE_FAILURE_FIELD, [f["field_name"] for f in rt_fields["fields"]])


class TestParseFailureV4KnownGap(TestCase):
    """锁定 V4 侧的已知缺口，避免被误当成本次改动引入的问题

    `_build_parse_failure_field_v4` 目前是死代码（全仓无调用点），且它的 assign 是从上游节点读
    `__parse_failure` key，而 V4 的 split_str / regex 算子并不产出该 key。也就是说 V4 链路上
    __parse_failure 既没有被写入、也无从写入，需要清洗引擎先支持失败标记 / drop 才能补齐。
    这不是本次改动造成的（master 上同样如此），单独跟进。
    """

    def test_v4_emits_no_parse_failure_rule(self):
        for name, storage_cls, extra, field_kwargs in CASES:
            with self.subTest(etl_type=name):
                etl_params = {**extra, "retain_original_text": False, "record_parse_failure": True}
                fields = [make_field("level", **field_kwargs)]
                config = get_fresh_config()
                result = storage_cls().build_log_v4_data_link(
                    fields, etl_params, config, build_test_field_list(fields, config)
                )
                assert_rule_absent(self, result["clean_rules"], PARSE_FAILURE_FIELD)
