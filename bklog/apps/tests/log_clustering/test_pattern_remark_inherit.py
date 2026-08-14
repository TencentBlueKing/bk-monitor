import copy
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from apps.feature_toggle.handlers.toggle import Toggle
from apps.log_clustering.constants import CLUSTERING_REMARK_GROUP_FALLBACK_BIZ_ID_BLACK_LIST
from apps.log_clustering.exceptions import ClusteringOwnersNotExistException
from apps.log_clustering.handlers.clustering_monitor import ClusteringMonitorHandler
from apps.log_clustering.handlers.pattern import PatternHandler
from apps.log_clustering.models import AiopsSignatureAndPattern, ClusteringConfig, ClusteringRemark

INDEX_SET_ID = 123
BK_BIZ_ID = 2
SIGNATURE = "e4b60ecf"
GROUP_FIELDS = ["service_name", "func"]
CURRENT_GROUPS = {"service_name": "gamesvr", "func": "AddExp"}

PARAMS = {
    "addition": [],
    "start_time": "2024-07-04 14:21:32",
    "end_time": "2024-07-11 14:21:32",
    "time_range": "customized",
    "keyword": "*",
    "size": 10000,
    "pattern_level": "05",
    "show_new_pattern": False,
    "year_on_year_hour": 0,
    "group_by": GROUP_FIELDS,
    "remark_config": "all",
    "owner_config": "all",
    "owners": [],
}

INHERITED_REMARK = {"username": "tester", "create_time": 1000, "remark": "inherited remark"}


def build_remark(groups, **kwargs):
    return ClusteringRemark.objects.create(
        bk_biz_id=BK_BIZ_ID,
        signature=kwargs.pop("signature", SIGNATURE),
        groups=groups,
        group_hash=ClusteringRemark.convert_groups_to_groups_hash(groups),
        **kwargs,
    )


