# pyright: reportArgumentType=false
# pyright: reportOperatorIssue=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportImplicitStringConcatenation=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnnecessaryComparison=false

"""
动态分组操作模块

提供动态分组的增删改查功能，使用Django ORM替代DAO层。
"""

import logging
from typing import Any

from django.db import transaction
from django.db.models import Count

from bk_monitor_base.domains.dynamic_group.define import DynamicGroup
from bk_monitor_base.domains.dynamic_group.errors import ErrorCodes
from bk_monitor_base.domains.dynamic_group.models import DynamicGroupMemberORM, DynamicGroupORM
from bk_monitor_base.domains.dynamic_group.operations.cache import (
    cache_dynamic_group_member,
    delete_dynamic_group_cache,
)
from bk_monitor_base.domains.dynamic_group.utils.comparator import MemberComparator
from bk_monitor_base.domains.dynamic_group.utils.condition import ConditionConverter
from bk_monitor_base.domains.dynamic_group.utils.fetcher import get_member_fetcher
from bk_monitor_base.domains.dynamic_group.utils.formatter import MemberFormatter
from bk_monitor_base.domains.dynamic_group.utils.usage_record import UsageRecordOperator
from bk_monitor_base.infras.third_party_api import cmdb
from bk_monitor_base.object_model import list_object_models

logger = logging.getLogger(__name__)


def list_dynamic_groups(
    dynamic_group_ids: list[int] | None = None,
    object_model_codes: list[str] | None = None,
    space_codes: list[str] | None = None,
    bk_tenant_ids: list[str] | None = None,
    name_contains: str | None = None,
    created_by: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    order_by: list[str] | None = None,
    raise_not_found: bool = False,
    with_member_count: bool = False,
) -> tuple[int, list[DynamicGroup]]:
    """
    根据条件查询动态分组列表

    Args:
        dynamic_group_ids: 动态分组ID列表
        object_model_codes: 对象模型代码列表
        space_codes: 空间代码列表
        bk_tenant_ids: 租户ID列表
        name_contains: 名称包含的字符串，用于模糊查询
        created_by: 创建者
        limit: 限制返回结果数量
        offset: 偏移量
        order_by: 排序字段列表，如 ["-created_at", "dynamic_group_name"]
        raise_not_found: 当查询结果为空时是否抛出异常
        with_member_count: 是否统计成员数量

    Returns:
        tuple[int, list[DynamicGroup]]: (总数, 分页后的动态分组列表)

    Raises:
        ErrorCodes.DYNAMIC_GROUP_NOT_FOUND: 当raise_not_found为True且查询结果为空时
    """
    qs = DynamicGroupORM.objects.all()

    # 过滤动态分组ID
    if dynamic_group_ids is not None:
        qs = qs.filter(dynamic_group_id__in=dynamic_group_ids)

    # 过滤对象模型代码
    if object_model_codes is not None:
        qs = qs.filter(object_model_code__in=object_model_codes)

    # 过滤空间代码
    if space_codes is not None:
        qs = qs.filter(space_code__in=space_codes)

    # 过滤租户ID
    if bk_tenant_ids is not None:
        qs = qs.filter(bk_tenant_id__in=bk_tenant_ids)

    # 过滤创建者
    if created_by is not None:
        qs = qs.filter(created_by=created_by)

    # 名称模糊查询
    if name_contains is not None:
        qs = qs.filter(dynamic_group_name__icontains=name_contains)

    # 在分页前统计总数
    total = qs.count()

    # 统计成员数量
    if with_member_count:
        qs = qs.annotate(member_count=Count("dynamicgroupmemberorm"))

    # 排序
    if order_by:
        qs = qs.order_by(*order_by)
    else:
        qs = qs.order_by("-created_at")

    # 分页
    if offset is not None:
        qs = qs[offset:]
    if limit is not None:
        qs = qs[:limit]

    results = list(qs)

    if raise_not_found and not results:
        raise ErrorCodes.DYNAMIC_GROUP_NOT_FOUND

    return total, [group.to_entity() for group in results]


