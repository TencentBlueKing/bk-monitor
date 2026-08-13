import copy
from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.iam.backends.v4.model_definition import ResourceTypeDefinition, build_model_definition
from apps.iam.backends.v4.model_migrator import (
    ActualModel,
    ModelMigrationBlocked,
    ModelMigrationPlan,
    V4ModelMigrator,
    _order_by_ancestors,
    build_plan,
)

PAYLOAD = {
    "version": 1,
    "system": {"name": "日志平台", "description": "desc", "clients": ["bk_log_search", "bk_bklog"]},
    "resource_types": [
        {"id": "space", "name": "空间", "ancestors": []},
        {"id": "indices", "name": "索引集", "ancestors": ["space"]},
    ],
    "actions": [
        {"id": "view_business", "name": "业务访问", "resource_type_id": "space"},
        {"id": "search_log", "name": "日志检索", "resource_type_id": "indices"},
    ],
    "roles": [
        {
            "id": "space_viewer",
            "name": "业务只读",
            "description": "只读",
            "actions": [
                {"id": "view_business", "resource_type_id": "space"},
                {"id": "search_log", "resource_type_id": "indices"},
            ],
        }
    ],
}

CALLBACK_URL = "https://bklog.example/api/v1/iam/v4/resource/"


def desired_model(payload=None):
    return build_model_definition(
        payload if payload is not None else copy.deepcopy(PAYLOAD),
        system_id="bk_log_search",
        callback_url=CALLBACK_URL,
    )


def converged_actual(model=None):
    """与基线完全一致的实际态。"""
    model = model or desired_model()
    return ActualModel(
        system={
            "id": model.system.id,
            "name": model.system.name,
            "description": model.system.description,
            "clients": list(model.system.clients),
            "callback_url": model.system.callback_url,
        },
        resource_types=tuple(
            {"id": item.id, "name": item.name, "ancestors": list(item.ancestors)} for item in model.resource_types
        ),
        actions=tuple(
            {"id": item.id, "name": item.name, "resource_type_id": item.resource_type_id} for item in model.actions
        ),
        roles=tuple(
            {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "actions": [{"id": action.id, "resource_type_id": action.resource_type_id} for action in role.actions],
            }
            for role in model.roles
        ),
    )


class BuildPlanEmptySystemTest(SimpleTestCase):
    def test_unregistered_system_produces_full_creation_plan(self):
        model = desired_model()

        plan = build_plan(model, ActualModel())

        self.assertTrue(plan.has_changes())
        self.assertEqual(plan.create_system["name"], "日志平台")
        self.assertEqual(plan.create_system["callback_url"], CALLBACK_URL)
        self.assertNotIn("managers", plan.create_system)
        self.assertIsNone(plan.update_system)
        self.assertEqual([item["id"] for item in plan.create_resource_types], ["space", "indices"])
        self.assertEqual([item["id"] for item in plan.create_actions], ["view_business", "search_log"])
        self.assertEqual([item["id"] for item in plan.create_roles], ["space_viewer"])
        self.assertEqual(plan.blocking, ())
        self.assertEqual(plan.drift, ())

    def test_managers_are_included_only_when_managed(self):
        model = build_model_definition(
            copy.deepcopy(PAYLOAD),
            system_id="bk_log_search",
            callback_url=CALLBACK_URL,
            managers=["colecai"],
        )

        plan = build_plan(model, ActualModel())

        self.assertEqual(plan.create_system["managers"], ["colecai"])

    def test_new_resource_types_are_ordered_after_their_ancestors(self):
        payload = copy.deepcopy(PAYLOAD)
        # 故意把子资源写在父资源前面，计划必须重排。
        payload["resource_types"] = [
            {"id": "indices", "name": "索引集", "ancestors": ["space"]},
            {"id": "space", "name": "空间", "ancestors": []},
        ]

        plan = build_plan(desired_model(payload), ActualModel())

        self.assertEqual([item["id"] for item in plan.create_resource_types], ["space", "indices"])