class TestPatternRemarkSubsetInherit(TestCase):
    """展示端：备注分组维度是当前分组组合子集时可继承。"""

    def setUp(self) -> None:  # pylint: disable=invalid-name
        ClusteringConfig.objects.create(
            index_set_id=INDEX_SET_ID,
            min_members=100,
            max_dist_list="xxx",
            predefined_varibles="^hi",
            delimeter="x",
            max_log_length=1024,
            bk_biz_id=BK_BIZ_ID,
            model_id="model_1",
            group_fields=GROUP_FIELDS,
        )
        AiopsSignatureAndPattern.objects.create(model_id="model_1", signature=SIGNATURE, pattern="some pattern")

    def search(self, feature_config=None):
        with (
            patch("apps.log_clustering.handlers.pattern.FeatureToggleObject.toggle") as mock_toggle,
            patch.object(PatternHandler, "_multi_query") as mock_multi_query,
        ):
            mock_toggle.return_value = Toggle(feature_config=feature_config or {})
            mock_multi_query.return_value = {
                "pattern_aggs": [{"key": SIGNATURE, "doc_count": 34, "group": "gamesvr|AddExp"}],
                "year_on_year_result": {},
                "new_class": set(),
            }
            return PatternHandler(INDEX_SET_ID, copy.deepcopy(PARAMS)).pattern_search()

    def test_inherits_remark_from_subset_group(self):
        build_remark({"service_name": "gamesvr"}, remark=[INHERITED_REMARK], owners=["admin"])

        result = self.search()

        self.assertEqual(result[0]["remark"], [INHERITED_REMARK])
        self.assertEqual(result[0]["owners"], ["admin"])

    def test_inherits_remark_from_empty_group(self):
        build_remark({}, remark=[INHERITED_REMARK])

        result = self.search()

        self.assertEqual(result[0]["remark"], [INHERITED_REMARK])

    def test_inherits_remark_only_when_source_has_no_owner(self):
        build_remark({"service_name": "gamesvr"}, remark=[INHERITED_REMARK], owners=[])

        result = self.search()

        self.assertEqual(result[0]["remark"], [INHERITED_REMARK])
        self.assertEqual(result[0]["owners"], [])

    def test_inherits_owner_only_when_source_has_no_remark(self):
        build_remark({"service_name": "gamesvr"}, remark=[], owners=["admin"])

        result = self.search()

        self.assertEqual(result[0]["remark"], [])
        self.assertEqual(result[0]["owners"], ["admin"])

    def test_split_content_keeps_only_the_winning_candidate(self):
        # 备注与负责人取自同一条获胜记录，分散在不同深度时落选那条的内容不展示
        build_remark({}, remark=[INHERITED_REMARK], owners=[])
        build_remark({"service_name": "gamesvr"}, remark=[], owners=["admin"])

        result = self.search()

        self.assertEqual(result[0]["remark"], [])
        self.assertEqual(result[0]["owners"], ["admin"])

    def test_split_content_keeps_deeper_remark_over_shallower_owner(self):
        build_remark({}, remark=[], owners=["admin"])
        build_remark({"service_name": "gamesvr"}, remark=[INHERITED_REMARK], owners=[])

        result = self.search()

        self.assertEqual(result[0]["remark"], [INHERITED_REMARK])
        self.assertEqual(result[0]["owners"], [])

    def test_exact_owner_only_record_stops_inheriting_parent_remark(self):
        build_remark({"service_name": "gamesvr"}, remark=[INHERITED_REMARK], owners=[])
        build_remark(CURRENT_GROUPS, remark=[], owners=["admin"])

        result = self.search()

        self.assertEqual(result[0]["remark"], [])
        self.assertEqual(result[0]["owners"], ["admin"])

    def test_skips_remark_when_shared_dimension_value_differs(self):
        build_remark({"service_name": "relaysvr"}, remark=[INHERITED_REMARK])

        result = self.search()

        self.assertEqual(result[0]["remark"], [])

    def test_skips_remark_when_group_is_not_subset(self):
        build_remark({"service_name": "gamesvr", "module": "trade"}, remark=[INHERITED_REMARK])

        result = self.search()

        self.assertEqual(result[0]["remark"], [])

    def test_prefers_candidate_with_more_matched_dimensions(self):
        build_remark({}, remark=[{**INHERITED_REMARK, "remark": "empty group"}])
        build_remark({"service_name": "gamesvr"}, remark=[{**INHERITED_REMARK, "remark": "one dimension"}])
        build_remark(CURRENT_GROUPS, remark=[{**INHERITED_REMARK, "remark": "exact"}])

        result = self.search()

        self.assertEqual(result[0]["remark"][0]["remark"], "exact")

    def test_breaks_same_length_tie_by_group_fields_order(self):
        build_remark({"func": "AddExp"}, remark=[{**INHERITED_REMARK, "remark": "by func"}])
        build_remark({"service_name": "gamesvr"}, remark=[{**INHERITED_REMARK, "remark": "by service_name"}])

        result = self.search()

        self.assertEqual(result[0]["remark"][0]["remark"], "by service_name")

    def test_does_not_inherit_for_black_list_biz(self):
        build_remark({"service_name": "gamesvr"}, remark=[INHERITED_REMARK], owners=["admin"])

        result = self.search(feature_config={CLUSTERING_REMARK_GROUP_FALLBACK_BIZ_ID_BLACK_LIST: [BK_BIZ_ID]})

        self.assertEqual(result[0]["remark"], [])
        self.assertEqual(result[0]["owners"], [])

    def test_does_not_inherit_strategy_binding(self):
        build_remark(
            {"service_name": "gamesvr"},
            remark=[INHERITED_REMARK],
            owners=["admin"],
            strategy_id=7,
            strategy_enabled=True,
        )

        result = self.search()

        # 备注可继承，但策略属于父维度：子维度行展示成已启用会得到一个停不掉的开关
        self.assertEqual(result[0]["remark"], [INHERITED_REMARK])
        self.assertEqual(result[0]["strategy_id"], 0)
        self.assertFalse(result[0]["strategy_enabled"])

    def test_keeps_strategy_binding_on_exact_group(self):
        build_remark(CURRENT_GROUPS, remark=[INHERITED_REMARK], strategy_id=7, strategy_enabled=True)

        result = self.search()

        self.assertEqual(result[0]["strategy_id"], 7)
        self.assertTrue(result[0]["strategy_enabled"])

    def test_group_value_is_compared_strictly(self):
        # 等长时该判定必须与 group_hash 相等等价，否则展示端会命中写入端定位不到的记录
        self.assertTrue(ClusteringRemark.is_groups_inheritable({"service_name": "1"}, {"service_name": "1"}))
        self.assertFalse(ClusteringRemark.is_groups_inheritable({"service_name": 1}, {"service_name": "1"}))

    def test_keeps_exact_group_remark_for_black_list_biz(self):
        build_remark(CURRENT_GROUPS, remark=[INHERITED_REMARK])

        result = self.search(feature_config={CLUSTERING_REMARK_GROUP_FALLBACK_BIZ_ID_BLACK_LIST: [BK_BIZ_ID]})

        self.assertEqual(result[0]["remark"], [INHERITED_REMARK])


