import datetime

from django.db import transaction
from django.db.models import Q

from bk_monitor_base.infras.constant import SPACE_UID_HYPHEN

from .define import Space, SpaceStatus, SpaceTypeEnum
from .models import SpaceModel


def save_spaces(spaces: list[Space], operator: str) -> list[Space]:
    """创建或更新空间

    根据 unique_together 约束 (space_type_id, space_id) 判断是创建还是更新。
    如果空间已存在则更新，否则创建新空间。

    此操作是原子性的：如果批量保存中的任何一个失败，所有更改都会回滚。
    使用批量操作优化性能，减少数据库查询次数。

    Args:
        spaces: 空间列表
        operator: 操作人

    Returns:
        list[Space]: 创建或更新成功的空间列表

    Raises:
        ValueError: 当 Space 对象缺少必需字段时
        django.db.IntegrityError: 当违反数据库唯一性约束时
    """
    if not spaces:
        return []

    with transaction.atomic():
        # 构建查询条件，批量查询已存在的空间
        # 使用 Q 对象构建 OR 条件，查询所有可能已存在的空间
        if len(spaces) == 1:
            # 单个空间时直接查询
            space = spaces[0]
            space_type, space_id = space.uid.split(SPACE_UID_HYPHEN, 1)
            existing_models = list(
                SpaceModel.objects.filter(space_type_id=space_type, space_id=space_id).select_for_update()
            )
        else:
            # 多个空间时批量查询
            query = Q()
            for space in spaces:
                space_type, space_id = space.uid.split(SPACE_UID_HYPHEN, 1)
                query |= Q(space_type_id=space_type, space_id=space_id)
            existing_models = list(SpaceModel.objects.filter(query).select_for_update())

        # 构建已存在空间的映射表，key 为 (space_type_id, space_id)
        existing_map: dict[tuple[SpaceTypeEnum, str], SpaceModel] = {
            (SpaceTypeEnum(model.space_type_id), model.space_id): model for model in existing_models
        }

        # 分离需要创建和更新的空间
        to_create: list[SpaceModel] = []
        to_update: list[SpaceModel] = []

        for space in spaces:
            space_type, space_id = space.uid.split(SPACE_UID_HYPHEN, 1)
            key = (SpaceTypeEnum(space_type), space_id)
            if key in existing_map:
                # 更新已存在的空间
                space_model = existing_map[key]
                space_model.bk_tenant_id = space.bk_tenant_id
                space_model.space_name = space.name
                space_model.status = space.status.value
                space_model.time_zone = space.timezone
                space_model.language = space.language
                space_model.is_global = space.is_global
                space_model.updater = operator
                space_model.update_time = space.update_time or datetime.datetime.now()
                to_update.append(space_model)
            else:
                # 创建新空间
                space_model = SpaceModel(
                    space_type_id=space.type.value,
                    space_id=space_id,
                    bk_tenant_id=space.bk_tenant_id,
                    space_name=space.name,
                    space_code=None,  # TODO: 后续需要补充该字段
                    status=space.status.value,
                    time_zone=space.timezone,
                    language=space.language,
                    is_global=space.is_global,
                    creator=operator,
                    updater=operator,
                )
                to_create.append(space_model)

        # 批量创建新空间
        if to_create:
            SpaceModel.objects.bulk_create(to_create, batch_size=500)
            # bulk_create() 在某些数据库后端可能不会自动设置 pk
            # 重新查询以确保所有对象都有 pk，并保持原有顺序
            create_query = Q()
            for space_model in to_create:
                create_query |= Q(space_type_id=space_model.space_type_id, space_id=space_model.space_id)
            queried_models = {
                (model.space_type_id, model.space_id): model for model in SpaceModel.objects.filter(create_query)
            }
            # 按照原始顺序重新排列
            to_create = [queried_models[(model.space_type_id, model.space_id)] for model in to_create]

        # 批量更新已存在的空间
        if to_update:
            SpaceModel.objects.bulk_update(
                to_update,
                fields=[
                    "bk_tenant_id",
                    "space_name",
                    "status",
                    "time_zone",
                    "language",
                    "is_global",
                    "updater",
                    "update_time",
                ],
                batch_size=500,
            )

        # 合并所有空间模型并转换为 Space 对象
        all_models = to_create + to_update
        return [model.to_space() for model in all_models]


def delete_spaces(bk_biz_ids: list[int | str] | None = None, space_uids: list[str] | None = None) -> list[Space]:
    """删除空间

    空间删除时，将空间设置为禁用状态（软删除）。

    Args:
        bk_biz_ids: 蓝鲸业务ID列表，支持 int 或 str 类型
        space_uids: 空间ID列表（格式：space_type_id__space_id）

    Returns:
        list[Space]: 删除成功的空间列表

    Raises:
        ValueError: 当两个参数都未提供时
    """
    if not bk_biz_ids and not space_uids:
        raise ValueError("至少需要提供 bk_biz_ids 或 space_uids 参数之一")

    query = Q()

    # 根据 bk_biz_ids 构建查询条件
    if bk_biz_ids:
        # 适配 bk_biz_ids 参数类型为字符串的情况
        int_biz_ids = [int(biz_id) for biz_id in bk_biz_ids]

        # BKCC 类型的空间，space_id 等于 bk_biz_id（字符串形式）
        bkcc_query = Q(space_type_id=SpaceTypeEnum.BKCC.value, space_id__in=[str(biz_id) for biz_id in int_biz_ids])

        # 其他类型的空间，需要通过 get_bk_biz_id() 反向查找
        # get_bk_biz_id() 返回 -pk，所以需要查找 pk = -bk_biz_id 的记录
        other_query = Q(pk__in=[-biz_id for biz_id in int_biz_ids if biz_id < 0])

        query |= bkcc_query | other_query

    # 根据 space_uids 构建查询条件
    if space_uids:
        uid_conditions = Q()
        for space_uid in space_uids:
            if SPACE_UID_HYPHEN not in space_uid:
                continue
            parts = space_uid.split(SPACE_UID_HYPHEN, 1)
            if len(parts) == 2:
                space_type_id, space_id = parts
                uid_conditions |= Q(space_type_id=space_type_id, space_id=space_id)
        query |= uid_conditions

    # 批量更新状态为 DISABLED
    SpaceModel.objects.filter(query).update(status=SpaceStatus.DISABLED.value)

    # 查询更新后的空间并转换为 Space 对象
    deleted_spaces = [space_model.to_space() for space_model in SpaceModel.objects.filter(query)]

    return deleted_spaces