def get_dynamic_group(
    dynamic_group_id: int,
    raise_not_found: bool = True,
    with_member_count: bool = False,
) -> DynamicGroup | None:
    """
    根据ID获取动态分组

    Args:
        dynamic_group_id: 动态分组ID
        raise_not_found: 当查询结果为空时是否抛出异常
        with_member_count: 是否统计成员数量

    Returns:
        DynamicGroup | None: 动态分组实体

    Raises:
        ErrorCodes.DYNAMIC_GROUP_NOT_FOUND: 当raise_not_found为True且查询结果为空时
    """
    try:
        qs = DynamicGroupORM.objects
        if with_member_count:
            qs = qs.annotate(member_count=Count("dynamicgroupmemberorm"))
        group = qs.get(dynamic_group_id=dynamic_group_id)
        return group.to_entity()
    except DynamicGroupORM.DoesNotExist:
        if raise_not_found:
            raise ErrorCodes.DYNAMIC_GROUP_NOT_FOUND.set_message(f"动态分组不存在: dynamic_group_id={dynamic_group_id}")
        return None


def create_dynamic_group(entity: DynamicGroup) -> tuple[DynamicGroup, list[int]]:
    """
    创建动态分组

    Args:
        entity: 动态分组实体，包含分组的完整信息
            - dynamic_group_name: 动态分组名称
            - condition_list: 分组条件列表
            - object_model_code: 对象模型代码
            - space_code: 空间代码（可选，默认为空字符串）
            - bk_tenant_id: 租户ID（可选，默认为 "system"）
            - created_by: 创建人（可选，默认为空字符串）

    Returns:
        tuple: (created_group, member_inst_ids)
            - created_group: 创建的动态分组实体
            - member_inst_ids: 成员 bk_inst_id 列表，供 view 层推送 Kafka

    Raises:
        ErrorCodes.DYNAMIC_GROUP_VALIDATE_ERROR: 当参数校验失败时
            - 动态分组名称已存在（同一空间和租户下）
            - 必填字段缺失

    Examples:
        # 创建新的动态分组
        group = DynamicGroup(
            dynamic_group_name="测试分组",
            condition_list=[{"field": "bk_host_innerip", "value": "10.", "operator": "contains"}],
            object_model_code="cw-Host",
            space_code="bkcc__2",
            bk_tenant_id="system",
            created_by="admin"
        )
        created_group, member_inst_ids = create_dynamic_group(group)
    """
    # 设置默认值
    space_code = entity.space_code or ""
    bk_tenant_id = entity.bk_tenant_id or "system"
    created_by = entity.created_by or ""

    # 校验同一空间下名称不重复
    if DynamicGroupORM.objects.filter(
        dynamic_group_name=entity.dynamic_group_name,
        space_code=space_code,
        bk_tenant_id=bk_tenant_id,
    ).exists():
        raise ErrorCodes.DYNAMIC_GROUP_VALIDATE_ERROR.set_message(f"动态分组名称已存在: {entity.dynamic_group_name}")

    # 使用事务保证数据一致性
    with transaction.atomic():
        group = DynamicGroupORM.objects.create(
            dynamic_group_name=entity.dynamic_group_name,
            condition_list=entity.condition_list,
            object_model_code=entity.object_model_code,
            space_code=space_code,
            bk_tenant_id=bk_tenant_id,
            created_by=created_by,
            updated_by=created_by,
        )

        # 查询成员并写入member表
        fetcher = get_member_fetcher(entity.object_model_code)
        try:
            # 解析业务ID
            bk_biz_id = 0
            if space_code:
                try:
                    bk_biz_id = int(space_code.split("__")[1])
                except (IndexError, ValueError):
                    pass

            # 统一交给 fetcher 将前端条件转换为 CMDBInstance DSL，这里只做结构归一化
            cmdb_condition = ConditionConverter.build_cmdb_condition(entity.condition_list)

            # 调用fetcher获取全部成员（自动翻页）
            members = fetcher.fetch_all(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                condition=cmdb_condition,
            )
            logger.info(
                f"create_dynamic_group: 查询到 {len(members)} 个成员, "
                f"dynamic_group_id={group.dynamic_group_id}, object_model_code={entity.object_model_code}"
            )
        except Exception as e:
            logger.warning(f"create_dynamic_group: 查询成员失败, dynamic_group_id={group.dynamic_group_id}, error={e}")
            members = []

        if members:
            # 精简 member 数据，只保存 bk_inst_id 和 ip_list，避免比对时因额外字段导致误判
            slim_members = [{"bk_inst_id": m.get("bk_inst_id"), "ip_list": m.get("ip_list", [])} for m in members]
            DynamicGroupMemberORM.objects.bulk_create(
                [
                    DynamicGroupMemberORM(dynamic_group_id=group.dynamic_group_id, member=member)
                    for member in slim_members
                ],
                batch_size=500,  # 批量插入优化
            )

            # 缓存分组成员信息到Redis（使用精简后的数据）
            cache_dynamic_group_member(
                dynamic_group_id=group.dynamic_group_id,
                member_list=slim_members,
                object_model_code=entity.object_model_code,
            )

    # 提取成员 bk_inst_id 列表
    member_inst_ids: list[int] = []
    for m in members:
        inst_id = m.get("bk_inst_id")
        if inst_id is not None:
            member_inst_ids.append(inst_id)

    # 创建对象模型使用记录
    UsageRecordOperator.create(group.to_entity())

    return group.to_entity(), member_inst_ids


