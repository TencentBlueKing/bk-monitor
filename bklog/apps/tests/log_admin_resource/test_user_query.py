from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase

from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers import user_query
from apps.log_search.models import Space


class TestUserQuery(TestCase):
    def setUp(self):
        for biz, uid, tenant in [(-12, "bkci__project", "ops"), (2, "bkcc__2", "ops"), (3, "bkcc__3", "other")]:
            Space.origin_objects.bulk_create([Space(bk_biz_id=biz, space_uid=uid, bk_tenant_id=tenant)])
        for i, biz, uid in [(1, -12, "bkci__project"), (2, -12, "bkci__project"), (3, 2, "bkcc__2")]:
            user_query.CollectorConfig.objects.bulk_create(
                [
                    user_query.CollectorConfig(
                        collector_config_id=i,
                        bk_biz_id=biz,
                        collector_config_name=f"collector{i}",
                        collector_scenario_id="row",
                    )
                ]
            )
            user_query.LogIndexSet.objects.bulk_create(
                [user_query.LogIndexSet(index_set_id=i, index_set_name=f"index{i}", space_uid=uid, scenario_id="log")]
            )
        self.enterContext(patch.object(user_query, "require_request_tenant_id", return_value="ops"))
        self.enterContext(
            patch.object(
                user_query,
                "request_tenant_spaces",
                side_effect=lambda: Space.origin_objects.filter(bk_tenant_id="ops"),
            )
        )
        self.evaluate_one = self.enterContext(
            patch.object(user_query, "_evaluate_one", return_value={"status": "ok", "allowed": True, "warnings": []})
        )
        self.permission = Mock()
        self.enterContext(patch.object(user_query, "Permission", return_value=self.permission))
        self.permission.make_engine_batch_request.side_effect = lambda actions, resources: (actions[0].id, resources)

        def decide(request):
            action, resources = request
            mapped = {}
            for (item,) in resources:
                self.assertEqual(item.attribute["_bk_iam_path_"], "/space,-12/")
                self.assertIn(item.id, ("1", "2"))
                mapped[item.id] = {action: item.id == "2"}
            return SimpleNamespace(items=[], as_allowed_dict=lambda: mapped)

        self.permission.mode_router.batch_is_allowed.side_effect = decide

    def _assert_visible_instance_pages_and_detail(self, kind, key):
        params = {
            "username": "alice",
            "space_uid": "bkci__project",
            "operation": f"bklog.{kind}.list",
            "query": {"page_size": 1},
        }
        data = user_query.read_user_query(params)["result"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0][key], 2)
        self.assertEqual(
            user_query.read_user_query({**params, "query": {"page": 2, "page_size": 1}})["result"]["items"], []
        )
        for i, allowed in [(1, False), (2, True), (3, False)]:
            with self.subTest(instance_id=i):
                reply = user_query.read_user_query({**params, "operation": f"bklog.{kind}.detail", "query": {key: i}})
                self.assertIs(reply["allowed"], allowed)
                if allowed:
                    self.assertEqual(reply["result"][kind][key], 2)

    def test_visible_collector_pages_and_detail(self):
        self._assert_visible_instance_pages_and_detail("collector", "collector_config_id")

    def test_visible_index_set_pages_and_detail(self):
        self._assert_visible_instance_pages_and_detail("index_set", "index_set_id")

    def test_scope_required_and_denied_before_instance_queries(self):
        params = {"username": "alice", "operation": "bklog.index_set.list", "query": {}}
        with self.assertRaises(ValidationError):
            user_query.read_user_query(params)
        for scope in [{"bk_biz_id": 3}, {"bk_biz_id": 2, "space_uid": "bkci__project"}]:
            self.assertFalse(user_query.read_user_query({**params, **scope})["allowed"])
        self.evaluate_one.return_value = {"status": "ok", "allowed": False, "warnings": []}
        self.assertFalse(user_query.read_user_query({**params, "bk_biz_id": -12})["allowed"])
        self.permission.mode_router.batch_is_allowed.assert_not_called()

    def test_registered_call_and_degraded_batch(self):
        from apps.log_admin_resource.registry import AdminResourceRegistry

        params = {
            "username": "alice",
            "operation": "bklog.collector.list",
            "bk_biz_id": -12,
            "query": {"page_size": 1},
        }
        result = AdminResourceRegistry.call(user_query.NAME, params, app_code="reader")
        self.assertEqual(result["result"]["items"][0]["collector_config_id"], 2)
        self.permission.mode_router.batch_is_allowed.side_effect = None
        self.permission.mode_router.batch_is_allowed.return_value = SimpleNamespace(
            items=[SimpleNamespace(decision=SimpleNamespace(degraded=True))]
        )
        with self.assertRaises(ValidationError):
            AdminResourceRegistry.call(user_query.NAME, params, app_code="reader")
        with self.assertRaises(ValidationError):
            AdminResourceRegistry.call(user_query.NAME, {**params, "bk_tenant_id": "other"}, app_code="reader")
