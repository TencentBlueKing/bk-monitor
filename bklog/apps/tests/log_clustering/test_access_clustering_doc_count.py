from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.log_clustering.tasks.msg import access_clustering, get_doc_count

MODULE = "apps.log_clustering.tasks.msg"
ONLINE_SERVICE = "apps.log_clustering.handlers.pipline_service.aiops_service_online.operator_aiops_service_online"

INDEX_SET_ID = 50984
BK_BIZ_ID = 20009


class TestGetDocCount(SimpleTestCase):
    @patch(f"{MODULE}.AggsViewAdapter")
    @patch(f"{MODULE}.UnifyQueryHandler")
    @patch(f"{MODULE}.FeatureToggleObject.switch", return_value=True)
    def test_unify_query_enabled_skips_esquery(self, _mock_switch, mock_unify_handler, mock_aggs_adapter):
        mock_unify_handler.return_value.date_histogram.return_value = {
            "aggs": {"group_by_histogram": {"buckets": [{"doc_count": 3}, {"doc_count": 4}]}}
        }

        doc_count = get_doc_count(index_set_id=INDEX_SET_ID, bk_biz_id=BK_BIZ_ID)

        self.assertEqual(doc_count, 7)
        mock_aggs_adapter.assert_not_called()
        query_data = mock_unify_handler.call_args.args[0]
        self.assertEqual(query_data["index_set_ids"], [INDEX_SET_ID])
        self.assertEqual(query_data["group_field"], "")
        self.assertEqual(query_data["bk_biz_id"], BK_BIZ_ID)

    @patch(f"{MODULE}.AggsViewAdapter")
    @patch(f"{MODULE}.UnifyQueryHandler")
    @patch(f"{MODULE}.FeatureToggleObject.switch", return_value=True)
    def test_unify_query_without_series_returns_zero(self, _mock_switch, mock_unify_handler, _mock_aggs_adapter):
        # UnifyQuery 查不到数据时只返回 {"aggs": {}}
        mock_unify_handler.return_value.date_histogram.return_value = {"aggs": {}}

        self.assertEqual(get_doc_count(index_set_id=INDEX_SET_ID, bk_biz_id=BK_BIZ_ID), 0)

    @patch(f"{MODULE}.AggsViewAdapter")
    @patch(f"{MODULE}.UnifyQueryHandler")
    @patch(f"{MODULE}.FeatureToggleObject.switch", return_value=False)
    def test_unify_query_disabled_falls_back_to_esquery(self, _mock_switch, mock_unify_handler, mock_aggs_adapter):
        mock_aggs_adapter.return_value.date_histogram.return_value = {
            "aggs": {"group_by_histogram": {"buckets": [{"doc_count": 5}]}}
        }

        doc_count = get_doc_count(index_set_id=INDEX_SET_ID, bk_biz_id=BK_BIZ_ID)

        self.assertEqual(doc_count, 5)
        mock_unify_handler.assert_not_called()
        call_kwargs = mock_aggs_adapter.return_value.date_histogram.call_args.kwargs
        self.assertEqual(call_kwargs["index_set_id"], INDEX_SET_ID)
        self.assertNotIn("index_set_ids", call_kwargs["query_data"])


@patch(f"{MODULE}.NOTIFY_EVENT")
@patch(ONLINE_SERVICE)
@patch(f"{MODULE}.get_doc_count")
@patch(f"{MODULE}.FeatureToggleObject")
@patch(f"{MODULE}.Space.objects")
@patch(f"{MODULE}.LogIndexSet.objects")
@patch(f"{MODULE}.ClusteringConfig.get_by_index_set_id")
class TestAccessClustering(SimpleTestCase):
    @staticmethod
    def _prepare(mock_get_config, mock_toggle_object, auto_approve_doc_count):
        mock_get_config.return_value = Mock(
            bk_biz_id=BK_BIZ_ID,
            index_set_id=INDEX_SET_ID,
            related_space_pre_bk_biz_id=None,
            created_by="tester",
        )
        mock_toggle_object.switch.return_value = True
        mock_toggle_object.toggle.return_value = Mock(feature_config={"auto_approve_doc_count": auto_approve_doc_count})

    def test_approval_disabled_skips_doc_count(
        self,
        mock_get_config,
        _mock_index_set,
        _mock_space,
        mock_toggle_object,
        mock_get_doc_count,
        mock_operator,
        _mock_notify,
    ):
        self._prepare(mock_get_config, mock_toggle_object, auto_approve_doc_count=-1)

        access_clustering(INDEX_SET_ID)

        mock_get_doc_count.assert_not_called()
        mock_operator.assert_called_once_with(INDEX_SET_ID)

    def test_doc_count_below_threshold_accesses_automatically(
        self,
        mock_get_config,
        _mock_index_set,
        _mock_space,
        mock_toggle_object,
        mock_get_doc_count,
        mock_operator,
        _mock_notify,
    ):
        self._prepare(mock_get_config, mock_toggle_object, auto_approve_doc_count=100)
        mock_get_doc_count.return_value = 10

        access_clustering(INDEX_SET_ID)

        mock_get_doc_count.assert_called_once()
        mock_operator.assert_called_once_with(INDEX_SET_ID)

    def test_doc_count_failure_falls_back_to_approval(
        self,
        mock_get_config,
        _mock_index_set,
        _mock_space,
        mock_toggle_object,
        mock_get_doc_count,
        mock_operator,
        mock_notify,
    ):
        self._prepare(mock_get_config, mock_toggle_object, auto_approve_doc_count=100)
        mock_get_doc_count.side_effect = Exception("meta api error")

        access_clustering(INDEX_SET_ID)

        mock_operator.assert_not_called()
        self.assertIn("待审批", mock_notify.call_args.kwargs["content"])