def update_dynamic_group(
    entity: DynamicGroup,
    only_member: bool = False,
) -> tuple[DynamicGroup, list[int], list[int], bool]:
    """
    更新动态分组（使用增量比对策略）

    Args:
        entity: 动态分组实体，包含分组的完整信息
            - dynamic_group_id: 动态分组ID（必填）
            - dynamic_group_name: 动态分组名称（可选）
            - condition_list: 分组条件列表（可选）
            - object_model_code: 对象模型代码（可选）
            - updated_by: 更新人（可选）
        only_member: 仅更新成员列表的标志，默认为False

    Returns:
        tuple: (updated_group, add_list, delete_list, has_changed)
            - updated_group: 更新后的动态分组实体
            - add_list: 新增的成员 bk_inst_id 列表
            - delete_list: 删除的成员 bk_inst_id 列表
            - has_changed: 是否有变更（成员变化或 ip_list 变化）

    Raises:
        ErrorCodes.DYNAMIC_GROUP_NOT_FOUND: 当动态分组不存在时
        ErrorCodes.DYNAMIC_GROUP_VALIDATE_ERROR: 当参数校验失败时
            - 动态分组名称已存在（同一空间和租户下）
            - dynamic_group_id 缺失

    Examples:
        # 更新现有动态分组
        group = DynamicGroup(
            dynamic_group_id=1,
            dynamic_group_name="更新的分组",
            updated_by="admin"
        )
        updated_group, add_list, delete_list, has_changed = update_dynamic_group(group)
    """
    if not entity.dynamic_group_id:
        raise ErrorCodes.DYNAMIC_GROUP_VALIDATE_ERROR.set_message("dynamic_group_id 不能为空")

    try:
        group = DynamicGroupORM.objects.get(dynamic_group_id=entity.dynamic_group_id)
    except DynamicGroupORM.DoesNotExist:
        raise ErrorCodes.DYNAMIC_GROUP_NOT_FOUND.set_message(
            f"动态分组不存在: dynamic_group_id={entity.dynamic_group_id}"
        )

    # 非仅更新成员模式，先更新分组基本信息
    if not only_member:
        # 构建更新字段
        update_fields: dict[str, Any] = {"updated_by": entity.updated_by or ""}

        if entity.dynamic_group_name is not None:
            # 校验同一空间下名称不重复
            if (
                DynamicGroupORM.objects.filter(
                    dynamic_group_name=entity.dynamic_group_name,
                    space_code=group.space_code,
                    bk_tenant_id=group.bk_tenant_id,
                )
                .exclude(dynamic_group_id=entity.dynamic_group_id)
                .exists()
            ):
                raise ErrorCodes.DYNAMIC_GROUP_VALIDATE_ERROR.set_message(
                    f"动态分组名称已存在: {entity.dynamic_group_name}"
                )
            update_fields["dynamic_group_name"] = entity.dynamic_group_name

        if entity.condition_list is not None:
            update_fields["condition_list"] = entity.condition_list

        if entity.object_model_code is not None:
            update_fields["object_model_code"] = entity.object_model_code

        # 更新分组信息
        DynamicGroupORM.objects.filter(dynamic_group_id=entity.dynamic_group_id).update(**update_fields)

        # 重新获取更新后的分组
        group.refresh_from_db()

    # 获取旧成员列表
    old_member_objs = DynamicGroupMemberORM.objects.filter(dynamic_group_id=entity.dynamic_group_id)
    old_member_list = [
        {"bk_inst_id": m.member.get("bk_inst_id"), "ip_list": m.member.get("ip_list", [])} for m in old_member_objs
    ]

    # 获取新成员列表
    fetcher = get_member_fetcher(group.object_model_code)
    try:
        # 解析业务ID
        bk_biz_id = 0
        if group.space_code:
            try:
                bk_biz_id = int(group.space_code.split("__")[1])
            except (IndexError, ValueError):
                pass

        # 统一交给 fetcher 将前端条件转换为 CMDBInstance DSL，这里只做结构归一化
        cmdb_condition = ConditionConverter.build_cmdb_condition(group.condition_list)

        # 调用fetcher获取全部成员（自动翻页）
        new_member_list = fetcher.fetch_all(
            bk_tenant_id=group.bk_tenant_id,
            bk_biz_id=bk_biz_id,
            condition=cmdb_condition,
        )
        logger.debug(f"update_dynamic_group: new_member_list={new_member_list}")
    except Exception as e:
        logger.exception(f"update_dynamic_group: 查询成员失败, error={e}")
        # 查询失败时保持原有成员不变
        new_member_list = old_member_list

    # 比较新旧成员列表
    add_list, delete_list, first_related = MemberComparator.compare(
        group.object_model_code, new_member_list, old_member_list
    )
    logger.info(
        f"update_dynamic_group: dynamic_group_id={entity.dynamic_group_id}, "
        f"add_list={add_list}, first_related={first_related}"
    )
    logger.info(f"update_dynamic_group: dynamic_group_id={entity.dynamic_group_id}, delete_list={delete_list}")

    # 检查 ip_list 变更但成员不变的情况
    update_member_list, need_push_kafka = MemberComparator.get_updated_members(old_member_list, new_member_list)
    logger.info(
        f"update_dynamic_group: dynamic_group_id={entity.dynamic_group_id}, "
        f"update_member_list={[m.get('bk_inst_id') for m in update_member_list]}"
    )

    # 使用事务保证成员更新的原子性
    with transaction.atomic():
        # 1. 更新 ip_list 有变化的成员
        for update_member in update_member_list:
            inst_id = update_member["bk_inst_id"]
            # 跳过将被删除的成员
            if inst_id in delete_list:
                continue
            # 更新成员的 ip_list（精简 member 数据）
            slim_member = {"bk_inst_id": inst_id, "ip_list": update_member.get("ip_list", [])}
            DynamicGroupMemberORM.objects.filter(
                dynamic_group_id=entity.dynamic_group_id,
                member__bk_inst_id=inst_id,
            ).update(member=slim_member)

        # 2. 删除需要删除的成员
        if delete_list:
            # 使用 member__bk_inst_id 过滤来删除成员
            deleted_count, _ = DynamicGroupMemberORM.objects.filter(
                dynamic_group_id=entity.dynamic_group_id,
                member__bk_inst_id__in=delete_list,
            ).delete()
            if deleted_count:
                logger.info(
                    f"update_dynamic_group: 删除了 {deleted_count} 个成员, dynamic_group_id={entity.dynamic_group_id}"
                )

        # 3. 新增需要新增的成员
        if add_list:
            add_member_data = [m for m in new_member_list if m.get("bk_inst_id") in add_list]
            if add_member_data:
                # 精简 member 数据，只保存 bk_inst_id 和 ip_list
                slim_add_members = [
                    {"bk_inst_id": m.get("bk_inst_id"), "ip_list": m.get("ip_list", [])} for m in add_member_data
                ]
                DynamicGroupMemberORM.objects.bulk_create(
                    [
                        DynamicGroupMemberORM(dynamic_group_id=group.dynamic_group_id, member=member)
                        for member in slim_add_members
                    ],
                    batch_size=500,
                )
                logger.info(
                    f"update_dynamic_group: 新增了 {len(add_member_data)} 个成员, "
                    f"dynamic_group_id={entity.dynamic_group_id}"
                )

    # 判断是否有变化
    has_changed = bool(add_list or delete_list or first_related or need_push_kafka)

    if has_changed:
        # 有变化时更新缓存（使用精简后的数据）
        slim_new_members = [
            {"bk_inst_id": m.get("bk_inst_id"), "ip_list": m.get("ip_list", [])} for m in new_member_list
        ]
        cache_dynamic_group_member(
            dynamic_group_id=group.dynamic_group_id,
            member_list=slim_new_members,
            object_model_code=group.object_model_code,
        )
        logger.info(f"update_dynamic_group: 有变化, dynamic_group_id={entity.dynamic_group_id}")
    else:
        logger.info(f"update_dynamic_group: 无变化, dynamic_group_id={entity.dynamic_group_id}")

    return group.to_entity(), list(add_list), list(delete_list), has_changed


