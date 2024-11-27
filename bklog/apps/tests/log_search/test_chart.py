from django.test import TestCase

from apps.log_search.constants import SQL_PREFIX, SQL_SUFFIX
from apps.log_search.handlers.search.chart_handlers import ChartHandler

SEARCH_PARAMS = {
    "start_time": 1732220441,
    "end_time": 1732220443,
    "addition": [
        {"field": "bk_host_id", "operator": "=", "value": ["1", "2"]},
        {"field": "service", "operator": "!=", "value": ["php"]},
        {"field": "count", "operator": "<", "value": [100]},
        {"field": "index", "operator": ">", "value": [500]},
        {"field": "number", "operator": ">=", "value": [100]},
        {"field": "id", "operator": "<=", "value": [500]},
        {"field": "gseIndex", "operator": "=~", "value": ["?proz/Saved/Logs/ProjectA_2024.10.20-23.17.50*"]},
        {"field": "path", "operator": "!=~", "value": ["?app/*/python.*"]},
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
        {"field": "name", "operator": "=", "value": ['\'hello\'', "\"world\""]},
    ],
}

SQL_RESULT = (
    f"{SQL_PREFIX} "
    "WHERE dtEventTimeStamp>=1732220441000 AND dtEventTimeStamp<=1732220443000"
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
    "gseIndex LIKE '_proz/Saved/Logs/ProjectA_2024.10.20-23.17.50%'"
    " AND "
    "path NOT LIKE '_app/%/python.%'"
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
    "(describe LIKE '_el%' AND describe LIKE 'wor_d')"
    " AND "
    "(theme NOT LIKE 'pg%' AND theme NOT LIKE '_h_')"
    " AND "
    "(name = \"\'hello\'\" OR name = '\"world\"')"
    f" {SQL_SUFFIX}"
)


class TestChart(TestCase):
    def test_generate_sql(self):
        sql = ChartHandler.generate_sql(SEARCH_PARAMS)
        self.assertEqual(sql, SQL_RESULT)
