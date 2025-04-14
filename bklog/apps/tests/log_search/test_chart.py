from django.test import TestCase

from apps.log_search.constants import SQL_PREFIX, SQL_SUFFIX
from apps.log_search.handlers.search.chart_handlers import ChartHandler

SEARCH_PARAMS = [
    {
        "keyword": "title:\"Pyth?n\"",
        "start_time": 1732220441,
        "end_time": 1732820443,
        "addition": [
            {"field": "bk_host_id", "operator": "=", "value": ["1", "2"]},
        ],
    },
    {
        "sql": "SELECT thedate, log, time LIMIT 10",
        "keyword": "title:\"Pyth?n\" OR title:/[Pp]ython.*/ AND __ext.bcs_id: \"test\"",
        "start_time": 1732220441,
        "end_time": 1732820443,
        "addition": [
            {"field": "bk_host_id", "operator": "=", "value": ["1", "2"]},
            {"field": "service", "operator": "!=", "value": ["php"]},
            {"field": "count", "operator": "<", "value": [100]},
            {"field": "index", "operator": ">", "value": [500]},
            {"field": "number", "operator": ">=", "value": [100]},
            {"field": "id", "operator": "<=", "value": [500]},
            {"field": "gseIndex", "operator": "=~", "value": ["?proz/Saved/Logs/ProjectA_2024.10.20-23.17.50*"]},
            {"field": "path", "operator": "!=~", "value": ["?app/*/python."]},
            {"field": "cloudId", "operator": "contains", "value": ["6", "9"]},
            {"field": "cloudId", "operator": "not contains", "value": ["1", "3"]},
            {"field": "is_deleted", "operator": "is false", "value": []},
            {"field": "flag", "operator": "is true", "value": [1]},
            {"field": "log", "operator": "contains match phrase", "value": ["html", "css"]},
            {"field": "log", "operator": "not contains match phrase", "value": ["js"]},
            {"field": "log", "operator": "all contains match phrase", "value": ["success", "200"]},
            {"field": "log", "operator": "all not contains match phrase", "value": ["error", "500"]},
            {"field": "describe", "operator": "&=~", "value": ["?el*", "wor?d"]},
            {"field": "theme", "operator": "&!=~", "value": ["pg*", "?h?"]},
            {"field": "name", "operator": "=", "value": ["he'll'o", "world'"]},
            {"field": "*", "operator": "=", "value": ["error"]},
            {"field": "query_string", "operator": "=", "value": ["error"]},
            {"field": "__ext.bcs_id", "operator": "=", "value": ["BCS-1", "BCS-2"]},
            {"field": "__ext.bcs_id", "operator": "!=", "value": ["BCS-3", "BCS-4"]},
            {"field": "__ext.label.component", "operator": "contains", "value": ["ds", "py"]},
            {"field": "__ext.label.component", "operator": "not contains", "value": ["a"]},
        ],
    },
]


SQL_RESULT = [
    f"{SQL_PREFIX} {SQL_SUFFIX}",
    "SELECT thedate, log, time  LIMIT 10",
]


