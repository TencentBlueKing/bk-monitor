from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from apps.log_search.constants import DorisFieldTypeEnum
from apps.log_unifyquery.handler.mapping import UnifyQueryMappingHandler


class TestDorisFieldTypeEnum(TestCase):
    def test_es_field_type_mapping(self):
        """测试基本类型映射关系"""
        # 测试普通类型映射
        test_cases = [
            # (字段配置, 预期ES类型)
            ({"field_type": "boolean"}, "boolean"),
            ({"field_type": "tinyint"}, "integer"),
            ({"field_type": "smallint"}, "integer"),
            ({"field_type": "int"}, "integer"),
            ({"field_type": "bigint"}, "long"),
            ({"field_type": "float"}, "float"),
            ({"field_type": "double"}, "double"),
            ({"field_type": "char(10)"}, "keyword"),  # 带长度参数
            ({"field_type": "varchar(32)"}, "keyword"),
            ({"field_type": "string"}, "keyword"),
            ({"field_type": "date"}, "date"),
            ({"field_type": "datetime"}, "date"),
            ({"field_type": "variant"}, "object"),
        ]

        for field, expected in test_cases:
            with self.subTest(field=field):
                result = DorisFieldTypeEnum.get_es_field_type(field)
                self.assertEqual(result, expected)

    def test_dteventtimestamp(self):
        """测试特殊字段 dtEventTimeStamp 映射"""
        field = {"field_name": "dtEventTimeStamp", "field_type": "bigint"}
        self.assertEqual(DorisFieldTypeEnum.get_es_field_type(field), "date")

    def test_analyzed_field(self):
        """测试 is_analyzed=True 时的映射"""
        test_cases = [
            {"field_type": "varchar(32)", "is_analyzed": True},
            {"field_type": "char", "is_analyzed": True},
        ]

        for field in test_cases:
            with self.subTest(field=field):
                self.assertEqual(DorisFieldTypeEnum.get_es_field_type(field), "text")


class TestUnifyQueryMappingHandler(TestCase):
    def test_normalize_dt_event_timestamp_field_type(self):
        test_cases = [
            ("dtEventTimeStamp", "long", "date"),
            ("dtEventTimeStamp", "date", "date"),
            ("dtEventTimeStamp", "date_nanos", "date_nanos"),
            ("dtEventTimeStampNanos", "long", "long"),
            ("time", "long", "long"),
        ]

        for field_name, field_type, expected in test_cases:
            with self.subTest(field_name=field_name, field_type=field_type):
                self.assertEqual(
                    UnifyQueryMappingHandler.normalize_dt_event_timestamp_field_type(field_name, field_type),
                    expected,
                )

    def test_get_final_fields_normalizes_dt_event_timestamp(self):
        handler = UnifyQueryMappingHandler(
            indices="2_bklog.demo",
            index_set_id=1,
            scenario_id="log",
            storage_cluster_id=1,
            only_search=True,
            index_set=SimpleNamespace(fields_snapshot={}, tag_ids=[]),
        )
        handler.get_all_index_fields = lambda: [
            {
                "field_name": "dtEventTimeStamp",
                "field_type": "long",
                "is_agg": True,
                "is_analyzed": False,
            },
            {
                "field_name": "dtEventTimeStampNanos",
                "field_type": "long",
                "is_agg": True,
                "is_analyzed": False,
            },
        ]

        with (
            patch("apps.log_unifyquery.handler.mapping.IndexSetTag.get_tag_id", return_value=-1),
            patch(
                "apps.log_unifyquery.handler.mapping.CollectorConfig.get_storage_cluster_type_map_by_table_ids",
                return_value={},
            ),
            patch("apps.log_unifyquery.handler.mapping.ClusteringConfig.get_by_index_set_id", return_value=None),
        ):
            fields = handler.get_final_fields()

        fields_by_name = {field["field_name"]: field for field in fields}
        self.assertEqual(fields_by_name["dtEventTimeStamp"]["field_type"], "date")
        self.assertEqual(fields_by_name["dtEventTimeStamp"]["tag"], "timestamp")
        self.assertEqual(fields_by_name["dtEventTimeStampNanos"]["field_type"], "long")
