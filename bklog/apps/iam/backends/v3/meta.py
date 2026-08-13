from __future__ import annotations

from typing import Any

from django.conf import settings
from django.utils.translation import gettext as _
from iam.meta import setup_action, setup_resource, setup_system

from apps.iam.exceptions import GetSystemInfoError

# 已注册过 meta 的 system_id。注册是幂等的，但按 system_id 记录可以在系统标识变化时重新注册。
_registered_system_id: str | None = None


def setup_meta(system_id: str = "") -> None:
    """把日志平台的系统、资源与动作注册到 V3 SDK 的全局 meta 表。

    ``gen_perms_apply_data`` 依赖该表把 ID 翻译成展示名称。
    """

    global _registered_system_id

    system_id = system_id or settings.BK_IAM_SYSTEM_ID
    if _registered_system_id == system_id:
        return

    # 动作与资源定义位于 handlers，延迟导入避免 handlers 与 backends 相互引用。
    from apps.iam.handlers.actions import _all_actions
    from apps.iam.handlers.resources import _all_resources

    systems = [
        {"system_id": system_id, "system_name": settings.BK_IAM_SYSTEM_NAME},
        {"system_id": "bk_monitorv3", "system_name": _("监控平台")},
    ]
    for system in systems:
        setup_system(**system)

    for resource in _all_resources.values():
        setup_resource(resource.system_id, resource.id, resource.name)

    for action in _all_actions.values():
        setup_action(system_id=system_id, action_id=action.id, action_name=action.name)

    _registered_system_id = system_id


def get_system_info(client, system_id: str = "") -> dict[str, Any]:
    """获取权限中心注册的动作列表。"""

    system_id = system_id or settings.BK_IAM_SYSTEM_ID
    ok, message, data = client._client.query(system_id)
    if not ok:
        raise GetSystemInfoError(_("获取系统信息错误：{message}").format(message=message))
    return data
