from bkm_space.api import SpaceApi
from bkm_space.define import Space
from bkmonitor.utils.local import local


def set_local_tenant_id(bk_tenant_id: str):
    """
    设置当前线程的租户ID
    """
    local.bk_tenant_id = bk_tenant_id


def get_local_tenant_id() -> str | None:
    """
    获取当前线程的租户ID
    """
    return getattr(local, "bk_tenant_id", None)


def space_uid_to_bk_tenant_id(space_uid: str) -> str:
    """
    空间 转换为 租户ID

    Args:
        space_uid: 空间UID

    Returns:
        str: 租户ID

    Raises:
        ValueError: convert space_uid to bk_tenant_id failed
    """
    space: Space | None = SpaceApi.get_space_detail(space_uid=space_uid)
    if not space:
        raise ValueError("convert space_uid to bk_tenant_id failed, space_uid: %s", space_uid)
    return space.bk_tenant_id


def bk_biz_id_to_bk_tenant_id(bk_biz_id: int) -> str:
    """
    业务ID 转换为 租户ID

    Args:
        bk_biz_id: 业务ID

    Returns:
        str: 租户ID

    Raises:
        ValueError: convert bk_biz_id to bk_tenant_id failed
    """
    space: Space | None = SpaceApi.get_space_detail(bk_biz_id=bk_biz_id)
    if not space:
        raise ValueError("convert bk_biz_id to bk_tenant_id failed, bk_biz_id: %s", bk_biz_id)
    return space.bk_tenant_id
