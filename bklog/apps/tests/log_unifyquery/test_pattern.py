from django.test import SimpleTestCase

from apps.log_unifyquery.handler.pattern import UnifyQueryPatternHandler


class TestUnifyQueryPatternHandler(SimpleTestCase):
    def test_signature_alias_is_restored_without_group_dimension(self):
        result = {
            "series": [
                {
                    "group_keys": ["signature"],
                    "group_values": ["255ede58d2a3390db8117bc61d23c39a"],
                    "values": [[1784625000000, 14]],
                }
            ]
        }

        reordered = UnifyQueryPatternHandler.deal_with_result_clustering_dimensions_order(result, ["__dist_05"])

        self.assertEqual(reordered["series"][0]["group_keys"], ["__dist_05"])
        self.assertEqual(reordered["series"][0]["group_values"], ["255ede58d2a3390db8117bc61d23c39a"])
        self.assertEqual(
            UnifyQueryPatternHandler.handle_result_formats(reordered),
            [{"key": "255ede58d2a3390db8117bc61d23c39a", "doc_count": 14, "group": ""}],
        )

    def test_signature_alias_is_ordered_before_group_dimension(self):
        result = {
            "series": [
                {
                    "group_keys": ["path", "signature"],
                    "group_values": ["/tmp/svm.log", "255ede58d2a3390db8117bc61d23c39a"],
                    "values": [[1784625000000, 4]],
                }
            ]
        }

        reordered = UnifyQueryPatternHandler.deal_with_result_clustering_dimensions_order(result, ["__dist_05", "path"])

        self.assertEqual(reordered["series"][0]["group_keys"], ["__dist_05", "path"])
        self.assertEqual(
            reordered["series"][0]["group_values"],
            ["255ede58d2a3390db8117bc61d23c39a", "/tmp/svm.log"],
        )
        self.assertEqual(
            UnifyQueryPatternHandler.handle_result_formats(reordered),
            [
                {
                    "key": "255ede58d2a3390db8117bc61d23c39a",
                    "doc_count": 4,
                    "group": "/tmp/svm.log",
                }
            ],
        )