def delete_dynamic_group(dynamic_group_id: int) -> tuple[str, list[int]]:
    """
    删除动态分组

    Args:
        dynamic_group_id: 动态分组ID

    Returns:
        tuple: (object_model_code, member_inst_ids)
            - object_model_code: 对象模型代码，供 view 层推送 Kafka
            - member_inst_ids: 删除的成员 bk_inst_id 列表，供 view 层推送 Kafka

    Raises:
        ErrorCodes.DYNAMIC_GROUP_NOT_FOUND: 当动态分组不存在时
    """
    try:
        group = DynamicGroupORM.objects.get(dynamic_group_id=dynamic_group_id)

        # 获取成员列表（用于删除缓存和返回）
        members = list(
            DynamicGroupMemberORM.objects.filter(dynamic_group_id=dynamic_group_id).values_list("member", flat=True)
        )

        # 提取成员 bk_inst_id 列表
        member_inst_ids = [m.get("bk_inst_id") for m in members if m.get("bk_inst_id") is not None]

        # 使用事务保证删除的原子性
        with transaction.atomic():
            # 先显式删除成员表（提高性能，避免级联触发）
            member_count = DynamicGroupMemberORM.objects.filter(dynamic_group_id=dynamic_group_id).delete()[0]

            # 再删除动态分组
            group.delete()

            logger.info(
                f"delete_dynamic_group: 成功删除动态分组, "
                f"dynamic_group_id={dynamic_group_id}, 删除成员数: {member_count}"
            )

        # 删除Redis缓存
        delete_dynamic_group_cache(
            dynamic_group_id=dynamic_group_id,
            member_list=members,
            object_model_code=group.object_model_code,
        )

        # 删除对象模型使用记录
        UsageRecordOperator.delete(group.to_entity())

        return group.object_model_code, member_inst_ids

    except DynamicGroupORM.DoesNotExist:
        raise ErrorCodes.DYNAMIC_GROUP_NOT_FOUND.set_message(f"动态分组不存在: dynamic_group_id={dynamic_group_id}")


