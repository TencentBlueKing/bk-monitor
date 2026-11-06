# -*- coding: utf-8 -*-
"""混挂索引组字段类型规范化的集成与接口层回归测试。

使用真实 Django model 构造等效索引组结构，覆盖字段类型规范化、
字段快照、路由护栏、字段模板保存、异步导出时间字段判定、
能力位判定、联合检索合并、字段统计与浮点分桶。
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.log_databus.constants import DORIS_CLUSTER_TYPE, STORAGE_CLUSTER_TYPE
from apps.log_databus.models import CollectorConfig
from apps.log_search.constants import ExportSearchType, OPERATORS
from apps.log_search.export.query import UnsupportedExportTimeField, snapshot_time_fields
from apps.log_search.handlers.index_set import BaseIndexSetHandler
from apps.log_search.handlers.search.search_handlers_esquery import UnionSearchHandler
from apps.log_search.models import (
    TAG_TYPE_INNER,
    IndexSetFieldsConfig,
    IndexSetTag,
    LogIndexSet,
    LogIndexSetData,
    Scenario,
)
from apps.log_search.views.field_views import FieldViewSet
from apps.log_unifyquery.handler.field import UnifyQueryFieldHandler
from apps.log_unifyquery.handler.mapping import UnifyQueryMappingHandler
from apps.tests.utils import FakeRedis

OVERRIDE_MIDDLEWARE = "apps.tests.middlewares.OverrideMiddleware"

GROUP_ID = 21708
CHILD_DORIS_A = 21693
CHILD_DORIS_B = 21694
CHILD_ES = 21692
BK_BIZ_ID = 100915
DORIS_CLUSTER_ID = 77

DORIS_TABLES = [
    "100915_bklog_pub_svrlog_pangusvr_other_9_analysis",
    "100915_bklog_pub_svrlog_pangusvr_other_9_analysis_his",
    "100915_bklog_pub_svrlog_pangusvr_other_other_analysis",
    "100915_bklog_pub_svrlog_pangusvr_other_other_analysis_his",
]

LOBBY_DORIS_TABLE = "100915_bklog_pub_svrlog_pangusvr_lobby_analysis"

CHILD_SPECS = [
    (CHILD_DORIS_A, "other_9", ",".join(DORIS_TABLES[:2]), "100915_bklog.other_9"),
    (CHILD_DORIS_B, "other_other", ",".join(DORIS_TABLES[2:]), "100915_bklog.other_other"),
    (CHILD_ES, "lobby", LOBBY_DORIS_TABLE, "100915_bklog.lobby"),
]


def _mixed_fields():
    """构造需求中的 8 个字段，每次返回全新对象，避免用例间互相污染。"""
    return [
        {"field_name": "dtEventTime", "field_type": "datetime", "is_agg": True},
        {"field_name": "localTime", "field_type": "varchar(32)", "is_agg": True},
        {"field_name": "thedate", "field_type": "int", "is_agg": True},
        {"field_name": "__shard_key__", "field_type": "bigint", "is_agg": True},
        {"field_name": "__unique_key__", "field_type": "varchar(512)", "is_agg": True},
        {"field_name": "time", "field_type": "date", "is_agg": True},
        {"field_name": "dtEventTimeStamp", "field_type": "date", "is_agg": True},
        {"field_name": "log", "field_type": "text", "is_analyzed": True, "is_agg": False},
    ]


class MixedStorageFixtureMixin:
    """提供真实 model 构造与 handler 构造，供两个测试类共用。"""

    def _create_models(self):
        """建立索引组、三个子索引集、采集项与索引集数据关联。"""
        self.index_set = LogIndexSet.objects.create(
            index_set_id=GROUP_ID,
            index_set_name="pub_svrlog_pangusvr",
            space_uid="bkcc__100915",
            scenario_id=Scenario.LOG,
            is_group=True,
            tag_ids=[],
            fields_snapshot=None,
        )
        doris_tag_id = str(IndexSetTag.get_tag_id("Doris", tag_type=TAG_TYPE_INNER))
        for child_id, name, doris_table_id, result_table_id in CHILD_SPECS:
            collector = CollectorConfig.objects.create(
                table_id=result_table_id,
                bk_biz_id=BK_BIZ_ID,
                collector_config_name=name,
                collector_scenario_id="log",
                category_id="other_rt",
                storage_cluster_type=STORAGE_CLUSTER_TYPE,
            )
            tag_ids = [] if child_id == CHILD_ES else [doris_tag_id]
            LogIndexSet.objects.create(
                index_set_id=child_id,
                index_set_name=name,
                space_uid="bkcc__100915",
                scenario_id=Scenario.LOG,
                is_group=False,
                tag_ids=tag_ids,
                support_doris=True,
                doris_table_id=doris_table_id,
                collector_config_id=collector.collector_config_id,
            )
            # 索引组到子索引集的关联行，结果表 ID 必须是字符串形式的子集 ID。
            LogIndexSetData.objects.create(
                index_set_id=GROUP_ID,
                result_table_id=str(child_id),
                type="index_set",
                scenario_id=Scenario.LOG,
                bk_biz_id=BK_BIZ_ID,
                apply_status=LogIndexSetData.Status.NORMAL,
            )
            # 子索引集到 ES 结果表的关联行，必须是已应用状态才会被取到。
            LogIndexSetData.objects.create(
                index_set_id=child_id,
                result_table_id=result_table_id,
                type="result_table",
                scenario_id=Scenario.LOG,
                bk_biz_id=BK_BIZ_ID,
                apply_status=LogIndexSetData.Status.NORMAL,
            )
        self.assertFalse(self.index_set.is_native_doris())

    def _build_handler(self, fields, indices="100915_bklog.lobby", index_set=None):
        """构造仅用于取字段的 UQ mapping handler，并注入字段映射返回值。"""
        handler = UnifyQueryMappingHandler(
            indices=indices,
            index_set_id=GROUP_ID,
            scenario_id=Scenario.LOG,
            storage_cluster_id=1,
            time_field="dtEventTimeStamp",
            start_time="1",
            end_time="2",
            bk_biz_id=BK_BIZ_ID,
            only_search=True,
            index_set=index_set or self.index_set,
        )
        self.mock_field_map.return_value = {"data": fields}
        return handler

    @staticmethod
    def _by_name(fields):
        """把字段列表转成按字段名索引的字典，便于逐字段精确断言。"""
        return {field["field_name"]: field for field in fields}


class TestMixedStorageFinalFields(MixedStorageFixtureMixin, TestCase):
    """覆盖混挂索引组的字段类型规范化及相关下游链路。"""

    def setUp(self):
        """建立真实 model，并只替换外部字段接口与聚类配置查询。"""
        super().setUp()
        self._create_models()
        self.mock_field_map = self.enterContext(
            patch("apps.log_unifyquery.handler.mapping.UnifyQueryApi.query_field_map")
        )
        self.enterContext(
            patch(
                "apps.log_unifyquery.handler.mapping.ClusteringConfig.get_by_index_set_id",
                return_value=None,
            )
        )

    def test_mixed_group_normalizes_sql_types_without_doris_tag(self):
        """组无 Doris 标签时，5 个 SQL 类型被规范化且操作符与聚合能力不变。"""
        handler = self._build_handler(_mixed_fields())
        fields = handler.get_final_fields()
        by_name = self._by_name(fields)

        self.assertEqual(len(fields), 8)
        expected_types = {
            "dtEventTime": "date",
            "localTime": "keyword",
            "thedate": "integer",
            "__shard_key__": "long",
            "__unique_key__": "keyword",
            "time": "date",
            "dtEventTimeStamp": "date",
            "log": "text",
        }
        for name, expected in expected_types.items():
            with self.subTest(name=name):
                self.assertEqual(by_name[name]["field_type"], expected)

        # 被规范化的字段保持原来的空操作符，不扩大查询能力。
        for name in ["dtEventTime", "localTime", "thedate", "__shard_key__", "__unique_key__"]:
            with self.subTest(name=name):
                self.assertEqual(by_name[name]["field_operator"], [])
        self.assertEqual(by_name["time"]["field_operator"], OPERATORS["date"])
        self.assertEqual(by_name["log"]["field_operator"], OPERATORS["text"])

        self.assertTrue(by_name["dtEventTime"]["es_doc_values"])
        self.assertFalse(by_name["log"]["es_doc_values"])

        self.assertEqual(by_name["dtEventTime"]["tag"], "timestamp")
        self.assertEqual(
            [field["field_name"] for field in fields],
            [
                "dtEventTime",
                "time",
                "localTime",
                "thedate",
                "__shard_key__",
                "__unique_key__",
                "log",
                "dtEventTimeStamp",
            ],
        )
        self.mock_field_map.assert_called_once()

    def test_capability_bits_follow_normalized_types(self):
        """能力位按规范化后的类型判定：数值类型放行，字符类型仍拒绝。"""
        fields = _mixed_fields()
        fields.extend(
            [
                {"field_name": "gseIndex", "field_type": "keyword", "is_agg": True},
                {"field_name": "serverIp", "field_type": "keyword", "is_agg": True},
                {"field_name": "path", "field_type": "keyword", "is_agg": True},
                {"field_name": "iterationIndex", "field_type": "bigint", "is_agg": True},
                {"field_name": "gseindex", "field_type": "bigint", "is_agg": True},
                {"field_name": "iteration", "field_type": "int", "is_agg": True},
            ]
        )

        # 场景一：数值型 SQL 类型规范化后为 long/integer，应放行，与原生 Doris 路径一致。
        normalized = self._build_handler(fields).get_final_fields()
        by_name = self._by_name(normalized)
        self.assertEqual(by_name["iterationIndex"]["field_type"], "long")
        self.assertEqual(by_name["gseindex"]["field_type"], "long")
        self.assertEqual(by_name["iteration"]["field_type"], "integer")
        after = UnifyQueryMappingHandler.analyze_fields(normalized)
        self.assertTrue(after["context_search_usable"])
        self.assertTrue(after["realtime_search_usable"])
        self.assertEqual(after["usable_reason"], "")

        # 场景二：字符型 SQL 类型规范化后为 keyword，不在数值白名单，仍应拒绝。
        rejected_fields = [dict(item) for item in fields]
        for item in rejected_fields:
            if item["field_name"] == "iterationIndex":
                item["field_type"] = "varchar(32)"
        rejected_normalized = self._build_handler(rejected_fields).get_final_fields()
        rejected_by_name = self._by_name(rejected_normalized)
        self.assertEqual(rejected_by_name["iterationIndex"]["field_type"], "keyword")
        rejected = UnifyQueryMappingHandler.analyze_fields(rejected_normalized)
        self.assertFalse(rejected["context_search_usable"])
        self.assertFalse(rejected["realtime_search_usable"])
        self.assertIn("iterationIndex", rejected["usable_reason"])

    def test_pure_es_index_set_fields_are_untouched(self):
        """纯 ES 索引集的字段列表与修复前逐字段一致。"""
        es_fields = [
            {"field_name": "dtEventTimeStamp", "field_type": "date", "is_agg": True},
            {"field_name": "serverIp", "field_type": "keyword", "is_agg": True},
            {"field_name": "level", "field_type": "long", "is_agg": True},
            {"field_name": "log", "field_type": "text", "is_agg": False},
        ]
        fields = self._build_handler(es_fields).get_final_fields()
        by_name = self._by_name(fields)
        self.assertEqual(len(fields), 4)
        self.assertEqual(by_name["dtEventTimeStamp"]["field_type"], "date")
        self.assertEqual(by_name["serverIp"]["field_type"], "keyword")
        self.assertEqual(by_name["level"]["field_type"], "long")
        self.assertEqual(by_name["log"]["field_type"], "text")

    def test_native_doris_index_set_keeps_existing_behavior(self):
        """原生 Doris 分支不受补充映射表影响，未覆盖类型原样返回。"""
        CollectorConfig.objects.create(
            table_id="100915_bklog.native_doris",
            bk_biz_id=BK_BIZ_ID,
            collector_config_name="native_doris",
            collector_scenario_id="log",
            category_id="other_rt",
            storage_cluster_type=DORIS_CLUSTER_TYPE,
        )
        fields = _mixed_fields()
        fields.extend(
            [
                {"field_name": "extra_largeint", "field_type": "largeint", "is_agg": True},
                {"field_name": "extra_decimal", "field_type": "decimal(10,2)", "is_agg": True},
                {"field_name": "extra_array", "field_type": "array", "is_agg": True},
            ]
        )
        handler = self._build_handler(fields, indices="100915_bklog.native_doris")
        by_name = self._by_name(handler.get_final_fields())
        self.assertEqual(by_name["dtEventTime"]["field_type"], "date")
        self.assertEqual(by_name["localTime"]["field_type"], "keyword")
        self.assertEqual(by_name["extra_largeint"]["field_type"], "largeint")
        self.assertEqual(by_name["extra_decimal"]["field_type"], "decimal(10,2)")
        self.assertEqual(by_name["extra_array"]["field_type"], "array")

    def test_manual_doris_tag_index_set_keeps_existing_behavior(self):
        """手动打 Doris 标签的索引集同样保持既有分支行为。"""
        doris_tag_id = str(IndexSetTag.get_tag_id("Doris", tag_type=TAG_TYPE_INNER))
        self.index_set.tag_ids = [doris_tag_id]
        self.index_set.save(update_fields=["tag_ids"])
        by_name = self._by_name(self._build_handler(_mixed_fields()).get_final_fields())
        self.assertEqual(by_name["dtEventTime"]["field_type"], "date")
        self.assertEqual(by_name["localTime"]["field_type"], "keyword")
        self.assertEqual(
            IndexSetTag.objects.filter(name="Doris", tag_type="inner").count(),
            1,
        )

    def test_fields_snapshot_persists_full_fields_result(self):
        """字段快照保存字段接口的完整返回，包含能力位配置且不裁剪。"""
        payload = {
            "fields": [{"field_name": "log", "field_type": "text"}],
            "config": [{"name": "context_and_realtime", "is_active": False, "extra": {"reason": ""}}],
        }
        result = LogIndexSet.fields_to_string(fields=payload)
        self.assertEqual(result["fields"], payload["fields"])
        self.assertEqual(result["config"], payload["config"])
        self.assertEqual(result["usable_reason"], "")

        with patch("apps.log_unifyquery.handler.base.UnifyQueryHandler") as mock_uq:
            mock_uq.return_value.fields.return_value = payload
            self.index_set.sync_fields_snapshot()
        mock_uq.assert_called_once()
        self.index_set.refresh_from_db()
        self.assertEqual(
            self.index_set.fields_snapshot["config"][0]["name"],
            "context_and_realtime",
        )
        self.assertIs(self.index_set.fields_snapshot["config"][0]["is_active"], False)

    def test_default_and_analysis_routes_are_unchanged(self):
        """默认与分析路由的集合及字段值由自建构造数据精确推导。"""
        with patch(
            "apps.log_search.handlers.index_set.DorisClusterHandler.get_cluster_id",
            return_value=DORIS_CLUSTER_ID,
        ):
            default_items = []
            analysis_items = []
            for child_id in [CHILD_DORIS_A, CHILD_DORIS_B, CHILD_ES]:
                child = LogIndexSet.objects.get(index_set_id=child_id)
                for is_analysis, bucket in [(False, default_items), (True, analysis_items)]:
                    bucket.extend(
                        BaseIndexSetHandler.get_index_set_table_info_list(
                            index_set=child,
                            is_analysis=is_analysis,
                            parent_index_set=self.index_set,
                        )
                    )

        expected_default = {
            f"bklog_index_set_{GROUP_ID}_{table}.__doris__" for table in DORIS_TABLES
        }
        expected_default.add(f"bklog_index_set_{GROUP_ID}_100915_bklog_lobby.__default__")
        expected_analysis = {
            f"bklog_index_set_{GROUP_ID}_{table}.__analysis__" for table in DORIS_TABLES
        }
        expected_analysis.add(f"bklog_index_set_{GROUP_ID}_{LOBBY_DORIS_TABLE}.__analysis__")
        self.assertEqual({item["table_id"] for item in default_items}, expected_default)
        self.assertEqual(len(default_items), len(expected_default))
        self.assertEqual({item["table_id"] for item in analysis_items}, expected_analysis)
        self.assertEqual(len(analysis_items), len(expected_analysis))

        for item in analysis_items:
            with self.subTest(table_id=item["table_id"]):
                self.assertEqual(item["storage_type"], "doris")
                self.assertEqual(item["source_type"], "bkdata")
                self.assertEqual(item["cluster_id"], DORIS_CLUSTER_ID)

        # 带 Doris 标签的子集在默认路由只返回 Doris 项，ES 断言只作用于默认后缀的项。
        es_default_items = [
            item for item in default_items if item["table_id"].endswith(".__default__")
        ]
        self.assertEqual(len(es_default_items), 1)
        for item in es_default_items:
            with self.subTest(table_id=item["table_id"]):
                self.assertEqual(item["source_type"], Scenario.LOG)
                # 构造未给存储集群 ID，路由项因此不带 storage_type 键。
                self.assertNotIn("storage_type", item)
                self.assertIsNone(item["cluster_id"])

    def test_empty_fields_early_return_normalizes_snapshot(self):
        """字段接口返回空列表时用快照兜底，并对快照中的 SQL 类型做同等规范化。"""
        self.index_set.fields_snapshot = {
            "fields": [
                {"field_name": "dtEventTime", "field_type": "datetime", "es_doc_values": True},
                {"field_name": "log", "field_type": "text", "es_doc_values": False},
            ]
        }
        self.index_set.save(update_fields=["fields_snapshot"])
        fields = self._build_handler([]).get_final_fields()
        by_name = self._by_name(fields)
        self.assertEqual(len(fields), 2)
        self.assertEqual(by_name["dtEventTime"]["field_type"], "date")
        self.assertEqual(by_name["dtEventTime"]["tag"], "timestamp")
        self.assertEqual(by_name["log"]["field_type"], "text")
        # 兜底返回的是深拷贝，不能改写索引集上保存的快照内容。
        self.assertEqual(self.index_set.fields_snapshot["fields"][0]["field_type"], "datetime")

    def test_export_time_field_judgement_unchanged(self):
        """补充映射表未泄漏到异步导出的时间字段类型判定。"""
        handler = SimpleNamespace(
            index_info_list=[{"index_set_id": GROUP_ID}],
            base_dict={
                "query_list": [{"table_id": f"bklog_index_set_{GROUP_ID}"}],
                "bk_biz_id": BK_BIZ_ID,
                "start_time": "1",
                "end_time": "2",
            },
        )
        with (
            patch(
                "apps.log_search.export.query.UnifyQueryHandler.init_time_field",
                return_value=("dtEventTimeStamp", "date", "millisecond"),
            ),
            patch(
                "apps.log_search.export.query.UnifyQueryApi.query_field_map",
                return_value={"data": [{"field_name": "dtEventTimeStamp", "field_type": "largeint"}]},
            ),
        ):
            with self.assertRaises(UnsupportedExportTimeField):
                snapshot_time_fields(handler, ExportSearchType.INDEX_SET)

    def test_default_display_fields_and_config_after_normalization(self):
        """无 log 与 text 字段时，默认展示字段由 keyword 兜底推导并精确落库。"""
        fields = [
            {"field_name": "dtEventTime", "field_type": "datetime", "is_agg": True},
            {"field_name": "localTime", "field_type": "varchar(32)", "is_agg": True},
            {"field_name": "thedate", "field_type": "int", "is_agg": True},
            {"field_name": "__shard_key__", "field_type": "bigint", "is_agg": True},
            {"field_name": "__unique_key__", "field_type": "varchar(512)", "is_agg": True},
            {"field_name": "time", "field_type": "date", "is_agg": True},
            {"field_name": "dtEventTimeStamp", "field_type": "date", "is_agg": True},
        ]
        handler = self._build_handler(fields)
        # 默认配置创建时会读取请求用户名，固定该值避免创建者字段落库为空。
        with patch("apps.log_unifyquery.handler.mapping.get_request_username", return_value="admin"):
            obj = handler.get_or_create_default_config()
        self.assertEqual(obj.display_fields, ["dtEventTimeStamp", "localTime"])
        self.assertEqual(obj.sort_list, [["dtEventTimeStamp", "desc"]])
        self.assertEqual(IndexSetFieldsConfig.objects.filter(index_set_id=GROUP_ID).count(), 1)

    def test_union_search_fields_marks_same_name_type_conflict(self):
        """联合检索中同名不同类型的字段被标记为类型冲突。"""
        ids = [CHILD_DORIS_A, CHILD_DORIS_B]

        def _result(thedate_type):
            return {
                "fields": [
                    {"field_name": "dtEventTimeStamp", "field_type": "date", "es_doc_values": True},
                    {"field_name": "thedate", "field_type": thedate_type, "es_doc_values": True},
                ],
                "display_fields": ["dtEventTimeStamp"],
                "config": [
                    {"name": "context_and_realtime", "is_active": False, "extra": {"reason": ""}}
                ],
            }

        multi_result = {
            f"union_search_fields_{ids[0]}": _result("integer"),
            f"union_search_fields_{ids[1]}": _result("long"),
        }
        fake_config = SimpleNamespace(id=1, display_fields=["dtEventTimeStamp"], sort_list=[])
        with (
            patch("apps.log_unifyquery.handler.base.UnifyQueryHandler"),
            patch("apps.utils.thread.MultiExecuteFunc.run", return_value=multi_result),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.SearchHandler.init_time_field",
                return_value=("dtEventTimeStamp", "date", "millisecond"),
            ),
            patch.object(UnionSearchHandler, "get_or_create_default_config", return_value=fake_config),
        ):
            ret = UnionSearchHandler().unifyquery_union_search_fields(
                {"index_set_ids": ids, "bk_biz_id": BK_BIZ_ID, "start_time": 1, "end_time": 2}
            )
        by_name = {item["field_name"]: item for item in ret["fields"]}
        self.assertEqual(by_name["thedate"]["field_type"], "conflict")
        self.assertEqual(set(by_name["thedate"]["index_set_ids"]), set(ids))
        self.assertEqual(by_name["dtEventTimeStamp"]["field_type"], "date")

    def _statistics_request(self, payload, action):
        """构造字段统计视图的请求；直接调用视图方法以绕过权限中间件。"""
        raw_request = APIRequestFactory().post(
            f"/api/v1/field/index_set/{action}/", data=payload, format="json"
        )
        request = Request(raw_request, parsers=[JSONParser()])
        view = FieldViewSet(format_kwarg=None)
        view.request = request
        view.kwargs = {}
        view.action = action
        return view, request

    def test_field_statistics_filter_excludes_text_and_non_agg_fields(self):
        """字段统计只保留非 text 且可聚合的字段，返回列表精确可预期。"""
        payload = {
            "bk_biz_id": BK_BIZ_ID,
            "index_set_ids": [GROUP_ID],
            "start_time": 1,
            "end_time": 2,
            "keyword": "",
        }
        view, request = self._statistics_request(payload, "fetch_distinct_count_list")
        fields_result = {
            "fields": [
                {"field_name": "thedate", "field_type": "integer", "es_doc_values": True},
                {"field_name": "localTime", "field_type": "keyword", "es_doc_values": True},
                {"field_name": "log", "field_type": "text", "es_doc_values": False},
                {"field_name": "__shard_key__", "field_type": "long", "es_doc_values": False},
            ]
        }
        multi_result = {"distinct_count_thedate": 7, "distinct_count_localTime": 3}
        with (
            patch("apps.log_search.views.field_views.UnionSearchHandler") as mock_union,
            patch("apps.log_search.views.field_views.UnifyQueryFieldHandler"),
            patch("apps.utils.thread.MultiExecuteFunc.run", return_value=multi_result),
        ):
            mock_union.return_value.unifyquery_union_search_fields.return_value = fields_result
            response = view.fetch_distinct_count_list(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            [
                {"field_name": "thedate", "distinct_count": 7},
                {"field_name": "localTime", "distinct_count": 3},
            ],
        )

    def test_statistics_graph_uses_single_branch_by_distinct_count(self):
        """统计图表按去重数量与阈值二选一，只调用对应分支。"""
        base = {
            "bk_biz_id": BK_BIZ_ID,
            "index_set_ids": [GROUP_ID],
            "start_time": 1,
            "end_time": 2,
            "keyword": "",
            "agg_field": "thedate",
            "field_type": "integer",
            "threshold": 10,
            "min": 0,
            "max": 100,
        }
        cases = [
            ({**base, "distinct_count": 1}, "get_topk_list", [10], "get_bucket_data"),
            ({**base, "distinct_count": 10}, "get_bucket_data", [0, 100], "get_topk_list"),
        ]
        for payload, called, args, not_called in cases:
            with self.subTest(distinct_count=payload["distinct_count"]):
                view, request = self._statistics_request(payload, "fetch_statistics_graph")
                with patch("apps.log_search.views.field_views.UnifyQueryFieldHandler") as mock_cls:
                    handler = mock_cls.return_value
                    handler.get_topk_list.return_value = [{"_value": 1, "_count": 2}]
                    handler.get_bucket_data.return_value = [[0, 2]]
                    response = view.fetch_statistics_graph(request)
                getattr(handler, called).assert_called_once_with(*args)
                getattr(handler, not_called).assert_not_called()
                self.assertEqual(response.status_code, 200)

    def test_floating_point_bucket_step_uses_two_digits(self):
        """浮点类型的聚合桶步长保留两位小数，整型类型按整数取整。"""
        handler = UnifyQueryFieldHandler.__new__(UnifyQueryFieldHandler)
        handler.search_params = {"field_type": "double"}
        with patch.object(UnifyQueryFieldHandler, "get_bucket_count", return_value=5):
            buckets = handler.get_bucket_data(0, 1, 3)
        self.assertEqual(buckets, [[0, 5], [0.33, 5], [0.66, 5]])

        handler.search_params = {"field_type": "integer"}
        with patch.object(UnifyQueryFieldHandler, "get_bucket_count", return_value=5):
            integer_buckets = handler.get_bucket_data(0, 1, 3)
        self.assertEqual(integer_buckets, [[0, 5], [0, 5], [0, 5]])


class TestMixedStorageFieldsEndpoint(MixedStorageFixtureMixin, TestCase):
    """接口层：带权限脚手架，精确断言实时字段响应与能力位。"""

    def setUp(self):
        """建立真实 model 并替换外部字段接口与聚类配置查询。"""
        super().setUp()
        self._create_models()
        self.mock_field_map = self.enterContext(
            patch("apps.log_unifyquery.handler.mapping.UnifyQueryApi.query_field_map")
        )
        self.enterContext(
            patch(
                "apps.log_unifyquery.handler.mapping.ClusteringConfig.get_by_index_set_id",
                return_value=None,
            )
        )

    @override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,), IGNORE_IAM_PERMISSION=True)
    @FakeRedis("apps.utils.cache.cache")
    def test_fields_endpoint_realtime_branch_returns_es_types(self):
        """实时字段接口返回规范化类型与空操作符；字段不命中组合时能力位为不可用。"""
        self.mock_field_map.return_value = {"data": _mixed_fields()}
        response = self.client.get(
            f"/api/v1/search/index_set/{GROUP_ID}/fields/",
            data={
                "bk_biz_id": BK_BIZ_ID,
                "start_time": 1,
                "end_time": 2,
                "is_realtime": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.data["result"], True)
        data = response.data["data"]
        by_name = self._by_name(data["fields"])
        self.assertEqual(len(data["fields"]), 8)
        self.assertEqual(by_name["dtEventTime"]["field_type"], "date")
        self.assertEqual(by_name["localTime"]["field_type"], "keyword")
        self.assertEqual(by_name["thedate"]["field_type"], "integer")
        self.assertEqual(by_name["__shard_key__"]["field_type"], "long")
        self.assertEqual(by_name["__unique_key__"]["field_type"], "keyword")
        self.assertEqual(by_name["dtEventTime"]["field_operator"], [])
        self.assertIsInstance(data["user_custom_config"], dict)
        self.assertIsInstance(data["custom_config"], dict)

        # 这组字段不命中上下文检索的字段组合，字段能力位在校验阶段提前返回。
        # 接口层据此固化基线；按规范化后类型判定的完整双场景由集成用例覆盖。
        config_item = next(
            item for item in data["config"] if item["name"] == "context_and_realtime"
        )
        self.assertFalse(config_item["is_active"])
        # 请求初始化时快照为空会先同步一次字段，业务字段接口再取一次，共两次。
        self.assertEqual(self.mock_field_map.call_count, 2)
        self.assertEqual(
            self.mock_field_map.call_args_list[-1].args[0],
            {
                "data_source": "bklog",
                "start_time": "1",
                "end_time": "2",
                "table_id": f"bklog_index_set_{GROUP_ID}",
                "bk_biz_id": BK_BIZ_ID,
            },
        )
