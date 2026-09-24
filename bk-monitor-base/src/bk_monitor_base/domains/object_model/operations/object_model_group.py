"""
对象模型分组操作模块

提供对象模型分组的增删改查、权限控制和内置分组树管理功能。
支持多语言、层级结构和数据验证。
"""

from collections import defaultdict
from typing import Any

from django.conf import settings
from django.db.models import Q
from django.utils.translation import gettext as _

from bk_monitor_base.domains.object_model.constants import (
    NOT_CREATE_GROUP_CODE_LIST,
    NOT_DELETE_OBJECT_MODEL_GROUP_CODE_LIST,
    NOT_UPDATE_OBJECT_MODEL_GROUP_CODE_LIST,
    RELATED_OBJECT_MODEL_GROUP,
)
from bk_monitor_base.domains.object_model.define import ObjectModelGroup
from bk_monitor_base.domains.object_model.errors import ErrorCodes
from bk_monitor_base.domains.object_model.models import ObjectModelGroupORM, ObjectModelORM
from bk_monitor_base.domains.object_model.operations.common import clean_model_i18n_db_field
from bk_monitor_base.infras.i18n.language import get_language


def list_object_model_groups(
    object_model_group_ids: list[int] | None = None,
    object_model_group_codes: list[str] | None = None,
    parent_object_model_group_ids: list[int] | None = None,
    name_contains: str | None = None,
    is_default: bool | None = None,
    is_child: bool | None = None,
    bk_tenant_ids: list[str] | None = None,
    raise_not_found: bool = False,
    model_cls: type[ObjectModelGroupORM] = ObjectModelGroupORM,
) -> list[ObjectModelGroup]:
    """
    根据条件查询对象模型分组列表

    支持多种过滤条件的组合查询，返回符合条件的对象模型分组列表。
    查询结果会自动填充权限相关字段（can_delete、can_create、can_update、related_obj）。

    Args:
        object_model_group_ids: 对象模型分组ID列表，用于精确匹配分组
        object_model_group_codes: 对象模型分组代码列表，用于精确匹配分组
        parent_object_model_group_ids: 父分组ID列表，用于查询指定父分组下的子分组
        name_contains: 分组名称包含的字符串，用于模糊查询
        is_default: 是否为内置分组的过滤条件
        is_child: 是否为子分组的过滤条件，True查询子分组，False查询一级分组
        bk_tenant_ids: 租户ID列表，用于过滤指定租户下的分组
        raise_not_found: 当查询结果为空时是否抛出异常
        model_cls: orm 模型，用于migration中指定model

    Returns:
        list[ObjectModelGroup]: 符合条件的对象模型分组列表，已填充权限相关字段

    Raises:
        ErrorCodes.OBJECT_MODEL_GROUP_NOT_FOUND: 当raise_not_found为True且查询结果为空时

    Examples:
        # 查询所有分组
        groups = list_object_model_groups()

        # 查询指定ID的分组
        groups = list_object_model_groups(object_model_group_ids=[1, 2, 3])

        # 查询一级分组
        groups = list_object_model_groups(is_child=False)

        # 模糊查询分组名
        groups = list_object_model_groups(name_contains="云平台")
    """
    qs = model_cls.objects.all()

    # 过滤分组id
    if object_model_group_ids is not None:
        qs = qs.filter(object_model_group_id__in=object_model_group_ids)

    # 过滤分组code
    if object_model_group_codes is not None:
        qs = qs.filter(object_model_group_code__in=object_model_group_codes)

    # 过滤父分组id
    if parent_object_model_group_ids is not None:
        qs = qs.filter(parent_object_model_group_id__in=parent_object_model_group_ids)

    # 过滤是否内置分组
    if is_default is not None:
        qs = qs.filter(is_default=is_default)

    if bk_tenant_ids is not None:
        qs = qs.filter(bk_tenant_id__in=bk_tenant_ids)

    # 过滤是否子分组
    if is_child is not None:
        if is_child:
            qs = qs.filter(parent_object_model_group__isnull=False)
        else:
            qs = qs.filter(parent_object_model_group__isnull=True)

    # 分组名模糊查询
    if name_contains is not None:
        qs = qs.filter(object_model_group_name__contains=name_contains)

    groups = [g.to_entity() for g in qs]
    if raise_not_found and not groups:
        raise ErrorCodes.OBJECT_MODEL_GROUP_NOT_FOUND
    _enrich_extra_fields(groups)
    return groups