def batch_delete_dynamic_groups(dynamic_group_ids: list[int]) -> dict[int, dict[str, Any]]:
    """
    批量删除动态分组

    Args:
        dynamic_group_ids: 动态分组ID列表

    Returns:
        dict: 每个分组的删除信息，格式为:
            {
                1: {"object_model_code": "cw-Host", "member_inst_ids": [101, 102]},
                2: {"object_model_code": "cw-Redis", "member_inst_ids": [201]},
            }
    """
    if not dynamic_group_ids:
        logger.warning("batch_delete_dynamic_groups: 动态分组ID列表为空，跳过删除")
        return {}

    # 先查询需要删除的分组信息（用于清理缓存、使用记录和返回）
    groups_to_delete_qs = DynamicGroupORM.objects.filter(dynamic_group_id__in=dynamic_group_ids)
    groups_to_delete = [g.to_entity() for g in groups_to_delete_qs]
    group_info_map = {g.dynamic_group_id: g.object_model_code for g in groups_to_delete}

    # 查询每个分组的成员信息
    delete_info: dict[int, dict[str, Any]] = {}
    members_qs = DynamicGroupMemberORM.objects.filter(dynamic_group_id__in=dynamic_group_ids)
    for member_obj in members_qs:
        # 使用 dynamic_group_id 字段（ForeignKey 的实际存储）
        group_id = member_obj.dynamic_group_id  # type: ignore
        if group_id not in delete_info:
            delete_info[group_id] = {
                "object_model_code": group_info_map.get(group_id, ""),
                "member_inst_ids": [],
            }
        inst_id = member_obj.member.get("bk_inst_id")
        if inst_id is not None:
            delete_info[group_id]["member_inst_ids"].append(inst_id)

    # 补充没有成员的分组
    for group_id, object_model_code in group_info_map.items():
        if group_id not in delete_info:
            delete_info[group_id] = {
                "object_model_code": object_model_code,
                "member_inst_ids": [],
            }

    # 使用事务保证批量删除的原子性
    with transaction.atomic():
        # 先批量删除成员表（保持与单个删除逻辑一致）
        member_count = DynamicGroupMemberORM.objects.filter(dynamic_group_id__in=dynamic_group_ids).delete()[0]

        # 再批量删除动态分组
        deleted_count = DynamicGroupORM.objects.filter(dynamic_group_id__in=dynamic_group_ids).delete()[0]

        logger.info(
            f"batch_delete_dynamic_groups: 批量删除完成, "
            f"删除分组数: {deleted_count}, 删除成员数: {member_count}, "
            f"请求删除ID数: {len(dynamic_group_ids)}"
        )

    # 批量删除Redis缓存
    for group_id in dynamic_group_ids:
        if group_id in group_info_map:
            delete_dynamic_group_cache(
                dynamic_group_id=group_id,
                member_list=[],
                object_model_code=group_info_map[group_id],
            )

    # 批量删除对象模型使用记录
    UsageRecordOperator.delete(groups_to_delete)

    return delete_info