class TestPatternRemarkMaterialize(TestCase):
    """写入端：继承内容先物化成当前分组组合的独立记录，再执行原有写入。"""

    def setUp(self) -> None:  # pylint: disable=invalid-name
        ClusteringConfig.objects.create(
            index_set_id=INDEX_SET_ID,
            min_members=100,
            max_dist_list="xxx",
            predefined_varibles="^hi",
            delimeter="x",
            max_log_length=1024,
            bk_biz_id=BK_BIZ_ID,
            group_fields=GROUP_FIELDS,
        )
        self.source = build_remark(
            {"service_name": "gamesvr"},
            remark=[INHERITED_REMARK],
            owners=["admin"],
            strategy_id=7,
            strategy_enabled=True,
            notice_group_id=11,
        )
        toggle_patcher = patch("apps.log_clustering.handlers.pattern.FeatureToggleObject.toggle")
        toggle_patcher.start().return_value = Toggle(feature_config={})
        self.addCleanup(toggle_patcher.stop)
        username_patcher = patch("apps.log_clustering.handlers.pattern.get_request_username", return_value="tester")
        username_patcher.start()
        self.addCleanup(username_patcher.stop)
        self.handler = PatternHandler(INDEX_SET_ID, copy.deepcopy(PARAMS))

    def get_materialized(self):
        return ClusteringRemark.objects.get(group_hash=ClusteringRemark.convert_groups_to_groups_hash(CURRENT_GROUPS))

    def base_params(self, **kwargs):
        return {"signature": SIGNATURE, "origin_pattern": "", "groups": copy.deepcopy(CURRENT_GROUPS), **kwargs}

    def test_create_remark_keeps_inherited_content(self):
        self.handler.set_clustering_remark(self.base_params(remark="new remark"), method="create")

        materialized = self.get_materialized()
        self.assertEqual([item["remark"] for item in materialized.remark], ["inherited remark", "new remark"])
        self.assertEqual(materialized.owners, ["admin"])

    def test_materialized_record_does_not_copy_strategy_binding(self):
        self.handler.set_clustering_remark(self.base_params(remark="new remark"), method="create")

        materialized = self.get_materialized()
        self.assertEqual(materialized.strategy_id, 0)
        self.assertFalse(materialized.strategy_enabled)
        self.assertEqual(materialized.notice_group_id, 0)

    def test_materialize_copies_instead_of_moving_source(self):
        self.handler.set_clustering_remark(self.base_params(remark="new remark"), method="create")

        self.source.refresh_from_db()
        self.assertEqual(self.source.remark, [INHERITED_REMARK])
        self.assertEqual(self.source.strategy_id, 7)

    def test_update_inherited_remark_after_materialize(self):
        self.handler.set_clustering_remark(
            self.base_params(create_time=1000, old_remark="inherited remark", new_remark="edited remark"),
            method="update",
        )

        self.assertEqual(self.get_materialized().remark[0]["remark"], "edited remark")
        self.source.refresh_from_db()
        self.assertEqual(self.source.remark, [INHERITED_REMARK])

    def test_delete_inherited_remark_after_materialize(self):
        self.handler.set_clustering_remark(
            self.base_params(create_time=1000, remark="inherited remark"), method="delete"
        )

        self.assertEqual(self.get_materialized().remark, [])
        self.source.refresh_from_db()
        self.assertEqual(self.source.remark, [INHERITED_REMARK])

    def test_set_owner_keeps_inherited_remark(self):
        self.handler.set_clustering_owner(self.base_params(owners=["new_owner"]))

        materialized = self.get_materialized()
        self.assertEqual(materialized.remark, [INHERITED_REMARK])
        self.assertEqual(materialized.owners, ["new_owner"])

    def test_does_not_materialize_for_black_list_biz(self):
        with patch("apps.log_clustering.handlers.pattern.FeatureToggleObject.toggle") as mock_toggle:
            mock_toggle.return_value = Toggle(
                feature_config={CLUSTERING_REMARK_GROUP_FALLBACK_BIZ_ID_BLACK_LIST: [BK_BIZ_ID]}
            )
            handler = PatternHandler(INDEX_SET_ID, copy.deepcopy(PARAMS))
            handler.set_clustering_remark(self.base_params(remark="new remark"), method="create")

        self.assertEqual([item["remark"] for item in self.get_materialized().remark], ["new remark"])


