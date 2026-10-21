"""BKLog settings/baseline adapter for common V4 convergence."""

from apps.iam.backends.v4.model_client import V4ModelClient
from apps.iam.backends.v4.model_definition import CURRENT_MODEL_FILE, load_model_definition
from iam_engine.model.convergence import (
    ActualModel as ActualModel,
    ModelMigrationBlocked as ModelMigrationBlocked,
    ModelMigrationPlan as ModelMigrationPlan,
    V4ModelMigrator as SharedV4ModelMigrator,
    build_plan as build_plan,
)


class V4ModelMigrator(SharedV4ModelMigrator):
    @classmethod
    def from_settings(cls, *, bk_tenant_id, username="admin", file_name=CURRENT_MODEL_FILE):
        return cls(
            V4ModelClient.from_settings(username=username, bk_tenant_id=bk_tenant_id),
            load_model_definition(file_name),
        )
