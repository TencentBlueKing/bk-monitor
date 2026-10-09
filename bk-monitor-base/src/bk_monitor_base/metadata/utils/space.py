from functools import lru_cache

from bk_monitor_base.metadata.models.space import Space
from bk_monitor_base.metadata.models.space.constants import SpaceTypes


@lru_cache(maxsize=2000)
def bk_biz_id_to_space_uid(bk_biz_id: str | int) -> str:
    """
    业务ID 转换为 空间唯一标识
    :param bk_biz_id: CMDB 业务ID
    :return: space_uid
    """
    bk_biz_id = int(bk_biz_id)
    if bk_biz_id >= 0:
        return f"{SpaceTypes.BKCC.value}__{bk_biz_id}"
    try:
        space: Space = Space.objects.get(id=-bk_biz_id)
        return space.space_uid
    except Space.DoesNotExist:
        return ""
