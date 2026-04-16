import copy
from unittest.mock import patch

from django.test import TestCase

from apps.log_clustering.constants import AGGS_FIELD_PREFIX, StorageTypeEnum
from apps.log_clustering.handlers.pattern import PatternHandler
from apps.log_clustering.models import AiopsSignatureAndPattern, ClusteringConfig

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
