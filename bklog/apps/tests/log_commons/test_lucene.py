import copy

from django.test import TestCase

from apps.log_search.handlers.search.favorite_handlers import FavoriteHandler
from apps.log_search.serializers import (
    GenerateQuerySerializer,
    GetSearchFieldsSerializer,
    InspectSerializer,
)
from apps.utils.lucene import (
    CaseInsensitiveLogicalEnhanceLucene,
    EnhanceLuceneAdapter,
    LuceneSyntaxResolver,
    OperatorEnhanceLucene,
    ReservedLogicalEnhanceLucene,
)

# =================================== TEST LUCENE =================================== #
KEYWORD = """number: >=83063 OR title: "The Right Way" AND text: go OR gseIndex: [ 200 TO 600 ] \
AND log: blue~ AND time: /[L-N].*z*l{2}a/ AND a: b AND c: d OR (a: (b OR c AND d) OR x: y ) AND INFO AND ERROR"""

KEYWORD_FIELDS = [
    {
        "pos": 0,
        "name": "number",
        "type": "Word",
        "operator": ">=",
        "value": "83063",
        "is_full_text_field": False,
        "repeat_count": 0,
    },
    {
        "pos": 19,
        "name": "title",
        "type": "Phrase",
        "operator": "=",
        "value": '"The Right Way"',
        "is_full_text_field": False,
        "repeat_count": 0,
    },
    {
        "pos": 46,
        "name": "text",
        "type": "Word",
        "operator": "~=",
        "value": "go",
        "is_full_text_field": False,
        "repeat_count": 0,
    },
    {
        "pos": 58,
        "name": "gseIndex",
        "type": "Range",
        "operator": "[]",
        "value": "[ 200 TO 600 ]",
        "is_full_text_field": False,
        "repeat_count": 0,
    },
    {
        "pos": 87,
        "name": "log",
        "type": "Fuzzy",
        "operator": "~=",
        "value": "blue~",
        "is_full_text_field": False,
        "repeat_count": 0,
    },
    {
        "pos": 102,
        "name": "time",
        "type": "Regex",
        "operator": "~=",
        "value": "/[L-N].*z*l{2}a/",
        "is_full_text_field": False,
        "repeat_count": 0,
    },
    {
        "pos": 129,
        "name": "a(1)",
        "operator": "~=",
        "type": "Word",
        "value": "b",
        "is_full_text_field": False,
        "repeat_count": 1,
    },
    {
        "pos": 138,
        "name": "c",
        "operator": "~=",
        "type": "Word",
        "value": "d",
        "is_full_text_field": False,
        "repeat_count": 0,
    },
    {
        "pos": 147,
        "name": "a(2)",
        "operator": "()",
        "type": "FieldGroup",
        "value": "(b OR c AND d)",
        "is_full_text_field": False,
        "repeat_count": 2,
    },
    {
        "pos": 168,
        "name": "x",
        "operator": "~=",
        "type": "Word",
        "value": "y",
        "is_full_text_field": False,
        "repeat_count": 0,
    },
    {
        "pos": 179,
        "name": "全文检索(1)",
        "operator": "~=",
        "type": "Word",
        "value": "INFO",
        "is_full_text_field": True,
        "repeat_count": 1,
    },
    {
        "pos": 188,
        "name": "全文检索(2)",
        "operator": "~=",
        "type": "Word",
        "value": "ERROR",
        "is_full_text_field": True,
        "repeat_count": 2,
    },
]
UPDATE_QUERY_PARAMS = [
    {
        "pos": 0,
        "value": "10000",
    },
    {
        "pos": 19,
        "value": '"hello"',
    },
    {
        "pos": 46,
        "value": "hello",
    },
    {
        "pos": 58,
        "value": "[100 TO 200]",
    },
    {
        "pos": 87,
        "value": "bk~",
    },
    {
        "pos": 102,
        "value": "/[L-N]/",
    },
    {
        "pos": 129,
        "value": "bb",
    },
    {
        "pos": 138,
        "value": "dd",
    },
    {
        "pos": 147,
        "value": "(bb OR cc AND dd)",
    },
    {
        "pos": 168,
        "value": "yy",
    },
    {
        "pos": 179,
        "value": "hello1",
    },
    {
        "pos": 188,
        "value": "hello2",
    },
]
EXPECT_NEW_QUERY = """number: >=10000 OR title: "hello" AND text: hello OR gseIndex: [100 TO 200] \
AND log: bk~0.5 AND time: /[L-N]/ AND a: bb AND c: dd OR (a: (bb OR cc AND dd) OR x: yy) AND hello1 AND hello2"""
ILLEGAL_KEYWORD = """log:: ERROR AND log: [TO 200] AND time: [100 TO OR log: TO 100]"""
INSPECT_KEYWORD_RESULT = {
    "is_legal": False,
    "is_resolved": True,
    "message": "非法RANGE语法\n异常字符",
    "keyword": "log: ERROR AND log: [* TO 200] AND time: [100 TO *] OR log: [* TO 100]",
}

