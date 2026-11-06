"""Offline tests call the real product grant entry, not an alternate orchestrator."""

from types import SimpleNamespace

from bkmonitor.iam.permission import Permission
from iam_engine.core.config import AuthMode


def grant_creator_actions(providers, resource_type, resource_id, creator, expired_at=None, tenant_id="system"):
    permission = Permission(username=creator, bk_tenant_id=tenant_id or "system")
    permission._providers = {provider.name: provider for provider in providers}
    names = set(permission._providers)
    mode = AuthMode.UNION if names == {"v3", "v4"} else AuthMode(next(iter(names)))
    permission.mode_provider = SimpleNamespace(get_mode=lambda resources=(): mode)
    if expired_at is not None:
        permission.provider_bundles[AuthMode.V4].writer.expired_at = expired_at
    resource = SimpleNamespace(type=resource_type, id=resource_id)
    return permission.grant_creator_action(resource, creator=creator)
