import copy

from django.test import TestCase

from apps.log_search.handlers.search.favorite_handlers import FavoriteHandler
from apps.log_search.serializers import (
    GenerateQuerySerializer,
    GetSearchFieldsSerializer,
)
from apps.utils.lucene import (
    CaseInsensitiveLogicalEnhanceLucene,
    EnhanceLuceneAdapter,
    LuceneChecker,
    LuceneFieldExistChecker,
    LuceneFieldExprChecker,
    LuceneFullWidthChecker,
    LuceneNumericOperatorChecker,
    LuceneNumericValueChecker,
    LuceneParenthesesChecker,
    LuceneQuotesChecker,
    LuceneRangeChecker,
    LuceneReservedCharChecker,
    LuceneSyntaxResolver,
    LuceneUnexpectedLogicOperatorChecker,
    OperatorEnhanceLucene,
    ReservedLogicalEnhanceLucene,
)

# =================================== TEST LUCENE =================================== #
KEYWORD = """number: >=83063 OR title: "The Right Way" AND text: go OR gseIndex: [ 200 TO 600 ] \
AND log: blue~ AND time: /[L-N].*z*l{2}a/ AND a: b AND c: d OR (a: (b OR c AND d) OR x: y ) AND INFO AND ERROR"""

KEYWORD_FIELDS = [
    {
        "pos": 0,
        "field_name": "number",
        "name": "number",
        "type": "Word",
        "operator": ">=",
        "value": "83063",
        "is_full_text_field": False,
        "repeat_count": 0,
    },
    {
        "pos": 19,
        "field_name": "title",
        "name": "title",
        "type": "Phrase",
        "operator": "=",
        "value": '"The Right Way"',
        "is_full_text_field": False,
        "repeat_count": 0,
    },
    {
        "pos": 46,
        "field_name": "text",
        "name": "text",
        "type": "Word",
        "operator": "~=",
        "value": "go",
        "is_full_text_field": False,
        "repeat_count": 0,
    },
    {
        "pos": 58,
        "field_name": "gseIndex",
        "name": "gseIndex",
        "type": "Range",
        "operator": "[]",
        "value": "[ 200 TO 600 ]",
        "is_full_text_field": False,
        "repeat_count": 0,
    },
    {
        "pos": 87,
        "field_name": "log",
        "name": "log",
        "type": "Fuzzy",
        "operator": "~=",
        "value": "blue~",
        "is_full_text_field": False,
        "repeat_count": 0,
    },
    {
        "pos": 102,
        "field_name": "time",
        "name": "time",
        "type": "Regex",
        "operator": "~=",
        "value": "/[L-N].*z*l{2}a/",
        "is_full_text_field": False,
        "repeat_count": 0,
    },
    {
        "pos": 129,
        "field_name": "a",
        "name": "a(1)",
        "operator": "~=",
        "type": "Word",
        "value": "b",
        "is_full_text_field": False,
        "repeat_count": 1,
    },
    {
        "pos": 138,
        "field_name": "c",
        "name": "c",
        "operator": "~=",
        "type": "Word",
        "value": "d",
        "is_full_text_field": False,
        "repeat_count": 0,
    },
    {
        "pos": 147,
        "field_name": "a",
        "name": "a(2)",
        "operator": "()",
        "type": "FieldGroup",
        "value": "(b OR c AND d)",
        "is_full_text_field": False,
        "repeat_count": 2,
    },
    {
        "pos": 168,
        "field_name": "x",
        "name": "x",
        "operator": "~=",
        "type": "Word",
        "value": "y",
        "is_full_text_field": False,
        "repeat_count": 0,
    },
    {
        "pos": 179,
        "field_name": "全文检索",
        "name": "全文检索(1)",
        "operator": "~=",
        "type": "Word",
        "value": "INFO",
        "is_full_text_field": True,
        "repeat_count": 1,
    },
    {
        "pos": 188,
        "field_name": "全文检索",
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
        "field_name": "number",
        'name': 'number',
        'type': 'Word',
        'operator': '>=',
        'value': '83063',
        'is_full_text_field': False,
        'repeat_count': 0,
    },
    {
        'pos': 19,
        "field_name": "title",
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
        'field_name': 'log',
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

# =================================== TEST LUCENE CHECKER =================================== #
FIELDS = [
    {
        "field_name": "log",
        "field_type": "text",
        "is_analyzed": True,
    },
    {"field_name": "id", "field_type": "integer", "is_analyzed": False},
    {"field_name": "number", "field_type": "integer", "is_analyzed": False},
    {"field_name": "title", "field_type": "text", "is_analyzed": True},
    {"field_name": "text", "field_type": "text", "is_analyzed": True},
    {"field_name": "gseIndex", "field_type": "integer", "is_analyzed": False},
    {"field_name": "time", "field_type": "text", "is_analyzed": True},
    {"field_name": "a", "field_type": "text", "is_analyzed": True},
    {"field_name": "c", "field_type": "text", "is_analyzed": True},
    {"field_name": "x", "field_type": "text", "is_analyzed": True},
]
LEGAL_CASE = {
    "keyword": KEYWORD,
    "fields": FIELDS,
    "check_result": True,
    "prompt": "",
}

PARENTHESES_CHECK_TEST_CASES = [LEGAL_CASE] + [
    {
        "keyword": """log: ("INFO" AND (a OR b""",
        "check_result": False,
        "prompt": """缺少 ), 你可能想输入: log: ("INFO" AND (a OR b))""",
    },
    {
        "keyword": """log: "INFO" AND a OR b)""",
        "check_result": False,
        "prompt": """多了 ), 你可能想输入: log: "INFO" AND a OR b""",
    },
]
QUOTE_CHECK_TEST_CASES = [LEGAL_CASE] + [
    {
        "keyword": """log:INFO' AND a OR b" """,
        "check_result": False,
        "prompt": """引号不匹配, 你可能想输入: log:'INFO' AND a OR "b" """,
    },
]
RANGE_CHECK_TEST_CASES = [LEGAL_CASE] + [
    {
        "keyword": """log: [100 TO 200 OR time: [100 TO 200] AND id: TO 100""",
        "check_result": False,
        "prompt": """RANGE语法异常, 格式错误, 你可能想输入: log: [100 TO 200] OR time: [100 TO 200] AND id: {* TO 100]""",
    },
    {
        "keyword": """log: [100 TO ] 200 OR time: [100 TO *]""",
        "check_result": False,
        "prompt": """RANGE语法异常, 格式错误, 你可能想输入: log: [100 TO 200] OR time: [100 TO *}""",
    },
    {
        "keyword": """gseindex: { 137677266 TO ]""",
        "check_result": False,
        "prompt": """RANGE语法异常, 格式错误, 你可能想输入: gseindex: { 137677266 TO *}""",
    },
]
FIELD_EXPR_TEST_CASES = [LEGAL_CASE] + [
    {
        "keyword": """log: [100 TO 200] AND : 100""",
        "fields": FIELDS,
        "check_result": False,
        "prompt": "缺少字段, 请补充字段",
    },
    {
        "keyword": """log: [100 TO 200] AND id: """,
        "fields": FIELDS,
        "check_result": False,
        "prompt": "字段id无查询内容, 请补齐查询内容",
    },
]
FIELD_EXIST_TEST_CASES = [LEGAL_CASE] + [
    {
        "keyword": """log: [100 TO 200] AND id_1: 1""",
        "fields": FIELDS,
        "check_result": False,
        "prompt": "字段id_1不存在, 请核对字段配置",
    }
]
RESERVED_CHAR_CHECK_TEST_CASES = [LEGAL_CASE] + [
    {
        "keyword": """+""",
        "fields": FIELDS,
        "check_result": False,
        "prompt": "未检测到查询内容, 请核对查询内容",
    },
    {
        "keyword": """log: &""",
        "fields": FIELDS,
        "check_result": False,
        "prompt": """该字段log已分词, 已自动忽略该符号'&', 参考案例: content: "id=11" 和 content: id=11, 结果不同""",
    },
]
FULL_WIDTH_CHAR_CHECK_TEST_CASES = [LEGAL_CASE] + [
    {
        "keyword": """log: 【 20 TO 100 】""",
        "fields": FIELDS,
        "check_result": False,
        "prompt": """检测到使用了全角字符【,】, 你可能想输入: log: [ 20 TO 100 ]""",
    },
]

NUMERIC_OPERATOR_CHECK_TEST_CASES = [LEGAL_CASE] + [
    {
        "keyword": """id: >>>>>>======<<<<<< 100""",
        "fields": FIELDS,
        "check_result": False,
        "prompt": """该字段id为数值类型, 不支持运算符'>>>>>>======<<<<<<', 请使用以下运算符: <,<=,>,>=,=""",
    }
]

NUMERIC_VALUE_CHECK_TEST_CASES = [LEGAL_CASE] + [
    {
        "keyword": """id: aaaaa""",
        "fields": FIELDS,
        "check_result": False,
        "prompt": """该字段id为数值类型, 请确认值的类型""",
    }
]

UNEXPECTED_LOGIC_OPERATOR_CHECK_TEST_CASES = [LEGAL_CASE] + [
    {
        "keyword": """log: INFO AND""",
        "fields": FIELDS,
        "check_result": False,
        "prompt": """多余的逻辑运算符AND, 你可能想输入: log: INFO""",
    }
]


FULL_CHECK_TEST_CASES = [
    {
        "keyword": KEYWORD,
        "fields": FIELDS,
        "check_result": {
            "is_legal": True,
            "is_resolved": True,
            "message": "",
            "keyword": KEYWORD,
        },
    },
    {
        "keyword": """log: ("INFO" AND (a OR b AND c OR d" AND id: AND id_1: 1""",
        "fields": FIELDS,
        "check_result": {
            "is_legal": False,
            "is_resolved": False,
            "message": """字段id_1不存在,字段id无查询内容,引号不匹配,缺少 )""",
            "keyword": """log: ("INFO" AND (a OR b AND c OR "d" AND id: AND id_1: 1))""",
        },
    },
    {
        "keyword": """log: [1 TO 9]}""",
        "fields": FIELDS,
        "check_result": {
            "is_legal": False,
            "is_resolved": True,
            "message": """RANGE语法异常, 格式错误""",
            "keyword": """log: [1 TO 9]""",
        },
    },
]


class TestLucene(TestCase):
    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.maxDiff = None  # pylint: disable=invalid-name

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
    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.maxDiff = None  # pylint: disable=invalid-name

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
    """
    测试增强Lucene Query在拆分关键字、更新关键字、检查关键字的行为
    """

    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.maxDiff = None  # pylint: disable=invalid-name

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


class TestLuceneChecker(TestCase):
    """
    测试Lucene检查器
    """

    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.maxDiff = None  # pylint: disable=invalid-name

    def test_pair_checker(self):
        for case in PARENTHESES_CHECK_TEST_CASES:
            checker = LuceneParenthesesChecker(case["keyword"], case.get("fields", []))
            checker.check()
            self.assertEqual(checker.check_result.legal, case["check_result"])
            self.assertEqual(checker.prompt(), case["prompt"])

        for case in QUOTE_CHECK_TEST_CASES:
            checker = LuceneQuotesChecker(case["keyword"], case.get("fields", []))
            checker.check()
            self.assertEqual(checker.check_result.legal, case["check_result"])
            checker.fix()
            self.assertEqual(checker.prompt(), case["prompt"])

    def test_range_checker(self):
        for case in RANGE_CHECK_TEST_CASES:
            checker = LuceneRangeChecker(case["keyword"], case.get("fields", []))
            checker.check()
            self.assertEqual(checker.check_result.legal, case["check_result"])
            checker.fix()
            self.assertEqual(checker.prompt(), case["prompt"])

    def test_lucene_field_checker(self):
        for case in FIELD_EXPR_TEST_CASES:
            checker = LuceneFieldExprChecker(case["keyword"], case.get("fields", []))
            checker.check()
            self.assertEqual(checker.check_result.legal, case["check_result"])
            checker.fix()
            self.assertEqual(checker.prompt(), case["prompt"])

        for case in FIELD_EXIST_TEST_CASES:
            checker = LuceneFieldExistChecker(case["keyword"], case.get("fields", []))
            checker.check()
            self.assertEqual(checker.check_result.legal, case["check_result"])
            checker.fix()
            self.assertEqual(checker.prompt(), case["prompt"])

    def test_reserved_char_checker(self):
        for case in RESERVED_CHAR_CHECK_TEST_CASES:
            checker = LuceneReservedCharChecker(case["keyword"], case.get("fields", []))
            checker.check()
            self.assertEqual(checker.check_result.legal, case["check_result"])
            checker.fix()
            self.assertEqual(checker.prompt(), case["prompt"])

    def test_full_width_char_checker(self):
        for case in FULL_WIDTH_CHAR_CHECK_TEST_CASES:
            checker = LuceneFullWidthChecker(case["keyword"], case.get("fields", []))
            checker.check()
            self.assertEqual(checker.check_result.legal, case["check_result"])
            checker.fix()
            self.assertEqual(checker.prompt(), case["prompt"])

    def test_numeric_operator_checker(self):
        for case in NUMERIC_OPERATOR_CHECK_TEST_CASES:
            checker = LuceneNumericOperatorChecker(case["keyword"], case.get("fields", []))
            checker.check()
            self.assertEqual(checker.check_result.legal, case["check_result"])
            checker.fix()
            self.assertEqual(checker.prompt(), case["prompt"])

    def test_numeric_value_checker(self):
        for case in NUMERIC_VALUE_CHECK_TEST_CASES:
            checker = LuceneNumericValueChecker(case["keyword"], case.get("fields", []))
            checker.check()
            self.assertEqual(checker.check_result.legal, case["check_result"])
            checker.fix()
            self.assertEqual(checker.prompt(), case["prompt"])

    def test_lucene_unexpected_logic_operator_checker(self):
        for case in UNEXPECTED_LOGIC_OPERATOR_CHECK_TEST_CASES:
            checker = LuceneUnexpectedLogicOperatorChecker(case["keyword"], case.get("fields", []))
            checker.check()
            self.assertEqual(checker.check_result.legal, case["check_result"])
            checker.fix()
            self.assertEqual(checker.prompt(), case["prompt"])

    def test_full_checker(self):
        for case in FULL_CHECK_TEST_CASES:
            checker = LuceneChecker(case["keyword"], case.get("fields", []))
            result = checker.resolve()
            self.assertDictEqual(result, case["check_result"])