def create_object_model_group(group: ObjectModelGroup) -> ObjectModelGroup:
    """
    创建对象模型分组

    支持多语言名称，会进行唯一性验证和层级结构验证。
    分组只能创建为一级分组或二级分组，不支持更深层级。

    Args:
        group: 要创建的对象模型分组实体，包含分组基本信息和多语言名称

    Returns:
        ObjectModelGroup: 创建成功的对象模型分组实体，已填充权限相关字段

    Raises:
        ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR: 当出现以下情况时
            - 对象模型分组名称必须包含默认语言名称
            - 对象模型分组code已存在
            - 对象模型分组名称已存在
        ErrorCodes.OBJECT_MODEL_GROUP_NOT_FOUND: 当父级分组不存在或父级分组只能是一级分组时

    Examples:
        # 创建一级分组
        group = ObjectModelGroup(
            object_model_group_code="custom_group",
            object_model_group_name="自定义分组",
            object_model_group_name_i18n={"zh-cn": "自定义分组", "en": "Custom Group"}
        )
        created_group = create_object_model_group(group)

        # 创建二级分组
        child_group = ObjectModelGroup(
            object_model_group_code="child_group",
            object_model_group_name="子分组",
            parent_object_model_group_id=1,
            object_model_group_name_i18n={"zh-cn": "子分组", "en": "Child Group"}
        )
        created_child = create_object_model_group(child_group)
    """
    if group.parent_object_model_group_id:
        try:
            p_group = ObjectModelGroupORM.objects.get(object_model_group_id=group.parent_object_model_group_id)
        except ObjectModelGroupORM.DoesNotExist:
            raise ErrorCodes.OBJECT_MODEL_GROUP_NOT_FOUND.set_message(_("父级分组不存在")).set_data(
                {"parent_object_model_group_id", group.parent_object_model_group_id}
            )
        if p_group.level != 1:
            raise ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR.set_message(_("父级分组只能是一级分组"))

    try:
        object_model_group_name_db_i18n = clean_model_i18n_db_field(group, "object_model_group_name")
    except AttributeError:
        raise ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR.set_message(_("对象模型分组名称必须包含默认语言名称"))
    qs = Q(object_model_group_code=group.object_model_group_code)
    for k, v in object_model_group_name_db_i18n.items():
        qs |= Q(**{k: v})
    qs &= Q(parent_object_model_group_id=group.parent_object_model_group_id)
    exist_group = ObjectModelGroupORM.objects.filter(qs).first()
    if exist_group:
        if exist_group.object_model_group_code == group.object_model_group_code:
            raise ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR.set_message(
                f"对象模型分组code已存在: {group.object_model_group_code}"
            )
        for k, v in object_model_group_name_db_i18n.items():
            if v and getattr(exist_group, k) == v:
                raise ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR.set_message(_("对象模型分组名称已存在")).set_data(
                    {k: v}
                )

    group_obj: ObjectModelGroupORM = ObjectModelGroupORM(
        **group.model_dump(
            include={
                "object_model_group_id",
                "object_model_group_code",
                "parent_object_model_group_id",
                "is_default",
                "index",
                "bk_tenant_id",
                "created_by",
                "created_at",
                "updated_at",
                "updated_by",
            }
        ),
        **object_model_group_name_db_i18n,
    )
    group_obj.save()
    entity = group_obj.to_entity()
    _enrich_extra_fields([entity])
    return entity