# =================================== TEST ENHANCE LUCENE =================================== #
ENHANCE_KEYWORD_TEST_CASES = [
    {
        "keyword": """number >=83063 or title: "The Right Way" AND log: and""",
        "expect": """number: >=83063 OR title: "The Right Way" AND log: \"and\"""",
    },
    {
        "keyword": """number < 83063 and title: "The Right Way" AND log: OR""",
        "expect": """number: <83063 AND title: "The Right Way" AND log: \"OR\"""",
    },
]

ENHANCE_KEYWORD_INSPECT_RESULT = {
    "is_legal": True,
    "is_resolved": True,
    "message": "",
    "keyword": """number: >=83063 OR title: "The Right Way" AND log: "and" """,
}

ENHANCE_KEYWORD_FIELDS = [
    {
        'pos': 0,
        'name': 'number',
        'type': 'Word',
        'operator': '>=',
        'value': '83063',
        'is_full_text_field': False,
        'repeat_count': 0,
    },
    {
        'pos': 19,
        'name': 'title',
        'type': 'Phrase',
        'operator': '=',
        'value': '"The Right Way"',
        'is_full_text_field': False,
        'repeat_count': 0,
    },
    {
        'pos': 46,
        'name': 'log',
        'type': 'Phrase',
        'operator': '=',
        'value': '"and"',
        'is_full_text_field': False,
        'repeat_count': 0,
    },
]


ENHANCE_UPDATE_QUERY_PARAMS = [
    {
        "pos": 0,
        "value": "100000",
    },
    {
        "pos": 19,
        "value": '"hello"',
    },
    {
        "pos": 46,
        "value": '"not"',
    },
]

ENHANCE_EXPECT_NEW_QUERY = """number: >=100000 OR title: "hello" AND log: \"not\""""


class TestLucene(TestCase):
    def setUp(self) -> None:
        self.maxDiff = None

    def test_get_search_fields(self):
        """测试获取Lucene Query字段"""
        search_fields_result = FavoriteHandler().get_search_fields(keyword=KEYWORD)
        for i in range(len(KEYWORD_FIELDS)):
            self.assertDictEqual(search_fields_result[i], KEYWORD_FIELDS[i])

    def test_update_query(self):
        """测试更新Lucene Query"""
        self.assertEqual(FavoriteHandler().generate_query_by_ui(KEYWORD, UPDATE_QUERY_PARAMS), EXPECT_NEW_QUERY)

    def test_inspect(self):
        """测试解析关键字"""
        inspect_result = LuceneSyntaxResolver(keyword=ILLEGAL_KEYWORD).resolve()
        self.assertEqual(inspect_result["is_legal"], INSPECT_KEYWORD_RESULT["is_legal"])
        self.assertEqual(inspect_result["is_resolved"], INSPECT_KEYWORD_RESULT["is_resolved"])
        self.assertEqual(inspect_result["keyword"], INSPECT_KEYWORD_RESULT["keyword"])
        self.assertEqual(
            sorted(inspect_result["message"].split("\n")), sorted(INSPECT_KEYWORD_RESULT["message"].split("\n"))
        )


