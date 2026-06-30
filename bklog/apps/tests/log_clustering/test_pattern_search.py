import copy
from unittest.mock import patch

import arrow
from django.test import TestCase

from apps.feature_toggle.handlers.toggle import Toggle
from apps.log_clustering.constants import (
    AGGS_FIELD_PREFIX,
    CLUSTERING_REMARK_GROUP_FALLBACK_BIZ_ID_BLACK_LIST,
    StorageTypeEnum,
)
from apps.log_clustering.handlers.pattern import PatternHandler
from apps.log_clustering.models import AiopsSignatureAndPattern, ClusteringConfig, ClusteringRemark

INDEX_SET_ID = 123
PARAMS = {
    "host_scopes": {"modules": [], "ips": "", "target_nodes": [], "target_node_type": ""},
    "addition": [{"field": "__dist_xx", "operator": "is not", "value": ""}],
    "start_time": "2024-07-04 14:21:32",
    "end_time": "2024-07-11 14:21:32",
    "time_range": "customized",
    "keyword": "*",
    "size": 10000,
    "pattern_level": "05",
    "show_new_pattern": False,
    "year_on_year_hour": 0,
    "group_by": [],
    "filter_not_clustering": True,
    "remark_config": "all",
    "owner_config": "no_owner",
    "owners": [],
    "fields": [{"field_name": "__dist_0xx", "sub_fields": {}}],
}

RESULT_DATA = [
    {
        "pattern": "",
        "origin_pattern": "",
        "label": "",
        "remark": [],
        "owners": ["xyy"],
        "count": 34,
        "signature": "e4b60ecf",
        "percentage": 0.62066447,
        "is_new_class": False,
        "year_on_year_count": 0,
        "year_on_year_percentage": 100,
        "group": [],
    },
    {
        "pattern": "",
        "origin_pattern": "",
        "label": "",
        "remark": [],
        "owners": ["myy"],
        "count": 24,
        "signature": "e9425893",
        "percentage": 0.4381161,
        "is_new_class": False,
        "year_on_year_count": 0,
        "year_on_year_percentage": 100,
        "group": [],
    },
    {
        "pattern": "",
        "origin_pattern": "",
        "label": "",
        "remark": [],
        "owners": ["htl"],
        "count": 24,
        "signature": "e9425893",
        "percentage": 0.4381161,
        "is_new_class": False,
        "year_on_year_count": 0,
        "year_on_year_percentage": 100,
        "group": [],
    },
    {
        "pattern": "",
        "origin_pattern": "",
        "label": "",
        "remark": [],
        "owners": [],
        "count": 51,
        "signature": "f189c7be",
        "percentage": 0.9309967,
        "is_new_class": False,
        "year_on_year_count": 0,
        "year_on_year_percentage": 100,
        "group": [],
    },
]


