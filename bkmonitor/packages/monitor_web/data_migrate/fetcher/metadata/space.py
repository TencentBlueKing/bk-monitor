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

    当前按业务维度过滤 ``Space`` 时，仅收敛 BKCC 空间，即 ``space_type_id='bkcc'`` 且 ``space_id=str(bk_biz_id)``。
    这是 Metadata Space 与业务 ID 之间最稳定的直接映射。
    """
    if bk_biz_id is None:
        space_filters = None
    else:
        space_filters = {"space_type_id": "bkcc", "space_id": str(bk_biz_id)}

    return [
        # (SpaceType, None, None),
        (Space, space_filters, None),
        (SpaceDataSource, space_filters, None),
        (SpaceResource, space_filters, None),
        # (SpaceStickyInfo, None, None),
    ]
