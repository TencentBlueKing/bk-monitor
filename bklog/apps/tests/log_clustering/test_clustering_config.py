from unittest.mock import Mock, call, patch

from django.test import SimpleTestCase, TestCase

from apps.log_clustering.constants import RegexRuleTypeEnum, StorageTypeEnum
from apps.log_clustering.exceptions import RegexTemplateNotExistException
from apps.log_clustering.handlers.clustering_config import ClusteringConfigHandler
from apps.log_clustering.models import ClusteringConfig, RegexTemplate
from apps.log_search.models import LogIndexSet

TEST_INDEX_SET_ID = 1
TEST_BK_BIZ_ID = 2
TEST_CLUSTERED_RT = "test_clustered_rt"


class TestClusteringConfigHandler(SimpleTestCase):
    @patch("apps.log_clustering.handlers.clustering_config.ClusteringConfig.objects.all")
    def test_list_all_configs_includes_placeholder_analysis_supported(self, mock_all):
        mock_all.return_value = [
            ClusteringConfig(
                index_set_id=TEST_INDEX_SET_ID,
                bk_biz_id=TEST_BK_BIZ_ID,
                min_members=1,
                max_dist_list="0.1",
                predefined_varibles="",
                delimeter=" ",
                max_log_length=1024,
                clustering_fields="log",
                storage_type=StorageTypeEnum.DORIS.value,
                clustered_rt=TEST_CLUSTERED_RT,
            )
        ]

        result = ClusteringConfigHandler.list_all_configs()

        self.assertTrue(result[0]["placeholder_analysis_supported"])

    def test_placeholder_analysis_supported_property(self):
        supported_config = ClusteringConfig(storage_type=StorageTypeEnum.DORIS.value, clustered_rt=TEST_CLUSTERED_RT)
        unsupported_config = ClusteringConfig(storage_type=StorageTypeEnum.ELASTICSEARCH.value, clustered_rt="")

        self.assertTrue(supported_config.placeholder_analysis_supported)
        self.assertFalse(unsupported_config.placeholder_analysis_supported)

    def test_get_access_total_count_uses_statistics_total_handler(self):
        clustering_config = Mock(index_set_id=TEST_INDEX_SET_ID, bk_biz_id=TEST_BK_BIZ_ID)
        addition = [{"field": "__dist_05", "operator": "exists"}]

        with patch.object(ClusteringConfigHandler, "_get_access_check_time_range", return_value=(1000, 2000)):
            with patch("apps.log_clustering.handlers.clustering_config.UnifyQueryFieldHandler") as mock_handler:
                mock_handler.return_value.get_total_count.return_value = 3

                result = ClusteringConfigHandler()._get_access_total_count(clustering_config, addition=addition)

        self.assertEqual(result, 3)
        mock_handler.assert_called_once_with(
            {
                "bk_biz_id": TEST_BK_BIZ_ID,
                "index_set_ids": [TEST_INDEX_SET_ID],
                "start_time": 1000,
                "end_time": 2000,
                "time_range": "customized",
                "addition": addition,
            }
        )

    @patch("apps.log_clustering.handlers.clustering_config.ClusteringConfig.get_by_index_set_id")
    def test_get_access_status_uses_unified_count_for_origin_and_clustered(self, mock_get_clustering_config):
        clustering_config = Mock(
            index_set_id=TEST_INDEX_SET_ID,
            bk_biz_id=TEST_BK_BIZ_ID,
            clustered_rt=TEST_CLUSTERED_RT,
            access_finished=False,
            task_records=[],
            task_details={},
            predict_flow_id=None,
            log_count_aggregation_flow_id=None,
        )
        mock_get_clustering_config.return_value = clustering_config

        with patch.object(ClusteringConfigHandler, "_get_access_total_count", side_effect=[1, 1]) as mock_total_count:
            result = ClusteringConfigHandler(index_set_id=TEST_INDEX_SET_ID).get_access_status()

        self.assertTrue(result["access_finished"])
        self.assertEqual(
            mock_total_count.call_args_list,
            [
                call(clustering_config),
                call(clustering_config, addition=[{"field": "__dist_05", "operator": "exists"}]),
            ],
        )
        clustering_config.save.assert_called_once_with(update_fields=["access_finished"])

    @patch("apps.log_clustering.handlers.clustering_config.ClusteringConfig.get_by_index_set_id")
    def test_retrieve_includes_placeholder_analysis_supported(self, mock_get_clustering_config):
        clustering_config = ClusteringConfig(
            index_set_id=TEST_INDEX_SET_ID,
            bk_biz_id=TEST_BK_BIZ_ID,
            min_members=1,
            max_dist_list="0.1",
            predefined_varibles="",
            delimeter=" ",
            max_log_length=1024,
            clustering_fields="log",
            storage_type=StorageTypeEnum.DORIS.value,
            clustered_rt=TEST_CLUSTERED_RT,
        )
        mock_get_clustering_config.return_value = clustering_config

        result = ClusteringConfigHandler(index_set_id=TEST_INDEX_SET_ID).retrieve()

        self.assertTrue(result["placeholder_analysis_supported"])


class TestSynchronousUpdateRegexTemplateSpace(TestCase):
    """更新聚类配置时，正则模板必须属于目标索引集所在空间"""

    SPACE_UID = "bkcc__2"
    OTHER_SPACE_UID = "bkcc__99"

    def setUp(self):
        self.index_set = LogIndexSet.objects.create(
            index_set_name="regex_template_space_index", space_uid=self.SPACE_UID, scenario_id="es"
        )
        ClusteringConfig.objects.create(
            index_set_id=self.index_set.index_set_id,
            bk_biz_id=TEST_BK_BIZ_ID,
            min_members=1,
            max_dist_list="0.1",
            predefined_varibles="origin",
            delimeter=" ",
            max_log_length=1024,
            clustering_fields="log",
        )
        self.local_template = RegexTemplate.objects.create(
            space_uid=self.SPACE_UID,
            template_name="local_template",
            predefined_varibles="local_vars",
        )
        self.foreign_template = RegexTemplate.objects.create(
            space_uid=self.OTHER_SPACE_UID,
            template_name="foreign_template",
            predefined_varibles="foreign_vars",
        )

    def _handler(self):
        return ClusteringConfigHandler(index_set_id=self.index_set.index_set_id)

    def test_same_space_template_copies_predefined_varibles(self):
        handler = self._handler()
        params = {
            "regex_rule_type": RegexRuleTypeEnum.TEMPLATE.value,
            "regex_template_id": self.local_template.id,
        }

        with patch.object(handler, "update", return_value="pipeline-1") as mock_update:
            result = handler.synchronous_update(params)

        self.assertEqual(result, ["pipeline-1"])
        mock_update.assert_called_once_with(params)
        self.assertEqual(params["predefined_varibles"], "local_vars")

    def test_cross_space_template_id_is_rejected(self):
        handler = self._handler()
        params = {
            "regex_rule_type": RegexRuleTypeEnum.TEMPLATE.value,
            "regex_template_id": self.foreign_template.id,
        }

        with patch.object(handler, "update") as mock_update:
            with self.assertRaises(RegexTemplateNotExistException):
                handler.synchronous_update(params)

        mock_update.assert_not_called()

    def test_unknown_template_id_is_rejected(self):
        handler = self._handler()
        params = {
            "regex_rule_type": RegexRuleTypeEnum.TEMPLATE.value,
            "regex_template_id": self.foreign_template.id + 1000,
        }

        with patch.object(handler, "update") as mock_update:
            with self.assertRaises(RegexTemplateNotExistException):
                handler.synchronous_update(params)

        mock_update.assert_not_called()
