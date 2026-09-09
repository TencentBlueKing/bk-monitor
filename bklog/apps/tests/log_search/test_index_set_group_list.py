from unittest.mock import patch

from django.test import TestCase

from apps.log_search.constants import IndexSetDataType
from apps.log_search.exceptions import ParentIndexSetNotExistException
from apps.log_search.handlers.index_set import IndexSetHandler
from apps.log_search.models import LogIndexSet, LogIndexSetData, Scenario

SPACE_UID = "bkcc__2"
BK_BIZ_ID = 2


class IndexSetGroupListTestCase(TestCase):
    """索引组列表：已归入索引组的子索引集不应再作为顶层节点重复返回。

    索引组的子集 ID 取自 LogIndexSetData.result_table_id（CharField，字符串），
    顶层过滤比对的却是 LogIndexSet.index_set_id（AutoField，整数）。两者类型一旦
    不一致，移除逻辑会整体失效，采集项在分组内和顶层各出现一次。
    """

    def setUp(self):
        for target, return_value in (
            ("apps.log_search.handlers.index_set.IndexSetHandler.get_all_related_space_uids", [SPACE_UID]),
            ("apps.log_search.models.space_uid_to_bk_biz_id", BK_BIZ_ID),
            ("apps.log_search.models.fetch_request_username", "admin"),
            ("apps.log_search.models.LogIndexSet.no_data_check_time", None),
            ("apps.log_search.models.LogIndexSet.batch_get_is_native_doris", {}),
        ):
            patcher = patch(target, return_value=return_value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.group = self._create_index_set("UGC服务-IDC测试环境", is_group=True)
        self.child_cpp = self._create_index_set("[采集项]王者UGC-C++服务日志", collector_config_id=1001)
        self.child_go = self._create_index_set("[采集项]王者UGC-GO服务日志", collector_config_id=1002)
        self.standalone = self._create_index_set("[采集项]未归组采集项", collector_config_id=1003)

        self._add_result_table(self.child_cpp, "2_bklog.ugc_cpp")
        self._add_result_table(self.child_go, "2_bklog.ugc_go")
        self._add_result_table(self.standalone, "2_bklog.standalone")
        self._add_child_index_set(self.group, self.child_cpp)
        self._add_child_index_set(self.group, self.child_go)

    @staticmethod
    def _create_index_set(name, is_group=False, collector_config_id=None):
        return LogIndexSet.objects.create(
            index_set_name=name,
            space_uid=SPACE_UID,
            scenario_id=Scenario.LOG,
            is_group=is_group,
            collector_config_id=collector_config_id,
        )

    @staticmethod
    def _add_result_table(index_set, result_table_id):
        return LogIndexSetData.objects.create(
            index_set_id=index_set.index_set_id,
            result_table_id=result_table_id,
            type=IndexSetDataType.RESULT_TABLE.value,
            apply_status=LogIndexSetData.Status.NORMAL,
            scenario_id=Scenario.LOG,
            bk_biz_id=BK_BIZ_ID,
        )

    @staticmethod
    def _add_child_index_set(group, child):
        return LogIndexSetData.objects.create(
            index_set_id=group.index_set_id,
            result_table_id=str(child.index_set_id),
            type=IndexSetDataType.INDEX_SET.value,
            apply_status=LogIndexSetData.Status.NORMAL,
            scenario_id=Scenario.LOG,
            bk_biz_id=BK_BIZ_ID,
        )

    @staticmethod
    def _get_item(index_sets, index_set_id):
        return next(item for item in index_sets if item["index_set_id"] == index_set_id)

    def test_grouped_child_index_set_not_duplicated_at_top_level(self):
        index_sets = IndexSetHandler.get_user_index_set(SPACE_UID, is_group=True)

        top_level_ids = {item["index_set_id"] for item in index_sets}
        self.assertIn(self.group.index_set_id, top_level_ids)
        self.assertNotIn(self.child_cpp.index_set_id, top_level_ids)
        self.assertNotIn(self.child_go.index_set_id, top_level_ids)

        group_item = self._get_item(index_sets, self.group.index_set_id)
        child_ids = {child["index_set_id"] for child in group_item["children"]}
        self.assertEqual(child_ids, {self.child_cpp.index_set_id, self.child_go.index_set_id})

    def test_ungrouped_index_set_stays_at_top_level(self):
        index_sets = IndexSetHandler.get_user_index_set(SPACE_UID, is_group=True)

        standalone_item = self._get_item(index_sets, self.standalone.index_set_id)
        self.assertFalse(standalone_item.get("children"))

    def test_child_shared_by_multiple_groups_appears_under_each_group_only(self):
        another_group = self._create_index_set("UGC服务-第二分组", is_group=True)
        self._add_child_index_set(another_group, self.child_cpp)

        index_sets = IndexSetHandler.get_user_index_set(SPACE_UID, is_group=True)

        top_level_ids = {item["index_set_id"] for item in index_sets}
        self.assertNotIn(self.child_cpp.index_set_id, top_level_ids)

        for group_id in (self.group.index_set_id, another_group.index_set_id):
            group_item = self._get_item(index_sets, group_id)
            child_ids = {child["index_set_id"] for child in group_item["children"]}
            self.assertIn(self.child_cpp.index_set_id, child_ids)

    def test_group_indices_are_replaced_by_child_indices(self):
        index_sets = IndexSetHandler.get_user_index_set(SPACE_UID, is_group=True)

        group_item = self._get_item(index_sets, self.group.index_set_id)
        result_table_ids = {index["result_table_id"] for index in group_item["indices"]}
        self.assertEqual(result_table_ids, {"2_bklog.ugc_cpp", "2_bklog.ugc_go"})


class ParentIndexSetScopeTestCase(TestCase):
    @staticmethod
    def _create_index_set(name, space_uid, is_group=False):
        return LogIndexSet.objects.create(
            index_set_name=name,
            space_uid=space_uid,
            scenario_id=Scenario.LOG,
            is_group=is_group,
        )

    @patch("apps.log_search.handlers.index_set.BaseIndexSetHandler.sync_router")
    @patch("apps.log_search.handlers.index_set.space_uid_to_bk_biz_id", return_value=-2)
    @patch("apps.log_search.handlers.index_set.IndexSetHandler.get_all_related_space_uids")
    def test_related_space_child_can_join_bkcc_parent(self, get_related_spaces, _convert_biz_id, _sync_router):
        get_related_spaces.return_value = ["bkcc__2", "bcs__cluster-a"]
        parent = self._create_index_set("parent", "bkcc__2", is_group=True)
        child = self._create_index_set("child", "bcs__cluster-a")

        IndexSetHandler(child.index_set_id).add_to_parent_index_sets([parent.index_set_id])

        # 关联空间以父组所在空间为基准查询（与索引组列表的可见范围一致）
        get_related_spaces.assert_called_once_with("bkcc__2")
        self.assertTrue(
            LogIndexSetData.objects.filter(
                index_set_id=parent.index_set_id,
                result_table_id=str(child.index_set_id),
                type=IndexSetDataType.INDEX_SET.value,
            ).exists()
        )

    @patch("apps.log_search.handlers.index_set.IndexSetHandler.get_all_related_space_uids")
    def test_unrelated_space_child_cannot_join_parent(self, get_related_spaces):
        get_related_spaces.return_value = ["bkcc__3"]
        parent = self._create_index_set("parent", "bkcc__3", is_group=True)
        child = self._create_index_set("child", "bcs__cluster-a")

        with self.assertRaises(ParentIndexSetNotExistException):
            IndexSetHandler(child.index_set_id).add_to_parent_index_sets([parent.index_set_id])

        self.assertFalse(
            LogIndexSetData.objects.filter(
                index_set_id=parent.index_set_id,
                result_table_id=str(child.index_set_id),
            ).exists()
        )
