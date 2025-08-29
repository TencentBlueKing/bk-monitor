from django.test import TestCase
from unittest.mock import patch, MagicMock

from apps.exceptions import GrepParseError
from apps.log_search.handlers.search.chart_handlers import ChartHandler
from apps.log_search.utils import add_highlight_mark
from apps.utils.grep_syntax_parse import grep_parser


INDEX_SET_ID = 1

GREP_TEST_CASE = [
    {
        "grep_syntax": "error",
        "grep_result": [{"command": "grep", "args": [], "pattern": "error"}],
        "where_clause": "log LIKE '%error%'",
    },
    {
        "grep_syntax": 'grep "error"',
        "grep_result": [{"command": "grep", "args": [], "pattern": "error"}],
        "where_clause": "log LIKE '%error%'",
    },
    {
        "grep_syntax": 'egrep -i "WARNING"',
        "grep_result": [{"command": "egrep", "args": ["i"], "pattern": "WARNING"}],
        "where_clause": "LOWER(log) REGEXP LOWER('WARNING')",
    },
    {
        "grep_syntax": 'grep -v "debug"',
        "grep_result": [{"command": "grep", "args": ["v"], "pattern": "debug"}],
        "where_clause": "log NOT LIKE '%debug%'",
    },
    {
        "grep_syntax": 'grep -i "error" | grep -v "test"',
        "grep_result": [
            {"command": "grep", "args": ["i"], "pattern": "error"},
            {"command": "grep", "args": ["v"], "pattern": "test"},
        ],
        "where_clause": "LOWER(log) LIKE LOWER('%error%') AND log NOT LIKE '%test%'",
    },
    {
        "grep_syntax": 'grep "hello\\"world"',
        "grep_result": [{"command": "grep", "args": [], "pattern": 'hello"world'}],
        "where_clause": "log LIKE '%hello\"world%'",
    },
    {
        "grep_syntax": 'grep "a|b|c"',
        "grep_result": [{"command": "grep", "args": [], "pattern": "a|b|c"}],
        "where_clause": "log LIKE '%a|b|c%'",
    },
    {
        "grep_syntax": 'grep "a\\|b\\|c"',
        "grep_result": [{"command": "grep", "args": [], "pattern": "a\\|b\\|c"}],
        "where_clause": "log LIKE '%a\\|b\\|c%'",
    },
    {
        "grep_syntax": '-v "success"',
        "grep_result": [{"command": "grep", "args": ["v"], "pattern": "success"}],
        "where_clause": "log NOT LIKE '%success%'",
    },
    {
        "grep_syntax": 'grep -v "info" | egrep -i "error" | grep   "failed"',
        "grep_result": [
            {"command": "grep", "args": ["v"], "pattern": "info"},
            {"command": "egrep", "args": ["i"], "pattern": "error"},
            {"command": "grep", "args": [], "pattern": "failed"},
        ],
        "where_clause": "log NOT LIKE '%info%' AND LOWER(log) REGEXP LOWER('error') AND log LIKE '%failed%'",
    },
    {
        "grep_syntax": "egrep -i 'OOM' | grep -v \"kill\"",
        "grep_result": [
            {"command": "egrep", "args": ["i"], "pattern": "OOM"},
            {"command": "grep", "args": ["v"], "pattern": "kill"},
        ],
        "where_clause": "LOWER(log) REGEXP LOWER('OOM') AND log NOT LIKE '%kill%'",
    },
    {
        "grep_syntax": 'egrep "error|warning"',
        "grep_result": [{"command": "egrep", "args": [], "pattern": "error|warning"}],
        "where_clause": "log REGEXP 'error|warning'",
    },
    {
        "grep_syntax": 'grep "https\\?://"',
        "grep_result": [{"command": "grep", "args": [], "pattern": "https\\?://"}],
        "where_clause": "log LIKE '%https\\?://%'",
    },
    {
        "grep_syntax": 'grep "192.168.\\[0-9\\]+.\\[0-9\\]+"',
        "grep_result": [{"command": "grep", "args": [], "pattern": "192.168.\\[0-9\\]+.\\[0-9\\]+"}],
        "where_clause": "log LIKE '%192.168.\\[0-9\\]+.\\[0-9\\]+%'",
    },
    {
        "grep_syntax": 'grep "192\\.168\\.[0-9]\\+\\.[0-9]\\+"',
        "grep_result": [{"command": "grep", "args": [], "pattern": "192\\.168\\.[0-9]\\+\\.[0-9]\\+"}],
        "where_clause": "log LIKE '%192\\.168\\.[0-9]\\+\\.[0-9]\\+%'",
    },
    {
        "grep_syntax": 'egrep "error|warning"',
        "grep_result": [{"command": "egrep", "args": [], "pattern": "error|warning"}],
        "where_clause": "log REGEXP 'error|warning'",
    },
    {
        "grep_syntax": 'egrep "https?://"',
        "grep_result": [{"command": "egrep", "args": [], "pattern": "https?://"}],
        "where_clause": "log REGEXP 'https?://'",
    },
    {
        "grep_syntax": 'egrep "[0-9]{4}-[0-9]{2}-[0-9]{2}"',
        "grep_result": [{"command": "egrep", "args": [], "pattern": "[0-9]{4}-[0-9]{2}-[0-9]{2}"}],
        "where_clause": "log REGEXP '[0-9]{4}-[0-9]{2}-[0-9]{2}'",
    },
    {
        "grep_syntax": 'egrep "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}"',
        "grep_result": [{"command": "egrep", "args": [], "pattern": "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}"}],
        "where_clause": "log REGEXP '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\\\.[a-zA-Z]{2,}'",
    },
    {
        "grep_syntax": 'egrep "ERR-([0-9]{3})"',
        "grep_result": [{"command": "egrep", "args": [], "pattern": "ERR-([0-9]{3})"}],
        "where_clause": "log REGEXP 'ERR-([0-9]{3})'",
    },
    {
        "grep_syntax": 'egrep "(start|end)[0-9]+"',
        "grep_result": [{"command": "egrep", "args": [], "pattern": "(start|end)[0-9]+"}],
        "where_clause": "log REGEXP '(start|end)[0-9]+'",
    },
    {
        "grep_syntax": 'egrep "[0-9]{3}-[A-Z]{2}"',
        "grep_result": [{"command": "egrep", "args": [], "pattern": "[0-9]{3}-[A-Z]{2}"}],
        "where_clause": "log REGEXP '[0-9]{3}-[A-Z]{2}'",
    },
    {
        "grep_syntax": "grep $#&*a\ d",
        "grep_result": [{"command": "grep", "args": [], "pattern": "$#&*a d"}],
        "where_clause": "log LIKE '%$#&*a d%'",
    },
    {
        "grep_syntax": "grep suc\.es.",
        "grep_result": [{"command": "grep", "args": [], "pattern": "suc\\.es."}],
        "where_clause": "log LIKE '%suc\\.es.%'",
    },
    {
        "grep_syntax": "grep ^suc*ess\*\^\$$",
        "grep_result": [{"command": "grep", "args": [], "pattern": "^suc*ess\\*\\^\\$$"}],
        "where_clause": "log LIKE '%^suc*ess\\*\\^\\$$%'",
    },
    {
        "grep_syntax": 'grep "er\\+or@?"',
        "grep_result": [{"command": "grep", "args": [], "pattern": "er\\+or@?"}],
        "where_clause": "log LIKE '%er\\+or@?%'",
    },
    {
        "grep_syntax": 'grep -i -v "suc{1,2}ess"',
        "grep_result": [{"command": "grep", "args": ["i", "v"], "pattern": "suc{1,2}ess"}],
        "where_clause": "LOWER(log) NOT LIKE LOWER('%suc{1,2}ess%')",
    },
    {
        "grep_syntax": 'grep "suc+e?s{2{1,2}"',
        "grep_result": [{"command": "grep", "args": [], "pattern": "suc+e?s{2{1,2}"}],
        "where_clause": "log LIKE '%suc+e?s{2{1,2}%'",
    },
    {
        "grep_syntax": 'egrep "suc\\+e\\?s\\{2{1,2}"',
        "grep_result": [{"command": "egrep", "args": [], "pattern": "suc\\+e\\?s\\{2{1,2}"}],
        "where_clause": "log REGEXP 'suc\\\\+e\\\\?s\\\\{2{1,2}'",
    },
    {
        "grep_syntax": 'egrep "s\\.s\\?c\\+e\\?s\\{2{1,2}a.*?"',
        "grep_result": [{"command": "egrep", "args": [], "pattern": "s\\.s\\?c\\+e\\?s\\{2{1,2}a.*?"}],
        "where_clause": "log REGEXP 's\\\\.s\\\\?c\\\\+e\\\\?s\\\\{2{1,2}a.*?'",
    },
    {
        "grep_syntax": 'grep -iv "xxx"',
        "grep_result": [{"command": "grep", "args": ["iv"], "pattern": "xxx"}],
        "where_clause": "LOWER(log) NOT LIKE LOWER('%xxx%')",
    },
    {
        "grep_syntax": 'grep -Ei -v "xxx"',
        "grep_result": [{"command": "egrep", "args": ["Ei", "v"], "pattern": "xxx"}],
        "where_clause": "LOWER(log) NOT REGEXP LOWER('xxx')",
    },
    {
        "grep_syntax": "grep 'abc'def'",
        "grep_result": [{"command": "grep", "args": [], "pattern": "abc'def"}],
        "where_clause": "log LIKE '%abc''def%'",
    },
]


