import logging
from functools import reduce
from typing import Any

logger = logging.getLogger("metadata")


def getitems(obj: dict, items: list | str, default: Any = None) -> Any:
    """
    递归获取数据
    注意：使用字符串作为键路径时，须确保 Key 值均为字符串

    :param obj: Dict 类型数据
    :param items: 键列表：['foo', 'bar']，或者用 "." 连接的键路径： ".foo.bar" 或 "foo.bar"
    :param default: 默认值
    :return: 返回对应的value或者默认值
    """
    if not isinstance(obj, dict):
        raise TypeError("Dict object support only!")
    if isinstance(items, str):
        items = items.strip(".").split(".")
    try:
        return reduce(lambda x, i: x[i], items, obj)
    except (IndexError, KeyError, TypeError):
        return default


def get_biz_id_by_space_uid(bk_tenant_id: str, space_uid: str):
    """
    根据space_uid查询归属的业务ID
    """
    from bk_monitor_base.metadata.models.space import SpaceResource
    from bk_monitor_base.metadata.models.space.constants import SpaceTypes

    try:
        space_type, space_id = space_uid.split("__")
        if space_type == SpaceTypes.BKCC.value:
            return int(space_id)
        bk_biz_id = SpaceResource.objects.get(
            bk_tenant_id=bk_tenant_id, space_type_id=space_type, space_id=space_id, resource_type=SpaceTypes.BKCC.value
        ).resource_id
        return int(bk_biz_id)
    except Exception:  # pylint: disable=broad-except
        return 0


def get_space_uid_and_bk_biz_id_by_bk_data_id(bk_tenant_id: str, bk_data_id: int):
    """
    根据data_id，查询对应的space_uid和bk_biz_id
    @param bk_data_id: 数据ID
    @return: bk_biz_id, space_uid
    """
    from bk_monitor_base.metadata.models.space import Space, SpaceDataSource

    try:
        # 查询DataSource关联的记录
        related_space_info = SpaceDataSource.objects.filter(bk_data_id=bk_data_id).first()
        if not related_space_info:
            logger.warning(
                "get_space_uid_and_bk_biz_id_by_bk_data_id: no related_space_info found for bk_data_id->[%s]",
                bk_data_id,
            )
            return 0, ""
        space_uid = related_space_info.space_type_id + "__" + related_space_info.space_id
        bk_biz_id = get_biz_id_by_space_uid(bk_tenant_id=bk_tenant_id, space_uid=space_uid)

        if bk_biz_id < 0:
            # NOTE：可能存在SpaceDataSource中绑定了错误的元信息的情况，这里ID为负数的话，则去Space中取真实的space_uid
            logger.warning(
                "get_space_uid_and_bk_biz_id_by_bk_data_id: bk_data_id->[%s],search space_resource found a "
                "negative biz_id->[%s]",
                bk_data_id,
                bk_biz_id,
            )
            space = Space.objects.get(id=abs(bk_biz_id))
            space_uid = space.space_uid
            bk_biz_id = get_biz_id_by_space_uid(bk_tenant_id=bk_tenant_id, space_uid=space_uid)

        return bk_biz_id, space_uid
    except Exception as e:  # pylint: disable=broad-except
        logger.warning(
            "get_space_uid_and_bk_biz_id_by_bk_data_id: failed to get info for bk_data_id->[%s],error->[%s]",
            bk_data_id,
            e,
        )
        return 0, ""
