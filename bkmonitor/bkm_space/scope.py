from bkm_space import api
from bkm_space.define import SpaceTypeEnum
from bkm_space.utils import bk_biz_id_to_space_uid, parse_space_uid, space_uid_to_bk_biz_id

MONITOR_SCOPE_QUERY_SENTINELS = {-1, -2}


def bk_biz_id_to_scope_id(bk_biz_id: str | int) -> str:
    """将监控 bk_biz_id 协议转换为 BKFara 标准 scope_id。"""
    if isinstance(bk_biz_id, str) and bk_biz_id.startswith(("bkcc_", "bcs_", "bkci_", "bksaas_")):
        return bk_biz_id

    try:
        numeric_bk_biz_id = int(bk_biz_id)
    except (TypeError, ValueError):
        return ""

    if numeric_bk_biz_id in MONITOR_SCOPE_QUERY_SENTINELS:
        raise ValueError("monitor query sentinel must be expanded before scope conversion")

    if numeric_bk_biz_id >= 0:
        return f"{SpaceTypeEnum.BKCC.value}_{numeric_bk_biz_id}"

    try:
        space_uid = bk_biz_id_to_space_uid(numeric_bk_biz_id)
    except Exception as error:
        raise ValueError(f"cannot resolve bk_biz_id: {bk_biz_id}") from error
    if not space_uid:
        raise ValueError(f"cannot resolve bk_biz_id: {bk_biz_id}")

    scope_type, scope_value = parse_space_uid(space_uid)
    return f"{scope_type}_{scope_value}"


def scope_id_to_bk_biz_id(scope_id: str) -> int:
    """将 BKFara 标准 scope_id 转回监控前端使用的 bk_biz_id。"""
    if not scope_id or "_" not in str(scope_id):
        return 0

    scope_type, scope_value = str(scope_id).split("_", 1)
    if scope_type == SpaceTypeEnum.BKCC.value:
        try:
            return int(scope_value)
        except (TypeError, ValueError):
            return 0

    try:
        return space_uid_to_bk_biz_id(api.SpaceApi.gen_space_uid(scope_type, scope_value))
    except Exception:
        return 0