GREP_PARAMS = [
    {
        "grep_field": "id_alias",
        "grep_query": "egrep a",
        "alias_mappings": {"id_alias": "id"},
        "excepted": "id REGEXP 'a'",
    },
    {
        "grep_field": "__ext.app.label",
        "grep_query": "egrep a",
        "alias_mappings": {"app_label": "__ext.app.label"},
        "excepted": "CAST(__ext['app']['label'] AS TEXT) REGEXP 'a'",
    },
]


ORDER_BY_PARAMS = [
    {
        "sort_list": [["time", "asc"], ["container_id", "desc"]],
        "index_set_id": INDEX_SET_ID,
        "alias_mappings": {"id_alias": "id"},
        "excepted": " ORDER BY time ASC, container_id DESC",
    },
    {
        "sort_list": [["time", "asc"], ["app_label", "asc"]],
        "index_set_id": INDEX_SET_ID,
        "alias_mappings": {"app_label": "__ext.app.label"},
        "excepted": " ORDER BY time ASC, CAST(__ext['app']['label'] AS TEXT) ASC",
    },
]

HIGHLIGHT_PARAMS = [
    {
        "data_list": [{"host_id": 21, "__ext": '{"container_id":"7df2fe1","labels":{"app":"dsa","component":"se"}}'}],
        "match_field": "host_id",
        "grep_query": "1",
        "excepted": [
            {
                "host_id": "2<mark>1</mark>",
                "__ext": '{"container_id":"7df2fe1","labels":{"app":"dsa","component":"se"}}',
            }
        ],
    },
    {
        "data_list": [{"host_id": 21, "__ext": '{"container_id":"7df2fe1","labels":{"app":"dsa","component":"se"}}'}],
        "match_field": "__ext.container_id",
        "grep_query": "df",
        "excepted": [
            {
                "host_id": 21,
                "__ext": '{"container_id": "7<mark>df</mark>2fe1", "labels": {"app": "dsa", "component": "se"}}',
            }
        ],
    },
    {
        "data_list": [{"host_id": 21, "__ext": '{"container_id":"7df2fe1","labels":{"app":"dsa","component":"se"}}'}],
        "match_field": "__ext.labels.app",
        "grep_query": "s",
        "excepted": [
            {
                "host_id": 21,
                "__ext": '{"container_id": "7df2fe1", "labels": {"app": "d<mark>s</mark>a", "component": "se"}}',
            }
        ],
    },
    {
        "data_list": [{"host_id": 21, "log": "123sasname age, des 1 ssa"}],
        "match_field": "log",
        "grep_query": '"name age"',
        "excepted": [{"host_id": 21, "log": "123sas<mark>name age</mark>, des 1 ssa"}],
    },
    {
        "data_list": [{"host_id": 21, "log": "123sasname age, 1 des ssa"}],
        "match_field": "log",
        "grep_query": '"name age, 1 des"',
        "excepted": [{"host_id": 21, "log": "123sas<mark>name age, 1 des</mark> ssa"}],
    },
    {
        "data_list": [{"host_id": 21, "log": "123sasname age, 1 des ssa"}],
        "match_field": "log",
        "grep_query": '-i "NAME"',
        "excepted": [{"host_id": 21, "log": "123sas<mark>name</mark> age, 1 des ssa"}],
    },
    {
        "data_list": [{"host_id": 21, "log": "123sasname age, 1 des ssa"}],
        "match_field": "log",
        "grep_query": "-E '\d+'",
        "excepted": [{"host_id": 21, "log": "<mark>123</mark>sasname age, <mark>1</mark> des ssa"}],
    },
]


