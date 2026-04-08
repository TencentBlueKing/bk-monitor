from django.test import TestCase

from apps.log_search.constants import DorisFieldTypeEnum


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