def update_object_model_group(group: ObjectModelGroup) -> ObjectModelGroup:
    """
    更新对象模型分组

    支持更新分组的基本信息和多语言名称，会进行权限验证、唯一性验证和层级结构验证。
    内置分组有更新限制，一级分组和二级分组之间的转换有业务规则限制。

    Args:
        group: 要更新的对象模型分组实体，包含分组ID和更新的信息

    Returns:
        ObjectModelGroup: 更新成功的对象模型分组实体，已填充权限相关字段

    Raises:
        ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR: 当出现以下情况时
            - 不允许修改特定的内置对象模型分组
            - 对象模型分组code已存在
            - 对象模型分组名称必须包含默认语言名称
            - 已存在相同的对象分组名称
            - 父级分组只能是一级分组
            - 已有子分组，不可修改为二级分组
            - 已有对象模型，不可修改为一级分组

    Examples:
        # 更新分组名称
        group = ObjectModelGroup(
            object_model_group_id=1,
            object_model_group_code="updated_group",
            object_model_group_name="更新的分组",
            object_model_group_name_i18n={"zh-cn": "更新的分组", "en": "Updated Group"}
        )
        updated_group = update_object_model_group(group)

        # 将一级分组改为二级分组
        group.parent_object_model_group_id = 2
        updated_group = update_object_model_group(group)
    """
    if group.object_model_group_code in NOT_UPDATE_OBJECT_MODEL_GROUP_CODE_LIST:
        raise ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR.set_message(_("不允许修改的对象模型分组"))
    qs = ObjectModelGroupORM.objects.exclude(object_model_group_id=group.object_model_group_id)
    # 分组code全局唯一
    if qs.filter(object_model_group_code=group.object_model_group_code).exists():
        raise ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR.set_message(_("对象模型分组code已存在"))

    try:
        object_model_group_name_db_i18n = clean_model_i18n_db_field(group, "object_model_group_name")
    except AttributeError:
        raise ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR.set_message(_("对象模型分组名称必须包含默认语言名称"))
    query = Q()
    for k, v in object_model_group_name_db_i18n.items():
        query |= Q(**{k: v})
    query = query & Q(parent_object_model_group_id=group.parent_object_model_group_id)
    exist_group = qs.filter(query).first()
    if exist_group:
        for k, v in object_model_group_name_db_i18n.items():
            if getattr(exist_group, k) == v:
                raise ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR.set_message(_("已存在相同的对象分组名称")).set_data(
                    {k: v}
                )

    old_group = ObjectModelGroupORM.objects.get(object_model_group_id=group.object_model_group_id)
    group.is_default = old_group.is_default

    if group.parent_object_model_group_id:
        # 新分组为二级分组
        p_group: ObjectModelGroupORM = ObjectModelGroupORM.objects.get(
            object_model_group_id=group.parent_object_model_group_id
        )
        if p_group.parent_object_model_group:
            raise ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR.set_message(_("父级分组只能是一级分组"))

        # 一级分组改为二级分组
        exist_child = ObjectModelGroupORM.objects.filter(
            parent_object_model_group_id=old_group.object_model_group_id
        ).exists()
        if not old_group.parent_object_model_group and exist_child:
            raise ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR.set_message(_("已有子分组，不可修改为二级分组"))
    else:
        # 新分组为一级分组
        # 二级分组改为一级分组时
        exist_object_model = ObjectModelORM.objects.filter(
            object_model_group_id=old_group.object_model_group_id
        ).exists()
        if old_group.parent_object_model_group and exist_object_model:
            raise ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR.set_message(_("已有对象模型，不可修改为一级分组"))
    update_fields = {
        "object_model_group_id",
        "object_model_group_code",
        "parent_object_model_group_id",
        "is_default",
        "updated_by",
        "updated_at",
    }
    for field in update_fields:
        setattr(old_group, field, getattr(group, field))
    for k, v in object_model_group_name_db_i18n.items():
        if v:
            setattr(old_group, k, v)
    old_group.save()
    entity = old_group.to_entity()
    _enrich_extra_fields([entity])
    return entity


