from __future__ import annotations

from iam import IAM

from apps.iam.backends.v3.config import V3Options


def build_v3_client(bk_tenant_id: str) -> IAM:
    """按当前 settings 构造指定租户的 IAM V3 客户端。"""

    options = V3Options.from_settings()
    return IAM(
        options.app_code,
        options.app_secret,
        options.gateway_url,
        bk_tenant_id=bk_tenant_id,
    )
