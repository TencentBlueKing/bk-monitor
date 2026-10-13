"""Monitor model content and historical V3 adapter; convergence is shared."""

import sys
from dataclasses import dataclass
from functools import partial

from django.conf import settings

from bkmonitor.iam.backends.config import get_schema, provider_options
from bkmonitor.iam.backends.v4.config import V4Options, make_client_options
from bkmonitor.iam.mode import get_deployment_mode_provider
from iam_engine.core.config import AuthMode
from iam_engine.model.client import V4ModelClient
from iam_engine.model.convergence import V4ModelMigrator
from iam_engine.model.definition import build_model_definition
from iam_engine.model.django import legacy_migration_command, model_sync_lock
from iam_engine.model.sync import ModelSyncService
from iam_engine.model.sync import ModelSyncError
from iam_engine.schema.visibility import is_visible_to


def expected_v4_model():
    """Derive from the runtime definitions; there is no second editable snapshot."""
    schema = get_schema()
    info = provider_options("v4")["system"]

    def visible(value):
        return is_visible_to(value, "v4")

    payload = {
        "version": 1,
        "system": {key: info[key] for key in ("name", "description", "clients")},
        "resource_types": [
            {"id": item.id, "name": item.name, "ancestors": schema.resolve_ancestor_types(item.id)}
            for item in schema.all_resource_types()
            if visible(item)
        ],
        "actions": [
            {"id": item.id, "name": item.name, "resource_type_id": item.resource_type}
            for item in schema.all_actions()
            if visible(item)
        ],
        "roles": [
            {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "actions": [
                    {"id": action.action_id, "resource_type_id": action.resource_type}
                    for action in role.actions
                    if visible(schema.get_action(action.action_id))
                ],
            }
            for role in schema.all_roles()
            if visible(role)
        ],
    }
    return build_model_definition(
        payload, system_id=info["id"], callback_url=info["callback_url"], managers=info["managers"] or None
    )


def v4_migrator():
    from iam_engine.v4.config import load_v4_paths

    options = provider_options("v4", settings.BK_APP_TENANT_ID)
    options["api_paths"] = load_v4_paths(settings)
    return V4ModelMigrator(
        V4ModelClient(make_client_options(V4Options.from_dict(options)), bk_tenant_id=settings.BK_APP_TENANT_ID),
        expected_v4_model(),
    )


@dataclass(frozen=True)
class LegacyModelPlan:
    pending: tuple[str, ...]
    skipped: str = ""

    def describe(self):
        if self.skipped:
            return "V3 original migration guard: " + self.skipped
        return "V3 pending migration files (not a remote diff): " + (", ".join(self.pending) or "none")


class LegacyModelMigrator:
    def migrate(self, *, dry_run=True):
        if settings.SKIP_IAM_PERMISSION_CHECK or settings.RUN_MODE == "DEVELOP":
            return LegacyModelPlan((), "SKIP_IAM_PERMISSION_CHECK or RUN_MODE=DEVELOP")
        from bkmonitor.migrate import Migrator
        from bkmonitor.models.config import MonitorMigration

        migrator = Migrator("iam", "bkmonitor.iam.migrations")
        migrator.load_migration()
        # Do not use the legacy migrator's silent missing-table fallback in deploys.
        applied = set(MonitorMigration.objects.filter(app="iam").values_list("name", flat=True))
        pending = tuple(sorted(set(migrator.migrations) - applied))
        if not dry_run and pending:
            with legacy_migration_command():
                # load_migration mutates the original graph; never load the
                # preview instance a second time inside Migrator.migrate().
                Migrator("iam", "bkmonitor.iam.migrations").migrate()
            remaining = set(pending) - set(MonitorMigration.objects.filter(app="iam").values_list("name", flat=True))
            if remaining:
                raise ModelSyncError("V3 migration did not record completion: " + ", ".join(sorted(remaining)))
        return LegacyModelPlan(pending)


def get_model_sync_service():
    identity = f"monitor:{settings.BK_APP_TENANT_ID}:{settings.BK_IAM_SYSTEM_ID}"
    return ModelSyncService(
        get_deployment_mode_provider(),
        {AuthMode.V3: LegacyModelMigrator, AuthMode.V4: v4_migrator},
        lock_factory=partial(model_sync_lock, identity),
    )


def migrate_iam_models(sender=None, **kwargs):
    if "migrate" not in sys.argv or kwargs.get("using", "default") != "default":
        return None
    return get_model_sync_service().run(apply=True)
