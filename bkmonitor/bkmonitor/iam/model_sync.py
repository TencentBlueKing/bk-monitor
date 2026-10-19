"""Monitor model content and historical V3 adapter; convergence is shared."""

import sys
from dataclasses import dataclass, replace
from functools import partial

from django.conf import settings

from bkmonitor.iam.backends.config import get_system_clients, provider_options
from bkmonitor.iam import definitions
from bkmonitor.iam.mode import get_deployment_mode_provider
from iam_engine.core.config import AuthMode
from iam_engine.model.client import V4ModelClient
from iam_engine.model.convergence import V4ModelMigrator
from iam_engine.model.definition import build_model_definition
from iam_engine.model.django import legacy_migration_command, model_sync_lock
from iam_engine.model.sync import ModelSyncService
from iam_engine.model.sync import ModelSyncError


def expected_v4_model():
    """Derive from the runtime definitions; there is no second editable snapshot."""
    schema = definitions
    info = {
        "id": settings.BK_IAM_V4_SYSTEM_ID or settings.BK_IAM_SYSTEM_ID,
        "name": "蓝鲸监控平台",
        "description": "蓝鲸监控平台-IAMv4 权限系统",
        "callback_url": settings.BK_IAM_V4_CALLBACK_URL
        or f"{settings.BK_IAM_RESOURCE_API_HOST.rstrip('/')}/rest/v2/iam/v4/callback/",
        "managers": [m.strip() for m in settings.BK_IAM_V4_MODEL_MANAGERS.split(",") if m.strip()],
        "clients": get_system_clients(),
    }

    payload = {
        "version": 1,
        "system": {key: info[key] for key in ("name", "description", "clients")},
        "resource_types": [
            {"id": item.id, "name": item.name, "ancestors": [item.ancestor] if item.ancestor else []}
            for item in schema.resource_types.values()
        ],
        "actions": [
            {"id": item.id, "name": item.name, "resource_type_id": item.resource_type}
            for item in schema.v4_actions.values()
        ],
        "roles": [
            {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "actions": [
                    {"id": action.action_id, "resource_type_id": action.resource_type} for action in role.actions
                ],
            }
            for role in schema.roles.values()
        ],
    }
    return build_model_definition(
        payload, system_id=info["id"], callback_url=info["callback_url"], managers=info["managers"] or None
    )


def v4_migrator():
    options = provider_options("v4", settings.BK_APP_TENANT_ID)
    # The model command uses the SaaS identity too, but has no request-time
    # provider factory to materialize deferred credentials before HTTP encoding.
    options = replace(options, app_code=str(options.app_code), app_secret=str(options.app_secret))
    return V4ModelMigrator(
        V4ModelClient(options, bk_tenant_id=settings.BK_APP_TENANT_ID),
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