class TestPatternRemarkMaterializeSplitContent(TestCase):
    """写入端：备注与负责人分散在不同深度记录时，物化只能带走获胜的那一条。"""

    def setUp(self) -> None:  # pylint: disable=invalid-name
        ClusteringConfig.objects.create(
            index_set_id=INDEX_SET_ID,
            min_members=100,
            max_dist_list="xxx",
            predefined_varibles="^hi",
            delimeter="x",
            max_log_length=1024,
            bk_biz_id=BK_BIZ_ID,
            group_fields=GROUP_FIELDS,
        )
        toggle_patcher = patch("apps.log_clustering.handlers.pattern.FeatureToggleObject.toggle")
        toggle_patcher.start().return_value = Toggle(feature_config={})
        self.addCleanup(toggle_patcher.stop)
        username_patcher = patch("apps.log_clustering.handlers.pattern.get_request_username", return_value="tester")
        username_patcher.start()
        self.addCleanup(username_patcher.stop)
        self.handler = PatternHandler(INDEX_SET_ID, copy.deepcopy(PARAMS))

    def create_remark(self):
        self.handler.set_clustering_remark(
            {
                "signature": SIGNATURE,
                "origin_pattern": "",
                "groups": copy.deepcopy(CURRENT_GROUPS),
                "remark": "new remark",
            },
            method="create",
        )
        return ClusteringRemark.objects.get(group_hash=ClusteringRemark.convert_groups_to_groups_hash(CURRENT_GROUPS))

    def test_materialize_carries_owner_from_remark_less_source(self):
        build_remark({"service_name": "gamesvr"}, remark=[], owners=["admin"])

        materialized = self.create_remark()

        self.assertEqual([item["remark"] for item in materialized.remark], ["new remark"])
        self.assertEqual(materialized.owners, ["admin"])

    def test_materialize_drops_content_from_losing_candidate(self):
        build_remark({}, remark=[INHERITED_REMARK], owners=[])
        build_remark({"service_name": "gamesvr"}, remark=[], owners=["admin"])

        materialized = self.create_remark()

        # 空维备注不在获胜记录上，物化带不走；精确记录建成后该行也不再向上继承
        self.assertEqual([item["remark"] for item in materialized.remark], ["new remark"])
        self.assertEqual(materialized.owners, ["admin"])