class BuildPlanConvergedTest(SimpleTestCase):
    def test_identical_model_produces_empty_plan(self):
        model = desired_model()

        plan = build_plan(model, converged_actual(model))

        self.assertFalse(plan.has_changes())
        self.assertEqual(plan.describe(), "no changes")

    def test_plan_is_stable_across_repeated_runs(self):
        model = desired_model()
        actual = ActualModel()

        self.assertEqual(build_plan(model, actual), build_plan(model, actual))

    def test_client_order_difference_does_not_trigger_update(self):
        model = desired_model()
        actual = converged_actual(model)
        actual.system["clients"] = list(reversed(actual.system["clients"]))

        self.assertIsNone(build_plan(model, actual).update_system)

    def test_managers_are_not_touched_when_unmanaged(self):
        model = desired_model()
        actual = converged_actual(model)
        actual.system["managers"] = ["someone-configured-by-hand"]

        self.assertIsNone(build_plan(model, actual).update_system)


class BuildPlanUpdateTest(SimpleTestCase):
    def test_system_field_change_produces_minimal_update(self):
        model = desired_model()
        actual = converged_actual(model)
        actual.system["callback_url"] = "https://old.example/api/v1/iam/resource/"

        plan = build_plan(model, actual)

        self.assertEqual(plan.update_system, {"callback_url": CALLBACK_URL})
        self.assertIsNone(plan.create_system)

    def test_resource_type_rename_and_ancestor_change_are_updated(self):
        model = desired_model()
        actual = converged_actual(model)
        actual.resource_types[1]["name"] = "旧名称"
        actual.resource_types[1]["ancestors"] = []

        plan = build_plan(model, actual)

        self.assertEqual(plan.update_resource_types, (("indices", {"name": "索引集", "ancestors": ["space"]}),))

    def test_action_rename_is_updated(self):
        model = desired_model()
        actual = converged_actual(model)
        actual.actions[0]["name"] = "旧名称"

        plan = build_plan(model, actual)

        self.assertEqual(plan.update_actions, (("view_business", {"name": "业务访问"}),))
        self.assertEqual(plan.blocking, ())

    def test_role_rename_and_description_change_are_updated(self):
        model = desired_model()
        actual = converged_actual(model)
        actual.roles[0]["name"] = "旧名称"
        actual.roles[0]["description"] = "旧描述"

        plan = build_plan(model, actual)

        self.assertEqual(plan.update_roles, (("space_viewer", {"name": "业务只读", "description": "只读"}),))

    def test_missing_role_action_is_added(self):
        model = desired_model()
        actual = converged_actual(model)
        actual.roles[0]["actions"] = [{"id": "view_business", "resource_type_id": "space"}]

        plan = build_plan(model, actual)

        self.assertEqual(
            plan.add_role_actions,
            (("space_viewer", ({"id": "search_log", "resource_type_id": "indices"},)),),
        )
        self.assertEqual(plan.remove_role_actions, ())

    def test_extra_role_action_is_removed(self):
        model = desired_model()
        actual = converged_actual(model)
        actual.roles[0]["actions"].append({"id": "manage_indices", "resource_type_id": "indices"})

        plan = build_plan(model, actual)

        self.assertEqual(plan.remove_role_actions, (("space_viewer", ("manage_indices",)),))
        self.assertEqual(plan.add_role_actions, ())

    def test_role_action_dimension_change_is_removed_then_added(self):
        model = desired_model()
        actual = converged_actual(model)
        actual.roles[0]["actions"][1]["resource_type_id"] = "space"

        plan = build_plan(model, actual)

        self.assertEqual(plan.remove_role_actions, (("space_viewer", ("search_log",)),))
        self.assertEqual(
            plan.add_role_actions,
            (("space_viewer", ({"id": "search_log", "resource_type_id": "indices"},)),),
        )


