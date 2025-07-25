from django.test import TestCase
from unittest.mock import patch, MagicMock

from apps.exceptions import GrepParseError
from apps.log_search.handlers.search.chart_handlers import ChartHandler
from apps.log_search.utils import add_highlight_mark
from apps.utils.grep_syntax_parse import grep_parser


INDEX_SET_ID = 1
GREP_SYNTAX_CASE = [
    "error",
    'grep "error"',
    'egrep -i "WARNING"',
    'grep -v "debug"',
    'grep -i "error" | grep -v "test"',
    'grep "hello\\"world"',
    "grep -i critical\ error",
    'grep -v "info" | egrep -i "error" | grep   "failed"',
    '-v "success"',
    "egrep -i 'OOM' | grep -v \"kill\"",
    'egrep "error|warning"',
    'grep "https\\?://"',
    'grep "192\\.168\\.[0-9]\\+\\.[0-9]\\+"',
    'egrep "error|warning"',
    'egrep "https?://"',
    'egrep "[0-9]{4}-[0-9]{2}-[0-9]{2}"',
    'egrep "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}"',
    'egrep "ERR-([0-9]{3})"',
    'egrep "(start|end)[0-9]+"',
    'egrep "[0-9]{3}-[A-Z]{2}"',
    "grep $#&*a\ d",
    "grep suc\.es.",
    "grep ^suc*ess\*\^\$$",
    'grep "er\\+or@?"',
    'grep -i -v "suc\\{1,2\\}ess"',
    'grep "suc+e?s{2{1,2}"',
    'egrep "suc\\+e\\?s\\{2{1,2}"',
    'egrep "s\\.s\\?c\\+e\\?s\\{2{1,2}a.*?"',
    'grep -iv "xxx"',
    'grep -Ei -v "xxx"',
]

GREP_RESULT_CASE = [
    [{"command": "grep", "args": [], "pattern": "error"}],
    [{"command": "grep", "args": [], "pattern": "error"}],
    [{"command": "egrep", "args": ["i"], "pattern": "WARNING"}],
    [{"command": "grep", "args": ["v"], "pattern": "debug"}],
    [{"command": "grep", "args": ["i"], "pattern": "error"}, {"command": "grep", "args": ["v"], "pattern": "test"}],
    [{"command": "grep", "args": [], "pattern": 'hello"world'}],
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
    [{"command": "grep", "args": [], "pattern": "suc\\.es."}],
    [{"command": "grep", "args": [], "pattern": "^suc*ess\\*\\^\\$$"}],
    [{"command": "grep", "args": [], "pattern": "er+or@\\?"}],
    [{"command": "grep", "args": ["i", "v"], "pattern": "suc{1,2}ess"}],
    [{"command": "grep", "args": [], "pattern": "suc\\+e\\?s\\{2\\{1,2\\}"}],
    [{"command": "egrep", "args": [], "pattern": "suc\\+e\\?s\\{2{1,2}"}],
    [{"command": "egrep", "args": [], "pattern": "s\\.s\\?c\\+e\\?s\\{2{1,2}a.*?"}],
    [{"command": "grep", "args": ["iv"], "pattern": "xxx"}],
    [{"command": "egrep", "args": ["Ei", "v"], "pattern": "xxx"}],
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
    "log REGEXP '192\.168\.[0-9]+\.[0-9]+'",
    "log REGEXP 'error|warning'",
    "log REGEXP 'https?://'",
    "log REGEXP '[0-9]{4}-[0-9]{2}-[0-9]{2}'",
    "log REGEXP '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}'",
    "log REGEXP 'ERR-([0-9]{3})'",
    "log REGEXP '(start|end)[0-9]+'",
    "log REGEXP '[0-9]{3}-[A-Z]{2}'",
    "log REGEXP '$#&*a d'",
    "log REGEXP 'suc\.es.'",
    "log REGEXP '^suc*ess\*\^\$$'",
    "log REGEXP 'er+or@\?'",
    "LOWER(log) NOT REGEXP LOWER('suc{1,2}ess')",
    "log REGEXP 'suc\+e\?s\{2\{1,2\}'",
    "log REGEXP 'suc\+e\?s\{2{1,2}'",
    "log REGEXP 's\.s\?c\+e\?s\{2{1,2}a.*?'",
    "LOWER(log) NOT REGEXP LOWER('xxx')",
    "LOWER(log) NOT REGEXP LOWER('xxx')",
]

