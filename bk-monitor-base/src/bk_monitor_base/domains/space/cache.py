import inspect
from collections.abc import Callable
from functools import lru_cache, wraps
from typing import Any, TypeVar, cast

from bk_monitor_base.config.all import get_config
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID, SPACE_UID_HYPHEN

from .define import SpaceTypeEnum
from .models import SpaceModel
from .operation import get_space

F = TypeVar("F", bound=Callable[..., Any])

SPACE_CACHE_MAXSIZE = get_config().domains.space.space_cache_size


@lru_cache(maxsize=SPACE_CACHE_MAXSIZE)
def bk_biz_id_to_space_uid(bk_biz_id: int | str) -> str:
    """根据蓝鲸业务ID获取空间UID

    Args:
        bk_biz_id: 蓝鲸业务ID

    Returns:
        str: 空间UID
    """
    bk_biz_id = int(bk_biz_id)

    if bk_biz_id > 0:
        return f"{SpaceTypeEnum.BKCC.value}{SPACE_UID_HYPHEN}{bk_biz_id}"
    space = SpaceModel.objects.get(pk=-bk_biz_id)
    return space.space_uid


@lru_cache(maxsize=SPACE_CACHE_MAXSIZE)
def bk_biz_id_to_bk_tenant_id(bk_biz_id: int | str) -> str:
    """根据蓝鲸业务ID获取蓝鲸租户ID

    Args:
        bk_biz_id: 蓝鲸业务ID

    Returns:
        str: 蓝鲸租户ID
    """
    if not get_config().blueking.enable_multi_tenancy:
        return DEFAULT_TENANT_ID

    bk_biz_id = int(bk_biz_id)

    return get_space(bk_biz_id=bk_biz_id).bk_tenant_id


@lru_cache(maxsize=SPACE_CACHE_MAXSIZE)
def space_uid_to_bk_biz_id(space_uid: str) -> int:
    """根据空间UID获取蓝鲸业务ID

    Args:
        space_uid: 空间UID

    Returns:
        int: 蓝鲸业务ID
    """
    return int(space_uid.split(SPACE_UID_HYPHEN, 1)[1])


@lru_cache(maxsize=SPACE_CACHE_MAXSIZE)
def space_uid_to_bk_tenant_id(space_uid: str) -> str:
    """根据空间UID获取蓝鲸租户ID

    Args:
        space_uid: 空间UID

    Returns:
        str: 蓝鲸租户ID
    """
    if not get_config().blueking.enable_multi_tenancy:
        return DEFAULT_TENANT_ID
    return get_space(space_uid=space_uid).bk_tenant_id


def check_bk_biz_id_and_bk_tenant_id(func: F) -> F:
    """装饰器：检查函数参数中的bk_tenant_id与bk_biz_id是否匹配

    该装饰器会自动检查被装饰函数的参数中是否同时包含bk_tenant_id和bk_biz_id，
    如果包含，则在函数执行前验证它们的关系是否匹配。

    Args:
        func: 被装饰的函数，需要包含bk_tenant_id和bk_biz_id参数

    Returns:
        装饰后的函数

    Raises:
        ValueError: 当bk_tenant_id与bk_biz_id不匹配时抛出异常

    Example:
        @check_bk_biz_id_and_bk_tenant_id
        def some_function(bk_tenant_id: str, bk_biz_id: int, other_param: str):
            # 函数执行前会自动检查bk_tenant_id和bk_biz_id是否匹配
            pass
    """
    sig = inspect.signature(func)

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # 构建参数字典，将位置参数和关键字参数合并
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        params = bound_args.arguments

        # 检查是否同时包含bk_tenant_id和bk_biz_id参数
        if "bk_tenant_id" in params and "bk_biz_id" in params:
            bk_tenant_id = params["bk_tenant_id"]
            bk_biz_id = params["bk_biz_id"]

            # 如果两个参数都有值，则进行验证
            if bk_tenant_id is not None and bk_biz_id is not None:
                expected_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
                if expected_tenant_id != bk_tenant_id:
                    error_msg = (
                        f"业务ID和租户ID不匹配: bk_biz_id={bk_biz_id}, "
                        f"expected_tenant_id={expected_tenant_id}, "
                        f"bk_tenant_id={bk_tenant_id}"
                    )
                    raise ValueError(error_msg)

        return func(*args, **kwargs)

    return cast(F, wrapper)
