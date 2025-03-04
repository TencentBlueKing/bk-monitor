from django.test import TestCase

from apps.log_search.constants import SQL_PREFIX, SQL_SUFFIX
from apps.log_search.handlers.search.chart_handlers import ChartHandler

SEARCH_PARAMS = [{
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
        "sql": "SELECT thedate, dtEventTimeStamp, iterationIndex, log, time WHERE a=1 or b=2 LIMIT 10",
        "addition": [
            {"field": "bk_host_id", "operator": "=", "value": ["x1", "x2"]},
            {"field": "is_deleted", "operator": "is true", "value": []
        }
    ]
}
]

SQL_RESULT = [(
    f"{SQL_PREFIX} "
    "WHERE (bk_host_id = '1' OR bk_host_id = '2')"
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
    "(JSON_EXTRACT(__ext,'$.bcs_id') = '\"BCS-1\"' OR JSON_EXTRACT(__ext,'$.bcs_id') = '\"BCS-2\"')"
    " AND "
    "(JSON_EXTRACT(__ext,'$.bcs_id') != '\"BCS-3\"' OR JSON_EXTRACT(__ext,'$.bcs_id') != '\"BCS-4\"')"
    " AND "
    "(JSON_EXTRACT(__ext,'$.label.component') LIKE '%ds%' OR JSON_EXTRACT(__ext,'$.label.component') LIKE '%py%')"
    " AND "
    "JSON_EXTRACT(__ext,'$.label.component') NOT LIKE '%a%'"
    f" {SQL_SUFFIX}"
),
    "SELECT thedate, dtEventTimeStamp, iterationIndex, log, `time`"
    " WHERE (bk_host_id = 'x1' OR bk_host_id = 'x2') AND is_deleted IS TRUE LIMIT 10"
]


class TestChart(TestCase):
    def test_generate_sql(self):
        sql = ChartHandler.generate_sql(SEARCH_PARAMS[0])
        self.assertEqual(sql, SQL_RESULT[0])
        sql = ChartHandler.generate_sql(SEARCH_PARAMS[1])
        self.assertEqual(sql, SQL_RESULT[1])
