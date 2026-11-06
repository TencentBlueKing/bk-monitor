"""V3 creator grants: product payload mapping, without dual-stack orchestration."""

from iam_engine.exceptions import ProviderError


class V3AuthorizationWriter:
    def __init__(self, provider, *, tenant_id="system", operator=""):
        self.provider = provider
        self.tenant_id = tenant_id
        self.operator = operator
        self.last_error = None

    def grant_resource_creator_actions(self, application):
        p = self.provider
        try:
            result = p._get_client(self.tenant_id).grant_resource_creator_actions(
                {
                    "system": p.system_id,
                    "type": p.codec.encode_resource_type(application["type"]),
                    "id": p.codec.encode_resource_id(application["type"], str(application["id"])),
                    "name": application.get("name") or application["id"],
                    "creator": application["creator"],
                }
            )
            if isinstance(result, tuple) and result and not result[0]:
                raise ProviderError(str(result[1]) if len(result) > 1 else "IAM V3 creator grant failed")
            return result
        except Exception as error:
            self.last_error = error
            raise
