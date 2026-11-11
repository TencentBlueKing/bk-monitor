from datetime import datetime, timezone
from unittest.mock import patch

from django.test import TestCase, override_settings, skipUnlessDBFeature

from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.model_query import get_model_spec_detail, query_model
from apps.log_admin_resource.registry import AdminResourceRegistry
from apps.log_search.models import LogIndexSet, Scenario, Space, UserIndexSetSearchHistory


@skipUnlessDBFeature("supports_json_field_contains")
@patch("apps.log_admin_resource.handlers.model_query.get_request_tenant_id", return_value="tenant-a")
class SearchHistoryModelQueryTest(TestCase):
    def setUp(self):
        for biz, tenant in ((2, "tenant-a"), (3, "tenant-b")):
            Space.objects.create(
                space_uid=f"bkcc__{biz}",
                bk_biz_id=biz,
                space_type_id="bkcc",
                space_type_name="business",
                space_id=str(biz),
                space_name=f"biz-{biz}",
                bk_tenant_id=tenant,
            )
        for index, biz in ((1001, 2), (1002, 2), (2001, 3)):
            LogIndexSet.objects.create(
                index_set_id=index,
                space_uid=f"bkcc__{biz}",
                index_set_name=f"index-{index}",
                category_id="host",
                scenario_id=Scenario.LOG,
            )

    def history(self, **kwargs):
        params = {"keyword": "*", "addition": [], "start_time": 1000, "end_time": 2000}
        params.update(kwargs.pop("params", {}))
        row = UserIndexSetSearchHistory.objects.create(params=params, **kwargs)
        # Audit fields are set by the request middleware on real writes.
        UserIndexSetSearchHistory.origin_objects.filter(pk=row.pk).update(
            created_by="example-user", created_at=datetime(2026, 1, 2, 3, tzinfo=timezone.utc)
        )
        return row

    def query(self, **kwargs):
        return query_model({"model": "log_search.UserIndexSetSearchHistory", **kwargs})

    def test_single_union_scene_and_soft_deleted_scope(self, _tenant):
        single = self.history(index_set_id=1001)
        union = self.history(index_set_type="union", index_set_ids=[1001, 1002])
        scene = self.history(index_set_id=0, params={"space_uid": "bkcc__2"})
        deleted = self.history(index_set_id=1002)
        UserIndexSetSearchHistory.origin_objects.filter(pk=deleted.pk).update(is_deleted=True)
        LogIndexSet.origin_objects.filter(index_set_id=1002).update(is_deleted=True)
        self.history(index_set_id=2001)
        self.history(index_set_type="union", index_set_ids=[2001])
        self.history(index_set_type="union", index_set_ids=[1001, 2001])
        self.history(index_set_type="union", index_set_ids=[1001, 9999])
        self.history(index_set_type="union", index_set_ids=[])
        self.history(index_set_type="union", index_set_ids=None)
        self.history(index_set_id=0, params={"space_uid": "bkcc__3"})
        self.history(index_set_id=0)
        self.history(index_set_id=9999)
        rows = self.query()["items"]
        self.assertEqual({row["id"] for row in rows}, {single.pk, union.pk, scene.pk, deleted.pk})

    def test_index_user_time_combination_matches_any_union_member(self, _tenant):
        single = self.history(index_set_id=1001)
        union = self.history(index_set_type="union", index_set_ids=[1001, 1002])
        self.history(index_set_id=1002)
        other_user = self.history(index_set_id=1001)
        UserIndexSetSearchHistory.objects.filter(pk=other_user.pk).update(created_by="another-user")
        older = self.history(index_set_id=1001)
        UserIndexSetSearchHistory.objects.filter(pk=older.pk).update(
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        filters = {
            "index_set_id": "1001",
            "created_by": "example-user",
            "created_at__gte": "2026-01-02T10:00:00+08:00",
            "created_at__lte": "2026-01-02T12:00:00+08:00",
        }
        self.assertEqual({r["id"] for r in self.query(filter=filters)["items"]}, {single.pk, union.pk})
        self.assertEqual(
            {r["id"] for r in self.query(filter={"index_set_id__in": [1002]})["items"]},
            {r["id"] for r in self.query(filter={"index_set_id__exact": 1002})["items"]},
        )
        self.assertIn(union.pk, {r["id"] for r in self.query(filter={"index_set_ids__contains": [1002]})["items"]})
        self.assertEqual(self.query(filter={"index_set_id": 2001})["count"], 0)

    def test_modes_types_empty_conditions_and_sensitive_params(self, _tenant):
        for search_type, search_mode in (("default", "ui"), ("context", "ui"), ("default", "sql")):
            self.history(index_set_id=1001, search_type=search_type, search_mode=search_mode)
        self.history(index_set_id=0, params={"space_uid": "bkcc__2", "token": "test-only-value"})
        self.assertEqual(self.query(filter={"search_mode": "sql"})["count"], 1)
        self.assertEqual(self.query(filter={"search_type": "context"})["count"], 1)
        scene = self.query(filter={"index_set_id": 0})["items"]
        self.assertEqual(len(scene), 1)
        self.assertEqual(scene[0]["params"]["token"], "***")
        self.assertEqual(scene[0]["params"]["keyword"], "*")
        self.assertEqual(scene[0]["params"]["addition"], [])

    def test_order_limit_and_invalid_filters(self, _tenant):
        first = self.history(index_set_id=1001)
        last = self.history(index_set_type="union", index_set_ids=[1001, 1002])
        result = self.query(limit=1)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["items"][0]["id"], last.pk)
        self.assertEqual(self.query(order_by=["id"], limit=1)["items"][0]["id"], first.pk)
        for filters in ({"index_set_id": "invalid"}, {"params__space_uid": "bkcc__2"}):
            with self.subTest(filters=filters), self.assertRaises(ValidationError):
                self.query(filter=filters)

    def test_detail_explains_recording_boundaries(self, _tenant):
        detail = get_model_spec_detail({"model": "log_search.UserIndexSetSearchHistory"})
        self.assertIn("not a complete request audit", detail["summary"])
        self.assertIn("gte", detail["field_lookups"]["created_at"])
        self.assertIn("contains", detail["field_lookups"]["index_set_ids"])
        self.assertEqual(detail["manager"], "origin_objects")

    @override_settings(RESOURCE_CALL_APP_CODE_WHITE_LIST=[])
    def test_resource_call_lists_describes_and_queries_union_history(self, _tenant):
        history = self.history(index_set_type="union", index_set_ids=[1001, 1002])
        alias = "log_search.UserIndexSetSearchHistory"
        listed = AdminResourceRegistry.call("bklog.model.list", {"domain": "log_search"}, app_code="resource-reader")
        self.assertIn(alias, {item["model"] for item in listed["items"]})
        detail = AdminResourceRegistry.call("bklog.model.detail", {"model": alias}, app_code="resource-reader")
        result = AdminResourceRegistry.call(
            "bklog.model.query",
            {"model": alias, "filter": {"index_set_id": 1002}, "fields": ["id", "index_set_ids"]},
            app_code="resource-reader",
        )
        self.assertEqual(detail["model"], alias)
        self.assertEqual(result["items"], [{"id": history.pk, "index_set_ids": [1001, 1002]}])
