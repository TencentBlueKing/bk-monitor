from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.log_search.models import Space


class SpaceGetSpacesByBkBizIdsTest(SimpleTestCase):
    def test_empty_or_invalid_ids_return_empty_without_query(self):
        with patch("apps.log_search.models.connection") as mock_connection:
            self.assertEqual(Space.get_spaces_by_bk_biz_ids("tenant-1", []), [])
            self.assertEqual(Space.get_spaces_by_bk_biz_ids("tenant-1", {"bad", None}), [])
            mock_connection.cursor.assert_not_called()

    def test_queries_valid_ids_and_maps_rows(self):
        cursor = MagicMock()
        cursor.description = [
            ("id",),
            ("space_type_id",),
            ("space_type_name",),
            ("space_id",),
            ("space_name",),
            ("space_uid",),
            ("space_code",),
            ("bk_biz_id",),
            ("bk_tenant_id",),
            ("time_zone",),
        ]
        cursor.fetchall.return_value = [
            (1, "bkcc", "业务", "2", "蓝鲸", "bkcc__2", "2", 2, "tenant-1", '"Asia/Shanghai"'),
        ]
        cursor_cm = MagicMock()
        cursor_cm.__enter__.return_value = cursor
        cursor_cm.__exit__.return_value = False

        with patch("apps.log_search.models.connection") as mock_connection:
            mock_connection.cursor.return_value = cursor_cm
            results = Space.get_spaces_by_bk_biz_ids("tenant-1", {"2", "x", 4})

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["bk_biz_id"], 2)
        self.assertEqual(results[0]["space_uid"], "bkcc__2")
        args = cursor.execute.call_args[0]
        self.assertIn("bk_biz_id IN", args[0])
        self.assertEqual(args[1][0], "tenant-1")
        self.assertEqual(set(args[1][1:]), {2, 4})
