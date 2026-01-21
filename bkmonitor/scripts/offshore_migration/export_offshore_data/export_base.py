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
from typing import Any, List, Optional

from django.db.models import QuerySet

from .export_adapters import AdapterManager
from .export_utils import IDMapper, model_to_dict

logger = logging.getLogger(__name__)


class BaseExporter:
    """
    基础导出器类
    """
    
    # 资源类型标识
    resource_type: str = None
    
    # Model 类
    model_class = None
    
    def __init__(self, config: dict, adapter_manager: AdapterManager, id_mapper: IDMapper):
        """
        初始化导出器
        
        Args:
            config: 配置字典
            adapter_manager: 适配器管理器
            id_mapper: ID 映射器
        """
        self.config = config
        self.adapter_manager = adapter_manager
        self.id_mapper = id_mapper
        self.export_config = config.get("export", {})
    
    def should_export(self) -> bool:
        """
        判断是否需要导出此资源（完整导出模式：始终返回True）
        """
        # 完整导出模式：导出所有资源
        return True
    
    def query_objects(self, bk_biz_ids: list[int]|None = None) -> QuerySet:
        """
        查询要导出的对象
        
        Args:
            bk_biz_ids: 业务 ID 列表，为 None 时导出所有业务
        
        Returns:
            QuerySet
        """
        queryset = self.model_class.objects.all()
        
        # 过滤业务
        if bk_biz_ids and hasattr(self.model_class, "bk_biz_id"):
            queryset = queryset.filter(bk_biz_id__in=bk_biz_ids)
        
        return queryset
    
    def serialize_object(self, obj) -> dict:
        """
        序列化单个对象为字典
        
        Args:
            obj: Model 实例
        
        Returns:
            序列化后的字典
        """
        return model_to_dict(obj)
    
    def export_relations(self, obj, data: dict) -> dict:
        """
        导出关联对象
        
        Args:
            obj: Model 实例
            data: 已序列化的数据
        
        Returns:
            包含关联对象的数据
        """
        # 子类可以重写此方法来导出关联对象
        return data
    
    def apply_adapters(self, data: dict) -> dict:
        """
        应用适配器
        
        Args:
            data: 原始数据
        
        Returns:
            适配后的数据
        """
        return self.adapter_manager.apply_adapters(data)
    
    def post_process(self, data: dict) -> dict:
        """
        后处理，在适配器之后执行
        
        Args:
            data: 数据
        
        Returns:
            处理后的数据
        """
        # 子类可以重写此方法进行额外处理
        return data
    
    def _get_primary_key_value(self, obj) -> Any:
        """
        获取对象的主键值
        
        Args:
            obj: Model 实例
        
        Returns:
            主键值
        """
        pk_field = obj._meta.pk
        return getattr(obj, pk_field.name)
    
    def export_single(self, obj) -> dict:
        """
        导出单个对象
        
        Args:
            obj: Model 实例
        
        Returns:
            导出的数据字典
        """
        # 获取主键值
        pk_value = self._get_primary_key_value(obj)
        
        # 1. 序列化基本字段
        data = self.serialize_object(obj)
        
        # 2. 导出关联对象
        data = self.export_relations(obj, data)
        
        # 3. 应用适配器
        data = self.apply_adapters(data)
        
        # 4. 后处理
        data = self.post_process(data)
        
        # 5. 添加元数据
        data["_metadata"] = {
            "resource_type": self.resource_type,
            "original_id": pk_value,
        }
        
        # 6. 记录 ID 映射
        self.id_mapper.add_mapping(self.resource_type, pk_value)
        
        return data
    
    def export(self, bk_biz_ids: Optional[List[int]] = None) -> List[dict]:
        """
        导出资源
        
        Args:
            bk_biz_ids: 业务 ID 列表
        
        Returns:
            导出的数据列表
        """
        if not self.should_export():
            logger.info(f"Skipping export for {self.resource_type}")
            return []
        
        logger.info(f"Exporting {self.resource_type}...")
        
        objects = self.query_objects(bk_biz_ids)
        count = objects.count()
        logger.info(f"Found {count} {self.resource_type} objects to export")
        
        results = []
        for obj in objects:
            try:
                data = self.export_single(obj)
                results.append(data)
            except Exception as e:
                pk_value = self._get_primary_key_value(obj)
                logger.error(f"Failed to export {self.resource_type} {pk_value}: {e}", exc_info=True)
        
        logger.info(f"Successfully exported {len(results)}/{count} {self.resource_type} objects")
        return results


class RelationMixin:
    """
    关联对象导出混入类
    注意本方法并非主动处理关联字段， 而是由调用者传入关联对象的QuerySet
    """
    
    def export_related_queryset(self, queryset: QuerySet) -> List[dict]:
        """
        序列化 QuerySet 中的对象为字典列表

        Args:
            queryset: 已经通过外键过滤的 QuerySet（例如: Item.objects.filter(strategy_id=100)）
        
        Returns:
            序列化后的关联对象字典列表
        """
        results = []
        for obj in queryset:
            # 序列化对象
            data = model_to_dict(obj)
            # 应用适配器(如果可用)
            if hasattr(self, 'apply_adapters'):
                data = self.apply_adapters(data)
            results.append(data)
        return results
    
    def export_foreign_key(self, obj, field_name: str) -> Optional[dict]:
        """
        通过外键字段获取并序列化关联对象
        
        Args:
            obj: 主对象（包含外键字段的对象）
            field_name: 外键字段名（例如: "plugin_id"）
        
        Returns:
            序列化后的关联对象字典, 如果外键为 None 则返回 None
        """
        related_obj = getattr(obj, field_name, None)
        if related_obj is None:
            return None
        
        # 序列化对象
        data = model_to_dict(related_obj)
        # 应用适配器(如果可用)
        if hasattr(self, 'apply_adapters'):
            data = self.apply_adapters(data)
        return data
