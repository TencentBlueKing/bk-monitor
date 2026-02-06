"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from typing import Any

from django.db import transaction
from django.db.models import Model

from .import_adapters import ImportAdapterManager

logger = logging.getLogger(__name__)


class BaseImporter:
    """
    基础导入器类
    """

    # 资源类型标识
    resource_type: str = None

    # Model 类
    model_class = None

    def __init__(self, config: dict, adapter_manager: ImportAdapterManager):
        """
        初始化导入器

        Args:
            config: 配置字典
            adapter_manager: 导入适配器管理器
        """
        self.config = config
        self.adapter_manager = adapter_manager
        self.import_config = config.get("import", {})
        self.conflict_strategy = self.import_config.get("conflict_strategy", "skip")

    def _get_primary_key_field(self, model_class):
        """
        获取主键字段名
        """
        return model_class._meta.pk.name

    def _get_primary_key_value(self, obj: Model) -> Any:
        """
        获取对象的主键值
        """
        pk_field = obj._meta.pk
        return getattr(obj, pk_field.name)

    def _check_conflict(self, data: dict) -> Model | None:
        """
        检查是否存在冲突[数据已创建]（优先使用主键ID检查）

        Args:
            data: 导入数据

        Returns:
            如果存在冲突，返回已存在的对象；否则返回 None
        """
        # 1. 优先通过主键ID检查（避免重复创建）
        pk_field = self._get_primary_key_field(self.model_class)
        original_pk = data.get(pk_field)

        if original_pk is not None:
            try:
                existing = self.model_class.objects.get(**{pk_field: original_pk})
                logger.debug(f"Found existing {self.resource_type} by {pk_field}={original_pk}")
                return existing
            except self.model_class.DoesNotExist:
                pass

        # 2. 子类可以重写此方法添加额外的业务唯一标识检查
        # 例如：name + bk_biz_id、plugin_type 等
        return None

    def _handle_conflict(self, data: dict, existing_obj: Model) -> Model:
        """
        处理冲突(如果要创建已存在的对象)
            - skip: 跳过导入，使用已存在的对象
            - overwrite: 覆盖已存在的对象
            - rename: 重命名后创建新对象

        Args:
            data: 导入数据
            existing_obj: 已存在的对象

        Returns:
            处理后的对象
        """
        # 获取主键
        existing_pk = self._get_primary_key_value(existing_obj)

        if self.conflict_strategy == "skip":
            logger.info(f"Skipping {self.resource_type} {existing_pk} (already exists)")
            return existing_obj
        elif self.conflict_strategy == "overwrite":
            logger.info(f"Overwriting {self.resource_type} {existing_pk}")
            # 更新现有对象
            for key, value in data.items():
                if key not in ["id", "_metadata", "_relations"]:
                    setattr(existing_obj, key, value)
            existing_obj.save()
            return existing_obj
        elif self.conflict_strategy == "rename":
            # 重命名
            original_name = data.get("name", "")
            new_name = f"{original_name}_imported_{data.get('_metadata', {}).get('original_id', '')}"
            data["name"] = new_name
            logger.info(f"Renaming {self.resource_type} to {new_name}")
            return self._create_object(data)
        else:
            raise ValueError(f"Unknown conflict strategy: {self.conflict_strategy}")

    def _create_object(self, data: dict) -> Model:
        """
        创建对象

        Args:
            data: 导入数据（已处理适配器）

        Returns:
            创建的对象

        Raises:
            ValueError: 如果主键ID已存在（说明对象已被导入过，但_check_conflict()未检测到）
        """
        # 获取主键字段名
        pk_field = self._get_primary_key_field(self.model_class)
        original_pk = data.get(pk_field)

        # 准备导入数据（保留原始主键ID）
        import_data = {k: v for k, v in data.items() if not k.startswith("_")}

        # 处理 JSONField 的 null 值问题
        for field in self.model_class._meta.get_fields():
            if hasattr(field, "get_internal_type") and field.get_internal_type() == "JSONField":
                field_name = field.name
                if field_name in import_data and import_data[field_name] is None:
                    if field.has_default():
                        default = field.get_default()
                        import_data[field_name] = default
                        logger.debug(f"Field {field_name} is null, using default value: {default}")

        # 创建对象
        try:
            obj = self.model_class.objects.create(**import_data)
            logger.debug(f"Created {self.resource_type} with {pk_field}={original_pk}")
            return obj
        except Exception as e:
            # 如果创建失败，抛出异常
            error_msg = f"Failed to create {self.resource_type} with {pk_field}={original_pk}: {e}. "
            logger.error(error_msg)
            raise ValueError(error_msg) from e

    def import_single(self, data: dict) -> Model:
        """
        导入单个对象 创建当前resource及其关联数据

        Args:
            data: 导入数据（包含 _metadata 和 _relations）

        Returns:
            导入的对象
        """
        # 应用导入适配器
        data = self.adapter_manager.apply_adapters(data)

        # 检查冲突
        existing_obj = self._check_conflict(data)
        if existing_obj:
            # 对象已存在，根据冲突策略处理
            obj = self._handle_conflict(data, existing_obj)
        else:
            # 创建对象
            obj = self._create_object(data)

        # 导入关联数据
        relations = data.get("_relations", {})
        if relations:
            self.import_relations(obj, relations)

        return obj

    def import_relations(self, obj: Model, relations: dict):
        """
        导入关联数据

        Args:
            obj: 主对象
            relations: 关联数据字典
        """
        # 子类可以重写此方法来处理特定的关联数据
        pass

    def import_all(self, resources_data: list[dict]) -> list[Model]:
        """
        导入所有资源

        Args:
            resources_data: 资源数据列表

        Returns:
            导入的对象列表
        """
        if not resources_data:
            return []

        results = []
        failed_count = 0

        with transaction.atomic():
            for i, data in enumerate(resources_data, 1):
                # 使用 savepoint 确保单个对象失败不影响其他对象
                sid = transaction.savepoint()
                try:
                    obj = self.import_single(data)
                    results.append(obj)
                    transaction.savepoint_commit(sid)

                except Exception as e:
                    transaction.savepoint_rollback(sid)
                    failed_count += 1
                    original_id = data.get("_metadata", {}).get("original_id", "unknown")
                    # 只记录第一个错误的详细堆栈，其他错误简略记录
                    if failed_count == 1:
                        logger.error(f"[{self.resource_type}] Failed to import {original_id}: {e}", exc_info=True)
                    else:
                        logger.debug(f"[{self.resource_type}] Failed to import {original_id}: {e}")

        # 返回统计结果供上层汇总
        return results


