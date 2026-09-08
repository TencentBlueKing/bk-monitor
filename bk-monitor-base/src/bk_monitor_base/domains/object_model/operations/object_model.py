"""
对象模型操作模块

提供对象模型的增删改查和验证功能。
"""

from collections import defaultdict

from django.db.models import Q
from django.utils.translation import gettext as _

from bk_monitor_base.domains.object_model.constants import (
    ALLOW_CREATE_CHILD_OBJECT_MODEL_GROUP,
    NOT_PLUGIN_MANAGE_OBJ_CODE_LIST,
    NOT_UPDATE_OBJECT_MODEL_CODE_LIST,
    BuiltinObjectModelGroupCode,
)
from bk_monitor_base.domains.object_model.define import DatasourceType, ObjectModel
from bk_monitor_base.domains.object_model.errors import ErrorCodes
from bk_monitor_base.domains.object_model.models import ObjectModelGroupORM, ObjectModelORM, ObjectModelUsageRecordORM
from bk_monitor_base.domains.object_model.operations.common import clean_model_i18n_db_field


def list_object_models(
    object_model_ids: list[int] | None = None,
    object_model_codes: list[str] | None = None,
    object_model_group_ids: list[int] | None = None,
    bk_cmdb_obj_ids: list[str] | None = None,
    name_contains: str | None = None,
    datasources: list[DatasourceType] | None = None,
    bk_tenant_ids: list[str] | None = None,
    limit: int | None = None,
    offset: int | None = None,
    raise_not_found: bool = False,
    model_cls: type[ObjectModelORM] = ObjectModelORM,
) -> list[ObjectModel]:
    """
    根据条件查询对象模型列表

    支持多种过滤条件的组合查询和分页，返回符合条件的对象模型列表。
    查询结果会自动填充字段（can_update、can_delete、plugin_manage）。

    Args:
        object_model_ids: 对象模型ID列表，用于精确匹配模型
        object_model_codes: 对象模型代码列表，用于精确匹配模型
        object_model_group_ids: 对象模型分组ID列表，用于查询指定分组下的模型
        bk_cmdb_obj_ids: CMDB对象ID列表，用于匹配CMDB数据源的模型
        name_contains: 模型名称包含的字符串，用于模糊查询
        datasources: 数据源类型列表，用于过滤特定数据源的模型
        bk_tenant_ids: 租户ID列表，用于多租户环境下的查询
        limit: 限制返回结果数量，用于分页
        offset: 偏移量，用于分页
        raise_not_found: 当查询结果为空时是否抛出异常
        model_cls: orm 模型，用于migration中指定model

    Returns:
        list[ObjectModel]: 符合条件的对象模型列表

    Raises:
        ErrorCodes.OBJECT_MODEL_NOT_FOUND: 当raise_not_found为True且查询结果为空时

    Examples:
        # 查询所有对象模型
        models = list_object_models()

        # 查询指定分组下的模型
        models = list_object_models(object_model_group_ids=[1, 2])

        # 查询CMDB数据源的模型
        models = list_object_models(datasources=[DatasourceType.CMDB])

        # 分页查询
        models = list_object_models(limit=10, offset=20)

        # 模糊查询模型名称
        models = list_object_models(name_contains="主机")
    """
    qs = model_cls.objects.all()

    # 过滤模型id
    if object_model_ids is not None:
        qs = qs.filter(object_model_id__in=object_model_ids)

    # 过滤模型code
    if object_model_codes is not None:
        qs = qs.filter(object_model_code__in=object_model_codes)

    # 过滤分组id
    if object_model_group_ids is not None:
        qs = qs.filter(object_model_group_id__in=object_model_group_ids)

    # 过滤CMDB对象ID
    if bk_cmdb_obj_ids is not None:
        qs = qs.filter(bk_cmdb_obj_id__in=bk_cmdb_obj_ids)

    # 过滤模型类型
    if datasources is not None:
        qs = qs.filter(datasource__in=datasources)

    # 名称模糊查询
    if name_contains is not None:
        qs = qs.filter(object_model_name__contains=name_contains)

    # 租户id查询
    if bk_tenant_ids is not None:
        qs = qs.filter(bk_tenant_id__in=bk_tenant_ids)

    # 分页
    if limit is not None or offset is not None:
        offset = offset or 0
        if limit is not None:
            limit = offset + limit
        qs = qs[offset:limit]

    object_models = [obj.to_entity() for obj in qs]
    if raise_not_found and not object_models:
        raise ErrorCodes.OBJECT_MODEL_NOT_FOUND

    _enrich_extra_fields(object_models)
    return object_models