WHERE_CLAUSE_CASE = [
    "*",
    "success",
    "\"\"",
    "\"002\" OR error",
    "year:[2020 TO 2023]",
    "title:/[Pp]ython.*/",
    "title:Pyth?n",
    "(name:John AND name: 6 OR name: \"7\") AND (python OR \"django\")",
    "__ext.bcs_id: 1 OR __ext.bcs_id: \"ts\"",
    "NOT log: \"ts\" AND -a : \"b\"",
    "span_id:(6cee80d18 OR \"c866d58ac1\") AND (-log:\"a\" OR NOT a:b)",
    "(index: >=200 OR index: <100) AND id: <10 AND age: >18",
    "log: (1 OR \"abc\" OR \"xxx\" AND 111)",
    "ID: (\"abc\" OR (\"cde\" AND \"ddd\"))",
    "ID: ((\"a\" AND b) OR \"d\" AND 2 AND 3 AND (4 OR 5))",
    "log: ((\"a\" OR (\"b\" OR \"c\")) AND \"d\") AND -name: test",
    "log: ((\"a\" OR (\"b\" OR \"c\")) OR \"d\") AND -name: test",
    "log: ((\"a\" AND b) OR \"c\" AND \"d\")",
    "log: (\"a\" OR (\"b\" OR \"c\")) AND (1 OR 2 AND 3) OR \"f\" AND \"g\"",
    "ID: (\"abc\" AND 5 OR 6 AND (\"cde\" AND \"ddd\") AND (1 AND 2))",
    "ID: (\"abc\" OR 5 AND 6 AND (\"cde\" AND \"ddd\") AND (1 OR 2))",
]
WHERE_CLAUSE_RESULT = [
    "log LIKE '%'",
    "log LIKE '%success%'",
    "log MATCH_PHRASE \"\"",
    "log MATCH_PHRASE \"002\" OR log LIKE '%error%'",
    "year BETWEEN 2020 AND 2023",
    "title REGEXP '[Pp]ython.*'",
    "title LIKE '%Pyth_n%'",
    "(name LIKE '%John%' AND name LIKE '%6%' OR name = \"7\") AND (log LIKE '%python%' OR log MATCH_PHRASE \"django\")",
    "CAST(__ext['bcs_id'] AS TEXT) LIKE '%1%' OR CAST(__ext['bcs_id'] AS TEXT) = \"ts\"",
    "NOT log MATCH_PHRASE \"ts\" AND NOT a = \"b\"",
    "(span_id LIKE '%6cee80d18%' OR span_id = \"c866d58ac1\") AND (NOT log MATCH_PHRASE \"a\" OR NOT a LIKE '%b%')",
    "(index >=200 OR index <100) AND id <10 AND age >18",
    "(log MATCH_PHRASE \"xxx\" AND log LIKE '%111%' OR (log LIKE '%1%' OR log MATCH_PHRASE \"abc\"))",
    "((ID = \"cde\" AND ID = \"ddd\") OR ID = \"abc\")",
    "((ID = \"a\" AND ID LIKE '%b%') OR ID = \"d\" AND ID LIKE '%2%' AND ID LIKE '%3%' AND "
    "(ID LIKE '%4%' OR ID LIKE '%5%'))",
    "((log MATCH_PHRASE \"b\" OR log MATCH_PHRASE \"c\") OR log MATCH_PHRASE \"a\") AND "
    "log MATCH_PHRASE \"d\" AND NOT name LIKE '%test%'",
    "(((log MATCH_PHRASE \"b\" OR log MATCH_PHRASE \"c\") OR log MATCH_PHRASE \"a\") OR "
    "log MATCH_PHRASE \"d\") AND NOT name LIKE '%test%'",
    "((log MATCH_PHRASE \"a\" AND log LIKE '%b%') OR log MATCH_PHRASE \"c\" AND log MATCH_PHRASE \"d\")",
    "((log MATCH_PHRASE \"b\" OR log MATCH_PHRASE \"c\") OR log MATCH_PHRASE \"a\") AND "
    "(log LIKE '%1%' OR log LIKE '%2%' AND log LIKE '%3%') OR log MATCH_PHRASE \"f\" AND log MATCH_PHRASE \"g\"",
    "(ID = \"abc\" AND ID LIKE '%5%' OR ID LIKE '%6%' AND (ID = \"cde\" AND ID = \"ddd\") AND "
    "(ID LIKE '%1%' AND ID LIKE '%2%'))",
    "(ID LIKE '%5%' AND ID LIKE '%6%' AND (ID = \"cde\" AND ID = \"ddd\") AND "
    "(ID LIKE '%1%' OR ID LIKE '%2%') OR ID = \"abc\")",
]


class TestChart(TestCase):
    def test_generate_sql(self):
        for search_param, sql_result in zip(SEARCH_PARAMS, SQL_RESULT):
            start_time = search_param["start_time"]
            end_time = search_param["end_time"]
            addition = search_param["addition"]
            sql_param = search_param.get("sql")
            keyword = search_param.get("keyword")
            data = ChartHandler.generate_sql(
                addition=addition,
                start_time=start_time,
                end_time=end_time,
                sql_param=sql_param,
                keyword=keyword,
            )
            self.maxDiff = None
            self.assertEqual(data["sql"], sql_result)

    def test_lucene_to_where_clause(self):
        for where_clause_case, where_clause_result in zip(WHERE_CLAUSE_CASE, WHERE_CLAUSE_RESULT):
            result = ChartHandler.lucene_to_where_clause(where_clause_case)
            self.assertEqual(result, where_clause_result)
