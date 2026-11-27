"""Prepare VIEW_BUSINESS once for an ordered directory query."""

from collections.abc import Callable
from dataclasses import dataclass

from iam import make_expression

from bkmonitor.iam.action import ActionEnum
from bkmonitor.iam.backends.v3.provider import _build_eval_obj
from bkmonitor.iam.concurrency import run_pair_concurrently
from iam_engine.core.config import AuthMode
from iam_engine.core.requests import ResourceInstance, Subject
from iam_engine.exceptions import ProviderUnavailable


@dataclass(frozen=True)
class SpacePageAccess:
    # None is a verified wildcard. An empty set without a matcher grants nothing.
    ids: frozenset[str] | None = frozenset()
    matches_policy: Callable[[str], bool] | None = None
    partial: bool = False

    def allows(self, biz_id):
        key = str(biz_id)
        return self.ids is None or key in self.ids or (self.matches_policy is not None and self.matches_policy(key))


def _v3_page_access(provider, subject, action):
    policy = provider.query_policy(subject, action)
    if not policy or policy.get("op") == "none":
        return SpacePageAccess()
    if policy.get("op") == "any":
        return SpacePageAccess(None)
    if policy.get("field") == "space.id" and policy.get("op") in ("eq", "in"):
        values = [policy.get("value")] if policy["op"] == "eq" else policy.get("value")
        if not isinstance(values, (list, tuple)):
            return SpacePageAccess()
        try:
            ids = frozenset(values)
        except TypeError:
            pass  # Nested SDK values need the original expression evaluator.
        else:
            return SpacePageAccess(frozenset(value for value in ids if isinstance(value, str)))
    expression = make_expression(policy)
    return SpacePageAccess(matches_policy=lambda key: expression.eval(_build_eval_obj(ResourceInstance("space", key))))


def prepare_space_page_access(permission):
    mode = permission.mode_provider.get_mode()
    subject = Subject(id=permission.username, tenant_id=permission.bk_tenant_id)
    action = ActionEnum.VIEW_BUSINESS.id

    def read(provider_mode):
        try:
            provider = permission.get_provider(provider_mode.value)
            if provider_mode is AuthMode.V3:
                return _v3_page_access(provider, subject, action)
            scope = provider.list_authorized_resources(
                action_id=action, resource_type="space", subject={"type": "user", "id": subject.id}
            )
            if not scope.ok:
                raise ProviderUnavailable(scope.reason)
            return SpacePageAccess(None if scope.is_wildcard else frozenset(scope.ids))
        except Exception as error:
            return ProviderUnavailable(str(error))

    if mode is AuthMode.UNION:
        sides = run_pair_concurrently(lambda: read(AuthMode.V3), lambda: read(AuthMode.V4))
    elif mode in (AuthMode.V3, AuthMode.V4):
        sides = (read(mode),)
    else:
        raise ProviderUnavailable("Unknown space authorization mode")
    healthy = [side for side in sides if isinstance(side, SpacePageAccess)]
    if not healthy:
        raise sides[0]
    if any(side.ids is None for side in healthy):
        return SpacePageAccess(None)
    return SpacePageAccess(
        frozenset().union(*(side.ids for side in healthy)),
        next((side.matches_policy for side in healthy if side.matches_policy is not None), None),
        partial=len(healthy) != len(sides),
    )
