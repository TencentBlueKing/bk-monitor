"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import datetime
from typing import Any

from scripts.offshore_migration.export_offshore_data.export_utils import recursive_process


class BaseImportAdapter:
    """
    基础导入适配器类
    """
    
    def __init__(self, config: dict):
        self.config = config
    
    def adapt(self, data: Any) -> Any:
        """
        适配数据（将导出格式转换为导入格式）
        
        Args:
            data: 要适配的数据
        
        Returns:
            适配后的数据
        """
        raise NotImplementedError


class TimestampImportAdapter(BaseImportAdapter):
    """
    时间戳导入适配器，将时间戳转换为 datetime
    """
    
    def adapt(self, data: Any) -> Any:
        """
        将时间戳转换为 datetime 对象
        """
        def convert_timestamp(value):
            if isinstance(value, int) and value > 0:
                # 判断是否是时间戳（通常时间戳是10位或13位数字）
                # 10位：秒级时间戳（2001-09-09 之后）
                # 13位：毫秒级时间戳
                if 1000000000 <= value <= 9999999999:
                    # 10位时间戳（秒）
                    return datetime.fromtimestamp(value)
                elif 1000000000000 <= value <= 9999999999999:
                    # 13位时间戳（毫秒）
                    return datetime.fromtimestamp(value / 1000)
            return value
        
        return recursive_process(data, convert_timestamp)


class BizIDImportAdapter(BaseImportAdapter):
    """
    业务ID导入适配器，处理业务ID映射
    """
    
    def __init__(self, config: dict):
        super().__init__(config)
        biz_id_config = config.get("biz_id_mapping", {})
        self.mapping = biz_id_config.get("mapping", {})
        # 将字符串key转换为字符串（保持一致性）
        self.mapping = {str(k): int(v) if isinstance(v, (int, str)) else v for k, v in self.mapping.items()}
    
    def adapt(self, data: Any) -> Any:
        """
        处理业务ID映射
        """
        if not isinstance(data, dict):
            return data
        
        # 检查是否需要业务ID映射
        if data.get("_biz_id_mapping_required"):
            original_biz_id = data.get("bk_biz_id")
            if original_biz_id is not None:
                new_biz_id = self.mapping.get(str(original_biz_id))
                if new_biz_id is None:
                    raise ValueError(
                        f"需要提供业务ID映射: 原始业务ID {original_biz_id} 没有对应的映射关系。"
                        f"请在配置文件的 biz_id_mapping.mapping 中添加映射。"
                    )
                data["bk_biz_id"] = new_biz_id
        
        # 无论什么情况都移除标记字段（确保不会传递到模型创建）
        data.pop("_biz_id_mapping_required", None)
        
        return data


class UserInfoImportAdapter(BaseImportAdapter):
    """
    用户信息导入适配器
    """
    
    def __init__(self, config: dict):
        super().__init__(config)
        user_config = config.get("user_mapping", {})
        self.strategy = user_config.get("strategy", "keep")
        self.default_user = user_config.get("default_user", "admin")
    
    def adapt(self, data: Any) -> Any:
        """
        处理用户字段
        """
        if not isinstance(data, dict):
            return data
        
        user_fields = ["create_user", "update_user", "created_by", "updated_by"]
        
        for field in user_fields:
            if field in data:
                if self.strategy == "replace":
                    data[field] = self.default_user
                elif self.strategy == "remove":
                    data[field] = ""
                # strategy == "keep" 时不做处理
        
        return data


class DomainImportAdapter(BaseImportAdapter):
    """
    域名导入适配器（通常不需要，但保留接口）
    """
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.domain_mapping = config.get("domain_mapping", {})
    
    def adapt(self, data: Any) -> Any:
        """
        替换域名（如果需要反向替换）
        """
        if not self.domain_mapping:
            return data
        
        def replace_domain(value):
            if isinstance(value, str):
                # 反向替换：新域名 -> 旧域名（如果需要）
                for new_domain, old_domain in self.domain_mapping.items():
                    if new_domain in value:
                        value = value.replace(new_domain, old_domain)
            return value
        
        return recursive_process(data, replace_domain)


class ImportAdapterManager:
    """
    导入适配器管理器
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.adapters = []
        self._initialize_adapters()
    
    def _initialize_adapters(self):
        """
        初始化适配器
        """
        adapters_config = self.config.get("adapters", {})
        
        # 1. 时间戳适配器（必需）
        self.adapters.append(TimestampImportAdapter(adapters_config))
        
        # 2. 业务ID适配器（如果配置了映射）
        if adapters_config.get("biz_id_mapping", {}).get("mapping"):
            self.adapters.append(BizIDImportAdapter(adapters_config))
        
        # 3. 用户信息适配器（如果配置了策略）
        user_mapping = adapters_config.get("user_mapping", {})
        if user_mapping.get("strategy") in ["replace", "remove"]:
            self.adapters.append(UserInfoImportAdapter(adapters_config))
        
        # 4. 域名适配器（通常不需要，但保留）
        if adapters_config.get("domain_mapping"):
            self.adapters.append(DomainImportAdapter(adapters_config))
    
    def apply_adapters(self, data: Any) -> Any:
        """
        应用所有适配器
        
        Args:
            data: 原始数据
        
        Returns:
            适配后的数据
        """
        result = data
        for adapter in self.adapters:
            result = adapter.adapt(result)
        return result
    
    def get_applied_adapter_names(self) -> list[str]:
        """
        获取已应用的适配器名称列表
        """
        return [adapter.__class__.__name__ for adapter in self.adapters]