class TestPatternSearch(TestCase):
    def setUp(self) -> None:  # pylint: disable=invalid-name
        # 测试数据库添加一条ClusteringConfig数据
        ClusteringConfig.objects.create(
            index_set_id=INDEX_SET_ID,
            min_members=100,
            max_dist_list="xxx",
            predefined_varibles="^hi",
            delimeter="x",
            max_log_length=1024,
            bk_biz_id=2,
        )
        self.pattern_handler = PatternHandler(INDEX_SET_ID, PARAMS)

    def test_get_remark_and_owner(self):
        """
        情况1：
        owner_config 为 all，owners为[]
        情况2：
        owner_config 为 no_owner，owners为[]
        情况3：
        owner_config 为 owner，owners为["xx1", "xx2"]
        情况4：(选择未指定责任人和xx责任人)
        owner_config 为 no_owner，owners为["xx1", "xx2"]
        """
        # owner_config,owners和预期的结果
        case_list = [
            ("all", [], RESULT_DATA),
            ("no_owner", [], RESULT_DATA[-1:]),
            ("owner", ["xyy", "myy"], RESULT_DATA[:2]),
            ("no_owner", ["htl"], RESULT_DATA[-2:]),
        ]
        for _owner_config, _owners, _result in case_list:
            result = copy.deepcopy(RESULT_DATA)
            self.pattern_handler._owner_config, self.pattern_handler._owners = _owner_config, _owners
            result = self.pattern_handler._get_remark_and_owner(result)
            self.assertEqual(result, _result)

    @patch("apps.log_clustering.handlers.pattern.UnifyQueryPatternHandler")
    def test_get_pattern_aggs_result_use_unify_query_for_doris(self, mock_unify_query_handler):
        ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).update(storage_type=StorageTypeEnum.DORIS.value)
        expected = [{"key": "e4b60ecf", "doc_count": 34, "group": ""}]
        query = copy.deepcopy(PARAMS)
        query["bk_biz_id"] = 2
        mock_unify_query_handler.return_value.query_pattern.return_value = expected

        result = PatternHandler(INDEX_SET_ID, copy.deepcopy(PARAMS))._get_pattern_aggs_result(INDEX_SET_ID, query)

        self.assertEqual(result, expected)
        mock_unify_query_handler.assert_called_once()
        called_query = mock_unify_query_handler.call_args.args[0]
        self.assertEqual(called_query["index_set_ids"], [INDEX_SET_ID])
        self.assertEqual(called_query["agg_field"], f"{AGGS_FIELD_PREFIX}_05")

    @patch.object(PatternHandler, "_get_pattern_aggs_result")
    @patch.object(PatternHandler, "_get_new_class")
    def test_new_class_multi_query_chunks_signature_condition_and_merges_results(
        self, mock_get_new_class, mock_get_pattern_aggs_result
    ):
        signatures = [f"signature-{index}" for index in range(901)]
        mock_get_new_class.return_value = {(signature,) for signature in signatures}

        def fake_get_pattern_aggs_result(index_set_id, query):  # pylint: disable=unused-argument
            chunk = query["addition"][-1]["value"]
            return [{"key": "e4b60ecf", "doc_count": len(chunk), "group": "gamesvr"}]

        mock_get_pattern_aggs_result.side_effect = fake_get_pattern_aggs_result

        query = copy.deepcopy(PARAMS)
        query["bk_biz_id"] = 2
        query["size"] = 1
        query["group_by"] = ["service_name"]

        result = PatternHandler(INDEX_SET_ID, query)._new_class_multi_query()

        self.assertEqual(mock_get_pattern_aggs_result.call_count, 2)
        chunks = [call.args[1]["addition"][-1]["value"] for call in mock_get_pattern_aggs_result.call_args_list]
        self.assertEqual(sum(len(chunk) for chunk in chunks), 901)
        self.assertTrue(all(len(chunk) <= 900 for chunk in chunks))
        self.assertEqual(result["pattern_aggs"], [{"key": "e4b60ecf", "doc_count": 901, "group": "gamesvr"}])

    @patch.object(PatternHandler, "_get_year_on_year_aggs_result")
    @patch.object(PatternHandler, "_get_pattern_aggs_result")
    @patch.object(PatternHandler, "_get_new_class")
    def test_new_class_multi_query_chunks_year_on_year_signature_condition(
        self, mock_get_new_class, mock_get_pattern_aggs_result, mock_get_year_on_year_aggs_result
    ):
        signatures = [f"signature-{index}" for index in range(901)]
        mock_get_new_class.return_value = {(signature,) for signature in signatures}
        mock_get_pattern_aggs_result.return_value = []

        def fake_get_year_on_year_aggs_result(query):
            chunk = query["addition"][-1]["value"]
            return {"e4b60ecf|gamesvr": len(chunk)}

        mock_get_year_on_year_aggs_result.side_effect = fake_get_year_on_year_aggs_result

        query = copy.deepcopy(PARAMS)
        query["bk_biz_id"] = 2
        query["year_on_year_hour"] = 24

        result = PatternHandler(INDEX_SET_ID, query)._new_class_multi_query()

        self.assertEqual(mock_get_year_on_year_aggs_result.call_count, 2)
        chunks = [call.args[0]["addition"][-1]["value"] for call in mock_get_year_on_year_aggs_result.call_args_list]
        self.assertEqual(sum(len(chunk) for chunk in chunks), 901)
        self.assertTrue(all(len(chunk) <= 900 for chunk in chunks))
        self.assertEqual(result["year_on_year_result"], {"e4b60ecf|gamesvr": 901})

    @patch.object(PatternHandler, "_multi_query")
    def test_pattern_search_returns_placeholders(self, mock_multi_query):
        ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).update(model_id="model_1")
        AiopsSignatureAndPattern.objects.create(
            model_id="model_1",
            signature="e4b60ecf",
            pattern="prefix #PATH# middle #NUMBER# suffix",
        )
        mock_multi_query.return_value = {
            "pattern_aggs": [{"key": "e4b60ecf", "doc_count": 34, "group": ""}],
            "year_on_year_result": {},
            "new_class": set(),
        }

        result = PatternHandler(INDEX_SET_ID, copy.deepcopy(PARAMS)).pattern_search()

        self.assertEqual(
            result[0]["placeholders"],
            [
                {"name": "PATH", "index": 0},
                {"name": "NUMBER", "index": 1},
            ],
        )

    @patch.object(PatternHandler, "_multi_query")
    def test_pattern_search_hides_origin_log_by_default(self, mock_multi_query):
        ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).update(model_id="model_1")
        AiopsSignatureAndPattern.objects.create(
            model_id="model_1",
            signature="e4b60ecf",
            pattern="fallback pattern",
            origin_log="large raw log sample",
        )
        mock_multi_query.return_value = {
            "pattern_aggs": [{"key": "e4b60ecf", "doc_count": 34, "group": ""}],
            "year_on_year_result": {},
            "new_class": set(),
        }

        result = PatternHandler(INDEX_SET_ID, copy.deepcopy(PARAMS)).pattern_search()

        self.assertEqual(result[0]["pattern"], "fallback pattern")
        self.assertEqual(result[0]["origin_log"], "")

    @patch.object(PatternHandler, "_multi_query")
    def test_pattern_search_returns_origin_log_when_requested(self, mock_multi_query):
        ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).update(model_id="model_1")
        AiopsSignatureAndPattern.objects.create(
            model_id="model_1",
            signature="e4b60ecf",
            pattern="fallback pattern",
            origin_log="large raw log sample",
        )
        mock_multi_query.return_value = {
            "pattern_aggs": [{"key": "e4b60ecf", "doc_count": 34, "group": ""}],
            "year_on_year_result": {},
            "new_class": set(),
        }
        query = copy.deepcopy(PARAMS)
        query["include_origin_log"] = True

        result = PatternHandler(INDEX_SET_ID, query).pattern_search()

        self.assertEqual(result[0]["origin_log"], "large raw log sample")

    @patch.object(PatternHandler, "_multi_query")
    def test_pattern_search_marks_signature_new_when_un_grouped_and_any_configured_group_is_new(self, mock_multi_query):
        ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).update(
            model_id="model_1", group_fields=["service_name", "func"]
        )
        AiopsSignatureAndPattern.objects.create(
            model_id="model_1",
            signature="e4b60ecf",
            pattern="fallback pattern",
        )
        mock_multi_query.return_value = {
            "pattern_aggs": [{"key": "e4b60ecf", "doc_count": 34, "group": ""}],
            "year_on_year_result": {},
            "new_class": {("e4b60ecf", "gamesvr", "AddCultivationExp")},
        }

        query = copy.deepcopy(PARAMS)
        query["group_by"] = []
        query["owner_config"] = "all"
        result = PatternHandler(INDEX_SET_ID, query).pattern_search()

        self.assertTrue(result[0]["is_new_class"])

    @patch.object(PatternHandler, "_multi_query")
    def test_pattern_search_keeps_exact_new_class_match_when_all_group_fields_visible(self, mock_multi_query):
        ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).update(
            model_id="model_1", group_fields=["service_name", "func"]
        )
        AiopsSignatureAndPattern.objects.create(
            model_id="model_1",
            signature="e4b60ecf",
            pattern="fallback pattern",
        )
        mock_multi_query.return_value = {
            "pattern_aggs": [
                {"key": "e4b60ecf", "doc_count": 34, "group": "gamesvr|AddCultivationExp"},
                {"key": "e4b60ecf", "doc_count": 21, "group": "gamesvr|OtherFunc"},
            ],
            "year_on_year_result": {},
            "new_class": {("e4b60ecf", "gamesvr", "AddCultivationExp")},
        }

        query = copy.deepcopy(PARAMS)
        query["group_by"] = ["service_name", "func"]
        query["owner_config"] = "all"
        result = PatternHandler(INDEX_SET_ID, query).pattern_search()

        self.assertTrue(result[0]["is_new_class"])
        self.assertFalse(result[1]["is_new_class"])

    @patch.object(PatternHandler, "_multi_query")
    def test_pattern_search_marks_visible_group_new_when_hidden_sub_group_is_new(self, mock_multi_query):
        ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).update(
            model_id="model_1", group_fields=["service_name", "func"]
        )
        AiopsSignatureAndPattern.objects.create(
            model_id="model_1",
            signature="e4b60ecf",
            pattern="fallback pattern",
        )
        mock_multi_query.return_value = {
            "pattern_aggs": [
                {"key": "e4b60ecf", "doc_count": 34, "group": "gamesvr"},
                {"key": "e4b60ecf", "doc_count": 21, "group": "relaysvr"},
            ],
            "year_on_year_result": {},
            "new_class": {("e4b60ecf", "gamesvr", "AddCultivationExp")},
        }

        query = copy.deepcopy(PARAMS)
        query["group_by"] = ["service_name"]
        query["owner_config"] = "all"
        result = PatternHandler(INDEX_SET_ID, query).pattern_search()

        self.assertTrue(result[0]["is_new_class"])
        self.assertFalse(result[1]["is_new_class"])

    @patch("apps.log_clustering.handlers.pattern.generate_time_range")
    @patch("apps.utils.bkdata.BkDataQueryApi.query")
    def test_get_pattern_data_for_bkbase_link_omits_origin_log_by_default(self, mock_query, mock_generate_time_range):
        ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).update(signature_pattern_rt="bklog_pattern_rt")
        mock_query.return_value = {"list": [{"signature": "e4b60ecf", "pattern": "fallback pattern"}]}
        mock_generate_time_range.return_value = (arrow.get(1720088492), arrow.get(1720693292))
        query = copy.deepcopy(PARAMS)
        query["time_range"] = "1h"

        result = PatternHandler(INDEX_SET_ID, query)._get_pattern_data(["e4b60ecf"])

        sql = mock_query.call_args.args[0]["sql"]
        self.assertEqual(result[0].get("origin_log"), None)
        self.assertNotIn("log as origin_log", sql)

    @patch("apps.log_clustering.handlers.pattern.generate_time_range")
    @patch("apps.utils.bkdata.BkDataQueryApi.query")
    def test_get_pattern_data_for_bkbase_link_selects_origin_log_when_requested(
        self, mock_query, mock_generate_time_range
    ):
        ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).update(signature_pattern_rt="bklog_pattern_rt")
        mock_query.return_value = {
            "list": [{"signature": "e4b60ecf", "pattern": "fallback pattern", "origin_log": "large raw log sample"}]
        }
        mock_generate_time_range.return_value = (arrow.get(1720088492), arrow.get(1720693292))
        query = copy.deepcopy(PARAMS)
        query["time_range"] = "1h"
        query["include_origin_log"] = True

        result = PatternHandler(INDEX_SET_ID, query)._get_pattern_data(["e4b60ecf"])

        sql = mock_query.call_args.args[0]["sql"]
        self.assertEqual(result[0]["origin_log"], "large raw log sample")
        self.assertIn("log as origin_log", sql)

    @patch("apps.log_clustering.handlers.pattern.FeatureToggleObject.toggle")
    @patch.object(PatternHandler, "_multi_query")
    def test_pattern_search_fallbacks_to_remark_without_group_by_default(self, mock_multi_query, mock_toggle):
        ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).update(model_id="model_1", group_fields=["module"])
        AiopsSignatureAndPattern.objects.create(
            model_id="model_1",
            signature="e4b60ecf",
            pattern="fallback pattern",
        )
        ClusteringRemark.objects.create(
            bk_biz_id=2,
            signature="e4b60ecf",
            groups={},
            group_hash=ClusteringRemark.convert_groups_to_groups_hash({}),
            remark=["default fallback remark"],
            owners=["admin"],
            strategy_id=1,
            strategy_enabled=True,
        )
        mock_multi_query.return_value = {
            "pattern_aggs": [{"key": "e4b60ecf", "doc_count": 34, "group": "module-a"}],
            "year_on_year_result": {},
            "new_class": set(),
        }
        mock_toggle.return_value = Toggle(feature_config={})

        query = copy.deepcopy(PARAMS)
        query["group_by"] = ["module"]
        query["owner_config"] = "all"
        result = PatternHandler(INDEX_SET_ID, query).pattern_search()

        self.assertEqual(result[0]["remark"], ["default fallback remark"])
        self.assertEqual(result[0]["owners"], ["admin"])
        self.assertEqual(result[0]["strategy_id"], 1)
        self.assertTrue(result[0]["strategy_enabled"])

    @patch("apps.log_clustering.handlers.pattern.FeatureToggleObject.toggle")
    @patch.object(PatternHandler, "_multi_query")
    def test_pattern_search_uses_exact_group_owner_when_remark_is_empty(self, mock_multi_query, mock_toggle):
        ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).update(model_id="model_1", group_fields=["module"])
        AiopsSignatureAndPattern.objects.create(
            model_id="model_1",
            signature="e4b60ecf",
            pattern="fallback pattern",
        )
        ClusteringRemark.objects.create(
            bk_biz_id=2,
            signature="e4b60ecf",
            groups={},
            group_hash=ClusteringRemark.convert_groups_to_groups_hash({}),
            remark=["default fallback remark"],
            owners=["admin"],
            strategy_id=1,
            strategy_enabled=True,
        )
        ClusteringRemark.objects.create(
            bk_biz_id=2,
            signature="e4b60ecf",
            groups={"module": "module-a"},
            group_hash=ClusteringRemark.convert_groups_to_groups_hash({"module": "module-a"}),
            remark=[],
            owners=["owner-only"],
        )
        mock_multi_query.return_value = {
            "pattern_aggs": [{"key": "e4b60ecf", "doc_count": 34, "group": "module-a"}],
            "year_on_year_result": {},
            "new_class": set(),
        }
        mock_toggle.return_value = Toggle(feature_config={})

        query = copy.deepcopy(PARAMS)
        query["group_by"] = ["module"]
        query["owner_config"] = "all"
        result = PatternHandler(INDEX_SET_ID, query).pattern_search()

        self.assertEqual(result[0]["remark"], [])
        self.assertEqual(result[0]["owners"], ["owner-only"])
        self.assertEqual(result[0]["strategy_id"], 0)
        self.assertFalse(result[0]["strategy_enabled"])

    @patch("apps.log_clustering.handlers.pattern.FeatureToggleObject.toggle")
    @patch.object(PatternHandler, "_multi_query")
    def test_pattern_search_does_not_fallback_for_black_list_biz(self, mock_multi_query, mock_toggle):
        ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).update(model_id="model_1", group_fields=["module"])
        AiopsSignatureAndPattern.objects.create(
            model_id="model_1",
            signature="e4b60ecf",
            pattern="fallback pattern",
        )
        ClusteringRemark.objects.create(
            bk_biz_id=2,
            signature="e4b60ecf",
            groups={},
            group_hash=ClusteringRemark.convert_groups_to_groups_hash({}),
            remark=["default fallback remark"],
            owners=["admin"],
            strategy_id=1,
            strategy_enabled=True,
        )
        mock_multi_query.return_value = {
            "pattern_aggs": [{"key": "e4b60ecf", "doc_count": 34, "group": "module-a"}],
            "year_on_year_result": {},
            "new_class": set(),
        }
        mock_toggle.return_value = Toggle(feature_config={CLUSTERING_REMARK_GROUP_FALLBACK_BIZ_ID_BLACK_LIST: [2]})

        query = copy.deepcopy(PARAMS)
        query["group_by"] = ["module"]
        query["owner_config"] = "all"
        result = PatternHandler(INDEX_SET_ID, query).pattern_search()

        self.assertEqual(result[0]["remark"], [])
        self.assertEqual(result[0]["owners"], [])
        self.assertEqual(result[0]["strategy_id"], 0)
        self.assertFalse(result[0]["strategy_enabled"])
