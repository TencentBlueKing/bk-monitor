"""
新环境迁移范围判断工具。
"""

from django.conf import settings

from bkm_space.api import SpaceApi
from bkm_space.define import SpaceTypeEnum
from bkm_space.utils import bk_biz_id_to_space_uid


def is_biz_id_need_managed(bk_biz_id: int | str) -> bool:
    """
    判断业务 ID 是否需要管理。
    """
    if not bk_biz_id:
        return True

    try:
        bk_biz_id_int = int(bk_biz_id)
    except (TypeError, ValueError):
        return False

    if bk_biz_id_int == 0:
        return True

    start_biz_id = settings.NEW_ENV_START_BIZ_ID
    biz_black_list = settings.NEW_ENV_BIZ_BLACK_LIST
    biz_white_list = settings.NEW_ENV_BIZ_WHITE_LIST

    # 业务在黑名单中
    if bk_biz_id_int in biz_black_list:
        return False

    # 业务在白名单中
    if bk_biz_id_int in biz_white_list:
        return True

    # 未配置起始业务ID
    if not start_biz_id:
        return True

    # 业务ID大于起始业务ID
    try:
        start_biz_id_int = int(start_biz_id)
    except (TypeError, ValueError):
        return True
    if bk_biz_id_int > start_biz_id_int:
        return True

    return False


def is_biz_id_in_black_list(bk_biz_id: int | str) -> bool:
    """
    判断业务 ID 是否在黑名单中。
    """

    try:
        bk_biz_id_int = int(bk_biz_id)
    except (TypeError, ValueError):
        return False

    if bk_biz_id_int == 0:
        return False

    if bk_biz_id_int in settings.NEW_ENV_BIZ_BLACK_LIST:
        return True

    if bk_biz_id_int < 0:
        space_uid = bk_biz_id_to_space_uid(bk_biz_id_int)
        related_cc_space = SpaceApi.get_related_space(space_uid, SpaceTypeEnum.BKCC.value)
        if related_cc_space and related_cc_space.bk_biz_id in settings.NEW_ENV_BIZ_BLACK_LIST:
            return True

    return False