class TestGrepLogic(TestCase):
    GREP_FIELD = "log"

    def test_grep_syntax(self):
        for case in GREP_TEST_CASE:
            grep_result_case = grep_parser(case["grep_syntax"])
            # 验证grep语法是否正确
            self.assertEqual(grep_result_case, case["grep_result"])

            # 验证sql的where条件是否正确
            where_clause = ChartHandler.convert_to_where_clause(self.GREP_FIELD, grep_result_case)
            self.assertEqual(where_clause, case["where_clause"])

    def test_grep_exception_syntax(self):
        exception_syntax = "grep a b c"
        with self.assertRaises(GrepParseError):
            grep_parser(exception_syntax)

    @patch("apps.log_search.models.LogIndexSet.objects.get")
    def test_get_grep_condition(self, mock_log_index_get):
        mock_data = MagicMock()
        mock_data.support_doris = 1
        mock_data.doris_table_id = "x"
        mock_log_index_get.return_value = mock_data
        instance = ChartHandler.get_instance(index_set_id=INDEX_SET_ID, mode="sql")
        for param in GREP_PARAMS:
            result = instance.get_grep_condition(
                grep_nodes=grep_parser(param["grep_query"]),
                grep_field=param["grep_field"],
                alias_mappings=param["alias_mappings"],
            )
            self.assertEqual(result, param["excepted"])

    @patch("apps.log_search.models.LogIndexSet.objects.get")
    def test_get_order_by_clause(self, mock_log_index_get):
        mock_data = MagicMock()
        mock_data.support_doris = 1
        mock_data.doris_table_id = "x"
        mock_log_index_get.return_value = mock_data
        instance = ChartHandler.get_instance(index_set_id=INDEX_SET_ID, mode="sql")
        for param in ORDER_BY_PARAMS:
            result = instance.get_order_by_clause(
                sort_list=param["sort_list"],
                index_set_id=param["index_set_id"],
                alias_mappings=param["alias_mappings"],
            )
            self.assertEqual(result, param["excepted"])

    def test_add_highlight_mark(self):
        for param in HIGHLIGHT_PARAMS:
            result = add_highlight_mark(
                data_list=param["data_list"],
                match_field=param["match_field"],
                grep_nodes=grep_parser(param["grep_query"]),
            )
            self.assertEqual(result, param["excepted"])
