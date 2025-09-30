from django.test import TestCase

from apps.log_clustering.handlers.dataflow.dataflow_handler import DataFlowHandler
from apps.log_clustering.models import ClusteringConfig

ALL_FIELDS_DICT = {
    "time": "time",
    "__ext": "__ext",
    "bk_host_id": "bk_host_id",
    "cloudId": "cloudId",
    "iterationIndex": "iterationIndex",
    "log": "log",
    "path": "path",
    "serverIp": "serverIp",
    "__dist_05": "__dist_05",
    "__module__": "__module__",
    "__set__": "__set__",
    "__ipv6__": "__ipv6__",
    "dtEventTimeStamp": "dtEventTimeStamp",
    "gseIndex": "gseIndex",
}

CLUSTERINGCONFIG_CREATE_PARAMS = {
    "id": "7",
    "created_by": "admin",
    "is_deleted": "0",
    "index_set_id": 30,
    "min_members": "1",
    "max_dist_list": "0.5",
    "predefined_varibles": "",
    "delimeter": "IlwifFxcXHUzMDAy...",
    "max_log_length": "1000",
    "is_case_sensitive": "0",
    "clustering_fields": "log",
    "filter_rules": [{"op": "LIKE", "value": ["%ERROR%", "info"], "fields_name": "log", "logic_operator": None}],
    "bk_biz_id": "2",
    "signature_enable": 1,
    "task_records": "[]",
    "depth": "100",
    "max_child": "2",
    "task_details": "0",
    "new_cls_strategy_enable": 0,
    "normal_strategy_enable": 0,
    "regex_rule_type": "template",
    "regex_template_id": 1,
}
RESULT = (
    "where `log` is not null and length(`log`) > 1 and ( `log` LIKE '%ERROR%' or `log` LIKE 'info' )",
    "where NOT ( `log` is not null and length(`log`) > 1 and ( `log` LIKE '%ERROR%' or `log` LIKE 'info' ) )",
)

TEST_CASES = [
    {
        "filters": [{"op": "LIKE", "value": "%ERROR%", "fields_name": "log.name", "logic_operator": None}],
        "result": (
            "where `log` is not null and length(`log`) > 1 and ( JSON_VALUE(`log`, '$.name') LIKE '%ERROR%' )",
            "where NOT ( `log` is not null and length(`log`) > 1 and ( JSON_VALUE(`log`, '$.name') LIKE '%ERROR%' ) )",
        ),
    },
    {
        "filters": [{"op": "LIKE", "value": "%ERROR%", "fields_name": "log", "logic_operator": None}],
        "result": (
            "where `log` is not null and length(`log`) > 1 and ( `log` LIKE '%ERROR%' )",
            "where NOT ( `log` is not null and length(`log`) > 1 and ( `log` LIKE '%ERROR%' ) )",
        ),
    },
    {
        "filters": [{"op": "LIKE", "value": ["%ERROR%", "INFO"], "fields_name": "log.name", "logic_operator": None}],
        "result": (
            "where `log` is not null and length(`log`) > 1 and ( JSON_VALUE(`log`, '$.name') LIKE '%ERROR%' or JSON_VALUE(`log`, '$.name') LIKE 'INFO' )",
            "where NOT ( `log` is not null and length(`log`) > 1 and ( JSON_VALUE(`log`, '$.name') LIKE '%ERROR%' or JSON_VALUE(`log`, '$.name') LIKE 'INFO' ) )",
        ),
    },
    {
        "filters": [
            {"op": "LIKE", "value": "%ERROR%", "fields_name": "log", "logic_operator": None},
            {"op": "=", "value": "1.1.1.1", "fields_name": "serverIp", "logic_operator": "and"},
        ],
        "result": (
            "where `log` is not null and length(`log`) > 1 and (  `serverIp` is not null  ) and ( `log` LIKE '%ERROR%' and `serverIp` = '1.1.1.1' )",
            "where NOT ( `log` is not null and length(`log`) > 1 and (  `serverIp` is not null  ) and ( `log` LIKE '%ERROR%' and `serverIp` = '1.1.1.1' ) )",
        ),
    },
    {
        "filters": [
            {"op": "LIKE", "value": ["%ERROR%", "INFO"], "fields_name": "log", "logic_operator": None},
            {"op": "=", "value": ["1.1.1.1"], "fields_name": "serverIp", "logic_operator": "and"},
        ],
        "result": (
            "where `log` is not null and length(`log`) > 1 and (  `serverIp` is not null  ) and ( ( `log` LIKE '%ERROR%' or `log` LIKE 'INFO' ) and `serverIp` = '1.1.1.1' )",
            "where NOT ( `log` is not null and length(`log`) > 1 and (  `serverIp` is not null  ) and ( ( `log` LIKE '%ERROR%' or `log` LIKE 'INFO' ) and `serverIp` = '1.1.1.1' ) )",
        ),
    },
    {
        "filters": [
            {"op": "LIKE", "value": ["%ERROR%", "INFO"], "fields_name": "log", "logic_operator": None},
            {"op": "=", "value": ["1.1.1.1", "0.0.0.0"], "fields_name": "serverIp", "logic_operator": "and"},
        ],
        "result": (
            "where `log` is not null and length(`log`) > 1 and (  `serverIp` is not null  ) and ( ( `log` LIKE '%ERROR%' or `log` LIKE 'INFO' ) and ( `serverIp` = '1.1.1.1' or `serverIp` = '0.0.0.0' ) )",
            "where NOT ( `log` is not null and length(`log`) > 1 and (  `serverIp` is not null  ) and ( ( `log` LIKE '%ERROR%' or `log` LIKE 'INFO' ) and ( `serverIp` = '1.1.1.1' or `serverIp` = '0.0.0.0' ) ) )",
        ),
    },
    {
        "filters": [
            {"op": "not contains", "value": ["ERROR", "INFO"], "fields_name": "log", "logic_operator": None},
            {"op": "!=", "value": ["1.1.1.1", "0.0.0.0"], "fields_name": "serverIp", "logic_operator": "and"},
        ],
        "result": (
            "where `log` is not null and length(`log`) > 1 and (  `serverIp` is not null  ) and ( ( `log` NOT LIKE '%ERROR%' and `log` NOT LIKE '%INFO%' ) and ( `serverIp` <> '1.1.1.1' and `serverIp` <> '0.0.0.0' ) )",
            "where NOT ( `log` is not null and length(`log`) > 1 and (  `serverIp` is not null  ) and ( ( `log` NOT LIKE '%ERROR%' and `log` NOT LIKE '%INFO%' ) and ( `serverIp` <> '1.1.1.1' and `serverIp` <> '0.0.0.0' ) ) )",
        ),
    },
]


class TestPatternSearch(TestCase):
    def test_init_filter_rule(self):
        ClusteringConfig.objects.create(**CLUSTERINGCONFIG_CREATE_PARAMS)
        clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=30)
        result = DataFlowHandler._init_filter_rule(
            clustering_config.filter_rules, ALL_FIELDS_DICT, clustering_config.clustering_fields
        )
        self.assertEqual(result, RESULT)

        for case in TEST_CASES:
            ClusteringConfig.objects.filter(index_set_id=30).update(filter_rules=case["filters"])
            clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=30)
            result = DataFlowHandler._init_filter_rule(
                clustering_config.filter_rules, ALL_FIELDS_DICT, clustering_config.clustering_fields
            )
            self.assertEqual(result, case["result"])