def delete_object_model_group(object_model_group_id: int) -> ObjectModelGroup:
    """
    删除对象模型分组

    删除指定的对象模型分组，会进行权限验证和关联关系检查。
    内置分组和已关联对象模型的分组不允许删除。

    Args:
        object_model_group_id: 要删除的对象模型分组ID

    Returns:
        ObjectModelGroup: 被删除的对象模型分组实体

    Raises:
        ErrorCodes.OBJECT_MODEL_GROUP_NOT_FOUND: 当对象模型分组不存在时
        ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR: 当出现以下情况时
            - 该对象模型分组不允许删除（内置分组）
            - 该对象模型分组或其子分组已关联对象模型，无法删除

    Examples:
        # 删除分组
        deleted_group = delete_object_model_group(object_model_group_id=1)

        # 删除一级分组（会同时检查子分组是否关联对象模型）
        deleted_group = delete_object_model_group(object_model_group_id=2)
    """
    try:
        group = ObjectModelGroupORM.objects.get(object_model_group_id=object_model_group_id)
    except ObjectModelGroupORM.DoesNotExist:
        raise ErrorCodes.OBJECT_MODEL_GROUP_NOT_FOUND
    if group.object_model_group_code in NOT_DELETE_OBJECT_MODEL_GROUP_CODE_LIST:
        raise ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR.set_message(_("该对象模型分组不允许删除"))
    object_model_group_ids: list[int] = list(
        ObjectModelGroupORM.objects.filter(parent_object_model_group=group).values_list(
            "object_model_group_id", flat=True
        )
    )
    object_model_group_ids.append(object_model_group_id)
    if ObjectModelORM.objects.filter(object_model_group_id__in=object_model_group_ids).exists():
        raise ErrorCodes.OBJECT_MODEL_GROUP_VALIDATE_ERROR.set_message(
            _("该对象模型分组或其子分组已关联对象模型，无法删除")
        )
    group.delete()
    return group.to_entity()


def _enrich_extra_fields(entity_list: list[ObjectModelGroup]) -> list[ObjectModelGroup]:
    """
    为对象模型分组实体列表填充权限相关的扩展字段

    计算并设置每个分组的权限相关字段，包括是否可删除、可创建、可更新和是否关联对象等。
    这些字段基于分组的关联关系、内置规则和业务逻辑计算得出。

    Args:
        entity_list: 对象模型分组实体列表

    Returns:
        list[ObjectModelGroup]: 已填充权限字段的对象模型分组列表

    权限字段说明:
        - related_obj: 是否关联了对象模型或处于特定的内置分组中
        - can_delete: 是否可删除，当满足以下条件时为False：
            * 关联了对象模型
            * 有子分组
            * 是内置不可删除的分组
        - can_create: 是否可在此分组下创建子分组或对象模型，内置特定分组为False
        - can_update: 是否可更新，内置不可更新的分组为False

    Examples:
        # 内部使用，由其他函数调用
        groups = [group1, group2, group3]
        enriched_groups = _enrich_extra_fields(groups)
        # 每个group现在都有了can_delete、can_create、can_update、related_obj字段
    """

    all_group_ids: list[int] = []
    first_group_ids: list[int] = []
    for entity in entity_list:
        if not entity.object_model_group_id:
            continue
        all_group_ids.append(entity.object_model_group_id)
        if not entity.parent_object_model_group_id:
            first_group_ids.append(entity.object_model_group_id)

    group_relate_map: dict[int | None, list[int]] = defaultdict(list)
    related_second_groups = ObjectModelGroupORM.objects.filter(parent_object_model_group_id__in=first_group_ids).values(
        "parent_object_model_group_id", "object_model_group_id"
    )
    all_second_group_ids: list[int] = []
    for g in related_second_groups:
        group_relate_map[g["parent_object_model_group_id"]].append(g["object_model_group_id"])
        all_second_group_ids.append(g["object_model_group_id"])

    has_model_group_ids = set(
        ObjectModelORM.objects.filter(object_model_group_id__in=all_group_ids + all_second_group_ids).values_list(
            "object_model_group_id", flat=True
        )
    )

    for entity in entity_list:
        related_ids: set[int | None] = set(group_relate_map[entity.object_model_group_id])
        related_ids.add(entity.object_model_group_id)
        related_obj = entity.object_model_group_code in RELATED_OBJECT_MODEL_GROUP
        entity.related_obj = True if related_ids & has_model_group_ids or related_obj else False

        has_child = group_relate_map.get(entity.object_model_group_id)
        not_delete = entity.object_model_group_code in NOT_DELETE_OBJECT_MODEL_GROUP_CODE_LIST
        # 关联了对象或有子分组或是内置不可删除的分组，不可删除
        entity.can_delete = False if any([entity.related_obj, has_child, not_delete]) else True

        # 内置不能创建二级分组或对象模型的分组
        entity.can_create = False if entity.object_model_group_code in NOT_CREATE_GROUP_CODE_LIST else True

        # 内置不可更新的分组
        entity.can_update = False if entity.object_model_group_code in NOT_UPDATE_OBJECT_MODEL_GROUP_CODE_LIST else True

    return entity_list


