from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

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


class SpaceGetSpacesPageTest(TestCase):
    def setUp(self):
        self._create_space(20, "tenant-1", "蓝鲸")
        self._create_space(21, "tenant-1", "监控")
        deleted = self._create_space(22, "tenant-1", "已删除")
        Space.origin_objects.filter(pk=deleted.pk).update(is_deleted=True)
        self._create_space(30, "tenant-2", "其他租户")

    @staticmethod
    def _create_space(bk_biz_id: int, tenant_id: str, name: str) -> Space:
        return Space.objects.create(
            space_uid=f"bkcc__{bk_biz_id}",
            bk_biz_id=bk_biz_id,
            space_type_id="bkcc",
            space_type_name="业务",
            space_id=str(bk_biz_id),
            space_name=name,
            bk_tenant_id=tenant_id,
        )

    def test_filters_tenant_and_deleted_records_before_paging(self):
        spaces, count = Space.get_spaces_page("tenant-1", offset=1, limit=1, keywords=["业务"])

        self.assertEqual(count, 2)
        self.assertEqual([space["bk_biz_id"] for space in spaces], [21])

    def test_searches_name_and_text_biz_id_in_database(self):
        by_name, name_count = Space.get_spaces_page("tenant-1", offset=0, limit=10, keywords=["蓝鲸"])
        by_biz_id, biz_id_count = Space.get_spaces_page("tenant-1", offset=0, limit=10, keywords=["20"])

        self.assertEqual(name_count, 1)
        self.assertEqual([space["bk_biz_id"] for space in by_name], [20])
        self.assertEqual(biz_id_count, 1)
        self.assertEqual([space["bk_biz_id"] for space in by_biz_id], [20])

    def test_blank_keywords_do_not_add_search_condition(self):
        spaces, count = Space.get_spaces_page("tenant-1", offset=0, limit=10, keywords=["", None])

        self.assertEqual(count, 2)
        self.assertEqual([space["bk_biz_id"] for space in spaces], [20, 21])
