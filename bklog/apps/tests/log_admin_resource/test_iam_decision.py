from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.exceptions import PermissionError as BklogPermissionError
from apps.exceptions import ValidationError
from apps.iam.handlers.actions import ActionEnum
from apps.iam.iam_engine.core.types import AuthDecision
from apps.log_admin_resource.handlers.iam_decision import FUNC_NAME, FUNCTIONS, evaluate_iam_decisions
from apps.log_admin_resource.registry import AdminResourceRegistry
from apps.log_admin_resource.schema import validate_params


def _decision(*, allowed=True, degraded=False, mode="v3"):
    return AuthDecision(allowed=allowed, provider_results=(), degraded=degraded, mode=mode)


@override_settings(ENABLE_MULTI_TENANT_MODE=False, DEMO_BIZ_EDIT_ENABLED=False)
class IamDecisionHandlerTest(SimpleTestCase):
    def test_registry_exposes_iam_decision_op(self):
        metadata = AdminResourceRegistry.call("__meta__", {"action": "list"}, app_code="reader-a")
        self.assertIn(FUNC_NAME, metadata["functions"])
        self.assertEqual(FUNCTIONS[FUNC_NAME]["safety_level"], "inspect")

    def test_schema_accepts_manage_actions_and_rejects_tenant_override(self):
        schema = FUNCTIONS[FUNC_NAME]["params_schema"]
        validate_params(
            {
                "username": "alice",
                "decisions": [
                    {
                        "action_id": ActionEnum.MANAGE_COLLECTION.id,
                        "resource_type": "collection",
                        "resource_id": "1",
                    },
                    {"action_id": ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE.id},
                ],
            },
            schema,
        )
        with self.assertRaises(ValidationError):
            validate_params(
                {
                    "username": "alice",
                    "bk_tenant_id": "other-tenant",
                    "decisions": [
                        {
                            "action_id": ActionEnum.VIEW_BUSINESS.id,
                            "resource_type": "business",
                            "resource_id": "2",
                        }
                    ],
                },
                schema,
            )

    @patch("apps.log_admin_resource.handlers.iam_decision.require_request_tenant_id", return_value="tenant-a")
    @patch("apps.log_admin_resource.handlers.iam_decision.Permission")
    def test_evaluate_returns_allow_and_deny(self, permission_cls, _tenant):
        permission = permission_cls.return_value
        permission.bk_tenant_id = "tenant-a"
        permission.is_demo_biz_resource.return_value = False
        permission.mode_router.is_allowed.side_effect = [
            _decision(allowed=True, mode="v3"),
            _decision(allowed=False, mode="v3"),
        ]
        permission.make_engine_request.side_effect = lambda action, resources: SimpleNamespace(
            resources=resources, action=action
        )
        permission._resource_type_label.return_value = "business"

        with (
            patch(
                "apps.log_admin_resource.handlers.iam_decision.require_biz_in_request_tenant",
                side_effect=lambda value: int(value),
            ),
            patch(
                "apps.log_admin_resource.handlers.iam_decision.scope_space_queryset",
                side_effect=lambda qs: qs,
            ),
            patch("apps.log_admin_resource.handlers.iam_decision.LogIndexSet.objects") as index_objects,
        ):
            index_objects.filter.return_value.first.return_value = SimpleNamespace(
                index_set_id=1001, space_uid="bkcc__2"
            )
            with patch(
                "apps.log_admin_resource.handlers.iam_decision.space_uid_to_bk_biz_id",
                return_value=2,
            ):
                result = evaluate_iam_decisions(
                    {
                        "username": "alice",
                        "decisions": [
                            {
                                "action_id": ActionEnum.VIEW_BUSINESS.id,
                                "resource_type": "business",
                                "resource_id": "2",
                            },
                            {
                                "action_id": ActionEnum.SEARCH_LOG.id,
                                "resource_type": "indices",
                                "resource_id": "1001",
                            },
                        ],
                    }
                )

        validate_params(result, FUNCTIONS[FUNC_NAME]["response_schema"], "response")
        self.assertEqual(result["bk_tenant_id"], "tenant-a")
        self.assertEqual([item["allowed"] for item in result["decisions"]], [True, False])
        self.assertEqual([item["status"] for item in result["decisions"]], ["ok", "ok"])

    @patch("apps.log_admin_resource.handlers.iam_decision.require_request_tenant_id", return_value="tenant-a")
    @patch("apps.log_admin_resource.handlers.iam_decision.Permission")
    def test_provider_degradation_is_unknown_not_false_deny(self, permission_cls, _tenant):
        permission = permission_cls.return_value
        permission.bk_tenant_id = "tenant-a"
        permission.is_demo_biz_resource.return_value = False
        permission.mode_router.is_allowed.return_value = _decision(allowed=False, degraded=True, mode="dual")
        permission.make_engine_request.return_value = SimpleNamespace(resources=[SimpleNamespace(id="2")])
        permission._resource_type_label.return_value = "business"

        with patch(
            "apps.log_admin_resource.handlers.iam_decision.require_biz_in_request_tenant",
            side_effect=lambda value: int(value),
        ):
            result = evaluate_iam_decisions(
                {
                    "username": "alice",
                    "decisions": [
                        {
                            "action_id": ActionEnum.VIEW_BUSINESS.id,
                            "resource_type": "business",
                            "resource_id": "2",
                        }
                    ],
                }
            )

        decision = result["decisions"][0]
        self.assertIsNone(decision["allowed"])
        self.assertEqual(decision["status"], "unknown")
        self.assertIn("iam_provider_degraded", decision["warnings"])

    @patch("apps.log_admin_resource.handlers.iam_decision.require_request_tenant_id", return_value="tenant-a")
    @patch("apps.log_admin_resource.handlers.iam_decision.Permission")
    def test_evaluate_manage_and_global_actions(self, permission_cls, _tenant):
        permission = permission_cls.return_value
        permission.bk_tenant_id = "tenant-a"
        permission.is_demo_biz_resource.return_value = False
        permission.mode_router.is_allowed.side_effect = [
            _decision(allowed=False, mode="v3"),
            _decision(allowed=True, mode="v3"),
        ]
        permission.make_engine_request.side_effect = lambda action, resources: SimpleNamespace(
            resources=resources, action=action
        )
        permission._resource_type_label.return_value = "collection"

        with (
            patch(
                "apps.log_admin_resource.handlers.iam_decision.scope_biz_queryset",
                side_effect=lambda qs: qs,
            ),
            patch("apps.log_admin_resource.handlers.iam_decision.CollectorConfig.objects") as collector_objects,
        ):
            collector_objects.filter.return_value.first.return_value = SimpleNamespace(collector_config_id=123)
            result = evaluate_iam_decisions(
                {
                    "username": "bob",
                    "decisions": [
                        {
                            "action_id": ActionEnum.MANAGE_COLLECTION.id,
                            "resource_type": "collection",
                            "resource_id": "123",
                        },
                        {"action_id": ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE.id},
                    ],
                }
            )

        validate_params(result, FUNCTIONS[FUNC_NAME]["response_schema"], "response")
        self.assertEqual(result["username"], "bob")
        self.assertEqual(
            [(item["action_id"], item["allowed"], item["resource_id"]) for item in result["decisions"]],
            [
                (ActionEnum.MANAGE_COLLECTION.id, False, "123"),
                (ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE.id, True, ""),
            ],
        )

    @patch("apps.log_admin_resource.handlers.iam_decision.require_request_tenant_id", return_value="tenant-a")
    @patch("apps.log_admin_resource.handlers.iam_decision.Permission")
    def test_rejects_caller_supplied_tenant_identity(self, permission_cls, _tenant):
        permission_cls.return_value.bk_tenant_id = "tenant-a"
        with self.assertRaisesRegex(ValidationError, "identity parameters"):
            evaluate_iam_decisions(
                {
                    "username": "alice",
                    "bk_tenant_id": "other-tenant",
                    "decisions": [
                        {
                            "action_id": ActionEnum.VIEW_BUSINESS.id,
                            "resource_type": "business",
                            "resource_id": "2",
                        }
                    ],
                }
            )

    @patch("apps.log_admin_resource.handlers.iam_decision.require_request_tenant_id", return_value="tenant-a")
    @patch("apps.log_admin_resource.handlers.iam_decision.Permission")
    def test_incompatible_resource_type_is_rejected(self, permission_cls, _tenant):
        permission_cls.return_value.bk_tenant_id = "tenant-a"
        with self.assertRaisesRegex(ValidationError, "incompatible"):
            evaluate_iam_decisions(
                {
                    "username": "alice",
                    "decisions": [
                        {
                            "action_id": ActionEnum.SEARCH_LOG.id,
                            "resource_type": "business",
                            "resource_id": "2",
                        }
                    ],
                }
            )

    @patch("apps.log_admin_resource.handlers.iam_decision.require_request_tenant_id", return_value="tenant-a")
    @patch("apps.log_admin_resource.handlers.iam_decision.Permission")
    def test_resource_not_found_for_missing_index_set(self, permission_cls, _tenant):
        permission_cls.return_value.bk_tenant_id = "tenant-a"
        with (
            patch(
                "apps.log_admin_resource.handlers.iam_decision.scope_space_queryset",
                side_effect=lambda qs: qs,
            ),
            patch("apps.log_admin_resource.handlers.iam_decision.LogIndexSet.objects") as index_objects,
        ):
            index_objects.filter.return_value.first.return_value = None
            with self.assertRaisesRegex(ValidationError, "resource_not_found"):
                evaluate_iam_decisions(
                    {
                        "username": "alice",
                        "decisions": [
                            {
                                "action_id": ActionEnum.SEARCH_LOG.id,
                                "resource_type": "indices",
                                "resource_id": "999",
                            }
                        ],
                    }
                )

    @patch("apps.log_admin_resource.handlers.iam_decision.require_request_tenant_id", return_value="tenant-a")
    def test_tenant_mismatch_on_permission_object_fails_closed(self, _tenant):
        with patch("apps.log_admin_resource.handlers.iam_decision.Permission") as permission_cls:
            permission_cls.return_value.bk_tenant_id = "other-tenant"
            with self.assertRaises(BklogPermissionError):
                evaluate_iam_decisions(
                    {
                        "username": "alice",
                        "decisions": [
                            {
                                "action_id": ActionEnum.VIEW_BUSINESS.id,
                                "resource_type": "business",
                                "resource_id": "2",
                            }
                        ],
                    }
                )