def create_builtin_group_tree(init_data: dict[str, Any]):
    """
    创建内置对象模型分组树
    """

    def _get_or_create_group(group_info: dict[str, Any], parent_id: int | None = None) -> ObjectModelGroupORM:
        group_code = group_info["object_model_group_code"]
        object_model_group_name_db_i18n = {}
        for lang_tuple in settings.LANGUAGES:
            language = get_language(code=lang_tuple[0])
            field_name = language.format_db_field_key("object_model_group_name")
            object_model_group_name_db_i18n[field_name] = group_info.get(field_name, None)
        group, _ = ObjectModelGroupORM.objects.get_or_create(
            object_model_group_code=group_code,
            defaults={
                "object_model_group_code": group_code,
                "object_model_group_name": group_info["object_model_group_name"],
                "parent_object_model_group_id": parent_id,
                "is_default": True,
                "created_by": "system",
                "updated_by": "system",
                **object_model_group_name_db_i18n,
            },
        )
        return group

    def _get_or_create_model(model_info: dict[str, Any], group_id: int):
        object_model_code = model_info["object_model_code"]
        object_model_name_db_i18n = {}
        for lang_tuple in settings.LANGUAGES:
            language = get_language(code=lang_tuple[0])
            field_name = language.format_db_field_key("object_model_name")
            object_model_name_db_i18n[field_name] = model_info.get(field_name, None)
        ObjectModelORM.objects.get_or_create(
            object_model_code=object_model_code,
            defaults={
                "object_model_code": object_model_code,
                "object_model_name": model_info["object_model_name"],
                "object_model_group_id": group_id,
                "is_default": True,
                "datasource": model_info["datasource"],
                "bk_cmdb_obj_id": model_info.get("bk_cmdb_obj_id", ""),
                "display_fields": model_info.get("display_fields", []),
                "inst_display_name": model_info.get("inst_display_name", ""),
                "host_related_field": model_info.get("host_related_field", ""),
                "operator_fields": model_info.get("operator_fields", []),
                "topo_related_field": model_info.get("topo_related_field", ""),
                "port_field": model_info.get("port_field", ""),
                "custom_model_field": model_info.get("custom_model_field", ""),
                "model_related_field": model_info.get("model_related_field", ""),
                "created_by": "系统",
                "updated_by": "系统",
                **object_model_name_db_i18n,
            },
        )

    # 一级分组
    first_group = _get_or_create_group(init_data)

    for second in init_data.get("children", []):
        if second.get("object_model_group_code"):
            # 二级分组
            second_group = _get_or_create_group(second, first_group.object_model_group_id)
            for object_model in second.get("children", []):
                # 对象模型
                _get_or_create_model(object_model, second_group.object_model_group_id)
        else:
            # 对象模型
            _get_or_create_model(second, first_group.object_model_group_id)