def _validate_simple_fields(entity: ObjectModel):
    """
    对象模型简单字段校验
    """
    try:
        group: ObjectModelGroupORM = ObjectModelGroupORM.objects.get(object_model_group_id=entity.object_model_group_id)
    except ObjectModelGroupORM.DoesNotExist:
        raise ErrorCodes.OBJECT_MODEL_GROUP_NOT_FOUND.set_data({"object_model_group_id": entity.object_model_group_id})
    if not entity.object_model_id and not entity.is_default:
        # 用户创建时只能在二级分组下创建对象模型, 除了主机监控, 其他_鲸眼
        if group.level != 2 and group.object_model_group_code not in ALLOW_CREATE_CHILD_OBJECT_MODEL_GROUP:
            raise ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR.set_message(_("对象模型分组必须选择二级分组"))

    if entity.datasource == DatasourceType.CMDB:
        if not entity.bk_cmdb_obj_id:
            raise ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR.set_message(_("bk_cmdb_obj_id不能为空"))
        if not entity.inst_display_name:
            raise ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR.set_message(_("inst_display_name不能为空"))
        if not 0 < len(entity.display_fields) <= 5:
            raise ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR.set_message(_("display_fields不能为空或超过5个字段"))


def create_object_model(entity: ObjectModel) -> ObjectModel:
    """
    创建对象模型

    支持多语言名称，会进行分组权限验证、唯一性验证和数据完整性检查。

    Args:
        entity: 对象模型实体，包含模型的完整信息和多语言名称
            - 如果object_model_id存在则为更新操作
            - 如果object_model_id为None则为创建操作

    Returns:
        ObjectModel: 创建成功的对象模型实体，已填充权限相关字段

    Raises:
        ErrorCodes.OBJECT_MODEL_GROUP_NOT_FOUND: 当指定的对象模型分组不存在时
        ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR: 当出现以下情况时
            - 用户创建的对象模型分组必须选择二级分组
            - 对象模型名称必须包含默认语言名称
            - 对象模型名称已存在
            - CMDB对象ID已存在
            - 对象模型code已存在

    业务规则:
        - 用户创建的模型只能在二级分组下创建，除了特定的允许分组
        - CMDB数据源的模型需要唯一的bk_cmdb_obj_id
        - 多语言名称在同一分组内必须唯一

    Examples:
        # 创建新的对象模型
        model = ObjectModel(
            object_model_code="custom_server",
            object_model_name="自定义服务器",
            object_model_group_id=5,
            datasource=DatasourceType.CUSTOM,
            object_model_name_i18n={"zh-cn": "自定义服务器", "en": "Custom Server"}
        )
        created_model = create_object_model(model)
    """
    update_fields = {
        "object_model_id",
        "object_model_code",
        "object_model_group_id",
        "datasource",
        "bk_tenant_id",
        "is_default",
        "bk_cmdb_obj_id",
        "display_fields",
        "inst_display_name",
        "host_related_field",
        "operator_fields",
        "topo_related_field",
        "port_field",
        "custom_model_field",
        "model_related_field",
        "related_model_type",
        "related_model_code",
        "ar_dimensionality",
        "attribute_config",
        "updated_at",
        "updated_by",
        "created_at",
        "created_by",
    }
    _validate_simple_fields(entity)
    try:
        object_model_name_db_i18n = clean_model_i18n_db_field(entity, "object_model_name")
    except AttributeError:
        raise ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR.set_message(_("对象模型名称必须包含默认语言名称"))
    qs = ObjectModelORM.objects.all()
    # 校验唯一性：
    # object_model_code 全局唯一
    if qs.filter(object_model_code=entity.object_model_code).exists():
        raise ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR.set_message(_("对象模型code已存在"))

    # datasource=CMDB，bk_cmdb_obj_id唯一
    if entity.datasource == DatasourceType.CMDB:
        if qs.filter(bk_cmdb_obj_id=entity.bk_cmdb_obj_id, datasource=DatasourceType.CMDB).exists():
            raise ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR.set_message(_("CMDB对象ID已存在"))

    # object_model_name_xx 国际化名称唯一
    query = Q()
    for k, v in object_model_name_db_i18n.items():
        query |= Q(**{k: v})
    exist_model = ObjectModelORM.objects.filter(query).first()
    if exist_model:
        for k, v in object_model_name_db_i18n.items():
            if getattr(exist_model, k) == v:
                raise ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR.set_message(_("对象模型名称已存在")).set_data({k: v})
    obj = ObjectModelORM(**entity.model_dump(include=update_fields), **object_model_name_db_i18n)
    obj.save()
    entity = obj.to_entity()
    _enrich_extra_fields([entity])
    return entity


