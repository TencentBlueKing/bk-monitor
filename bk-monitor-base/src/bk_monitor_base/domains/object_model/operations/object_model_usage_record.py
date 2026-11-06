"""
对象模型使用记录操作模块

提供对象模型使用记录的增删改查功能，用于跟踪和管理对象模型在各个应用和模块中的使用情况。
支持批量操作和分页查询，确保使用记录的准确性和完整性。
"""

import logging

from django.db.models import Q

from bk_monitor_base.domains.object_model.define import ObjectModelUsageRecord
from bk_monitor_base.domains.object_model.models import ObjectModelORM, ObjectModelUsageRecordORM

logger = logging.getLogger("object_model_usage_record")


def list_object_model_usage_records(
    ids: list[int] | None = None,
    object_model_ids: list[int] | None = None,
    app_ids: list[str] | None = None,
    app_name_contains: str | None = None,
    module_ids: list[str] | None = None,
    module_name_contains: str | None = None,
    inst_ids: list[str] | None = None,
    inst_name_contains: str | None = None,
    bk_tenant_ids: list[str] | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[ObjectModelUsageRecord]:
    """
    根据条件查询对象模型使用记录列表

    支持多种过滤条件的组合查询和分页，用于追踪对象模型在各个应用、模块和实例中的使用情况。
    可以按记录ID、对象模型ID、应用信息、模块信息、实例信息等多个维度进行筛选。

    Args:
        ids: 使用记录ID列表，用于精确匹配记录
        object_model_ids: 对象模型ID列表，用于查询特定模型的使用记录
        app_ids: 应用ID列表，用于查询特定应用的使用记录
        app_name_contains: 应用名称包含的字符串，用于模糊查询
        module_ids: 模块ID列表，用于查询特定模块的使用记录
        module_name_contains: 模块名称包含的字符串，用于模糊查询
        inst_ids: 实例ID列表，用于查询特定实例的使用记录
        inst_name_contains: 实例名称包含的字符串，用于模糊查询
        bk_tenant_ids: 租户ID列表，用于过滤特定租户的记录
        limit: 限制返回结果数量，用于分页
        offset: 偏移量，用于分页

    Returns:
        list[ObjectModelUsageRecord]: 符合条件的对象模型使用记录列表

    Examples:
        # 查询所有使用记录
        records = list_object_model_usage_records()

        # 查询特定对象模型的使用记录
        records = list_object_model_usage_records(object_model_ids=[1, 2, 3])

        # 查询特定应用的使用记录
        records = list_object_model_usage_records(app_ids=["bk_monitor", "bk_log"])

        # 模糊查询应用名称
        records = list_object_model_usage_records(app_name_contains="监控")

        # 分页查询
        records = list_object_model_usage_records(limit=50, offset=100)

        # 组合查询：特定模型在特定应用中的使用
        records = list_object_model_usage_records(
            object_model_ids=[1],
            app_name_contains="监控"
        )
    """
    qs = ObjectModelUsageRecordORM.objects.all()

    # 过滤id
    if ids is not None:
        qs = qs.filter(id__in=ids)

    # 过滤模型id
    if object_model_ids is not None:
        qs = qs.filter(object_model_id__in=object_model_ids)

    # 过滤app_id
    if app_ids is not None:
        qs = qs.filter(app_id__in=app_ids)

    # app名称模糊查询
    if app_name_contains is not None:
        qs = qs.filter(app_name__contains=app_name_contains)

    # 过滤module_id
    if module_ids is not None:
        qs = qs.filter(module_id__in=module_ids)

    # module名称模糊查询
    if module_name_contains is not None:
        qs = qs.filter(module_name__contains=module_name_contains)

    # 过滤inst_id
    if inst_ids is not None:
        qs = qs.filter(inst_id__in=inst_ids)

    # inst名称模糊查询
    if inst_name_contains is not None:
        qs = qs.filter(inst_name__contains=inst_name_contains)

    if bk_tenant_ids is not None:
        qs = qs.filter(bk_tenant_id__in=bk_tenant_ids)

    # 分页
    if limit is not None or offset is not None:
        offset = offset or 0
        if limit is not None:
            limit = offset + limit
        qs = qs[offset:limit]

    object_model_usage_records = [obj.to_entity() for obj in qs]

    return object_model_usage_records


def create_object_model_usage_records(records: list[ObjectModelUsageRecord]) -> list[ObjectModelUsageRecord]:
    """
    批量创建对象模型使用记录

    批量创建多个对象模型使用记录，用于记录对象模型在各个应用、模块和实例中的使用情况。
    会验证关联的对象模型是否存在，无效的记录会被跳过并记录警告日志。

    Args:
        records: 要创建的对象模型使用记录列表

    Returns:
        list[ObjectModelUsageRecord]: 成功创建的对象模型使用记录列表

    业务逻辑:
        1. 如果记录列表为空，直接返回空列表
        2. 验证所有记录关联的对象模型是否存在
        3. 过滤掉关联不存在对象模型的记录，并记录警告日志
        4. 使用批量创建的方式插入有效记录（批次大小500）
        5. 返回创建成功的记录实体列表

    Examples:
        # 创建单个使用记录
        record = ObjectModelUsageRecord(
            object_model_id=1,
            app_id="bk_monitor",
            app_name="蓝鲸监控",
            module_id="alert_manager",
            module_name="告警管理",
            inst_id="strategy_001",
            inst_name="CPU使用率策略",
            created_by="admin"
        )
        created_records = create_object_model_usage_records([record])

        # 批量创建多个使用记录
        records = [
            ObjectModelUsageRecord(
                object_model_id=1,
                app_id="bk_monitor",
                app_name="蓝鲸监控",
                module_id="strategy",
                module_name="策略配置",
                inst_id="strategy_001",
                inst_name="主机CPU策略"
            ),
            ObjectModelUsageRecord(
                object_model_id=2,
                app_id="bk_log",
                app_name="日志平台",
                module_id="collect",
                module_name="采集配置",
                inst_id="collect_001",
                inst_name="应用日志采集"
            )
        ]
        created_records = create_object_model_usage_records(records)
    """
    if not records:
        return []

    object_model_ids = [r.object_model_id for r in records]
    model_ids = ObjectModelORM.objects.filter(object_model_id__in=object_model_ids).values_list(
        "object_model_id", flat=True
    )

    valid_records: list[ObjectModelUsageRecordORM] = []
    for record in records:
        if record.object_model_id not in model_ids:
            logger.warning(
                f"app_id={record.app_id} module_id={record.module_id} inst_id={record.inst_id} related object_model_id {record.object_model_id} not found, skip"
            )
            continue
        valid_records.append(
            ObjectModelUsageRecordORM(
                **record.model_dump(
                    include={
                        "object_model_id",
                        "app_id",
                        "app_name",
                        "module_id",
                        "module_name",
                        "inst_id",
                        "inst_name",
                        "bk_tenant_id",
                        "created_by",
                        "created_at",
                    }
                )
            )
        )
    record_list = ObjectModelUsageRecordORM.objects.bulk_create(valid_records, batch_size=500)
    return [r.to_entity() for r in record_list]


def update_object_model_usage_records(records: list[ObjectModelUsageRecord]):
    """
    批量更新对象模型使用记录

    批量更新现有的对象模型使用记录，主要用于更新记录的名称信息和更新时间。
    只能更新已存在的记录，不能创建新记录。

    Args:
        records: 要更新的对象模型使用记录列表，必须包含有效的记录ID

    可更新字段:
        - app_name: 应用名称
        - module_name: 模块名称
        - inst_name: 实例名称
        - updated_by: 更新者
        - updated_at: 更新时间

    业务逻辑:
        1. 过滤出包含有效ID的记录
        2. 根据ID查询数据库中现有的记录
        3. 更新指定字段的值
        4. 使用批量更新的方式保存修改（批次大小500）

    注意事项:
        - 只有包含ID的记录才会被处理
        - 不存在的记录ID会被忽略
        - 核心关联字段（object_model_id、app_id、module_id、inst_id）不能修改

    Examples:
        # 更新单个记录的名称信息
        record = ObjectModelUsageRecord(
            id=1,
            app_name="蓝鲸监控平台（更新）",
            module_name="告警策略管理",
            inst_name="CPU高使用率告警策略",
            updated_by="admin",
            updated_at=datetime.now()
        )
        update_object_model_usage_records([record])

        # 批量更新多个记录
        records = [
            ObjectModelUsageRecord(
                id=1,
                app_name="蓝鲸监控（新版）",
                module_name="策略管理",
                inst_name="主机CPU监控策略"
            ),
            ObjectModelUsageRecord(
                id=2,
                app_name="日志平台（升级版）",
                module_name="数据采集",
                inst_name="业务日志采集配置"
            )
        ]
        update_object_model_usage_records(records)
    """
    record_id_map = {r.id: r for r in records if r.id}
    curr_records = list(ObjectModelUsageRecordORM.objects.filter(id__in=record_id_map.keys()))
    for r in curr_records:
        new_record = record_id_map[r.id]
        r.app_name = new_record.app_name
        r.module_name = new_record.module_name
        r.inst_name = new_record.inst_name
        r.updated_by = new_record.updated_by
        r.updated_at = new_record.updated_at

    if curr_records:
        ObjectModelUsageRecordORM.objects.bulk_update(
            curr_records, fields=["app_name", "module_name", "inst_name", "updated_by", "updated_at"], batch_size=500
        )


def delete_object_model_usage_records(records: list[ObjectModelUsageRecord]):
    """
    批量删除对象模型使用记录

    根据对象模型使用记录的关键字段（object_model_id、app_id、module_id、inst_id）
    批量删除匹配的记录。采用分批处理的方式提高删除性能。

    Args:
        records: 要删除的对象模型使用记录列表

    删除逻辑:
        1. 按批次处理记录（批次大小100）
        2. 为每个记录构建删除条件：
           - object_model_id: 对象模型ID
           - app_id: 应用ID
           - module_id: 模块ID
           - inst_id: 实例ID
        3. 使用OR条件组合所有删除条件
        4. 执行批量删除操作

    注意事项:
        - 删除条件基于业务主键（object_model_id + app_id + module_id + inst_id）
        - 不依赖记录的数据库主键ID
        - 如果记录不存在，删除操作不会报错
        - 采用分批处理避免单次删除过多记录

    Examples:
        # 删除单个使用记录
        record = ObjectModelUsageRecord(
            object_model_id=1,
            app_id="bk_monitor",
            module_id="alert_manager",
            inst_id="strategy_001"
        )
        delete_object_model_usage_records([record])

        # 批量删除多个使用记录
        records = [
            ObjectModelUsageRecord(
                object_model_id=1,
                app_id="bk_monitor",
                module_id="strategy",
                inst_id="strategy_001"
            ),
            ObjectModelUsageRecord(
                object_model_id=2,
                app_id="bk_log",
                module_id="collect",
                inst_id="collect_001"
            )
        ]
        delete_object_model_usage_records(records)

        # 删除特定应用的所有使用记录
        app_records = list_object_model_usage_records(app_ids=["old_app"])
        delete_object_model_usage_records(app_records)
    """
    batch_size = 100
    for i in range(0, len(records), batch_size):
        batch_records = records[i : i + batch_size]
        query = Q()
        for record in batch_records:
            q = Q(
                object_model_id=record.object_model_id,
                app_id=record.app_id,
                module_id=record.module_id,
                inst_id=record.inst_id,
            )
            query |= q
        if query:
            ObjectModelUsageRecordORM.objects.filter(query).delete()