GREP_PARAMS = [
    {
        "grep_field": "id_alias",
        "grep_query": "egrep a",
        "alias_mappings": {"id_alias": "id"},
    },
    {
        "grep_field": "__ext.app.label",
        "grep_query": "egrep a",
        "alias_mappings": {"app_label": "__ext.app.label"},
    },
]

GREP_QUERY_RESULT = [
    "id REGEXP 'a'",
    "CAST(__ext['app']['label'] AS TEXT) REGEXP 'a'",
]


ORDER_BY_PARAMS = [
    {
        "sort_list": [["time", "asc"], ["container_id", "desc"]],
        "index_set_id": INDEX_SET_ID,
        "alias_mappings": {"id_alias": "id"},
    },
    {
        "sort_list": [["time", "asc"], ["app_label", "asc"]],
        "index_set_id": INDEX_SET_ID,
        "alias_mappings": {"app_label": "__ext.app.label"},
    },
]

ORDER_BY_RESULT = [
    " ORDER BY time ASC, container_id DESC",
    " ORDER BY time ASC, CAST(__ext['app']['label'] AS TEXT) ASC",
]

HIGHLIGHT_PARAMS = [
    {
        "data_list": [{"host_id": 21, "__ext": '{"container_id":"7df2fe1","labels":{"app":"dsa","component":"se"}}'}],
        "match_field": "host_id",
        "pattern": "1",
    },
    {
        "data_list": [{"host_id": 21, "__ext": '{"container_id":"7df2fe1","labels":{"app":"dsa","component":"se"}}'}],
        "match_field": "__ext.container_id",
        "pattern": "df",
    },
    {
        "data_list": [{"host_id": 21, "__ext": '{"container_id":"7df2fe1","labels":{"app":"dsa","component":"se"}}'}],
        "match_field": "__ext.labels.app",
        "pattern": "s",
    },
    {
        "data_list": [{"host_id": 21, "log": "123sasname age, des 1 ssa"}],
        "match_field": "log",
        "pattern": "name age",
    },
    {
        "data_list": [{"host_id": 21, "log": "123sasname age, 1 des ssa"}],
        "match_field": "log",
        "pattern": "name age, 1 des",
    },
]
HIGHLIGHT_RESULT = [
    [{"host_id": "2<mark>1</mark>", "__ext": '{"container_id":"7df2fe1","labels":{"app":"dsa","component":"se"}}'}],
    [{"host_id": 21, "__ext": '{"container_id": "7<mark>df</mark>2fe1", "labels": {"app": "dsa", "component": "se"}}'}],
    [{"host_id": 21, "__ext": '{"container_id": "7df2fe1", "labels": {"app": "d<mark>s</mark>a", "component": "se"}}'}],
    [{"host_id": 21, "log": "123sas<mark>name age</mark>, des 1 ssa"}],
    [{"host_id": 21, "log": "123sas<mark>name age, 1 des</mark> ssa"}],
]


class TestGrepLogic(TestCase):
    GREP_FIELD = "log"

    def test_grep_syntax(self):
        for i in range(len(GREP_SYNTAX_CASE)):
            grep_result_case = grep_parser(GREP_SYNTAX_CASE[i])
            # 验证grep语法是否正确
            self.assertEqual(grep_result_case, GREP_RESULT_CASE[i])

            # 验证sql的where条件是否正确
            where_clause = ChartHandler.convert_to_where_clause(self.GREP_FIELD, grep_result_case)
            self.assertEqual(where_clause, WHERE_CLAUSE_RESULT[i])

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
        for grep_param, grep_query_result in zip(GREP_PARAMS, GREP_QUERY_RESULT):
            grep_condition_dict = instance.get_grep_condition(**grep_param)
            result = grep_condition_dict["grep_where_clause"]
            self.assertEqual(result, grep_query_result)

    @patch("apps.log_search.models.LogIndexSet.objects.get")
    def test_get_order_by_clause(self, mock_log_index_get):
        mock_data = MagicMock()
        mock_data.support_doris = 1
        mock_data.doris_table_id = "x"
        mock_log_index_get.return_value = mock_data
        instance = ChartHandler.get_instance(index_set_id=INDEX_SET_ID, mode="sql")
        for order_by_param, order_by_result in zip(ORDER_BY_PARAMS, ORDER_BY_RESULT):
            result = instance.get_order_by_clause(**order_by_param)
            self.assertEqual(result, order_by_result)

    def test_add_highlight_mark(self):
        for highlight_param, highlight_result in zip(HIGHLIGHT_PARAMS, HIGHLIGHT_RESULT):
            result = add_highlight_mark(**highlight_param)
            self.assertEqual(result, highlight_result)
