from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from iam.exceptions import AuthAPIError

from apps.iam.backends.v3.scope import V3AuthorizedScopeQuery
from apps.iam.iam_engine.core.types import AuthStatus


class V3AuthorizedScopeQueryTest(SimpleTestCase):
    subject = {"type": "user", "id": "admin"}

    def setUp(self):
        self.client = Mock()
        self.query = V3AuthorizedScopeQuery(self.client, "bk_log_search")

    def list_scope(self, **kwargs):
        return self.query.list_authorized_resources(
            action_id="view_business_v2",
            subject=self.subject,
            **kwargs,
        )

    def test_v3_requires_candidate_ids_so_callers_preload_local_ids(self):
        self.assertTrue(V3AuthorizedScopeQuery.requires_candidate_ids)

    def test_policy_query_request_keeps_v3_semantics(self):
        self.client._do_policy_query.return_value = None

        self.list_scope()

        request = self.client._do_policy_query.call_args.args[0]
        self.assertEqual(
            request.to_dict(),
            {
                "system": "bk_log_search",
                "subject": {"type": "user", "id": "admin"},
                "action": {"id": "view_business_v2"},
                "resources": [],
                "environment": {},
            },
        )

    def test_no_policy_is_empty_scope_not_wildcard(self):
        self.client._do_policy_query.return_value = None

        scope = self.list_scope()

        self.assertEqual(scope.status, AuthStatus.ALLOW)
        self.assertFalse(scope.is_wildcard)
        self.assertEqual(scope.ids, frozenset())
        self.assertEqual(scope.provider_name, "v3")

    def test_any_policy_becomes_wildcard_without_candidate_evaluation(self):
        self.client._do_policy_query.return_value = {"op": "any", "field": "space.id", "value": []}

        scope = self.list_scope(candidate_ids=frozenset({"2", "3"}))

        self.assertTrue(scope.is_wildcard)
        self.assertEqual(scope.ids, frozenset())
        self.client._eval_expr.assert_not_called()

    def test_flattenable_policy_returns_ids_without_candidate_evaluation(self):
        self.client._do_policy_query.return_value = {
            "op": "OR",
            "content": [
                {"op": "eq", "field": "space.id", "value": "2"},
                {"op": "in", "field": "space.id", "value": ["3", "100"]},
            ],
        }

        scope = self.list_scope(candidate_ids=frozenset({"2", "3"}))

        # 不与候选集求交，交集由调用方统一处理，Provider 只报告 IAM 侧的授权范围。
        self.assertEqual(scope.ids, frozenset({"2", "3", "100"}))
        self.client._eval_expr.assert_not_called()

    def test_non_flattenable_policy_evaluates_each_candidate(self):
        self.client._do_policy_query.return_value = {
            "op": "AND",
            "content": [
                {"op": "in", "field": "space.id", "value": ["2", "3"]},
                {"op": "eq", "field": "space.id", "value": "2"},
            ],
        }
        self.client._eval_expr.side_effect = lambda _expr, obj_set: obj_set.get_object("space")["id"] == "2"

        with patch("apps.iam.backends.v3.scope.make_expression", return_value="expr"):
            scope = self.list_scope(candidate_ids=frozenset({"2", "3"}))

        self.assertEqual(scope.ids, frozenset({"2"}))
        self.assertEqual(self.client._eval_expr.call_count, 2)

    def test_non_flattenable_policy_without_candidates_is_an_error_not_an_empty_scope(self):
        self.client._do_policy_query.return_value = {"op": "starts_with", "field": "space.id", "value": "1"}

        scope = self.list_scope()

        self.assertEqual(scope.status, AuthStatus.ERROR)
        self.assertEqual(scope.error_type, "MissingCandidateIds")
        self.client._eval_expr.assert_not_called()

    def test_policy_query_failure_is_reported_as_error_scope(self):
        self.client._do_policy_query.side_effect = AuthAPIError("boom")

        scope = self.list_scope(candidate_ids=frozenset({"2"}))

        self.assertEqual(scope.status, AuthStatus.ERROR)
        self.assertEqual(scope.provider_name, "v3")
        self.assertEqual(scope.reason, "boom")
        self.assertEqual(scope.error_type, "AuthAPIError")

    def test_blank_subject_is_rejected_before_calling_iam(self):
        scope = self.query.list_authorized_resources(action_id="view_business_v2", subject={"type": "user", "id": " "})

        self.assertEqual(scope.status, AuthStatus.ERROR)
        self.assertEqual(scope.error_type, "InvalidSubject")
        self.client._do_policy_query.assert_not_called()

    def test_resource_type_drives_object_set_key(self):
        self.client._do_policy_query.return_value = {"op": "starts_with", "field": "space.id", "value": "1"}
        self.client._eval_expr.return_value = True

        with patch("apps.iam.backends.v3.scope.make_expression", return_value="expr"):
            scope = self.query.list_authorized_resources(
                action_id="view_business_v2",
                resource_type="biz",
                subject=self.subject,
                candidate_ids=frozenset({"7"}),
            )

        obj_set = self.client._eval_expr.call_args.args[1]
        self.assertEqual(obj_set.get_object("biz"), {"id": "7"})
        self.assertEqual(scope.resource_type, "biz")
