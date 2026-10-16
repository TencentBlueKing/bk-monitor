"""BKLog deployment adapters; protocol selection and V4 convergence are shared."""

import sys
from dataclasses import dataclass
from functools import partial

from django.conf import settings
from iam.contrib.iam_migration.migrator import IAMMigrator

from apps.iam.handlers.permission import Permission
from apps.iam.backends.v4.model_migrator import V4ModelMigrator
from apps.iam.mode import get_deployment_mode_provider
from iam_engine.core.config import AuthMode
from iam_engine.model.django import legacy_migration_command, model_sync_lock
from iam_engine.model.sync import ModelSyncService


@dataclass(frozen=True)
class LegacyModelPlan:
    files: tuple[str, ...]

    def describe(self):
        return (
            "V3 original model files (not a remote diff): "
            + ", ".join(self.files)
            + "; apply uses the original IAM SDK upsert flow"
        )


class LegacyModelMigrator:
    def migrate(self, *, dry_run=True):
        # A preview must not query policies or call the legacy write-only migrator.
        if dry_run:
            return LegacyModelPlan(("legacy.json (only if V1 compatibility is detected)", "initial.json"))
        with legacy_migration_command():
            if Permission.get_iam_client(settings.BK_APP_TENANT_ID).in_compatibility_mode():
                IAMMigrator("legacy.json").migrate()
            IAMMigrator("initial.json").migrate()
        return LegacyModelPlan(("initial.json",))


def get_model_sync_service():
    identity = f"bklog:{settings.BK_APP_TENANT_ID}:{settings.BK_IAM_SYSTEM_ID}"
    return ModelSyncService(
        get_deployment_mode_provider(),
        {
            AuthMode.V3: LegacyModelMigrator,
            AuthMode.V4: partial(V4ModelMigrator.from_settings, bk_tenant_id=settings.BK_APP_TENANT_ID),
        },
        lock_factory=partial(model_sync_lock, identity),
    )


def migrate_iam_models(sender=None, **kwargs):
    if "migrate" not in sys.argv or kwargs.get("using", "default") != "default":
        return None
    return get_model_sync_service().run(apply=True)
