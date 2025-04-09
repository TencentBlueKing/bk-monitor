from django.test import TestCase

from apps.log_search.handlers.search.doris_handlers import GrepParser

GREP_SYNTAX_CASE = [
    "error",
    "grep \"error\"",
    "egrep -i \"WARNING\"",
    "grep -v \"debug\"",
    "grep -i \"error\" | grep -v \"test\"",
    "grep \"hello\\\"world\"",
    r"grep -i critical\ error",
    "grep -v \"info\" | egrep -i \"error\" | grep \"failed\"",
    "-v \"success\"",
    "egrep -i 'OOM' | grep -v \"kill\"",
    "egrep \"error|warning\"",
    "grep \"https\\?://\"",
    "grep \"192\\.168\\.[0-9]\\+\\.[0-9]\\+\"",
]

GREP_RESULT_CASE = [
    [{'command': 'grep', 'args': [], 'pattern': 'error'}],
    [{'command': 'grep', 'args': [], 'pattern': 'error'}],
    [{'command': 'egrep', 'args': ['i'], 'pattern': 'WARNING'}],
    [{'command': 'grep', 'args': ['v'], 'pattern': 'debug'}],
    [{'command': 'grep', 'args': ['i'], 'pattern': 'error'}, {'command': 'grep', 'args': ['v'], 'pattern': 'test'}],
    [{'command': 'grep', 'args': [], 'pattern': 'hello"world'}],
    [{'command': 'grep', 'args': ['i'], 'pattern': 'critical error'}],
    [
        {'command': 'grep', 'args': ['v'], 'pattern': 'info'},
        {'command': 'egrep', 'args': ['i'], 'pattern': 'error'},
        {'command': 'grep', 'args': [], 'pattern': 'failed'},
    ],
    [{'command': 'grep', 'args': ['v'], 'pattern': 'success'}],
    [{'command': 'egrep', 'args': ['i'], 'pattern': 'OOM'}, {'command': 'grep', 'args': ['v'], 'pattern': 'kill'}],
    [{'command': 'egrep', 'args': [], 'pattern': 'error|warning'}],
    [{'command': 'grep', 'args': [], 'pattern': 'https?://'}],
    [{'command': 'grep', 'args': [], 'pattern': '192.168.[0-9]+.[0-9]+'}],
    [{'command': 'egrep', 'args': [], 'pattern': 'error|warning'}],
]


class TestGrepLogic(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grep_parser_obj = GrepParser()

    def test_grep_syntax(self):
        for i in range(len(GREP_SYNTAX_CASE)):
            # 验证grep语法是否正确
            self.assertEqual(self.grep_parser_obj.parse(GREP_SYNTAX_CASE[i]), GREP_RESULT_CASE[i])