class BuildPlanBlockingAndDriftTest(SimpleTestCase):
    def test_action_resource_type_change_is_blocking(self):
        model = desired_model()
        actual = converged_actual(model)
        actual.actions[1]["resource_type_id"] = "space"

        plan = build_plan(model, actual)

        self.assertEqual(len(plan.blocking), 1)
        self.assertIn("search_log", plan.blocking[0])
        self.assertIn("manual delete and recreate", plan.blocking[0])
        self.assertEqual(plan.update_actions, ())

    def test_objects_only_present_in_iam_are_reported_as_drift(self):
        model = desired_model()
        actual = converged_actual(model)
        actual = ActualModel(
            system=actual.system,
            resource_types=(*actual.resource_types, {"id": "cluster", "name": "集群", "ancestors": []}),
            actions=(*actual.actions, {"id": "legacy_action", "name": "旧操作", "resource_type_id": "space"}),
            roles=(*actual.roles, {"id": "legacy_role", "name": "旧角色", "description": "", "actions": []}),
        )

        plan = build_plan(model, actual)

        self.assertEqual(len(plan.drift), 3)
        self.assertFalse(plan.has_changes())
        self.assertIn("resource_type cluster exists in IAM but not in the baseline", plan.drift)
        self.assertIn("action legacy_action exists in IAM but not in the baseline", plan.drift)
        self.assertIn("role legacy_role exists in IAM but not in the baseline", plan.drift)


class V4ModelMigratorTest(SimpleTestCase):
    def setUp(self):
        self.model = desired_model()
        self.client = Mock()

    def test_fetch_actual_skips_sub_resource_queries_when_system_missing(self):
        self.client.retrieve_system.return_value = None

        actual = V4ModelMigrator(self.client, self.model).fetch_actual()

        self.assertEqual(actual, ActualModel())
        self.client.list_resource_types.assert_not_called()
        self.client.list_actions.assert_not_called()
        self.client.list_roles.assert_not_called()

    def test_apply_creates_in_dependency_order(self):
        migrator = V4ModelMigrator(self.client, self.model)
        plan = build_plan(self.model, ActualModel())

        migrator.apply(plan)

        self.assertEqual(
            [call[0] for call in self.client.method_calls],
            [
                "create_system",
                "batch_create_resource_types",
                "batch_create_actions",
                "batch_create_roles",
            ],
        )

    def test_apply_removes_role_actions_before_adding_them(self):
        migrator = V4ModelMigrator(self.client, self.model)
        plan = ModelMigrationPlan(
            add_role_actions=(("space_viewer", ({"id": "search_log", "resource_type_id": "indices"},)),),
            remove_role_actions=(("space_viewer", ("search_log",)),),
        )

        migrator.apply(plan)

        self.assertEqual(
            [call[0] for call in self.client.method_calls],
            ["batch_delete_role_actions", "batch_create_role_actions"],
        )

    def test_apply_refuses_blocking_plan(self):
        migrator = V4ModelMigrator(self.client, self.model)
        plan = ModelMigrationPlan(blocking=("action search_log needs manual rebinding",))

        with self.assertRaisesRegex(ModelMigrationBlocked, "manual rebinding"):
            migrator.apply(plan)

        self.assertEqual(self.client.method_calls, [])

    def test_dry_run_never_writes(self):
        self.client.retrieve_system.return_value = None

        plan = V4ModelMigrator(self.client, self.model).migrate(dry_run=True)

        self.assertTrue(plan.has_changes())
        self.assertEqual([call[0] for call in self.client.method_calls], ["retrieve_system"])

    def test_migrate_applies_when_not_dry_run(self):
        self.client.retrieve_system.return_value = None

        V4ModelMigrator(self.client, self.model).migrate(dry_run=False)

        self.assertIn("create_system", [call[0] for call in self.client.method_calls])

    def test_migrate_skips_write_when_already_converged(self):
        actual = converged_actual(self.model)
        self.client.retrieve_system.return_value = actual.system
        self.client.list_resource_types.return_value = list(actual.resource_types)
        self.client.list_actions.return_value = list(actual.actions)
        self.client.list_roles.return_value = list(actual.roles)

        plan = V4ModelMigrator(self.client, self.model).migrate(dry_run=False)

        self.assertFalse(plan.has_changes())
        self.assertEqual(
            [call[0] for call in self.client.method_calls],
            ["retrieve_system", "list_resource_types", "list_actions", "list_roles"],
        )

    def test_describe_lists_every_planned_operation(self):
        description = build_plan(self.model, ActualModel()).describe()

        self.assertIn("create system: 日志平台", description)
        self.assertIn("create resource_type: space", description)
        self.assertIn("create action: view_business", description)
        self.assertIn("create role: space_viewer", description)

    def test_apply_runs_update_operations(self):
        migrator = V4ModelMigrator(self.client, self.model)
        plan = ModelMigrationPlan(
            update_system={"callback_url": CALLBACK_URL},
            update_resource_types=(("indices", {"name": "索引集"}),),
            update_actions=(("search_log", {"name": "日志检索"}),),
            update_roles=(("space_viewer", {"name": "业务只读"}),),
        )

        migrator.apply(plan)

        self.assertEqual(
            [call[0] for call in self.client.method_calls],
            ["update_system", "update_resource_type", "update_action", "update_role"],
        )

    def test_migrate_logs_drift_before_applying(self):
        actual = converged_actual(self.model)
        self.client.retrieve_system.return_value = actual.system
        self.client.list_resource_types.return_value = list(actual.resource_types)
        self.client.list_actions.return_value = [
            *actual.actions,
            {"id": "legacy_action", "name": "旧操作", "resource_type_id": "space"},
        ]
        self.client.list_roles.return_value = list(actual.roles)

        with self.assertLogs("iam.v4.model_migrator", level="WARNING") as logs:
            plan = V4ModelMigrator(self.client, self.model).migrate(dry_run=False)

        self.assertEqual(plan.drift, ("action legacy_action exists in IAM but not in the baseline",))
        self.assertIn("legacy_action", logs.output[0])


