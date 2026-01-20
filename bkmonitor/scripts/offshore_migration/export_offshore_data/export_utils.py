"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any


def serialize_datetime(value: Any) -> Any:
    """
    将 datetime 对象转换为时间戳
    """
    if isinstance(value, datetime):
        return int(value.timestamp())
    return value


def serialize_decimal(value: Any) -> Any:
    """
    将 Decimal 对象转换为 float
    """
    if isinstance(value, Decimal):
        return float(value)
    return value


def model_to_dict(instance) -> dict:
    """
    将 Django Model 实例转换为字典
    
    Args:
        instance: Django Model 实例
    
    Returns:
        字典表示的模型数据
    """
    data = {}
    opts = instance._meta
    
    for field in opts.fields:
        field_name = field.name
        
        value = getattr(instance, field_name, None)
        
        # 处理外键字段：导出ID而不是对象
        if hasattr(field, 'related_model') and field.related_model:
            if value is not None:
                # 获取外键对象的ID
                value = value.pk if hasattr(value, 'pk') else value
            data[field_name] = value
            continue
        
        # 处理 None 值
        if value is None:
            data[field_name] = None
            continue
        
        # 处理特殊类型
        value = serialize_datetime(value)
        value = serialize_decimal(value)
        
        data[field_name] = value
    
    return data


def recursive_process(data: Any, processor_func) -> Any:
    """
    递归处理数据结构，对所有值应用处理函数
    
    Args:
        data: 要处理的数据
        processor_func: 处理函数，接收单个值并返回处理后的值
    
    Returns:
        处理后的数据
    """
    if isinstance(data, dict):
        return {key: recursive_process(value, processor_func) for key, value in data.items()}
    elif isinstance(data, (list, tuple)):
        return [recursive_process(item, processor_func) for item in data]
    else:
        return processor_func(data)


def safe_json_dumps(data: Any, **kwargs) -> str:
    """
    安全地序列化 JSON，处理特殊类型
    """
    class CustomEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime):
                return int(obj.timestamp())
            if isinstance(obj, Decimal):
                return float(obj)
            if isinstance(obj, set):
                return list(obj)
            if isinstance(obj, bytes):
                try:
                    return obj.decode('utf-8')
                except:
                    return str(obj)
            # 处理其他不可序列化的对象
            try:
                return str(obj)
            except:
                return None
    
    return json.dumps(data, cls=CustomEncoder, **kwargs)


def safe_json_loads(json_str: str) -> Any:
    """
    安全地反序列化 JSON
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        raise ValueError(f"Invalid JSON string: {e}")


class IDMapper:
    """
    ID 映射器，用于记录导出时的原始 ID 和导入时的新 ID 映射关系
    防止数据关联时， 由于id变化导致的错误
    """
    
    def __init__(self):
        self.mappings: dict[str, dict[str, Any]] = {}
    
    def add_mapping(self, resource_type: str, original_id: Any):
        """
        添加 ID 映射
        
        Args:
            resource_type: 资源类型
            original_id: 原始 ID
        """
        if resource_type not in self.mappings:
            self.mappings[resource_type] = {}
        self.mappings[resource_type][str(original_id)] = None
    
    def get_mappings(self) -> dict:
        """
        获取所有映射关系
        """
        return self.mappings
    
    def to_dict(self) -> dict:
        """
        转换为字典格式
        """
        return {
            "id_mapping": self.mappings
        }


# 资源导出顺序定义（按依赖关系排序）
EXPORT_ORDER = [
    # 基础资源（无依赖）
    "action_plugin",
    "collector_plugin",
    "duty_rule",
    
    # 告警处理相关
    "user_group",
    "action_config",
    
    # 数据采集相关
    "custom_ts_group",
    "custom_ts_table",
    "collect_config",
    
    # 告警配置相关
    "strategy",
    "shield",
    "alert_assign_group",
    
    # 仪表盘
    "dashboard",
]


# Model 导入映射
MODEL_IMPORTS = {
    "strategy": ("bkmonitor.models.strategy", "StrategyModel"),
    "item": ("bkmonitor.models", "Item"),
    "detect": ("bkmonitor.models.strategy", "DetectModel"),
    "algorithm": ("bkmonitor.models.strategy", "AlgorithmModel"),
    "user_group": ("bkmonitor.models.strategy", "UserGroup"),
    "duty_rule": ("bkmonitor.models.strategy", "DutyRule"),
    "duty_arrange": ("bkmonitor.models.strategy", "DutyArrange"),
    "action_config": ("bkmonitor.models.fta.action", "ActionConfig"),
    "action_plugin": ("bkmonitor.models.fta.action", "ActionPlugin"),
    "alert_assign_group": ("bkmonitor.models.fta.assign", "AlertAssignGroup"),
    "alert_assign_rule": ("bkmonitor.models.fta.assign", "AlertAssignRule"),
    "shield": ("bkmonitor.models", "Shield"),
    "dashboard": ("bk_dataview.models", "Dashboard"),
    "data_source": ("bk_dataview.models", "DataSource"),
    "collect_config": ("monitor_web.models.collecting", "CollectConfigMeta"),
    "collector_plugin": ("monitor_web.models.plugin", "CollectorPluginMeta"),
    "custom_ts_table": ("monitor_web.models.custom_report", "CustomTSTable"),
    "custom_ts_field": ("monitor_web.models.custom_report", "CustomTSField"),
    "custom_ts_group": ("metadata.models.custom_report.time_series", "TimeSeriesGroup"),
}
