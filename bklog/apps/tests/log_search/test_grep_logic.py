from django.test import TestCase

from apps.utils.grep_syntax_parse import convert_to_where_clause, grep_parser

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
    "grep a b c",  # 异常情况
    r"grep $#&*a\ d",
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
    [{"command": "grep", "args": [], "pattern": "c"}],
    [{"command": "grep", "args": [], "pattern": "$#&*a d"}],
]

WHERE_CLAUSE_RESULT = [
    "WHERE log REGEXP 'error'",
    "WHERE log REGEXP 'error'",
    "WHERE LOWER(log) REGEXP 'WARNING'",
    "WHERE log NOT REGEXP 'debug'",
    "WHERE LOWER(log) REGEXP 'error' AND log NOT REGEXP 'test'",
    "WHERE log REGEXP 'hello\"world'",
    "WHERE LOWER(log) REGEXP 'critical error'",
    "WHERE log NOT REGEXP 'info' AND LOWER(log) REGEXP 'error' AND log REGEXP 'failed'",
    "WHERE log NOT REGEXP 'success'",
    "WHERE LOWER(log) REGEXP 'OOM' AND log NOT REGEXP 'kill'",
    "WHERE log REGEXP 'error|warning'",
    "WHERE log REGEXP 'https?://'",
    r"WHERE log REGEXP '192\.168\.[0-9]+\.[0-9]+'",
    "WHERE log REGEXP 'error|warning'",
    "WHERE log REGEXP 'https?://'",
    "WHERE log REGEXP '[0-9]{4}-[0-9]{2}-[0-9]{2}'",
    "WHERE log REGEXP '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}'",
    "WHERE log REGEXP 'ERR-([0-9]{3})'",
    "WHERE log REGEXP '(start|end)[0-9]+'",
    "WHERE log REGEXP '[0-9]{3}-[A-Z]{2}'",
    "WHERE log REGEXP 'c'",
    "WHERE log REGEXP '$#&*a d'",
]


class TestGrepLogic(TestCase):
    def test_grep_syntax(self):
        for i in range(len(GREP_SYNTAX_CASE)):
            grep_result_case = grep_parser(GREP_SYNTAX_CASE[i])
            # 验证grep语法是否正确
            self.assertEqual(grep_result_case, GREP_RESULT_CASE[i])

            # 验证sql的where条件是否正确
            where_clause = convert_to_where_clause(grep_result_case)
            self.assertEqual(where_clause, WHERE_CLAUSE_RESULT[i])
