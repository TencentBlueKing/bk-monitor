"""
新环境迁移范围判断工具。
"""

from django.conf import settings


def is_biz_id_in_new_env_scope(
    bk_biz_id: int | str | None,
    *,
    start_biz_id: int | str | None,
    biz_black_list: list[int | str] | None = None,
    biz_white_list: list[int | str] | None = None,
) -> bool:
    """
    判断业务 ID 是否满足新环境接管条件。

    业务 0 承载公共配置，不受黑名单、白名单和起始业务 ID 阈值约束。其它业务规则优先级：
    黑名单 > 白名单 > 起始业务 ID 阈值。未配置或非法阈值时关闭阈值过滤，保持历史全量接管行为。
    """
    if bk_biz_id is None:
        return False

    biz_id = str(bk_biz_id).strip()
    if biz_id == "0":
        return True

    black_list = {str(item).strip() for item in biz_black_list or [] if str(item).strip()}
    white_list = {str(item).strip() for item in biz_white_list or [] if str(item).strip()}

    if biz_id in black_list:
        return False

    if biz_id in white_list:
        return True

    if start_biz_id in ("", None):
        return True

    try:
        biz_id_int = int(biz_id)
    except (TypeError, ValueError):
        return False

    try:
        start_biz_id_int = int(start_biz_id)
    except (TypeError, ValueError):
        return True

    return biz_id_int > start_biz_id_int


def is_biz_id_need_managed(bk_biz_id: int | str) -> bool:
    """
    判断业务 ID 是否需要管理。
    """
    if not bk_biz_id:
        return True

    bk_biz_id = int(bk_biz_id)

    start_biz_id = settings.NEW_ENV_START_BIZ_ID
    biz_black_list = settings.NEW_ENV_BIZ_BLACK_LIST
    biz_white_list = settings.NEW_ENV_BIZ_WHITE_LIST

    # 业务在黑名单中
    if bk_biz_id in biz_black_list:
        return False

    # 业务在白名单中
    if bk_biz_id in biz_white_list:
        return True

    # 未配置起始业务ID
    if not start_biz_id:
        return True

    # 业务ID大于起始业务ID
    try:
        start_biz_id_int = int(start_biz_id)
    except (TypeError, ValueError):
        return True
    if bk_biz_id > start_biz_id_int:
        return True

    return False