class TestSavePatternStrategyRemarkFallback(TestCase):
    """启停告警入口：无精确记录时先物化，彻底没有可继承内容时也不能抛 AttributeError。"""

    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.handler = ClusteringMonitorHandler.__new__(ClusteringMonitorHandler)
        self.handler.index_set_id = INDEX_SET_ID
        self.handler.bk_biz_id = BK_BIZ_ID
        self.handler.conf = {}
        self.handler.clustering_config = SimpleNamespace(
            bk_biz_id=BK_BIZ_ID, group_fields=GROUP_FIELDS, new_cls_index_set_id=None
        )
        self.handler.index_set = SimpleNamespace(index_set_name="test_set", time_field="dtEventTimeStamp")

    def params(self, strategy_enabled):
        return {
            "signature": SIGNATURE,
            "origin_pattern": "",
            "groups": copy.deepcopy(CURRENT_GROUPS),
            "strategy_enabled": strategy_enabled,
        }

    def test_disable_without_any_remark_returns_empty_strategy(self):
        result = self.handler.save_pattern_strategy("2_bklog.rt", self.params(strategy_enabled=False))

        self.assertEqual(result, {"strategy_id": None})

    def test_enable_without_any_remark_raises_owners_not_exist(self):
        with self.assertRaises(ClusteringOwnersNotExistException):
            self.handler.save_pattern_strategy("2_bklog.rt", self.params(strategy_enabled=True))

    def test_enable_with_inherited_owner_creates_dedicated_strategy(self):
        source = build_remark(
            {"service_name": "gamesvr"},
            remark=[INHERITED_REMARK],
            owners=["admin"],
            strategy_id=7,
            strategy_enabled=True,
        )

        with (
            patch("apps.log_clustering.handlers.clustering_monitor.MonitorApi") as mock_api,
            patch("apps.log_clustering.handlers.clustering_monitor.MonitorUtils") as mock_utils,
            patch("apps.log_clustering.handlers.clustering_monitor.LogIndexSet") as mock_index_set,
        ):
            mock_api.search_user_groups.return_value = []
            mock_api.save_alarm_strategy_v3.return_value = {"id": 888}
            mock_utils.save_notice_group.return_value = {"id": 555}
            mock_index_set.objects.filter.return_value.first.return_value = SimpleNamespace(index_set_name="test_set")

            result = self.handler.save_pattern_strategy("2_bklog.rt", self.params(strategy_enabled=True))

            strategy_params = mock_api.save_alarm_strategy_v3.call_args.kwargs["params"]
            notice_receiver = mock_utils.save_notice_group.call_args.kwargs["notice_receiver"]

        materialized = ClusteringRemark.objects.get(
            group_hash=ClusteringRemark.convert_groups_to_groups_hash(CURRENT_GROUPS)
        )
        source.refresh_from_db()

        self.assertEqual(result, {"strategy_id": 888})
        self.assertEqual(materialized.owners, ["admin"])
        self.assertEqual(materialized.strategy_id, 888)
        self.assertTrue(materialized.strategy_enabled)
        self.assertEqual(materialized.notice_group_id, 555)
        self.assertEqual(notice_receiver, [{"type": "user", "id": "admin"}])
        self.assertEqual(
            strategy_params["items"][0]["query_configs"][0]["agg_dimension"],
            ["__dist_05", "service_name", "func"],
        )
        # 请求不带 id 才是新建；带上会把父分组那条策略改成子分组的配置
        self.assertNotIn("id", strategy_params)
        self.assertEqual(source.strategy_id, 7)
        self.assertTrue(source.strategy_enabled)

    def test_disable_materializes_inherited_remark_without_strategy_binding(self):
        build_remark(
            {"service_name": "gamesvr"},
            remark=[INHERITED_REMARK],
            owners=["admin"],
            strategy_id=7,
            strategy_enabled=True,
            notice_group_id=11,
        )

        result = self.handler.save_pattern_strategy("2_bklog.rt", self.params(strategy_enabled=False))

        materialized = ClusteringRemark.objects.get(
            group_hash=ClusteringRemark.convert_groups_to_groups_hash(CURRENT_GROUPS)
        )
        self.assertEqual(result, {"strategy_id": None})
        self.assertEqual(materialized.remark, [INHERITED_REMARK])
        self.assertEqual(materialized.owners, ["admin"])
        self.assertEqual(materialized.strategy_id, 0)
        self.assertEqual(materialized.notice_group_id, 0)