class DescribePlanTest(SimpleTestCase):
    def test_describe_covers_update_and_role_action_operations(self):
        plan = ModelMigrationPlan(
            update_system={"callback_url": CALLBACK_URL},
            update_resource_types=(("indices", {"name": "索引集"}),),
            update_actions=(("search_log", {"name": "日志检索"}),),
            update_roles=(("space_viewer", {"name": "业务只读"}),),
            add_role_actions=(("space_viewer", ({"id": "search_log", "resource_type_id": "indices"},)),),
            remove_role_actions=(("space_viewer", ("manage_indices",)),),
            blocking=("action search_log needs manual rebinding",),
            drift=("role legacy_role exists in IAM but not in the baseline",),
        )

        description = plan.describe()

        self.assertIn("update system: ['callback_url']", description)
        self.assertIn("update resource_type: indices -> {'name': '索引集'}", description)
        self.assertIn("update action: search_log -> {'name': '日志检索'}", description)
        self.assertIn("update role: space_viewer -> {'name': '业务只读'}", description)
        self.assertIn("remove role actions: space_viewer -> ['manage_indices']", description)
        self.assertIn("add role actions: space_viewer -> ['search_log']", description)
        self.assertIn("BLOCKING: action search_log needs manual rebinding", description)
        self.assertIn("DRIFT: role legacy_role exists in IAM but not in the baseline", description)


class OrderByAncestorsTest(SimpleTestCase):
    def test_ancestors_already_registered_in_iam_do_not_block_ordering(self):
        ordered = _order_by_ancestors([ResourceTypeDefinition(id="indices", name="索引集", ancestors=("space",))])

        self.assertEqual([item.id for item in ordered], ["indices"])

    def test_cycle_is_refused_instead_of_looping_forever(self):
        # model_definition 已经拒绝环，这里守住兜底分支，防止未来绕过校验时死循环。
        resource_types = [
            ResourceTypeDefinition(id="a", name="A", ancestors=("b",)),
            ResourceTypeDefinition(id="b", name="B", ancestors=("a",)),
        ]

        with self.assertRaisesRegex(ModelMigrationBlocked, "cannot order resource types"):
            _order_by_ancestors(resource_types)
