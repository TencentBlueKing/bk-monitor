from unittest.mock import patch

from django.test import TestCase

from apps.log_search.constants import IndexSetDataType, InnerTag
from apps.log_search.models import LogIndexSet, LogIndexSetData
from apps.log_search.tasks.no_data import index_set_no_data_check


class NoDataCheckTestCase(TestCase):
    def _create_index_set(self, name, is_group=False):
        return LogIndexSet.objects.create(
            index_set_name=name,
            space_uid="bkcc__2",
            scenario_id="es",
            is_group=is_group,
        )

    def _add_child_index_set(self, parent, child):
        return LogIndexSetData.objects.create(
            index_set_id=parent.index_set_id,
            result_table_id=str(child.index_set_id),
            type=IndexSetDataType.INDEX_SET.value,
        )

    @patch("apps.log_search.tasks.no_data.LogIndexSet.delete_tag_by_name")
    @patch("apps.log_search.tasks.no_data.LogIndexSet.set_tag")
    @patch("apps.log_search.tasks.no_data._index_set_has_data")
    def test_group_delete_no_data_tag_when_any_child_has_data(self, mock_has_data, mock_set_tag, mock_delete_tag):
        parent = self._create_index_set("group", is_group=True)
        child_without_data = self._create_index_set("child_without_data")
        child_with_data = self._create_index_set("child_with_data")
        self._add_child_index_set(parent, child_without_data)
        self._add_child_index_set(parent, child_with_data)

        mock_has_data.side_effect = lambda index_set_id, *args: index_set_id == child_with_data.index_set_id

        has_data = index_set_no_data_check(parent.index_set_id, bk_biz_id=2)

        self.assertTrue(has_data)
        mock_delete_tag.assert_called_once_with(parent.index_set_id, InnerTag.NO_DATA.value)
        mock_set_tag.assert_not_called()

    @patch("apps.log_search.tasks.no_data.LogIndexSet.delete_tag_by_name")
    @patch("apps.log_search.tasks.no_data.LogIndexSet.set_tag")
    @patch("apps.log_search.tasks.no_data._index_set_has_data")
    def test_group_set_no_data_tag_when_all_children_have_no_data(self, mock_has_data, mock_set_tag, mock_delete_tag):
        parent = self._create_index_set("group", is_group=True)
        child_1 = self._create_index_set("child_1")
        child_2 = self._create_index_set("child_2")
        self._add_child_index_set(parent, child_1)
        self._add_child_index_set(parent, child_2)
        mock_has_data.return_value = False

        has_data = index_set_no_data_check(parent.index_set_id, bk_biz_id=2)

        self.assertFalse(has_data)
        mock_set_tag.assert_called_once_with(parent.index_set_id, InnerTag.NO_DATA.value)
        mock_delete_tag.assert_not_called()
        checked_child_ids = {args[0] for args, _kwargs in mock_has_data.call_args_list}
        self.assertEqual(checked_child_ids, {child_1.index_set_id, child_2.index_set_id})

    @patch("apps.log_search.tasks.no_data.LogIndexSet.delete_tag_by_name")
    @patch("apps.log_search.tasks.no_data.LogIndexSet.set_tag")
    @patch("apps.log_search.tasks.no_data._index_set_has_data")
    def test_group_reuse_checked_child_result(self, mock_has_data, mock_set_tag, mock_delete_tag):
        parent = self._create_index_set("group", is_group=True)
        child = self._create_index_set("child")
        self._add_child_index_set(parent, child)

        has_data = index_set_no_data_check(parent.index_set_id, bk_biz_id=2, checked_results={child.index_set_id: True})

        self.assertTrue(has_data)
        mock_has_data.assert_not_called()
        mock_delete_tag.assert_called_once_with(parent.index_set_id, InnerTag.NO_DATA.value)
        mock_set_tag.assert_not_called()

    @patch("apps.log_search.tasks.no_data.LogIndexSet.delete_tag_by_name")
    @patch("apps.log_search.tasks.no_data.LogIndexSet.set_tag")
    @patch("apps.log_search.tasks.no_data._index_set_has_data")
    def test_group_reuse_checked_child_no_data_result(self, mock_has_data, mock_set_tag, mock_delete_tag):
        parent = self._create_index_set("group", is_group=True)
        child = self._create_index_set("child")
        self._add_child_index_set(parent, child)

        has_data = index_set_no_data_check(
            parent.index_set_id, bk_biz_id=2, checked_results={child.index_set_id: False}
        )

        self.assertFalse(has_data)
        mock_has_data.assert_not_called()
        mock_set_tag.assert_called_once_with(parent.index_set_id, InnerTag.NO_DATA.value)
        mock_delete_tag.assert_not_called()

    @patch("apps.log_search.tasks.no_data.LogIndexSet.delete_tag_by_name")
    @patch("apps.log_search.tasks.no_data.LogIndexSet.set_tag")
    @patch("apps.log_search.tasks.no_data._index_set_has_data")
    def test_group_cache_missing_child_result(self, mock_has_data, mock_set_tag, mock_delete_tag):
        parent = self._create_index_set("group", is_group=True)
        child = self._create_index_set("child")
        self._add_child_index_set(parent, child)
        checked_results = {}
        mock_has_data.return_value = True

        has_data = index_set_no_data_check(parent.index_set_id, bk_biz_id=2, checked_results=checked_results)

        self.assertTrue(has_data)
        self.assertEqual(checked_results, {child.index_set_id: True})
        mock_has_data.assert_called_once()
        mock_delete_tag.assert_called_once_with(parent.index_set_id, InnerTag.NO_DATA.value)
        mock_set_tag.assert_not_called()

    @patch("apps.log_search.tasks.no_data.LogIndexSet.delete_tag_by_name")
    @patch("apps.log_search.tasks.no_data.LogIndexSet.set_tag")
    @patch("apps.log_search.tasks.no_data._index_set_has_data")
    def test_index_set_set_no_data_tag_when_no_data(self, mock_has_data, mock_set_tag, mock_delete_tag):
        index_set = self._create_index_set("index_set")
        mock_has_data.return_value = False

        has_data = index_set_no_data_check(index_set.index_set_id, bk_biz_id=2)

        self.assertFalse(has_data)
        mock_set_tag.assert_called_once_with(index_set.index_set_id, InnerTag.NO_DATA.value)
        mock_delete_tag.assert_not_called()

    @patch("apps.log_search.tasks.no_data.LogIndexSet.delete_tag_by_name")
    @patch("apps.log_search.tasks.no_data.LogIndexSet.set_tag")
    @patch("apps.log_search.tasks.no_data._index_set_has_data")
    def test_index_set_delete_no_data_tag_when_has_data(self, mock_has_data, mock_set_tag, mock_delete_tag):
        index_set = self._create_index_set("index_set")
        mock_has_data.return_value = True

        has_data = index_set_no_data_check(index_set.index_set_id, bk_biz_id=2)

        self.assertTrue(has_data)
        mock_delete_tag.assert_called_once_with(index_set.index_set_id, InnerTag.NO_DATA.value)
        mock_set_tag.assert_not_called()
