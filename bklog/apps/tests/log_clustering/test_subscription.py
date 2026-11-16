from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.log_clustering.constants import LogColShowTypeEnum
from apps.log_clustering.models import ClusteringConfig, ClusteringSubscription
from apps.log_clustering.tasks.subscription import clean_pattern


class TestSubscriptionLogSamples(SimpleTestCase):
    def setUp(self):
        self.config = ClusteringSubscription(
            space_uid="bkcc__2",
            index_set_id=30,
            log_col_show_type=LogColShowTypeEnum.LOG.value,
            addition=[],
        )
        self.clustering_config = ClusteringConfig(clustering_fields="log")
        self.time_config = {
            "start_time": "2026-11-01 10:00:00",
            "end_time": "2026-11-01 10:30:00",
        }

    def clean(self, is_new_class=True):
        return clean_pattern(
            self.config,
            self.time_config,
            [
                {
                    "pattern": "example *",
                    "signature": "example-signature",
                    "count": 3,
                    "percentage": 100,
                    "is_new_class": is_new_class,
                }
            ],
            self.clustering_config,
            "[subscription-test]",
        )

    def test_log_mode_uses_subscription_space_and_replaces_pattern(self):
        for is_new_class in (False, True):
            with self.subTest(is_new_class=is_new_class):
                with patch("apps.log_clustering.tasks.subscription.UnifyQueryHandler") as query_handler:
                    query_handler.return_value.search.return_value = {"list": [{"log": "example log sample"}]}

                    result = self.clean(is_new_class=is_new_class)

                query_handler.assert_called_once()
                params = query_handler.call_args.args[0]
                self.assertEqual(params["bk_biz_id"], 2)
                self.assertEqual(params["index_set_ids"], [self.config.index_set_id])
                self.assertEqual(params["size"], 1)
                self.assertIn(
                    {"field": "__dist_05", "operator": "is", "value": "example-signature"}, params["addition"]
                )
                result_key = "new_patterns" if is_new_class else "patterns"
                self.assertEqual(result[result_key]["data"][0]["pattern"], "example log sample")

    @patch("bkm_space.utils.api.SpaceApi.get_space_detail", return_value=SimpleNamespace(id=9))
    @patch("apps.log_clustering.tasks.subscription.UnifyQueryHandler")
    def test_log_mode_supports_non_business_space(self, query_handler, get_space):
        self.config.space_uid = "bkci__sample-project"
        query_handler.return_value.search.return_value = {"list": [{"log": "project log sample"}]}

        result = self.clean()

        get_space.assert_called_once_with(space_uid=self.config.space_uid)
        self.assertEqual(query_handler.call_args.args[0]["bk_biz_id"], -9)
        self.assertEqual(result["new_patterns"]["data"][0]["pattern"], "project log sample")

    @patch("apps.log_clustering.tasks.subscription.UnifyQueryHandler")
    def test_log_mode_keeps_pattern_when_no_sample_is_found(self, query_handler):
        query_handler.return_value.search.return_value = {"list": []}

        result = self.clean()

        self.assertEqual(result["new_patterns"]["data"][0]["pattern"], "example *")
