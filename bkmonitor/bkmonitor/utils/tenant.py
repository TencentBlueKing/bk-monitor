from functools import lru_cache
from typing import NamedTuple

from django.conf import settings

from bkm_space.api import SpaceApi
from bkm_space.define import Space
from bkmonitor.utils.local import local
from constants.common import DEFAULT_TENANT_ID


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


@lru_cache(maxsize=10000)
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
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return DEFAULT_TENANT_ID

    space: Space | None = SpaceApi.get_space_detail(space_uid=space_uid)
    if not space:
        raise ValueError("convert space_uid to bk_tenant_id failed, space_uid: %s", space_uid)
    return space.bk_tenant_id


@lru_cache(maxsize=10000)
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
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return DEFAULT_TENANT_ID

    space: Space | None = SpaceApi.get_space_detail(bk_biz_id=int(bk_biz_id))
    if not space:
        raise ValueError(f"convert bk_biz_id to bk_tenant_id failed, bk_biz_id: {bk_biz_id}")
    return space.bk_tenant_id


@lru_cache(maxsize=1024)
def get_tenant_default_biz_id(bk_tenant_id: str) -> int:
    """
    获取租户下的默认业务ID
    """
    # 如果未开启多租户模式，则返回默认业务ID
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return settings.DEFAULT_BK_BIZ_ID

    from core.drf_resource import api

    variables = api.bk_login.list_tenant_variables(bk_tenant_id=bk_tenant_id)
    for variable in variables:
        if variable["name"] == "default_bk_biz_id":
            return int(variable["value"])
    raise ValueError("get tenant system biz id failed, bk_tenant_id: %s", bk_tenant_id)


class DatalinkBizIds(NamedTuple):
    """
    数据链路业务ID
    """

    # 数据归属业务ID
    label_biz_id: int
    # 实际存储业务ID
    data_biz_id: int


def get_tenant_datalink_biz_id(bk_tenant_id: str, bk_biz_id: int | None = None) -> DatalinkBizIds:
    """
    获取租户下的数据链路业务ID
    """
    # 获取默认数据存储业务ID
    default_data_biz_id = get_tenant_default_biz_id(bk_tenant_id)

    # 如果业务ID小于等于0，则标记业务ID为默认业务ID
    if bk_biz_id is None or bk_biz_id <= 0:
        label_biz_id: int = default_data_biz_id
        data_biz_id = default_data_biz_id
    else:
        label_biz_id = bk_biz_id

        # 如果开启的多租户模式，则数据归属业务ID为实际的业务ID
        if settings.ENABLE_MULTI_TENANT_MODE:
            data_biz_id = bk_biz_id
        else:
            data_biz_id = settings.DEFAULT_BKDATA_BIZ_ID
    return DatalinkBizIds(label_biz_id=label_biz_id, data_biz_id=data_biz_id)
