"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import hashlib
from datetime import date, datetime
from typing import Any, Optional


def generate_import_hash(data: dict) -> str:
    """
    生成导入标记哈希值（用于识别已导入的数据，避免重复导入）
    基于原始ID和导出时间生成唯一标识
    
    Args:
        data: 包含 _metadata 的数据字典
    
    Returns:
        MD5 哈希值字符串
    
    Example:
        >>> data = {"_metadata": {"original_id": 123, "export_time": "2024-01-01"}}
        >>> hash_value = generate_import_hash(data)
        >>> # 可以将 hash_value 存储到模型的某个字段中，用于后续检查是否已导入
    """
    original_id = data.get("_metadata", {}).get("original_id")
    export_time = data.get("_metadata", {}).get("export_time", "")
    
    # 使用 original_id + export_time 生成唯一标识
    unique_str = f"import_{original_id}_{export_time}"
    return hashlib.md5(unique_str.encode()).hexdigest()


def convert_datetime_to_string(data: Any) -> Any:
    """
    递归遍历数据结构，将所有 datetime 和 date 对象转换为 ISO 格式字符串
    
    Args:
        data: 任意数据结构（dict、list、datetime、date 或其他）
    
    Returns:
        转换后的数据结构
    """
    if isinstance(data, datetime):
        return data.isoformat()
    elif isinstance(data, date):
        return data.isoformat()
    elif isinstance(data, dict):
        return {k: convert_datetime_to_string(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_datetime_to_string(item) for item in data]
    else:
        return data


class ImportIDMapper:
    """
    导入ID映射器，用于维护原始ID到新ID的映射关系
    在导入过程中，当创建新对象后，记录原始ID到新ID的映射
    用于后续关联数据的导入时，将原始ID转换为新ID
    
    @deprecated: 在全量迁移模式下，ID 保持不变，此类已不再使用。
    保留此类定义仅为向后兼容，新代码不应使用。
    """
    
    def __init__(self):
        self.mappings: dict[str, dict[str, Any]] = {}
    
    def add_mapping(self, resource_type: str, original_id: Any, new_id: Any):
        """
        添加 ID 映射
        
        Args:
            resource_type: 资源类型
            original_id: 原始 ID
            new_id: 新 ID
        """
        if resource_type not in self.mappings:
            self.mappings[resource_type] = {}
        self.mappings[resource_type][str(original_id)] = new_id
    
    def get_new_id(self, resource_type: str, original_id: Any) -> Optional[Any]:
        """
        获取新ID
        
        Args:
            resource_type: 资源类型
            original_id: 原始 ID
        
        Returns:
            新ID，如果不存在则返回 None
        """
        if resource_type not in self.mappings:
            return None
        return self.mappings[resource_type].get(str(original_id))
    
    def update_mapping(self, resource_type: str, original_id: Any, new_id: Any):
        """
        更新 ID 映射
        
        Args:
            resource_type: 资源类型
            original_id: 原始 ID
            new_id: 新 ID
        """
        self.add_mapping(resource_type, original_id, new_id)
    
    def to_dict(self) -> dict:
        """
        转换为字典格式
        """
        return {
            "id_mapping": self.mappings
        }
    
    def from_dict(self, data: dict):
        """
        从字典加载映射关系（用于初始化）
        
        Args:
            data: 包含 id_mapping 的字典
        
        注意：导出文件中的 id_mapping 值都是 None（因为导出时还不知道导入后的新ID）
        这里只初始化资源类型的键，不加载 None 值，让导入过程中动态填充实际的新ID
        """
        id_mapping = data.get("id_mapping", {})
        # 只初始化资源类型的键，不加载 None 值
        # 实际的 original_id -> new_id 映射会在导入过程中动态添加
        for resource_type in id_mapping.keys():
            if resource_type not in self.mappings:
                self.mappings[resource_type] = {}