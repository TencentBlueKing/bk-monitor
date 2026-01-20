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
from datetime import datetime, date
from typing import Any, List, Optional

from django.db import transaction
from django.db.models import Model

from .import_adapters import ImportAdapterManager
from .import_utils import ImportIDMapper


def convert_datetime_to_string(data):
    """
    递归转换数据中的 datetime 对象为 ISO 格式字符串
    
    Args:
        data: 任意数据类型
    
    Returns:
        转换后的数据
    """
    if isinstance(data, datetime):
        return data.isoformat()
    elif isinstance(data, date):
        return data.isoformat()
    elif isinstance(data, dict):
        return {k: convert_datetime_to_string(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_datetime_to_string(item) for item in data]
    elif isinstance(data, tuple):
        return tuple(convert_datetime_to_string(item) for item in data)
    else:
        return data

logger = logging.getLogger(__name__)


class BaseImporter:
    """
    基础导入器类
    """
    
    # 资源类型标识
    resource_type: str = None
    
    # Model 类
    model_class = None
    
    def __init__(self, config: dict, adapter_manager: ImportAdapterManager, id_mapper: ImportIDMapper):
        """
        初始化导入器
        
        Args:
            config: 配置字典
            adapter_manager: 导入适配器管理器
            id_mapper: ID 映射器
        """
        self.config = config
        self.adapter_manager = adapter_manager
        self.id_mapper = id_mapper
        self.import_config = config.get("import", {})
        self.conflict_strategy = self.import_config.get("conflict_strategy", "skip")
    
    def should_import(self) -> bool:
        """
        判断是否需要导入此资源
        """
        resources = self.import_config.get("resources", [])
        if not resources:
            return True
        return self.resource_type in resources
    
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
    
    def _check_conflict(self, data: dict) -> Optional[Model]:
        """
        检查是否存在冲突
        
        Args:
            data: 导入数据
        
        Returns:
            如果存在冲突，返回已存在的对象；否则返回 None
        """
        # 默认使用 name + bk_biz_id 作为唯一标识
        # 子类可以重写此方法
        name = data.get("name")
        bk_biz_id = data.get("bk_biz_id")
        
        if name and bk_biz_id is not None:
            try:
                return self.model_class.objects.get(name=name, bk_biz_id=bk_biz_id)
            except self.model_class.DoesNotExist:
                pass
        
        return None
    
    def _handle_conflict(self, data: dict, existing_obj: Model) -> Model:
        """
        处理冲突
        
        Args:
            data: 导入数据
            existing_obj: 已存在的对象
        
        Returns:
            处理后的对象
        """
        if self.conflict_strategy == "skip":
            logger.info(f"Skipping {self.resource_type} {existing_obj.id} (already exists)")
            return existing_obj
        elif self.conflict_strategy == "overwrite":
            logger.info(f"Overwriting {self.resource_type} {existing_obj.id}")
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
        """
        # 获取主键字段名
        pk_field = self._get_primary_key_field(self.model_class)
        
        # 获取模型的所有字段名（包括外键）
        model_field_names = {f.name for f in self.model_class._meta.get_fields()}
        
        # 移除元数据、关联数据、主键字段和所有以 _ 开头的内部字段
        # 同时过滤掉模型不存在的字段（如属性、方法等）
        import_data = {}
        for k, v in data.items():
            if k.startswith("_"):
                continue
            if k == pk_field:
                continue
            # 只保留模型实际存在的字段
            if k in model_field_names:
                import_data[k] = v
        
        # 处理外键字段：将ID转换为 _id 后缀形式（Django推荐方式）
        for field in self.model_class._meta.get_fields():
            if hasattr(field, 'related_model') and field.related_model:
                field_name = field.name
                if field_name in import_data and import_data[field_name] is not None:
                    # 如果值是整数或可转换为整数的字符串，使用 _id 后缀形式
                    try:
                        fk_id = int(import_data[field_name])
                        # 使用 _id 后缀形式，Django会自动处理
                        import_data[f"{field_name}_id"] = fk_id
                        del import_data[field_name]
                    except (ValueError, TypeError):
                        # 如果不是数字，可能是对象实例或其他类型，保持原样
                        pass
        
        # 转换 datetime 对象为字符串（避免 JSON 序列化错误）
        import_data = convert_datetime_to_string(import_data)
        
        # 创建对象
        obj = self.model_class.objects.create(**import_data)
        return obj
    
    def _resolve_foreign_keys(self, data: dict) -> dict:
        """
        解析外键字段，将原始ID转换为新ID
        
        Args:
            data: 导入数据
        
        Returns:
            处理后的数据
        """
        # 获取模型的所有字段
        fields = self.model_class._meta.get_fields()
        pk_field = self._get_primary_key_field(self.model_class)
        
        for field in fields:
            # 检查是否是外键字段
            if hasattr(field, 'related_model') and field.related_model:
                field_name = field.name
                if field_name in data and data[field_name] is not None:
                    # 尝试推断资源类型（通过字段名和关联模型）
                    related_model = field.related_model
                    resource_type = self._infer_resource_type(related_model)
                    
                    if resource_type:
                        original_id = data[field_name]
                        new_id = self.id_mapper.get_new_id(resource_type, original_id)
                        if new_id is not None:
                            data[field_name] = new_id
                            logger.debug(f"Mapped {field_name}: {original_id} -> {new_id}")
                        elif field_name == pk_field:
                            # 如果主键字段映射失败，抛出错误
                            raise ValueError(
                                f"Failed to map {field_name} (primary key) for {self.resource_type}: "
                                f"original_id={original_id}, resource_type={resource_type}. "
                                f"Make sure {resource_type} is imported before {self.resource_type}."
                            )
        
        return data
    
    def _infer_resource_type(self, model_class) -> Optional[str]:
        """
        根据模型类推断资源类型
        
        Args:
            model_class: 模型类
        
        Returns:
            资源类型，如果无法推断则返回 None
        """
        # 从导出器的注册表中查找
        from .importers import IMPORTER_REGISTRY
        
        for resource_type, importer_class in IMPORTER_REGISTRY.items():
            if importer_class.model_class == model_class:
                return resource_type
        
        return None
    
    def import_single(self, data: dict) -> Model:
        """
        导入单个对象
        
        Args:
            data: 导入数据（包含 _metadata 和 _relations）
        
        Returns:
            导入的对象
        """
        # 获取原始ID
        original_id = data.get("_metadata", {}).get("original_id")
        
        # 1. 应用导入适配器
        data = self.adapter_manager.apply_adapters(data)
        
        # 2. 解析外键字段（将原始ID转换为新ID）
        data = self._resolve_foreign_keys(data)
        
        # 3. 检查冲突
        existing_obj = self._check_conflict(data)
        if existing_obj:
            obj = self._handle_conflict(data, existing_obj)
        else:
            # 4. 创建对象
            obj = self._create_object(data)
        
        # 5. 记录ID映射
        new_id = self._get_primary_key_value(obj)
        if original_id is not None:
            self.id_mapper.add_mapping(self.resource_type, original_id, new_id)
        
        # 6. 导入关联数据
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
    
    def import_all(self, resources_data: List[dict]) -> List[Model]:
        """
        导入所有资源
        
        Args:
            resources_data: 资源数据列表
        
        Returns:
            导入的对象列表
        """
        if not self.should_import():
            logger.info(f"Skipping import for {self.resource_type}")
            return []
        
        logger.info(f"Importing {self.resource_type}...")
        
        results = []
        with transaction.atomic():
            for data in resources_data:
                try:
                    obj = self.import_single(data)
                    results.append(obj)
                except Exception as e:
                    original_id = data.get("_metadata", {}).get("original_id", "unknown")
                    logger.error(f"Failed to import {self.resource_type} {original_id}: {e}", exc_info=True)
        
        logger.info(f"Successfully imported {len(results)}/{len(resources_data)} {self.resource_type} objects")
        return results


class RelationImportMixin:
    """
    关联数据导入混入类
    """
    
    def import_related_queryset(self, obj: Model, relation_key: str, relation_data: List[dict], 
                                model_class, foreign_key_field: str):
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
        
        # 获取主对象的新ID
        pk_field = obj._meta.pk
        new_id = getattr(obj, pk_field.name)
        
        # 获取关联模型的主键字段名
        related_pk_field = model_class._meta.pk.name
        
        # 导入每个关联对象
        for item_data in relation_data:
            # 移除主键字段和所有以 _ 开头的内部字段（让数据库自动生成新的主键）
            item_data = {k: v for k, v in item_data.items() if not k.startswith("_") and k != related_pk_field}
            
            # 应用适配器
            item_data = self.adapter_manager.apply_adapters(item_data)
            
            # 解析外键（关联到主对象）
            item_data[foreign_key_field] = new_id
            
            # 解析其他外键（关联到其他资源）
            item_data = self._resolve_foreign_keys_for_model(item_data, model_class)
            
            # 转换 datetime 对象为字符串（避免 JSON 序列化错误）
            item_data = convert_datetime_to_string(item_data)
            
            # 创建关联对象
            try:
                model_class.objects.create(**item_data)
            except Exception as e:
                logger.error(f"Failed to import {relation_key} for {self.resource_type} {new_id}: {e}", exc_info=True)
    
    def _resolve_foreign_keys_for_model(self, data: dict, model_class) -> dict:
        """
        为特定模型解析外键字段
        """
        fields = model_class._meta.get_fields()
        
        for field in fields:
            if hasattr(field, 'related_model') and field.related_model:
                field_name = field.name
                if field_name in data and data[field_name] is not None:
                    related_model = field.related_model
                    resource_type = self._infer_resource_type(related_model)
                    
                    if resource_type:
                        original_id = data[field_name]
                        new_id = self.id_mapper.get_new_id(resource_type, original_id)
                        if new_id is not None:
                            data[field_name] = new_id
        
        return data
    
    def _infer_resource_type(self, model_class) -> Optional[str]:
        """
        根据模型类推断资源类型（RelationImportMixin 也需要此方法）
        """
        # 延迟导入避免循环依赖
        try:
            from .importers import IMPORTER_REGISTRY
            
            for resource_type, importer_class in IMPORTER_REGISTRY.items():
                if importer_class.model_class == model_class:
                    return resource_type
        except ImportError:
            # 如果导入失败，尝试通过模型类名推断
            model_name = model_class.__name__
            # 简单的映射规则
            if model_name == "StrategyModel":
                return "strategy"
            elif model_name == "UserGroup":
                return "user_group"
            elif model_name == "DutyRule":
                return "duty_rule"
            elif model_name == "ActionConfig":
                return "action_config"
            elif model_name == "ActionPlugin":
                return "action_plugin"
            elif model_name == "AlertAssignGroup":
                return "alert_assign_group"
            elif model_name == "Shield":
                return "shield"
            elif model_name == "Dashboard":
                return "dashboard"
            elif model_name == "CollectConfigMeta":
                return "collect_config"
            elif model_name == "CollectorPluginMeta":
                return "collector_plugin"
            elif model_name == "CustomTSTable":
                return "custom_ts_table"
            elif model_name == "TimeSeriesGroup":
                return "custom_ts_group"
        
        return None
