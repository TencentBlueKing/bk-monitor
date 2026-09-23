from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from django.conf import settings

from apps.iam.backends.v3.exceptions import V3GrantError
from apps.iam.iam_engine.provider.capabilities import PreparedAuthorizationGrant


class V3AuthorizationWriter:
    """把 V3 SDK 的返回值归一为统一的授权写入结果。"""

    def __init__(
        self,
        client,
        *,
        bk_tenant_id: str = "",
        grant_instance_api: Callable[..., Any] | None = None,
    ) -> None:
        self.client = client
        # 授权 API 走 DataAPI，不像 SDK client 那样自带租户，必须显式带上，
        # 否则后台任务里会回落到请求上下文的租户，授到错误租户上。
        self.bk_tenant_id = bk_tenant_id
        # V3 SDK 只提供「新建实例关联权限」，给已存在资源授权只能调权限中心的实例授权 API。
        # 依赖注入是为了单测可替换，不要在调用点再传。
        self._grant_instance_api = grant_instance_api

    def prepare_resource_creator_actions(
        self, application: Mapping[str, Any], *, expired_at: int | None = None
    ) -> PreparedAuthorizationGrant:
        del expired_at
        return PreparedAuthorizationGrant(payload=dict(application))

    def grant_prepared(self, grant: PreparedAuthorizationGrant) -> Any:
        result = self.client.grant_resource_creator_actions(dict(grant.payload))
        # SDK 的成功标记来自 HTTP 层，不保证是 False 这个单例，取假值统一当失败。
        if isinstance(result, tuple) and result and not result[0]:
            message = str(result[1]) if len(result) > 1 else "IAM V3 creator grant failed"
            raise V3GrantError(message)
        return result

    def grant_resource_creator_actions(self, application: Mapping[str, Any]) -> Any:
        return self.grant_prepared(self.prepare_resource_creator_actions(application))

    def grant_space_access(self, *, space_id: str, subject_id: str, space_name: str = "") -> Any:
        """为主体授予业务访问权限。

        空间不是本次新建的实例，且 V3 的空间资源归属监控平台（``ResourceEnum.BUSINESS.system_id``），
        `grant_resource_creator_actions` 两头都对不上，只能走权限中心的批量实例授权 API。
        不带 ``expired_at``，与 V3 创建者授权同样是长期授权。
        """
        # ActionEnum / ResourceEnum 会反向依赖 backends，延迟导入避免模块级环形引用。
        from apps.iam.handlers.actions import ActionEnum
        from apps.iam.handlers.resources import ResourceEnum

        params = {
            "asynchronous": False,
            "operate": "grant",
            "system": settings.BK_IAM_SYSTEM_ID,
            "actions": [{"id": ActionEnum.VIEW_BUSINESS.id}],
            "subject": {"type": "user", "id": str(subject_id)},
            "resources": [
                {
                    "system": ResourceEnum.BUSINESS.system_id,
                    "type": ResourceEnum.BUSINESS.id,
                    "instances": [{"id": str(space_id), "name": space_name or str(space_id)}],
                }
            ],
        }
        return self._resolve_grant_instance_api()(params, bk_tenant_id=self.bk_tenant_id)

    def _resolve_grant_instance_api(self) -> Callable[..., Any]:
        if self._grant_instance_api is not None:
            return self._grant_instance_api

        from apps.api import IAMApi

        return IAMApi.batch_instance
