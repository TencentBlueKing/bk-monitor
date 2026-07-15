from metadata.models.space.space import Space, SpaceDataSource, SpaceResource
from monitor_web.data_migrate.fetcher.base import FetcherResultType


def get_metadata_space_fetcher(bk_biz_id: int | None) -> list[FetcherResultType]:
    """
    获取 Metadata 中 Space 相关表。

    分层规则：
    - ``SpaceType`` 是全局空间类型定义，始终全量导出
    - ``Space`` 是空间主表
    - ``SpaceDataSource``、``SpaceResource`` 通过 ``space_type_id + space_id`` 关联回空间主表
    - ``SpaceStickyInfo`` 为用户级空间置顶配置，不带业务字段，单独全量导出

    按业务维度过滤 ``Space`` 时，需先将业务 ID 还原为真实空间：
    - 正数业务 ID 对应 ``bkcc__<bk_biz_id>``
    - 负数业务 ID 对应 ``Space`` 主键取反后的非 BKCC 空间
    """
    if bk_biz_id is None:
        space_filters = None
    elif bk_biz_id == 0:
        # 保留原有的平台业务查询语义。
        space_filters = {"space_type_id": "bkcc", "space_id": "0"}
    else:
        space_info = Space.objects.get_space_info_by_biz_id(bk_biz_id=int(bk_biz_id))
        space_filters = {
            "space_type_id": space_info["space_type"],
            "space_id": str(space_info["space_id"]),
        }

    return [
        # (SpaceType, None, None),
        (Space, space_filters, None),
        (SpaceDataSource, space_filters, None),
        (SpaceResource, space_filters, None),
        # (SpaceStickyInfo, None, None),
    ]
