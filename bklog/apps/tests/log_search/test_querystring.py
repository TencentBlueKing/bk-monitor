from django.test import TestCase

from apps.log_search.handlers.es.querystring_builder import QueryStringBuilder

SEARCH_PARAMS = {
    "addition": [
        {"field": "bk_host_id", "operator": "=", "value": ["1", "2"]},
        {"field": "bk_host_id", "operator": "eq", "value": ["3", "4"]},
        {"field": "bk_host_id", "operator": "is", "value": ["5", "6"]},
        {"field": "service", "operator": "!=", "value": ["php"]},
        {"field": "service", "operator": "is not", "value": ["a", "b"]},
        {"field": "service", "operator": "is one of", "value": ["c", "d"]},
        {"field": "service", "operator": "is not one of", "value": ["e", "f"]},
        {"field": "count", "operator": "<", "value": [100, 200]},
        {"field": "index", "operator": ">", "value": [500]},
        {"field": "number", "operator": ">=", "value": [100, 50]},
        {"field": "id", "operator": "<=", "value": [500]},
        {"field": "count", "operator": "lt", "value": [100, 200]},
        {"field": "index", "operator": "gt", "value": [500]},
        {"field": "number", "operator": "gte", "value": [100, 50]},
        {"field": "id", "operator": "lte", "value": [500]},
        {"field": "gseIndex", "operator": "=~", "value": ["?proz/Saved/Logs/ProjectA_2024.10.20-23.17.50*"]},
        {"field": "path", "operator": "!=~", "value": ["?app/*/python.*", "*/python.*"]},
        {"field": "cloudId", "operator": "contains", "value": ["6", "9"]},
        {"field": "cloudId", "operator": "not contains", "value": ["1", "3"]},
        {"field": "is_deleted", "operator": "is false", "value": []},
        {"field": "flag", "operator": "is true", "value": [1]},
        {"field": "log", "operator": "contains match phrase", "value": ["html", "hello world"]},
        {"field": "log", "operator": "not contains match phrase", "value": ["are you ok"]},
        {"field": "log", "operator": "all contains match phrase", "value": ["su 7"]},
        {"field": "log", "operator": "all not contains match phrase", "value": ["error", "500"]},
        {"field": "log", "operator": "all not contains match phrase", "value": ["This is a \"test\" string"]},
        {"field": "describe", "operator": "&=~", "value": ["?el*", "wor?d"]},
        {"field": "theme", "operator": "&!=~", "value": ["pg*", "?h?"]},
        {"field": "*", "operator": "contains match phrase", "value": ["error"]},
        {"field": "querystring", "operator": "contains match phrase", "value": ["success"]},
        {"field": "querystring", "operator": "=", "value": []},
        {"field": "error", "operator": "contains", "value": []},
        {"field": "test", "operator": "test", "value": ["test"]},
    ],
}


TRANSFORM_RESULT = (
    "bk_host_id: (1 OR 2)"
    " AND "
    "bk_host_id: (3 OR 4)"
    " AND "
    "bk_host_id: (5 OR 6)"
    " AND "
    "NOT service: php"
    " AND "
    "NOT service: (a OR b)"
    " AND "
    "service: (c OR d)"
    " AND "
    "NOT service: (e OR f)"
    " AND "
    "count: <200"
    " AND "
    "index: >500"
    " AND "
    "number: >=50"
    " AND "
    "id: <=500"
    " AND "
    "count: <200"
    " AND "
    "index: >500"
    " AND "
    "number: >=50"
    " AND "
    "id: <=500"
    " AND "
    "gseIndex: ?proz/Saved/Logs/ProjectA_2024.10.20-23.17.50*"
    " AND "
    "NOT path: (?app/*/python.* OR */python.*)"
    " AND "
    "cloudId: (*6* OR *9*)"
    " AND "
    "NOT cloudId: (*1* OR *3*)"
    " AND "
    "is_deleted: false"
    " AND "
    "flag: true"
    " AND "
    "log: (\"html\" OR \"hello world\")"
    " AND "
    "NOT log: \"are you ok\""
    " AND "
    "log: \"su 7\""
    " AND "
    "NOT log: (\"error\" AND \"500\")"
    " AND "
    "NOT log: \"This is a \\\"test\\\" string\""
    " AND "
    "describe: (?el* AND wor?d)"
    " AND "
    "NOT theme: (pg* AND ?h?)"
    " AND "
    "(\"error\")"
    " AND "
    "(success)"
)


class TestQueryString(TestCase):
    def test_querystring(self):
        result = QueryStringBuilder.to_querystring(SEARCH_PARAMS)
        self.assertEqual(result, TRANSFORM_RESULT)