class RelationImportMixin:
    """
    关联数据导入混入类
    """

    adapter_manager: ImportAdapterManager
    resource_type: str

    def import_related_queryset(
        self, obj: Model, relation_key: str, relation_data: list[dict], model_class, foreign_key_field: str
    ):
        """
        导入关联的 QuerySet 数据

        Args:
            obj: 主对象
            relation_key: 关联键名（用于日志）
            relation_data: 关联数据列表
            model_class: 关联模型类
            foreign_key_field: 外键字段名（如 "strategy_id"）
        """
        if not relation_data:
            return

        # 获取主对象的ID
        pk_field = obj._meta.pk
        new_id = getattr(obj, pk_field.name)

        # 获取关联模型的主键字段名
        related_pk_field = model_class._meta.pk.name

        # 导入每个关联对象
        for item_data in relation_data:
            # 保存原始主键ID（用于冲突检查）
            original_pk = item_data.get(related_pk_field)

            # 移除主键字段和所有以 _ 开头的内部字段（让数据库自动生成新的主键）
            item_data = {k: v for k, v in item_data.items() if not k.startswith("_") and k != related_pk_field}

            # 应用适配器
            item_data = self.adapter_manager.apply_adapters(item_data)

            # 解析外键（关联到主对象）
            item_data[foreign_key_field] = new_id

            # 检查关联对象是否已存在
            existing_obj = None
            if original_pk is not None:
                try:
                    existing_obj = model_class.objects.get(**{related_pk_field: original_pk})
                    logger.debug(f"Related {model_class.__name__} {original_pk} already exists, skipping")
                except model_class.DoesNotExist:
                    pass

            # 如果对象已存在，跳过创建
            if existing_obj:
                continue

            # 创建关联对象
            try:
                model_class.objects.create(**item_data)
            except Exception as e:
                logger.error(f"Failed to import {relation_key} for {self.resource_type} {new_id}: {e}", exc_info=True)
