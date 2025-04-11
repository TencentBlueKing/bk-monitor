from django.test import TestCase

from apps.exceptions import GrepParseError
from apps.log_search.handlers.search.chart_handlers import ChartHandler
from apps.utils.grep_syntax_parse import grep_parser

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
    "egrep \"error|warning\"",
    "egrep \"https?://\"",
    "egrep \"[0-9]{4}-[0-9]{2}-[0-9]{2}\"",
    "egrep \"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}\"",
    "egrep \"ERR-([0-9]{3})\"",
    "egrep \"(start|end)[0-9]+\"",
    "egrep \"[0-9]{3}-[A-Z]{2}\"",
    r"grep $#&*a\ d",
    r"grep suc\.es.",
    r"grep ^suc*ess\*\^\$$",
    "grep \"er\\+or@?\"",
    "grep -i -v \"suc\\{1,2\\}ess\"",
    "grep \"suc+e?s{2{1,2}\"",
    "egrep \"suc\\+e\\?s\\{2{1,2}\"",
    "egrep \"s\\.s\\?c\\+e\\?s\\{2{1,2}a.*?\"",
]

GREP_RESULT_CASE = [
    [{"command": "grep", "args": [], "pattern": "error"}],
    [{"command": "grep", "args": [], "pattern": "error"}],
    [{"command": "egrep", "args": ["i"], "pattern": "WARNING"}],
    [{"command": "grep", "args": ["v"], "pattern": "debug"}],
    [{"command": "grep", "args": ["i"], "pattern": "error"}, {"command": "grep", "args": ["v"], "pattern": "test"}],
    [{"command": "grep", "args": [], "pattern": "hello\"world"}],
    [{"command": "grep", "args": ["i"], "pattern": "critical error"}],
    [
        {"command": "grep", "args": ["v"], "pattern": "info"},
        {"command": "egrep", "args": ["i"], "pattern": "error"},
        {"command": "grep", "args": [], "pattern": "failed"},
    ],
    [{"command": "grep", "args": ["v"], "pattern": "success"}],
    [{"command": "egrep", "args": ["i"], "pattern": "OOM"}, {"command": "grep", "args": ["v"], "pattern": "kill"}],
    [{"command": "egrep", "args": [], "pattern": "error|warning"}],
    [{"command": "grep", "args": [], "pattern": "https?://"}],
    [{"command": "grep", "args": [], "pattern": "192\\.168\\.[0-9]+\\.[0-9]+"}],
    [{"command": "egrep", "args": [], "pattern": "error|warning"}],
    [{"command": "egrep", "args": [], "pattern": "https?://"}],
    [{"command": "egrep", "args": [], "pattern": "[0-9]{4}-[0-9]{2}-[0-9]{2}"}],
    [{"command": "egrep", "args": [], "pattern": "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}"}],
    [{"command": "egrep", "args": [], "pattern": "ERR-([0-9]{3})"}],
    [{"command": "egrep", "args": [], "pattern": "(start|end)[0-9]+"}],
    [{"command": "egrep", "args": [], "pattern": "[0-9]{3}-[A-Z]{2}"}],
    [{"command": "grep", "args": [], "pattern": "$#&*a d"}],
    [{'command': 'grep', 'args': [], 'pattern': 'suc\\.es.'}],
    [{'command': 'grep', 'args': [], 'pattern': '^suc*ess\\*\\^\\$$'}],
    [{"command": "grep", "args": [], "pattern": "er+or@\\?"}],
    [{"command": "grep", "args": ['i', 'v'], "pattern": 'suc{1,2}ess'}],
    [{'command': 'grep', 'args': [], 'pattern': 'suc\\+e\\?s\\{2\\{1,2\\}'}],
    [{'command': 'egrep', 'args': [], 'pattern': 'suc\\+e\\?s\\{2{1,2}'}],
    [{'command': 'egrep', 'args': [], 'pattern': 's\\.s\\?c\\+e\\?s\\{2{1,2}a.*?'}],
]

WHERE_CLAUSE_RESULT = [
    "log REGEXP 'error'",
    "log REGEXP 'error'",
    "LOWER(log) REGEXP LOWER('WARNING')",
    "log NOT REGEXP 'debug'",
    "LOWER(log) REGEXP LOWER('error') AND log NOT REGEXP 'test'",
    "log REGEXP 'hello\"world'",
    "LOWER(log) REGEXP LOWER('critical error')",
    "log NOT REGEXP 'info' AND LOWER(log) REGEXP LOWER('error') AND log REGEXP 'failed'",
    "log NOT REGEXP 'success'",
    "LOWER(log) REGEXP LOWER('OOM') AND log NOT REGEXP 'kill'",
    "log REGEXP 'error|warning'",
    "log REGEXP 'https?://'",
    r"log REGEXP '192\.168\.[0-9]+\.[0-9]+'",
    "log REGEXP 'error|warning'",
    "log REGEXP 'https?://'",
    "log REGEXP '[0-9]{4}-[0-9]{2}-[0-9]{2}'",
    "log REGEXP '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}'",
    "log REGEXP 'ERR-([0-9]{3})'",
    "log REGEXP '(start|end)[0-9]+'",
    "log REGEXP '[0-9]{3}-[A-Z]{2}'",
    "log REGEXP '$#&*a d'",
    r"log REGEXP 'suc\.es.'",
    r"log REGEXP '^suc*ess\*\^\$$'",
    r"log REGEXP 'er+or@\?'",
    "LOWER(log) NOT REGEXP LOWER('suc{1,2}ess')",
    r"log REGEXP 'suc\+e\?s\{2\{1,2\}'",
    r"log REGEXP 'suc\+e\?s\{2{1,2}'",
    r"log REGEXP 's\.s\?c\+e\?s\{2{1,2}a.*?'",
]


class TestGrepLogic(TestCase):
    def test_grep_syntax(self):
        for i in range(len(GREP_SYNTAX_CASE) - 1):
            grep_result_case = grep_parser(GREP_SYNTAX_CASE[i])
            # 验证grep语法是否正确
            self.assertEqual(grep_result_case, GREP_RESULT_CASE[i])

            # 验证sql的where条件是否正确
            where_clause = ChartHandler.convert_to_where_clause(grep_result_case)
            self.assertEqual(where_clause, WHERE_CLAUSE_RESULT[i])

    def test_grep_exception_syntax(self):
        exception_syntax = "grep a b c"
        with self.assertRaises(GrepParseError):
            grep_parser(exception_syntax)
