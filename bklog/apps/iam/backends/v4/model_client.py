"""BKLog settings adapter for the common model API client."""

from apps.iam.backends.v4.config import V4Options
from iam_engine.model.client import V4ModelClient as SharedV4ModelClient


class V4ModelClient(SharedV4ModelClient):
    @classmethod
    def from_settings(cls, *, username, bk_tenant_id):
        return cls(V4Options.from_settings(), username=username, bk_tenant_id=bk_tenant_id)