def update_object_model(entity: ObjectModel) -> ObjectModel:
    """
    更新对象模型

    支持多语言名称，会进行分组权限验证、唯一性验证和数据完整性检查。

    Args:
        entity: 对象模型实体，包含模型的完整信息和多语言名称

    Returns:
        ObjectModel: 更新成功的对象模型实体，已填充权限相关字段

    Raises:
        ErrorCodes.OBJECT_MODEL_GROUP_NOT_FOUND: 当指定的对象模型分组不存在时
        ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR: 当出现以下情况时
            - 对象模型名称必须包含默认语言名称
            - 对象模型code不允许更新
            - 对象模型名称已存在
            - CMDB对象ID已存在
        ErrorCodes.OBJECT_MODEL_NOT_FOUND: 当更新时指定的对象模型不存在时

    业务规则:
        - 对象模型code创建后不可修改
        - CMDB数据源的模型需要唯一的bk_cmdb_obj_id
        - 多语言名称在同一分组内必须唯一

    Examples:
        # 更新现有对象模型
        model.object_model_id = 1
        model.object_model_name = "更新的服务器"
        updated_model = update_object_model(model)
    """
    update_fields = {
        "object_model_id",
        "object_model_code",
        "object_model_group_id",
        "datasource",
        "bk_tenant_id",
        "is_default",
        "bk_cmdb_obj_id",
        "display_fields",
        "inst_display_name",
        "host_related_field",
        "operator_fields",
        "topo_related_field",
        "port_field",
        "custom_model_field",
        "model_related_field",
        "related_model_type",
        "related_model_code",
        "ar_dimensionality",
        "attribute_config",
        "updated_at",
        "updated_by",
    }
    _validate_simple_fields(entity)
    try:
        object_model_name_db_i18n = clean_model_i18n_db_field(entity, "object_model_name")
    except AttributeError:
        raise ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR.set_message(_("对象模型名称必须包含默认语言名称"))
    try:
        obj = ObjectModelORM.objects.get(object_model_id=entity.object_model_id)
    except ObjectModelORM.DoesNotExist:
        raise ErrorCodes.OBJECT_MODEL_NOT_FOUND.set_data({"object_model_id": entity.object_model_id})
    if obj.object_model_code != entity.object_model_code:
        raise ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR.set_message(_("对象模型code不允许更新"))

    qs = ObjectModelORM.objects.exclude(object_model_id=obj.object_model_id)
    if entity.datasource == DatasourceType.CMDB:
        # datasource=CMDB，bk_cmdb_obj_id唯一
        if qs.filter(bk_cmdb_obj_id=entity.bk_cmdb_obj_id, datasource=DatasourceType.CMDB).exists():
            raise ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR.set_message(_("CMDB对象ID已存在"))

    # object_model_name_xx 国际化名称唯一
    query = Q()
    for k, v in object_model_name_db_i18n.items():
        query |= Q(**{k: v})
    exist_obj = qs.filter(query).first()
    if exist_obj:
        for k, v in object_model_name_db_i18n.items():
            if getattr(exist_obj, k) == v:
                raise ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR.set_message(_("对象模型名称已存在")).set_data({k: v})

    for field in update_fields:
        if field == "attribute_config":
            setattr(obj, field, entity.attribute_config.model_dump())
            continue
        setattr(obj, field, getattr(entity, field))
    for field, value in object_model_name_db_i18n.items():
        setattr(obj, field, value)
    obj.save()
    entity = obj.to_entity()
    _enrich_extra_fields([entity])
    return entity