def list_spaces(
    bk_tenant_id: str | None = None,
    bk_biz_ids: list[int | str] | None = None,
    space_uids: list[str] | None = None,
) -> list[Space]:
    """查询空间列表

    根据提供的条件查询空间列表，支持多个条件的组合查询。

    Args:
        bk_tenant_id: 蓝鲸租户ID
        bk_biz_ids: 蓝鲸业务ID列表，支持 int 或 str 类型
        space_uids: 空间ID列表（格式：space_type_id__space_id）

    Returns:
        list[Space]: 符合条件的空间列表，如果没有匹配的空间则返回空列表
    """
    query = Q()

    # 根据 bk_tenant_id 过滤
    if bk_tenant_id is not None:
        query &= Q(bk_tenant_id=bk_tenant_id)

    # 根据 bk_biz_ids 构建查询条件
    if bk_biz_ids:
        # 适配 bk_biz_ids 参数类型为字符串的情况
        int_biz_ids = [int(biz_id) for biz_id in bk_biz_ids]

        # BKCC 类型的空间，space_id 等于 bk_biz_id（字符串形式）
        bkcc_query = Q(space_type_id=SpaceTypeEnum.BKCC.value, space_id__in=[str(biz_id) for biz_id in int_biz_ids])

        # 其他类型的空间，需要通过 get_bk_biz_id() 反向查找
        # get_bk_biz_id() 返回 -pk，所以需要查找 pk = -bk_biz_id 的记录
        other_query = Q(pk__in=[-biz_id for biz_id in int_biz_ids if biz_id < 0])

        query &= bkcc_query | other_query

    # 根据 space_uids 构建查询条件
    if space_uids:
        uid_conditions = Q()
        for space_uid in space_uids:
            if SPACE_UID_HYPHEN not in space_uid:
                continue
            parts = space_uid.split(SPACE_UID_HYPHEN, 1)
            if len(parts) == 2:
                space_type_id, space_id = parts
                uid_conditions |= Q(space_type_id=space_type_id, space_id=space_id)
        query &= uid_conditions

    # 查询并转换为 Space 对象列表
    space_models = SpaceModel.objects.filter(query)
    return [space_model.to_space() for space_model in space_models]


def get_space(bk_biz_id: int | str | None = None, space_uid: str | None = None) -> Space:
    """获取单个空间

    根据 bk_biz_id 或 space_uid 查询单个空间。

    Args:
        bk_biz_id: 蓝鲸业务ID
        space_uid: 空间ID（格式：space_type_id__space_id）

    Returns:
        Space: 空间对象

    Raises:
        ValueError: 当两个参数都未提供，或空间不存在时
    """
    # 适配 bk_biz_id 参数类型为字符串的情况，先归一化再校验
    if bk_biz_id is not None:
        bk_biz_id = int(bk_biz_id)

    if bk_biz_id is None and not space_uid:
        raise ValueError("至少需要提供 bk_biz_id 或 space_uid 参数之一")

    query = Q()

    # 根据 bk_biz_id 构建查询条件
    if bk_biz_id is not None:
        # BKCC 类型的空间，space_id 等于 bk_biz_id（字符串形式）
        if bk_biz_id >= 0:
            query = Q(space_type_id=SpaceTypeEnum.BKCC.value, space_id=str(bk_biz_id))
        else:
            # 其他类型的空间，get_bk_biz_id() 返回 -pk
            query = Q(pk=-bk_biz_id)

    # 根据 space_uid 构建查询条件
    if space_uid:
        if SPACE_UID_HYPHEN not in space_uid:
            raise ValueError(f"space_uid 格式错误，应为 space_type_id{SPACE_UID_HYPHEN}space_id")
        parts = space_uid.split(SPACE_UID_HYPHEN, 1)
        if len(parts) != 2:
            raise ValueError(f"space_uid 格式错误，应为 space_type_id{SPACE_UID_HYPHEN}space_id")
        space_type_id, space_id = parts
        if query:
            # 如果同时提供了两个参数，需要同时满足
            query &= Q(space_type_id=space_type_id, space_id=space_id)
        else:
            query = Q(space_type_id=space_type_id, space_id=space_id)

    try:
        space_model = SpaceModel.objects.get(query)
        return space_model.to_space()
    except SpaceModel.DoesNotExist as err:
        raise ValueError("空间不存在") from err
