from typing import Any

from bkmonitor.iam.action import ActionEnum
from bkmonitor.iam.drf import filter_data_by_permission
from bkmonitor.iam.resource import ResourceEnum


def filter_viewable_apm_applications(
    bk_tenant_id: str, data: list[dict[str, Any]], username: str | None = None
) -> list[dict[str, Any]]:
    """过滤无查看权限的应用；未指定用户时沿用当前请求的鉴权上下文。"""
    return filter_data_by_permission(
        bk_tenant_id=bk_tenant_id,
        data=data,
        actions=[ActionEnum.VIEW_APM_APPLICATION],
        resource_meta=ResourceEnum.APM_APPLICATION,
        id_field=lambda item: item["application_id"],
        instance_create_func=ResourceEnum.APM_APPLICATION.create_instance_by_info,
        mode="any",
        username=username,
    )