def count_dynamic_groups(
    object_model_codes: list[str] | None = None,
    space_codes: list[str] | None = None,
    bk_tenant_ids: list[str] | None = None,
) -> int:
    """
    统计动态分组数量
    Args:
        object_model_codes: 对象模型代码列表
        space_codes: 空间代码列表
        bk_tenant_ids: 租户ID列表

    Returns:
        int: 符合条件的动态分组数量
    """
    qs = DynamicGroupORM.objects.all()

    if object_model_codes is not None:
        qs = qs.filter(object_model_code__in=object_model_codes)

    if space_codes is not None:
        qs = qs.filter(space_code__in=space_codes)

    if bk_tenant_ids is not None:
        qs = qs.filter(bk_tenant_id__in=bk_tenant_ids)

    return qs.count()


def exists_dynamic_group(
    dynamic_group_name: str,
    space_code: str,
    bk_tenant_id: str = "system",
    exclude_id: int | None = None,
) -> bool:
    """
    检查动态分组是否存在

    Args:
        dynamic_group_name: 动态分组名称
        space_code: 空间代码
        bk_tenant_id: 租户ID
        exclude_id: 排除的动态分组ID

    Returns:
        bool: 是否存在
    """
    qs = DynamicGroupORM.objects.filter(
        dynamic_group_name=dynamic_group_name,
        space_code=space_code,
        bk_tenant_id=bk_tenant_id,
    )

    if exclude_id is not None:
        qs = qs.exclude(dynamic_group_id=exclude_id)

    return qs.exists()


