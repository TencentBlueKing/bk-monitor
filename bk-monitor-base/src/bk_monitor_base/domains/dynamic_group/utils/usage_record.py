# pyright: reportUnknownVariableType=false

"""
动态分组使用记录操作工具

提供对象模型使用记录的创建和删除功能。
"""

import logging
from typing import ClassVar

from bk_monitor_base.domains.dynamic_group.constants import (
    USAGE_RECORD_APP_ID,
    USAGE_RECORD_APP_NAME,
    USAGE_RECORD_MODULE_ID,
    USAGE_RECORD_MODULE_NAME,
)
from bk_monitor_base.domains.dynamic_group.define import DynamicGroup
from bk_monitor_base.object_model import list_object_models
from bk_monitor_base.object_model_usage_record import (
    ObjectModelUsageRecord,
    create_object_model_usage_records,
    delete_object_model_usage_records,
)

logger = logging.getLogger(__name__)


class UsageRecordOperator:
    """
    使用记录操作器

    管理动态分组的对象模型使用记录的创建和删除。

    Usage:
        >>> # 创建使用记录
        >>> UsageRecordOperator.create(group)

        >>> # 删除使用记录
        >>> UsageRecordOperator.delete(group)

        >>> # 批量删除使用记录
        >>> UsageRecordOperator.delete([group1, group2, group3])
    """

    # 操作类型常量
    CREATE: ClassVar[str] = "create"
    DELETE: ClassVar[str] = "delete"

    @classmethod
    def create(cls, dynamic_groups: DynamicGroup | list[DynamicGroup]) -> None:
        """
        创建动态分组的对象模型使用记录

        操作失败不影响主流程，仅记录警告日志。

        Args:
            dynamic_groups: 动态分组实体或实体列表
        """
        cls._operate(cls.CREATE, dynamic_groups)

    @classmethod
    def delete(cls, dynamic_groups: DynamicGroup | list[DynamicGroup]) -> None:
        """
        删除动态分组的对象模型使用记录

        操作失败不影响主流程，仅记录警告日志。

        Args:
            dynamic_groups: 动态分组实体或实体列表
        """
        cls._operate(cls.DELETE, dynamic_groups)

    @classmethod
    def _operate(
        cls,
        operation: str,
        dynamic_groups: DynamicGroup | list[DynamicGroup],
    ) -> None:
        """
        操作动态分组的对象模型使用记录

        统一入口，根据操作类型执行创建或删除操作。
        操作失败不影响主流程，仅记录警告日志。

        Args:
            operation: 操作类型，可选值：CREATE, DELETE
            dynamic_groups: 动态分组实体或实体列表
        """
        # 统一转换为列表
        groups = dynamic_groups if isinstance(dynamic_groups, list) else [dynamic_groups]
        if not groups:
            return

        try:
            # 构建使用记录
            records = cls._build_records(groups)
            if not records:
                return

            # 根据操作类型执行
            if operation == cls.CREATE:
                create_object_model_usage_records(records)
                logger.info(f"UsageRecordOperator: 创建使用记录成功, count={len(records)}")
            elif operation == cls.DELETE:
                delete_object_model_usage_records(records)
                logger.info(f"UsageRecordOperator: 删除使用记录成功, count={len(records)}")
            else:
                logger.warning(f"UsageRecordOperator: 未知的操作类型 {operation}")
        except Exception as e:
            # 记录失败不影响主流程
            group_ids = [g.dynamic_group_id for g in groups]
            logger.warning(f"UsageRecordOperator: {operation}使用记录失败, dynamic_group_ids={group_ids}, error={e}")

    @classmethod
    def _build_records(cls, groups: list[DynamicGroup]) -> list[ObjectModelUsageRecord]:
        """
        构建使用记录列表

        Args:
            groups: 动态分组实体列表

        Returns:
            使用记录列表
        """
        if not groups:
            return []

        # 获取所有需要的对象模型
        object_model_codes = list(set(g.object_model_code for g in groups))
        object_models = list_object_models(
            object_model_codes=object_model_codes,
            raise_not_found=False,
        )
        code_to_model_id = {m.object_model_code: m.object_model_id for m in object_models}

        records = []
        for group in groups:
            object_model_id = code_to_model_id.get(group.object_model_code)
            if not object_model_id:
                logger.warning(
                    f"UsageRecordOperator._build_records: 对象模型不存在, object_model_code={group.object_model_code}"
                )
                continue

            records.append(
                ObjectModelUsageRecord(
                    object_model_id=object_model_id,
                    app_id=USAGE_RECORD_APP_ID,
                    app_name=USAGE_RECORD_APP_NAME,
                    module_id=USAGE_RECORD_MODULE_ID,
                    module_name=USAGE_RECORD_MODULE_NAME,
                    inst_id=str(group.dynamic_group_id),
                    inst_name=group.dynamic_group_name,
                    created_by=group.created_by or "",
                )
            )

        return records