def delete_object_model(object_model_id: int, valid_only: bool = False) -> ObjectModel:
    """
    删除对象模型

    删除指定的对象模型，会进行删除前的验证检查。
    内置模型和已关联使用记录的模型不允许删除。

    Args:
        object_model_id: 要删除的对象模型ID
        valid_only: 是否只进行验证而不实际删除，True时只验证不删除

    Returns:
        ObjectModel: 被删除的对象模型实体（或验证通过的模型实体）

    Raises:
        ErrorCodes.OBJECT_MODEL_NOT_FOUND: 当对象模型不存在时
        ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR: 当出现以下情况时
            - 内置对象模型不可删除
            - 该对象模型已被其他模块关联使用，无法删除

    Examples:
        # 删除对象模型
        deleted_model = delete_object_model(object_model_id=1)

        # 只验证是否可删除，不实际删除
        model = delete_object_model(object_model_id=1, valid_only=True)
    """
    try:
        obj_model = ObjectModelORM.objects.get(object_model_id=object_model_id)
    except ObjectModelORM.DoesNotExist:
        raise ErrorCodes.OBJECT_MODEL_NOT_FOUND.set_data({"object_model_id": object_model_id})
    _validate_delete_object_model(obj_model)
    if not valid_only:
        obj_model.delete()

    return obj_model.to_entity()


def get_cloud_object_model_code_list() -> list[str]:
    """
    获取所有云平台对象模型code列表

    查询云平台分组下所有子分组中的对象模型代码。
    如果云平台分组不存在，则返回空列表。

    Returns:
        list[str]: 云平台对象模型代码列表

    Examples:
        # 获取所有云平台对象模型代码
        cloud_codes = get_cloud_object_model_code_list()
        # 返回示例: ["aws_ec2", "azure_vm", "tencent_cvm"]
    """
    try:
        group = ObjectModelGroupORM.objects.get(object_model_group_code=BuiltinObjectModelGroupCode.CLOUD_PLATFORMS)
    except ObjectModelGroupORM.DoesNotExist:
        return []
    group_ids = ObjectModelGroupORM.objects.filter(
        parent_object_model_group_id=group.object_model_group_id
    ).values_list("object_model_group_id", flat=True)

    return list(
        ObjectModelORM.objects.filter(object_model_group_id__in=group_ids).values_list("object_model_code", flat=True)
    )


