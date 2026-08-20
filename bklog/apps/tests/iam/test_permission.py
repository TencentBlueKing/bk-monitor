from unittest.mock import Mock

from django.test import SimpleTestCase, override_settings
from iam import ObjectSet, make_expression

from apps.iam.handlers.actions import ActionEnum
from apps.iam.handlers.permission import Permission
from apps.iam.handlers.resources import ResourceEnum


@override_settings(IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=0)
class PermissionPolicyFlattenTest(SimpleTestCase):
    def setUp(self):
        self.permission = Permission(username="tester", bk_tenant_id="default")
        self.sdk_eval_expr = self.permission.iam_client._eval_expr
        self.spaces = [
            {"bk_biz_id": 3, "space_uid": "bkcc__3"},
            {"bk_biz_id": 1, "space_uid": "bkcc__1"},
            {"bk_biz_id": -3, "space_uid": "bkci__project"},
            {"bk_biz_id": 4, "space_uid": "bkcc__4"},
            {"bk_biz_id": 2, "space_uid": "bkcc__2"},
        ]

    def evaluate_with_sdk(self, policies, spaces=None):
        spaces = self.spaces if spaces is None else spaces
        expr = make_expression(policies)
        results = []
        for space in spaces:
            obj_set = ObjectSet()
            obj_set.add_object(_type=ResourceEnum.BUSINESS.id, obj={"id": str(space["bk_biz_id"])})
            if self.sdk_eval_expr(expr, obj_set):
                results.append(space)
        return results

    def filter_spaces(self, policies, spaces=None):
        spaces = self.spaces if spaces is None else spaces
        self.permission.iam_client._do_policy_query = Mock(return_value=policies)
        eval_expr = Mock(wraps=self.sdk_eval_expr)
        self.permission.iam_client._eval_expr = eval_expr
        try:
            results = self.permission.filter_space_list_by_action(
                ActionEnum.VIEW_BUSINESS,
                space_list=spaces,
            )
        finally:
            self.permission.iam_client._eval_expr = self.sdk_eval_expr
        return results, eval_expr

    def test_supported_fast_paths_match_sdk(self):
        policies = [
            {"op": "eq", "field": "space.id", "value": "1"},
            {"op": "in", "field": "space.id", "value": ["1", "4"]},
            {
                "op": "OR",
                "content": [
                    {"op": "eq", "field": "space.id", "value": "3"},
                    {
                        "op": "OR",
                        "content": [
                            {"op": "in", "field": "space.id", "value": ["1", "2"]},
                        ],
                    },
                ],
            },
            {"op": "OR", "content": []},
            {"op": "any", "field": "space.id", "value": []},
            {"op": "any", "field": "", "value": []},
        ]

        for policy in policies:
            with self.subTest(policy=policy):
                expected = self.evaluate_with_sdk(policy)
                results, eval_expr = self.filter_spaces(policy)
                self.assertEqual(results, expected)
                eval_expr.assert_not_called()

    def test_generated_flattenable_policy_matrix_matches_sdk(self):
        leaves = [
            {"op": "eq", "field": "space.id", "value": "-3"},
            {"op": "eq", "field": "space.id", "value": "999"},
            {"op": "in", "field": "space.id", "value": []},
            {"op": "in", "field": "space.id", "value": ["-3", "2", "2"]},
            {"op": "in", "field": "space.id", "value": ("1", "4")},
            {"op": "any", "field": "space.id", "value": None},
            {"op": "any", "field": "", "value": "*"},
        ]
        policies = leaves + [{"op": "OR", "content": [left, right]} for left in leaves for right in leaves]

        for policy in policies:
            with self.subTest(policy=policy):
                expected = self.evaluate_with_sdk(policy)
                results, eval_expr = self.filter_spaces(policy)
                self.assertEqual(results, expected)
                eval_expr.assert_not_called()

    def test_nested_any_in_compatible_or_is_flattened_to_any(self):
        policies = {
            "op": "OR",
            "content": [
                {"op": "in", "field": "space.id", "value": ["1"]},
                {"op": "any", "field": "space.id", "value": []},
            ],
        }

        flattened = Permission._try_flatten_space_policy(policies)

        self.assertEqual(flattened, {"mode": "any"})

    def test_unsafe_policy_shapes_fall_back(self):
        policies = [
            None,
            {"op": "eq", "field": "biz.id", "value": "1"},
            {"op": "eq", "field": "space.id", "value": 1},
            {"op": "in", "field": "space.id", "value": "12"},
            {"op": "in", "field": "space.id", "value": ["1", 2]},
            {"op": "starts_with", "field": "space.id", "value": "1"},
            {
                "op": "AND",
                "content": [
                    {"op": "in", "field": "space.id", "value": ["1", "2"]},
                    {"op": "eq", "field": "space.id", "value": "2"},
                ],
            },
            {"op": "any", "field": "space.unknown", "value": []},
            {"op": "any", "value": []},
            {"op": "OR"},
            {"op": "OR", "content": [{"op": "AND", "content": []}]},
        ]

        for policy in policies:
            with self.subTest(policy=policy):
                self.assertIsNone(Permission._try_flatten_space_policy(policy))

    def test_unknown_any_field_preserves_sdk_failure(self):
        policies = {"op": "any", "field": "space.unknown", "value": []}

        with self.assertRaises(KeyError):
            self.filter_spaces(policies)

    @override_settings(DEMO_BIZ_ID=2)
    def test_flat_path_preserves_order_and_demo_exemption(self):
        policies = {
            "op": "OR",
            "content": [
                {"op": "eq", "field": "space.id", "value": "3"},
                {"op": "in", "field": "space.id", "value": ["1"]},
            ],
        }

        results, eval_expr = self.filter_spaces(policies)

        self.assertEqual([space["bk_biz_id"] for space in results], [3, 1, 2])
        eval_expr.assert_not_called()

    def test_flat_path_preserves_duplicate_rows_and_negative_space_ids(self):
        spaces = [
            {"bk_biz_id": 2, "space_uid": "bkcc__2-a"},
            {"bk_biz_id": -3, "space_uid": "bkci__project"},
            {"bk_biz_id": 2, "space_uid": "bkcc__2-b"},
            {"bk_biz_id": 4, "space_uid": "bkcc__4"},
        ]
        policies = {"op": "in", "field": "space.id", "value": ["-3", "2", "2"]}

        expected = self.evaluate_with_sdk(policies, spaces)
        results, eval_expr = self.filter_spaces(policies, spaces)

        self.assertEqual(results, expected)
        self.assertEqual(
            [space["space_uid"] for space in results],
            ["bkcc__2-a", "bkci__project", "bkcc__2-b"],
        )
        eval_expr.assert_not_called()

    def test_fast_paths_accept_empty_space_list(self):
        policies = [
            {"op": "eq", "field": "space.id", "value": "1"},
            {"op": "any", "field": "space.id", "value": []},
            {"op": "OR", "content": []},
        ]

        for policy in policies:
            with self.subTest(policy=policy):
                results, eval_expr = self.filter_spaces(policy, [])
                self.assertEqual(results, [])
                eval_expr.assert_not_called()

    def test_flat_path_filters_100k_spaces_without_sdk_eval(self):
        spaces = [{"bk_biz_id": bk_biz_id, "space_uid": f"bkcc__{bk_biz_id}"} for bk_biz_id in range(1, 100_001)]
        policies = {"op": "in", "field": "space.id", "value": ["1", "50000", "100000"]}

        results, eval_expr = self.filter_spaces(policies, spaces)

        self.assertEqual([space["bk_biz_id"] for space in results], [1, 50000, 100000])
        eval_expr.assert_not_called()

    def test_any_fast_path_preserves_missing_biz_id_failure(self):
        policies = {"op": "any", "field": "space.id", "value": []}
        spaces = [{"space_uid": "missing-biz-id"}]

        with self.assertRaises(KeyError):
            self.filter_spaces(policies, spaces)

    def test_and_policy_uses_original_sdk_eval(self):
        policies = {
            "op": "AND",
            "content": [
                {"op": "in", "field": "space.id", "value": ["1", "2"]},
                {"op": "eq", "field": "space.id", "value": "2"},
            ],
        }

        expected = self.evaluate_with_sdk(policies)
        results, eval_expr = self.filter_spaces(policies)

        self.assertEqual(results, expected)
        self.assertEqual(eval_expr.call_count, len(self.spaces))

    def test_raw_v1_field_falls_back_without_changing_sdk_semantics(self):
        policies = {"op": "eq", "field": "biz.id", "value": "2"}

        expected = self.evaluate_with_sdk(policies)
        results, eval_expr = self.filter_spaces(policies)

        self.assertEqual(results, expected)
        self.assertEqual(eval_expr.call_count, len(self.spaces))

    def test_non_string_values_fall_back_without_type_coercion(self):
        policies = [
            {"op": "eq", "field": "space.id", "value": 2},
            {"op": "in", "field": "space.id", "value": "12"},
        ]

        for policy in policies:
            with self.subTest(policy=policy):
                expected = self.evaluate_with_sdk(policy)
                results, eval_expr = self.filter_spaces(policy)
                self.assertEqual(results, expected)
                self.assertEqual(eval_expr.call_count, len(self.spaces))

    def test_supported_non_flat_operators_match_sdk(self):
        policies = [
            {"op": "not_eq", "field": "space.id", "value": "2"},
            {"op": "not_in", "field": "space.id", "value": ["1", "4"]},
            {"op": "starts_with", "field": "space.id", "value": "-"},
            {"op": "ends_with", "field": "space.id", "value": "3"},
            {"op": "gt", "field": "space.id", "value": "2"},
            {"op": "lt", "field": "space.id", "value": "2"},
        ]

        for policy in policies:
            with self.subTest(policy=policy):
                expected = self.evaluate_with_sdk(policy)
                results, eval_expr = self.filter_spaces(policy)
                self.assertEqual(results, expected)
                self.assertEqual(eval_expr.call_count, len(self.spaces))

    def test_malformed_policies_preserve_sdk_errors(self):
        policies_and_errors = [
            ({"op": "unknown", "field": "space.id", "value": "1"}, ValueError),
            ({"op": "OR"}, KeyError),
            ({"op": "any", "value": []}, KeyError),
            ({"op": "any", "field": "space.id"}, KeyError),
        ]

        for policy, error in policies_and_errors:
            with self.subTest(policy=policy):
                with self.assertRaises(error):
                    self.filter_spaces(policy)
