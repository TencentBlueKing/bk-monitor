import json
from dataclasses import asdict

from django.test import TestCase

from apps.log_clustering.constants import AGGS_FIELD_PREFIX, PatternEnum, StorageTypeEnum
from apps.log_clustering.handlers.dataflow.constants import FlowMode
from apps.log_clustering.handlers.dataflow.data_cls import (
    DorisCls,
    ModelClusterPredictNodeCls,
    PredictDataFlowCls,
    RealTimeCls,
)
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
            {"op": "=", "value": "server_ip_a", "fields_name": "serverIp", "logic_operator": "and"},
        ],
        "result": (
            "where `log` is not null and length(`log`) > 1 and (  `serverIp` is not null  ) and ( `log` LIKE '%ERROR%' and `serverIp` = 'server_ip_a' )",
            "where NOT ( `log` is not null and length(`log`) > 1 and (  `serverIp` is not null  ) and ( `log` LIKE '%ERROR%' and `serverIp` = 'server_ip_a' ) )",
        ),
    },
    {
        "filters": [
            {"op": "LIKE", "value": ["%ERROR%", "INFO"], "fields_name": "log", "logic_operator": None},
            {"op": "=", "value": ["server_ip_a"], "fields_name": "serverIp", "logic_operator": "and"},
        ],
        "result": (
            "where `log` is not null and length(`log`) > 1 and (  `serverIp` is not null  ) and ( ( `log` LIKE '%ERROR%' or `log` LIKE 'INFO' ) and `serverIp` = 'server_ip_a' )",
            "where NOT ( `log` is not null and length(`log`) > 1 and (  `serverIp` is not null  ) and ( ( `log` LIKE '%ERROR%' or `log` LIKE 'INFO' ) and `serverIp` = 'server_ip_a' ) )",
        ),
    },
    {
        "filters": [
            {"op": "LIKE", "value": ["%ERROR%", "INFO"], "fields_name": "log", "logic_operator": None},
            {"op": "=", "value": ["server_ip_a", "server_ip_b"], "fields_name": "serverIp", "logic_operator": "and"},
        ],
        "result": (
            "where `log` is not null and length(`log`) > 1 and (  `serverIp` is not null  ) and ( ( `log` LIKE '%ERROR%' or `log` LIKE 'INFO' ) and ( `serverIp` = 'server_ip_a' or `serverIp` = 'server_ip_b' ) )",
            "where NOT ( `log` is not null and length(`log`) > 1 and (  `serverIp` is not null  ) and ( ( `log` LIKE '%ERROR%' or `log` LIKE 'INFO' ) and ( `serverIp` = 'server_ip_a' or `serverIp` = 'server_ip_b' ) ) )",
        ),
    },
    {
        "filters": [
            {"op": "not contains", "value": ["ERROR", "INFO"], "fields_name": "log", "logic_operator": None},
            {"op": "!=", "value": ["server_ip_a", "server_ip_b"], "fields_name": "serverIp", "logic_operator": "and"},
        ],
        "result": (
            "where `log` is not null and length(`log`) > 1 and (  `serverIp` is not null  ) and ( ( `log` NOT LIKE '%ERROR%' and `log` NOT LIKE '%INFO%' ) and ( `serverIp` <> 'server_ip_a' and `serverIp` <> 'server_ip_b' ) )",
            "where NOT ( `log` is not null and length(`log`) > 1 and (  `serverIp` is not null  ) and ( ( `log` NOT LIKE '%ERROR%' and `log` NOT LIKE '%INFO%' ) and ( `serverIp` <> 'server_ip_a' and `serverIp` <> 'server_ip_b' ) ) )",
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

    def test_build_doris_fields(self):
        all_fields = [
            {"field_name": "dtEventTimeStamp", "field_type": "timestamp"},
            {"field_name": "message", "field_type": "string"},
            {"field_name": "raw_message", "field_type": "string"},
            {"field_name": "attributes", "field_type": "object"},
            {"field_name": "serverIp", "field_type": "long"},
        ]
        is_dimension_fields_map = {
            "dtEventTimeStamp": "dtEventTimeStamp",
            "message": "log",
            "raw_message": "log",
            "attributes": "attributes",
            "serverIp": "serverIp",
        }

        result = DataFlowHandler._build_doris_fields(
            all_fields=all_fields,
            is_dimension_fields_map=is_dimension_fields_map,
            analyzed_fields=["message"],
            json_fields=["attributes"],
        )

        self.assertEqual(
            result[:2],
            [
                {"alias": "_startTime_", "field": "_startTime_", "type": "string", "config": ""},
                {"alias": "_endTime_", "field": "_endTime_", "type": "string", "config": ""},
            ],
        )
        self.assertEqual(len([field for field in result if field["field"] == "log"]), 1)
        self.assertIn({"alias": "log", "field": "log", "type": "string", "config": "search_en"}, result)
        self.assertIn({"alias": "attributes", "field": "attributes", "type": "string", "config": "json"}, result)
        self.assertIn({"alias": "serverIp", "field": "serverIp", "type": "long", "config": ""}, result)
        self.assertIn(
            {"alias": "dtEventTimeStamp", "field": "dtEventTimeStamp", "type": "string", "config": ""},
            result,
        )
        expected_dist_fields = {
            f"{AGGS_FIELD_PREFIX}_{pattern_level}" for pattern_level in PatternEnum.get_dict_choices().keys()
        }
        actual_dist_fields = {field["field"] for field in result if field["field"].startswith(f"{AGGS_FIELD_PREFIX}_")}
        self.assertSetEqual(actual_dist_fields, expected_dist_fields)

    def test_render_predict_flow_with_doris_storage(self):
        predict_flow = PredictDataFlowCls(
            table_name_no_id="bklog_30_clustered",
            result_table_id="2_bklog_30_clean",
            clustering_stream_source=RealTimeCls(
                fields="`log`, `dtEventTimeStamp`",
                table_name="bklog_30_clustering",
                result_table_id="2_bklog_30_clustering",
                filter_rule="",
            ),
            clustering_predict=ModelClusterPredictNodeCls(
                table_name="bklog_30_clustering_output",
                result_table_id="2_bklog_30_clustering_output",
                clustering_training_params={
                    "min_members": 1,
                    "st_list": "0.5",
                    "predefined_variables": "",
                    "delimeter": " ",
                    "max_log_length": 1024,
                    "is_case_sensitive": 0,
                    "depth": 100,
                    "max_child": 2,
                    "use_offline_model": 0,
                    "max_dist_list": "0.5",
                },
                model_release_id=1,
                model_id="model_id",
                input_fields="[]",
                output_fields="[]",
            ),
            format_signature=RealTimeCls(
                fields="`log`, `dtEventTimeStamp`",
                table_name="bklog_30_clustered",
                result_table_id="2_bklog_30_clustered",
                filter_rule="",
            ),
            bk_biz_id=2,
            storage_type=StorageTypeEnum.DORIS.value,
            doris=DorisCls(
                expires_dup="30d",
                fields=json.dumps(
                    [
                        {"alias": "_startTime_", "field": "_startTime_", "type": "string", "config": ""},
                        {"alias": "__dist_05", "field": "__dist_05", "type": "string", "config": ""},
                    ]
                ),
            ),
            doris_storage="test_doris_cluster",
        )

        rendered = DataFlowHandler._render_template(
            flow_mode=FlowMode.PREDICT_FLOW.value,
            render_obj={"predict": asdict(predict_flow)},
        )
        flow = json.loads(rendered)
        node_types = [node["node_type"] for node in flow]
        doris_node = next(node for node in flow if node["node_type"] == "doris")

        self.assertIn("doris", node_types)
        self.assertNotIn("elastic_storage", node_types)
        self.assertEqual(doris_node["cluster"], "test_doris_cluster")
        self.assertEqual(doris_node["custom_param_config"]["expires_dup"], "30d")