class TestEnhanceLucene(TestCase):
    def setUp(self) -> None:
        self.maxDiff = None

    def test_enhance(self):
        """测试增强Lucene Query"""
        for i in ENHANCE_KEYWORD_TEST_CASES:
            # 测试单个增强函数是否符合预期
            keyword = i["keyword"]
            self.assertEqual(CaseInsensitiveLogicalEnhanceLucene(keyword).match(), True)
            keyword = CaseInsensitiveLogicalEnhanceLucene(keyword).transform()
            self.assertEqual(OperatorEnhanceLucene(keyword).match(), True)
            keyword = OperatorEnhanceLucene(keyword).transform()
            self.assertEqual(ReservedLogicalEnhanceLucene(keyword).match(), True)
            keyword = ReservedLogicalEnhanceLucene(keyword).transform()
            self.assertEqual(keyword, i["expect"])

        # 完整的流程
        for i in ENHANCE_KEYWORD_TEST_CASES:
            keyword = i["keyword"]
            adapter = EnhanceLuceneAdapter(keyword)
            adapter.enhance()
            self.assertEqual(adapter.is_enhanced, True)
            self.assertEqual(adapter.origin_query_string, keyword)
            self.assertEqual(adapter.query_string, i["expect"])

        # 测试正常的字符串
        keyword = copy.deepcopy(KEYWORD)
        self.assertEqual(CaseInsensitiveLogicalEnhanceLucene(keyword).match(), False)
        self.assertEqual(OperatorEnhanceLucene(keyword).match(), False)
        self.assertEqual(ReservedLogicalEnhanceLucene(keyword).match(), False)

        keyword = CaseInsensitiveLogicalEnhanceLucene(keyword).transform()
        keyword = OperatorEnhanceLucene(keyword).transform()
        keyword = ReservedLogicalEnhanceLucene(keyword).transform()
        self.assertEqual(keyword, KEYWORD)


class TestFavoriteWithEnhanceLucene(TestCase):
    def setUp(self) -> None:
        self.maxDiff = None

    def test_inspect(self):
        """测试解析关键字"""
        slz = InspectSerializer(data={"keyword": ENHANCE_KEYWORD_TEST_CASES[0]["keyword"]})
        slz.is_valid(raise_exception=True)
        inspect_result = FavoriteHandler().inspect(keyword=slz.validated_data["keyword"])
        self.assertEqual(inspect_result["is_legal"], True)
        self.assertEqual(inspect_result["is_resolved"], True)
        self.assertEqual(inspect_result["keyword"], ENHANCE_KEYWORD_TEST_CASES[0]["expect"])
        self.assertEqual(inspect_result["message"], "")

    def test_get_search_fields(self):
        """测试获取Lucene Query字段"""
        slz = GetSearchFieldsSerializer(data={"keyword": ENHANCE_KEYWORD_TEST_CASES[0]["keyword"]})
        slz.is_valid(raise_exception=True)
        search_fields_result = FavoriteHandler().get_search_fields(keyword=slz.validated_data["keyword"])
        self.assertEqual(len(search_fields_result), len(ENHANCE_KEYWORD_FIELDS))
        for i in range(len(ENHANCE_KEYWORD_FIELDS)):
            self.assertDictEqual(search_fields_result[i], ENHANCE_KEYWORD_FIELDS[i])

    def test_generate_query_by_ui(self):
        """测试更新Lucene Query"""
        slz = GenerateQuerySerializer(
            data={"keyword": ENHANCE_KEYWORD_TEST_CASES[0]["keyword"], "params": ENHANCE_UPDATE_QUERY_PARAMS}
        )
        slz.is_valid(raise_exception=True)
        self.assertEqual(FavoriteHandler().generate_query_by_ui(**slz.validated_data), ENHANCE_EXPECT_NEW_QUERY)
