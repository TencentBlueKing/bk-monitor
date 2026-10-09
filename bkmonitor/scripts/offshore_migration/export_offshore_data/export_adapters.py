"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from .export_utils import recursive_process, serialize_datetime


class BaseAdapter:
    """
    基础适配器类
    """

    def __init__(self, config: dict):
        self.config = config

    def adapt(self, data: Any) -> Any:
        """
        适配数据(修改导出的数据内容)

        Args:
            data: 要适配的数据

        Returns:
            适配后的数据
        """
        raise NotImplementedError


class DomainAdapter(BaseAdapter):
    """
    域名替换适配器
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.domain_mapping = config.get("domain_mapping", {})

    def adapt(self, data: Any) -> Any:
        """
        替换数据中的域名
        """

        def replace_domain(value):
            if isinstance(value, str):
                for old_domain, new_domain in self.domain_mapping.items():
                    if old_domain in value:
                        value = value.replace(old_domain, new_domain)
            return value

        # 递归处理数据
        return recursive_process(data, replace_domain)


class TimestampAdapter(BaseAdapter):
    """
    时间戳适配器，将 datetime 转换为时间戳
    """

    def adapt(self, data: Any) -> Any:
        """
        将所有 datetime 对象转换为时间戳
        """
        return recursive_process(data, serialize_datetime)


class UserInfoAdapter(BaseAdapter):
    """
    用户信息适配器
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.strategy = config.get("user_mapping", {}).get("strategy", "keep")
        self.default_user = config.get("user_mapping", {}).get("default_user", "admin")

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


class BizIDAdapter(BaseAdapter):
    """
    业务 ID 适配器
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.biz_id_mapping = config.get("biz_id_mapping", {})
        self.auto_generate = self.biz_id_mapping.get("auto", True)
        self.manual_mapping = self.biz_id_mapping.get("mapping", {})

    def adapt(self, data: Any) -> Any:
        """
        处理业务 ID 字段

        如果启用 auto，则记录需要映射的业务 ID
        如果提供了 manual_mapping，则使用手动映射
        """
        if isinstance(data, dict) and "bk_biz_id" in data:
            original_biz_id = data["bk_biz_id"]

            # 如果有手动映射，使用手动映射
            if str(original_biz_id) in self.manual_mapping:
                data["bk_biz_id"] = self.manual_mapping[str(original_biz_id)]
            elif self.auto_generate:
                # 标记为需要映射，实际映射在导入时进行
                data["_biz_id_mapping_required"] = True

        return data


class JSONFieldAdapter(BaseAdapter):
    """
    JSON 字段适配器，递归处理 JSON 字段中的数据
    """

    def __init__(self, config: dict, other_adapters: list):
        super().__init__(config)
        self.other_adapters = other_adapters

    def adapt(self, data: Any) -> Any:
        """
        对 JSON 字段递归应用其他适配器
        """
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                # 对每个值应用所有适配器
                adapted_value = value
                if isinstance(value, dict | list):
                    for adapter in self.other_adapters:
                        adapted_value = adapter.adapt(adapted_value)
                result[key] = adapted_value
            return result
        elif isinstance(data, list):
            return [self.adapt(item) for item in data]

        return data


class AdapterManager:
    """
    适配器管理器，统一管理和应用所有适配器
    """

    def __init__(self, config: dict):
        self.config = config
        self.adapters = self._initialize_adapters()

    def _initialize_adapters(self) -> list:
        """
        初始化所有适配器
        """
        adapters_config = self.config.get("adapters", {})

        # 基础适配器（总是启用）
        adapters: list[BaseAdapter] = [
            TimestampAdapter(adapters_config),
        ]

        # 可选适配器（根据配置启用）
        if adapters_config.get("domain_mapping"):
            adapters.append(DomainAdapter(adapters_config))

        if adapters_config.get("user_mapping"):
            adapters.append(UserInfoAdapter(adapters_config))

        if adapters_config.get("biz_id_mapping"):
            adapters.append(BizIDAdapter(adapters_config))

        # JSON 字段适配器需要引用其他适配器，所以最后添加
        json_adapter = JSONFieldAdapter(adapters_config, adapters)
        adapters.append(json_adapter)

        return adapters

    def apply_adapters(self, data: Any) -> Any:
        """
        对数据应用所有适配器
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
