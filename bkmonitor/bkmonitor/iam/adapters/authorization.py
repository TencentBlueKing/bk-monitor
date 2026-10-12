"""Monitor creator-role payloads; dual-write/recovery policy belongs to the shared engine."""

from datetime import timedelta

from django.utils import timezone

from iam_engine.migration.grant_config import AuthorizationGrantConfig
from iam_engine.provider.capabilities import GrantFailureKind, PreparedAuthorizationGrant

from ..iam_engine.core.exceptions import ProviderError, ProviderUnavailable


class MonitorAuthorizationWriter:
    def __init__(self, provider, *, tenant_id, operator, expired_at=None):
        self.provider = provider
        self.tenant_id = tenant_id
        self.operator = operator
        self.expired_at = expired_at
        self.last_error = None

    def grant_resource_creator_actions(self, application):
        try:
            return self.provider.grant_creator_action(
                application["type"], application["id"], application["creator"], self.expired_at, self.tenant_id
            )
        except Exception as error:
            self.last_error = error
            raise

    def prepare_resource_creator_actions(self, application):
        codec = self.provider.codec
        resource_type = codec.encode_resource_type(application["type"])
        resource_id = codec.encode_resource_id(application["type"], application["id"])
        role_id = codec.encode_role("space_operator")
        expiry = self.expired_at
        if expiry is None:
            config = AuthorizationGrantConfig.from_settings()
            expiry = int((timezone.now() + timedelta(days=config.v4_expire_days)).timestamp())
        return PreparedAuthorizationGrant(
            payload=[
                {
                    "subject": {"type": "user", "id": application["creator"]},
                    "role_id": role_id,
                    "related_resource_type_id": resource_type,
                    "resources": [{"type": resource_type, "id": resource_id}],
                    "expired_at": expiry,
                }
            ],
            role_id=role_id,
            expired_at=expiry,
        )

    def grant_prepared(self, prepared):
        return self.provider._get_client(self.tenant_id).add_authorization(prepared.payload, operator=self.operator)

    @staticmethod
    def classify_failure(error):
        code = getattr(error, "code", 0)
        if isinstance(error, ProviderUnavailable):
            if code == 429 or isinstance(code, int) and code >= 500:
                return GrantFailureKind.RETRY_WAIT
            if isinstance(code, int) and 400 <= code < 500:
                return GrantFailureKind.FAILED_FINAL
            return GrantFailureKind.UNKNOWN
        if isinstance(error, ProviderError | ValueError):
            return GrantFailureKind.FAILED_FINAL
        return GrantFailureKind.RETRY_WAIT
