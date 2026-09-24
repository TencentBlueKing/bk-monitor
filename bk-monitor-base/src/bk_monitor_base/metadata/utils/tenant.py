from functools import lru_cache
from typing import NamedTuple

from django.db.models import Q

from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID
from bk_monitor_base.infras.third_party_api.user.api import list_tenant_variables
from bk_monitor_base.metadata.config import settings
from bk_monitor_base.metadata.models.space.constants import SPACE_UID_HYPHEN, SpaceTypes
from bk_monitor_base.metadata.utils.local import local


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
    if not settings.blueking.enable_multi_tenancy:
        return DEFAULT_TENANT_ID

    from bk_monitor_base.metadata.models.space import Space

    if SPACE_UID_HYPHEN not in space_uid:
        raise ValueError("invalid space_uid format, space_uid: %s", space_uid)

    space_type_id, space_id = space_uid.split(maxsplit=1)
    try:
        space: Space = Space.objects.get(space_type_id=space_type_id, space_id=space_id)
    except Space.DoesNotExist:
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
    if not settings.blueking.enable_multi_tenancy:
        return DEFAULT_TENANT_ID

    from bk_monitor_base.metadata.models.space import Space

    # BKCC 类型的空间，space_id 等于 bk_biz_id（字符串形式）
    if bk_biz_id >= 0:
        query = Q(space_type_id=SpaceTypes.BKCC.value, space_id=str(bk_biz_id))
    else:
        # 其他类型的空间，get_bk_biz_id() 返回 -pk
        query = Q(pk=-bk_biz_id)

    try:
        space = Space.objects.get(query)
    except Space.DoesNotExist:
        raise ValueError(f"convert bk_biz_id to bk_tenant_id failed, bk_biz_id: {bk_biz_id}")
    return space.bk_tenant_id


@lru_cache(maxsize=1024)
def get_tenant_default_biz_id(bk_tenant_id: str) -> int:
    """
    获取租户下的默认业务ID
    """
    # 如果未开启多租户模式，则返回默认业务ID
    if not settings.blueking.enable_multi_tenancy:
        return settings.blueking.default_bk_biz_id

    variables = list_tenant_variables(bk_tenant_id=bk_tenant_id)
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
        if settings.blueking.enable_multi_tenancy:
            data_biz_id = bk_biz_id
        else:
            data_biz_id = settings.blueking.default_bk_biz_id
    return DatalinkBizIds(label_biz_id=label_biz_id, data_biz_id=data_biz_id)
