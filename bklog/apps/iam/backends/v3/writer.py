from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apps.iam.backends.v3.exceptions import V3GrantError
from apps.iam.iam_engine.provider.capabilities import PreparedAuthorizationGrant


class V3AuthorizationWriter:
    """把 V3 SDK 的返回值归一为统一的授权写入结果。"""

    def __init__(self, client) -> None:
        self.client = client

    def prepare_resource_creator_actions(
        self, application: Mapping[str, Any], *, expired_at: int | None = None
    ) -> PreparedAuthorizationGrant:
        del expired_at
        return PreparedAuthorizationGrant(payload=dict(application))

    def grant_prepared(self, grant: PreparedAuthorizationGrant) -> Any:
        result = self.client.grant_resource_creator_actions(dict(grant.payload))
        if isinstance(result, tuple) and result and result[0] is False:
            message = str(result[1]) if len(result) > 1 else "IAM V3 creator grant failed"
            raise V3GrantError(message)
        return result

    def grant_resource_creator_actions(self, application: Mapping[str, Any]) -> Any:
        return self.grant_prepared(self.prepare_resource_creator_actions(application))