def preview_dynamic_group_members(
    dynamic_group_id: int | None = None,
    object_model_code: str | None = None,
    condition_list: list[dict[str, Any]] | None = None,
    space_code: str | None = None,
    bk_tenant_id: str = "default",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """
    预览动态分组成员列表

    根据条件预览动态分组将包含哪些成员，支持分页。
    可以通过动态分组ID查询，也可以直接传入条件列表预览。

    注意：
        search_condition 相关的过滤逻辑（包括 cw-agent_status 特殊处理）
        已迁移至 View 层处理，base 层只提供基础的数据查询功能。

    Args:
        dynamic_group_id: 动态分组ID，如果提供则使用该分组的条件
        object_model_code: 对象模型代码，如果提供dynamic_group_id则可以省略
        condition_list: 分组条件列表，如果提供dynamic_group_id则可以省略
        space_code: 空间代码，如果提供dynamic_group_id则可以省略
        bk_tenant_id: 租户ID
        page: 页码，从1开始
        page_size: 每页数量，传入 -1 表示获取全部数据

    Returns:
        dict: 包含以下键的字典
            - items: 成员列表
            - count: 总数量
            - page: 当前页码
            - page_size: 每页数量

    Raises:
        ErrorCodes.DYNAMIC_GROUP_NOT_FOUND: 当动态分组不存在时
        ErrorCodes.DYNAMIC_GROUP_VALIDATE_ERROR: 当参数不足或无效时

    Example:
        >>> # 通过动态分组ID预览
        >>> preview_dynamic_group_members(dynamic_group_id=1, page=1, page_size=10)
        {'items': [...], 'count': 100, 'page': 1, 'page_size': 10}

        >>> # 直接使用条件预览
        >>> preview_dynamic_group_members(
        ...     object_model_code='cw-Host',
        ...     condition_list=[{'field': 'bk_host_innerip', 'value': '10.', 'operator': 'contains'}],
        ...     space_code='bkcc__0',
        ...     page=1,
        ...     page_size=20
        ... )
    """
    # 如果提供了动态分组ID，从数据库获取条件
    if dynamic_group_id is not None:
        try:
            group = DynamicGroupORM.objects.get(dynamic_group_id=dynamic_group_id)
            object_model_code = group.object_model_code
            condition_list = group.condition_list
            space_code = group.space_code
            bk_tenant_id = group.bk_tenant_id
        except DynamicGroupORM.DoesNotExist:
            raise ErrorCodes.DYNAMIC_GROUP_NOT_FOUND.set_message(f"动态分组不存在: dynamic_group_id={dynamic_group_id}")

    # 验证必要参数
    if not object_model_code:
        raise ErrorCodes.DYNAMIC_GROUP_VALIDATE_ERROR.set_message("必须提供 object_model_code 或 dynamic_group_id")

    if condition_list is None:
        raise ErrorCodes.DYNAMIC_GROUP_VALIDATE_ERROR.set_message("必须提供 condition_list 或 dynamic_group_id")

    # 解析业务ID
    bk_biz_id = 0
    if space_code:
        try:
            bk_biz_id = int(space_code.split("__")[1])
        except (IndexError, ValueError):
            pass

    # 构建 CMDB API 分页参数
    start = (page - 1) * page_size
    cmdb_page: cmdb.PageParams = {"start": start, "limit": page_size}

    # 统一交给 fetcher 将前端条件转换为 CMDBInstance DSL，这里只做结构归一化
    cmdb_condition = ConditionConverter.build_cmdb_condition(condition_list)

    # 获取对象模型信息，提取 display_fields
    display_fields: list[str] | None = None
    try:
        obj_models = list_object_models(
            object_model_codes=[object_model_code],
            raise_not_found=True,
        )
        obj_model = obj_models[0]
        display_fields = [
            f["bk_property_id"] for f in obj_model.display_fields if f["bk_property_id"] != "bk_inst_display_name"
        ]
    except Exception as e:
        logger.warning(f"获取对象模型失败: {object_model_code}, 将不进行字段过滤: {e}")

    # 使用策略模式获取对应的成员获取器
    try:
        fetcher = get_member_fetcher(object_model_code)
        count, data = fetcher.fetch(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            condition=cmdb_condition,
            page=cmdb_page,
            fields=display_fields,
        )

        # 格式化成员数据（翻译枚举值、生成展示名称）
        data = MemberFormatter.format_members(
            members=data,
            object_model_code=object_model_code,
            bk_tenant_id=bk_tenant_id,
        )

        return {
            "items": data,
            "count": count,
            "page": page,
            "page_size": page_size,
            "object_model_code": object_model_code,
        }

    except Exception as e:
        # 记录错误但不中断，返回空结果
        logger.exception("调用CMDB API失败")
        return {
            "items": [],
            "count": 0,
            "page": page,
            "page_size": page_size,
            "object_model_code": object_model_code,
            "error": str(e),
            "message": f"调用CMDB API失败: {str(e)}",
        }


def list_dynamic_group_members(
    dynamic_group: DynamicGroup,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[dict[str, Any]]]:
    """
    查询动态分组成员列表（增强版）

    提供完整的成员查询功能，包括：
    - 条件转换（操作符映射、字段类型转换）
    - 分页支持

    注意：
        search_condition 相关的过滤逻辑（包括 cw-agent_status 特殊处理）
        已迁移至 View 层处理，base 层只提供基础的数据查询功能。

    Args:
        dynamic_group: 动态分组实体
        page: 页码，从1开始
        page_size: 每页数量

    Returns:
        tuple[int, list[dict]]: (总数, 成员列表)

    Example:
        >>> group = get_dynamic_group(1)
        >>> count, members = list_dynamic_group_members(group, page=1, page_size=20)
        >>> print(f"共 {count} 个成员，当前页 {len(members)} 个")
    """
    # 1. 解析业务ID
    try:
        bk_biz_id = dynamic_group.get_bk_biz_id()
    except (ValueError, AttributeError):
        bk_biz_id = 0

    # 2. 统一交给 fetcher 将前端条件转换为 CMDBInstance DSL，这里只做结构归一化
    cmdb_condition = ConditionConverter.build_cmdb_condition(dynamic_group.condition_list)

    # 3. 构建分页参数
    start = (page - 1) * page_size
    cmdb_page: cmdb.PageParams = {"start": start, "limit": page_size}

    # 4. 获取对应的成员获取器并查询
    try:
        fetcher = get_member_fetcher(dynamic_group.object_model_code)
        count, members = fetcher.fetch(
            bk_tenant_id=dynamic_group.bk_tenant_id,
            bk_biz_id=bk_biz_id,
            condition=cmdb_condition,
            page=cmdb_page,
        )
    except Exception:
        logger.exception(f"查询动态分组成员失败, dynamic_group_id={dynamic_group.dynamic_group_id}")
        return 0, []

    return count, members


def get_dynamic_group_members(
    dynamic_group_id: int,
    raise_not_found: bool = True,
) -> list[dict[str, Any]]:
    """
    获取动态分组的成员列表

    Args:
        dynamic_group_id: 动态分组ID
        raise_not_found: 当查询结果为空时是否抛出异常

    Returns:
        list[dict]: 成员列表

    Raises:
        ErrorCodes.DYNAMIC_GROUP_NOT_FOUND: 当动态分组不存在时
    """
    # 验证动态分组是否存在
    group = get_dynamic_group(dynamic_group_id, raise_not_found=raise_not_found)
    if not group:
        return []

    # 查询成员列表
    members = DynamicGroupMemberORM.objects.filter(dynamic_group_id=dynamic_group_id).values_list("member", flat=True)
    return list(members)


def fetch_dynamic_group_inst_map(dynamic_group_ids: list[int] | None = None) -> dict[str, list[int]]:
    """
    基于动态分组ID列表，返回对象模型与实例ID的映射关系

    Args:
        dynamic_group_ids: 动态分组ID列表，如果为None则查询所有

    Returns:
        dict: 对象模型代码到实例ID列表的映射，格式为:
            {
                "cw-Host": [1, 2, 3],
                "cw-Redis": [1, 2, 3]
            }

    Example:
        >>> fetch_dynamic_group_inst_map([1, 2, 3])
        {'cw-Host': [101, 102], 'cw-Redis': [201, 202]}
    """
    # 查询动态分组及其对象模型代码
    qs = DynamicGroupORM.objects.all()
    if dynamic_group_ids is not None:
        qs = qs.filter(dynamic_group_id__in=dynamic_group_ids)

    dynamic_groups_id_map_code = dict(qs.values_list("dynamic_group_id", "object_model_code"))

    # 查询成员
    member_qs = DynamicGroupMemberORM.objects.filter(dynamic_group_id__in=list(dynamic_groups_id_map_code.keys()))

    # 构建对象模型代码到实例ID的映射
    object_code_map_inst: dict[str, list[int]] = {}
    for member_obj in member_qs:
        object_model_code = dynamic_groups_id_map_code.get(member_obj.dynamic_group_id)
        if object_model_code:
            inst_id = member_obj.member.get("bk_inst_id")
            if inst_id:
                object_code_map_inst.setdefault(object_model_code, []).append(inst_id)

    # 去重
    for object_model_code in object_code_map_inst:
        object_code_map_inst[object_model_code] = list(set(object_code_map_inst[object_model_code]))

    return object_code_map_inst
