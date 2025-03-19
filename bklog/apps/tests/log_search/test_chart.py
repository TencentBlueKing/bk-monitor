from django.test import TestCase

from apps.log_search.constants import SQL_PREFIX, SQL_SUFFIX
from apps.log_search.handlers.search.chart_handlers import ChartHandler

SEARCH_PARAMS = [
    {
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
    {
        "keyword": "log : * and year:[2020 TO 2023] AND \"abc\" AND def",
        "start_time": 1732220441,
        "end_time": 1732820443,
        "sql": "SELECT thedate, dtEventTimeStamp, iterationIndex, log, time FROM xx.x1 WHERE a=1 or b=2 LIMIT 10",
        "addition": [
            {"field": "bk_host_id", "operator": "=", "value": ["x1", "x2"]},
            {"field": "is_deleted", "operator": "is true", "value": []},
        ],
    },
    {
        "keyword": "title:\"Python Programming\" AND (author:John AND author: 6 OR author: \"7\")",
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
    (
        f"{SQL_PREFIX} "
        "WHERE title = \"Pyth?n\" OR title REGEXP '[Pp]ython.*' AND CAST(__ext['bcs_id'] AS TEXT) = \"test\""
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
        "gseIndex LIKE '%_proz/Saved/Logs/ProjectA_2024.10.20-23.17.50%'"
        " AND "
        "path NOT LIKE '%_app/%/python.%'"
        " AND "
        "(cloudId LIKE '%6%' OR cloudId LIKE '%9%')"
        " AND "
        "(cloudId NOT LIKE '%1%' OR cloudId NOT LIKE '%3%')"
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
        "(describe LIKE '%_el%' AND describe LIKE '%wor_d%')"
        " AND "
        "(theme NOT LIKE '%pg%' AND theme NOT LIKE '%_h_%')"
        " AND "
        "(name = 'he''ll''o' OR name = 'world''')"
        " AND "
        "(CAST(__ext['bcs_id'] AS TEXT) = 'BCS-1' OR CAST(__ext['bcs_id'] AS TEXT) = 'BCS-2')"
        " AND "
        "(CAST(__ext['bcs_id'] AS TEXT) != 'BCS-3' OR CAST(__ext['bcs_id'] AS TEXT) != 'BCS-4')"
        " AND "
        "(CAST(__ext['label']['component'] AS TEXT) LIKE '%ds%'"
        " OR "
        "CAST(__ext['label']['component'] AS TEXT) LIKE '%py%')"
        " AND "
        "CAST(__ext['label']['component'] AS TEXT) NOT LIKE '%a%'"
        f" {SQL_SUFFIX}"
    ),
    (
        "SELECT thedate, dtEventTimeStamp, iterationIndex, log, time "
        "WHERE log LIKE '%' AND year BETWEEN 2020 AND 2023 AND log MATCH_PHRASE \"abc\""
        " AND "
        "(bk_host_id = 'x1' OR bk_host_id = 'x2') AND is_deleted IS TRUE LIMIT 10"
    ),
    (
        "SELECT thedate, dtEventTimeStamp, log "
        "WHERE title = \"Python Programming\" AND (author LIKE '%John%' AND author LIKE '%6%' OR author = \"7\")"
        " AND "
        "(bk_host_id = 'x1' OR bk_host_id = 'x2') AND is_deleted IS TRUE LIMIT 10"
    ),
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
            self.assertEqual(data["sql"], sql_result)
