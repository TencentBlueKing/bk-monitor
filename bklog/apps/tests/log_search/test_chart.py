from django.test import TestCase

from apps.log_search.constants import SQL_PREFIX, SQL_SUFFIX
from apps.log_search.handlers.search.chart_handlers import ChartHandler

SEARCH_PARAMS = [
    {
        "keyword": 'title:"Pyth?n"',
        "start_time": 1732220441,
        "end_time": 1732820443,
        "addition": [
            {"field": "bk_host_id", "operator": "=", "value": ["1", "2"]},
        ],
    },
    {
        "sql": "SELECT thedate, log, time LIMIT 10",
        "keyword": 'title:"Pyth?n" OR title:/[Pp]ython.*/ AND __ext.bcs_id: "test"',
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
    {
        "keyword": 'log : * and year:[2020 TO 2023] AND "abc" AND def',
        "start_time": 1732220441,
        "end_time": 1732820443,
        "sql": "SELECT thedate, dtEventTimeStamp, iterationIndex, log, time FROM xx.x1 WHERE a=1 or b=2 LIMIT 10",
        "addition": [
            {"field": "bk_host_id", "operator": "=", "value": ["x1", "x2"]},
            {"field": "is_deleted", "operator": "is true", "value": []},
        ],
    },
    {
        "keyword": 'title:"Python Programming" AND (author:John AND author: 6 OR author: "7")',
        "start_time": 1732220441,
        "end_time": 1732820443,
        "sql": "SELECT thedate, dtEventTimeStamp, log WHERE a=1 or b=2 LIMIT 10",
        "addition": [
            {"field": "bk_host_id", "operator": "=", "value": ["x1", "x2"]},
            {"field": "is_deleted", "operator": "is true", "value": []},
        ],
    },
]


SQL_RESULT = [
    f"{SQL_PREFIX} {SQL_SUFFIX}",
    "SELECT thedate, log, time LIMIT 10",
    "SELECT thedate, dtEventTimeStamp, iterationIndex, log, time FROM xx.x1 WHERE a=1 or b=2 LIMIT 10",
    "SELECT thedate, dtEventTimeStamp, log WHERE a=1 or b=2 LIMIT 10",
]


WHERE_CLAUSE = [
    (
        "WHERE thedate >= 20241121 AND thedate <= 20241128 "
        "AND "
        "dtEventTimeStamp >= 1732220441 "
        "AND "
        "dtEventTimeStamp <= 1732820443"
        " AND "
        'title1 = "Pyth?n"'
        " AND "
        "(bk_host_id = '1' OR bk_host_id = '2')"
    ),
    (
        "WHERE thedate >= 20241121 AND thedate <= 20241128 "
        "AND "
        "dtEventTimeStamp >= 1732220441 AND dtEventTimeStamp <= 1732820443"
        " AND "
        "title1 = \"Pyth?n\" OR title1 REGEXP '[Pp]ython.*'"
        " AND "
        "CAST(__ext['bcs_id'] AS TEXT) = \"test\""
        " AND "
        "(bk_host_id = '1' OR bk_host_id = '2')"
        " AND "
        "service != 'php'"
        " AND "
        "count < 100"
        " AND "
        "index > 500"
        " AND "
        "number >= 100"
        " AND "
        "id <= 500"
        " AND "
        "LOWER(gseIndex) LIKE LOWER('%_proz/Saved/Logs/ProjectA_2024.10.20-23.17.50%')"
        " AND "
        "LOWER(path) NOT LIKE LOWER('%_app/%/python.%')"
        " AND "
        "(LOWER(cloudId) LIKE LOWER('%6%') OR LOWER(cloudId) LIKE LOWER('%9%'))"
        " AND "
        "(LOWER(cloudId) NOT LIKE LOWER('%1%') OR LOWER(cloudId) NOT LIKE LOWER('%3%'))"
        " AND "
        "is_deleted IS FALSE"
        " AND "
        "flag IS TRUE"
        " AND "
        "(log MATCH_PHRASE 'html' OR log MATCH_PHRASE 'css')"
        " AND "
        "log NOT MATCH_PHRASE 'js'"
        " AND "
        "(log MATCH_PHRASE 'success' AND log MATCH_PHRASE '200')"
        " AND "
        "(log NOT MATCH_PHRASE 'error' AND log NOT MATCH_PHRASE '500')"
        " AND "
        "(LOWER(desc) LIKE LOWER('%_el%') AND LOWER(desc) LIKE LOWER('%wor_d%'))"
        " AND "
        "(LOWER(theme) NOT LIKE LOWER('%pg%') AND LOWER(theme) NOT LIKE LOWER('%_h_%'))"
        " AND "
        "(name = 'he''ll''o' OR name = 'world''')"
        " AND "
        "(CAST(__ext['bcs_id'] AS TEXT) = 'BCS-1' OR CAST(__ext['bcs_id'] AS TEXT) = 'BCS-2')"
        " AND "
        "(CAST(__ext['bcs_id'] AS TEXT) != 'BCS-3' OR CAST(__ext['bcs_id'] AS TEXT) != 'BCS-4')"
        " AND "
        "(LOWER(CAST(__ext['label']['component'] AS TEXT)) LIKE LOWER('%ds%')"
        " OR "
        "LOWER(CAST(__ext['label']['component'] AS TEXT)) LIKE LOWER('%py%'))"
        " AND "
        "LOWER(CAST(__ext['label']['component'] AS TEXT)) NOT LIKE LOWER('%a%')"
    ),
    (
        "WHERE thedate >= 20241121 AND thedate <= 20241128"
        " AND "
        "dtEventTimeStamp >= 1732220441 AND dtEventTimeStamp <= 1732820443"
        " AND "
        "LOWER(log) LIKE LOWER('%') AND year BETWEEN 2020 AND 2023 AND log MATCH_PHRASE \"abc\" AND LOWER(log) LIKE LOWER('%def%')"
        " AND "
        "(bk_host_id = 'x1' OR bk_host_id = 'x2') AND is_deleted IS TRUE"
    ),
    (
        "WHERE thedate >= 20241121 AND thedate <= 20241128"
        " AND "
        "dtEventTimeStamp >= 1732220441 AND dtEventTimeStamp <= 1732820443"
        " AND "
        "title1 = \"Python Programming\" AND (LOWER(author) LIKE LOWER('%John%') AND LOWER(author) LIKE LOWER('%6%') OR author = \"7\")"
        " AND "
        "(bk_host_id = 'x1' OR bk_host_id = 'x2') AND is_deleted IS TRUE"
    ),
]


WHERE_CLAUSE_CASE = [
    "*",
    "success",
    '""',
    '"002" OR error',
    "year:[2020 TO 2023]",
    "title:/[Pp]ython.*/",
    "title:Pyth?n",
    '(name:John AND name: 6 OR name: "7") AND (python OR "django")',
    '__ext.bcs_id: 1 OR __ext.bcs_id: "ts"',
    'NOT log: "ts" AND -a : "b"',
    'span_id:(6cee80d18 OR "c866d58ac1") AND (-log:"a" OR NOT a:b)',
    "(index: >=200 OR index: <100) AND id: <10 AND age: >18",
    'log: (1 OR "abc" OR "xxx" AND 111)',
    'ID: ("abc" OR ("cde" AND "ddd"))',
    'ID: (("a" AND b) OR "d" AND 2 AND 3 AND (4 OR 5))',
    'log: (("a" OR ("b" OR "c")) AND "d") AND -name: test',
    'log: (("a" OR ("b" OR "c")) OR "d") AND -name: test',
    'log: (("a" AND b) OR "c" AND "d")',
    'log: ("a" OR ("b" OR "c")) AND (1 OR 2 AND 3) OR "f" AND "g"',
    'ID: ("abc" AND 5 OR 6 AND ("cde" AND "ddd") AND (1 AND 2))',
    'ID: ("abc" OR 5 AND 6 AND ("cde" AND "ddd") AND (1 OR 2))',
]
WHERE_CLAUSE_RESULT = [
    "LOWER(log) LIKE LOWER('%')",
    "LOWER(log) LIKE LOWER('%success%')",
    'log MATCH_PHRASE ""',
    "log MATCH_PHRASE \"002\" OR LOWER(log) LIKE LOWER('%error%')",
    "year BETWEEN 2020 AND 2023",
    "title1 REGEXP '[Pp]ython.*'",
    "LOWER(title1) LIKE LOWER('%Pyth_n%')",
    "(LOWER(name) LIKE LOWER('%John%') AND LOWER(name) LIKE LOWER('%6%') OR name = \"7\") AND (LOWER(log) LIKE LOWER('%python%') OR log MATCH_PHRASE \"django\")",
    "LOWER(CAST(__ext['bcs_id'] AS TEXT)) LIKE LOWER('%1%') OR CAST(__ext['bcs_id'] AS TEXT) = \"ts\"",
    'NOT log MATCH_PHRASE "ts" AND NOT a = "b"',
    "(LOWER(span_id) LIKE LOWER('%6cee80d18%') OR span_id = \"c866d58ac1\") AND (NOT log MATCH_PHRASE \"a\" OR NOT LOWER(a) LIKE LOWER('%b%'))",
    "(index >=200 OR index <100) AND id <10 AND age >18",
    "(log MATCH_PHRASE \"xxx\" AND LOWER(log) LIKE LOWER('%111%') OR (LOWER(log) LIKE LOWER('%1%') OR log MATCH_PHRASE \"abc\"))",
    '((ID = "cde" AND ID = "ddd") OR ID = "abc")',
    "((ID = \"a\" AND LOWER(ID) LIKE LOWER('%b%')) OR ID = \"d\" AND LOWER(ID) LIKE LOWER('%2%') AND LOWER(ID) LIKE LOWER('%3%') AND "
    "(LOWER(ID) LIKE LOWER('%4%') OR LOWER(ID) LIKE LOWER('%5%')))",
    '((log MATCH_PHRASE "b" OR log MATCH_PHRASE "c") OR log MATCH_PHRASE "a") AND '
    "log MATCH_PHRASE \"d\" AND NOT LOWER(name) LIKE LOWER('%test%')",
    '(((log MATCH_PHRASE "b" OR log MATCH_PHRASE "c") OR log MATCH_PHRASE "a") OR '
    "log MATCH_PHRASE \"d\") AND NOT LOWER(name) LIKE LOWER('%test%')",
    '((log MATCH_PHRASE "a" AND LOWER(log) LIKE LOWER(\'%b%\')) OR log MATCH_PHRASE "c" AND log MATCH_PHRASE "d")',
    '((log MATCH_PHRASE "b" OR log MATCH_PHRASE "c") OR log MATCH_PHRASE "a") AND '
    "(LOWER(log) LIKE LOWER('%1%') OR LOWER(log) LIKE LOWER('%2%') AND LOWER(log) LIKE LOWER('%3%')) OR log MATCH_PHRASE \"f\" AND log MATCH_PHRASE \"g\"",
    '(ID = "abc" AND LOWER(ID) LIKE LOWER(\'%5%\') OR LOWER(ID) LIKE LOWER(\'%6%\') AND (ID = "cde" AND ID = "ddd") AND '
    "(LOWER(ID) LIKE LOWER('%1%') AND LOWER(ID) LIKE LOWER('%2%')))",
    "(LOWER(ID) LIKE LOWER('%5%') AND LOWER(ID) LIKE LOWER('%6%') AND (ID = \"cde\" AND ID = \"ddd\") AND "
    "(LOWER(ID) LIKE LOWER('%1%') OR LOWER(ID) LIKE LOWER('%2%')) OR ID = \"abc\")",
]


class TestChart(TestCase):
    def test_generate_sql(self):
        for search_param, sql_result, where_clause in zip(SEARCH_PARAMS, SQL_RESULT, WHERE_CLAUSE):
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
                alias_mappings={"title": "title1", "describe": "desc"},
            )
            self.assertEqual(data["sql"], sql_result)
            self.assertEqual(data["additional_where_clause"], where_clause)

    def test_lucene_to_where_clause(self):
        for where_clause_case, where_clause_result in zip(WHERE_CLAUSE_CASE, WHERE_CLAUSE_RESULT):
            result = ChartHandler.lucene_to_where_clause(where_clause_case, alias_mappings={"title": "title1"})
            self.assertEqual(result, where_clause_result)