def _validate_delete_object_model(object_model: ObjectModelORM):
    """
    对象模型删除校验

    验证对象模型是否可以被删除，检查内置模型限制和关联关系。
    内置模型不允许删除，已被其他模块使用的模型也不允许删除。

    Args:
        object_model: 要删除的对象模型ORM实例

    Raises:
        ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR: 当出现以下情况时
            - 内置对象模型不可删除
            - 该对象模型已被其他模块关联使用，无法删除

    内部逻辑:
        1. 检查是否为内置模型（is_default=True）
        2. 查询该模型的使用记录
        3. 按应用和模块分组统计关联的实例
        4. 如果存在关联则生成详细的错误信息
    """
    if object_model.is_default and object_model.datasource != DatasourceType.LEGACY:
        raise ErrorCodes.OBJECT_MODEL_OPERATE_ERROR.set_message(_("内置对象模型不可删除"))
    relation_msgs: dict[str, list[str]] = defaultdict(list)
    relate_records = ObjectModelUsageRecordORM.objects.filter(object_model_id=object_model.object_model_id)
    for record in relate_records:
        relation_msgs[f"{record.app_name}——{record.module_name}"].append(f"{record.inst_name}")

    msg = "\n".join(
        [
            _("该对象与模块`{}`关联, 无法删除，关联对象：{};").format(module, ",".join(insts))
            for module, insts in relation_msgs.items()
        ]
    )
    if msg:
        raise ErrorCodes.OBJECT_MODEL_VALIDATE_ERROR.set_message(msg)


def _enrich_extra_fields(entity_list: list[ObjectModel]) -> list[ObjectModel]:
    """
    为对象模型实体列表填充权限相关的扩展字段

    计算并设置每个对象模型的权限相关字段，包括是否可更新、可删除和插件管理权限。
    这些字段基于模型的类型、所属分组和内置规则计算得出。

    Args:
        entity_list: 对象模型实体列表

    Returns:
        list[ObjectModel]: 已填充权限字段的对象模型列表

    权限字段说明:
        - can_update: 是否可更新，规则如下：
            * 不在禁止更新列表中的模型可更新
            * 云平台模型一般不可更新
            * 云平台虚拟机分组下的模型例外，可以更新
        - can_delete: 是否可删除，规则如下：
            * 非内置模型可删除
            * 硬件相关的内置模型可删除
        - plugin_manage: 是否支持插件管理，规则如下：
            * CMDB数据源的模型支持插件管理
            * 不在禁止插件管理列表中的非云平台模型支持插件管理

    Examples:
        # 内部使用，由其他函数调用
        models = [model1, model2, model3]
        enriched_models = _enrich_extra_fields(models)
        # 每个model现在都有了can_update、can_delete、plugin_manage、path字段
    """
    cloud_object_codes = get_cloud_object_model_code_list()
    vm_group = ObjectModelGroupORM.objects.filter(
        object_model_group_code=BuiltinObjectModelGroupCode.CLOUD_VIRTUAL_MACHINE
    ).first()
    entity_group_ids = {entity.object_model_group_id for entity in entity_list}
    group_relations = dict(
        ObjectModelGroupORM.objects.filter(object_model_group_id__in=entity_group_ids).values_list(
            "object_model_group_id", "parent_object_model_group_id"
        )
    )
    for entity in entity_list:
        parent_group_id = group_relations.get(entity.object_model_group_id)
        path = [parent_group_id, entity.object_model_group_id] if parent_group_id else [entity.object_model_group_id]
        entity.path = path
        if entity.object_model_code not in NOT_UPDATE_OBJECT_MODEL_CODE_LIST + cloud_object_codes:
            entity.can_update = True
        elif vm_group and entity.object_model_group_id == vm_group.object_model_group_id:
            # 如果是云平台虚拟机对象模型对象，则允许编辑
            entity.can_update = True
        entity.can_delete = not entity.is_default
        entity.plugin_manage = (
            entity.datasource == DatasourceType.CMDB
            or entity.object_model_code not in NOT_PLUGIN_MANAGE_OBJ_CODE_LIST + cloud_object_codes
        )
        if entity.datasource == DatasourceType.LEGACY:
            # legacy数据源的对象模型不允许编辑和插件管理，但允许删除
            entity.can_update = False
            entity.can_delete = True
            entity.plugin_manage = False

    return entity_list
