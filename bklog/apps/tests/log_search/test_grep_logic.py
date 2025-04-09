from django.test import TestCase

from apps.log_search.handlers.search.doris_handlers import GrepParser

GREP_SYNTAX_CASE = [
    "grep 'hello'",
    "grep -i -v \"hello\"",
    "egrep -E \"pattern\"",
    "grep hello",
    "-i -v pattern",
    "grep -i \"hello\" | egrep -v -E world",
    "grep -i -v \"search term\" | egrep -E result | grep -i final",
]

GREP_RESULT_CASE = [
    [{"command": "grep", "args": [], "pattern": "hello"}],
    [{"command": "grep", "args": ["i", "v"], "pattern": 'hello'}],
    [{"command": "egrep", "args": ['E'], "pattern": "pattern"}],
    [{"command": "grep", "args": [], "pattern": "hello"}],
    [{"command": "grep", "args": ["i", "v"], "pattern": "pattern"}],
    [
        {"command": "grep", "args": ["i"], "pattern": "hello"},
        {"command": "egrep", "args": ["v", "E"], "pattern": "world"},
    ],
    [
        {"command": "grep", "args": ["i", "v"], "pattern": "search term"},
        {"command": "egrep", "args": ["E"], "pattern": 'result'},
        {"command": "grep", "args": ["i"], "pattern": "final"},
    ],
]


class TestGrepLogic(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grep_parser_obj = GrepParser()

    def test_grep_syntax(self):
        for i in range(len(GREP_SYNTAX_CASE)):
            # 验证grep语法是否正确
            self.assertEqual(self.grep_parser_obj.parse(GREP_SYNTAX_CASE[i]), GREP_RESULT_CASE[i])
