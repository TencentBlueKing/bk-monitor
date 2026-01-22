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

    说明：
    - 如果数据有 _biz_id_mapping_required 标记，说明 Export 时没有映射，需要在此处映射
    - 如果数据没有标记，说明 Export 时已经映射过了，直接使用即可
    """

    def __init__(self, config: dict):
        super().__init__(config)
        biz_id_config = config.get("biz_id_mapping", {})
        self.mapping = biz_id_config.get("mapping", {})
        # 将字符串key转换为字符串（保持一致性）
        self.mapping = {str(k): int(v) if isinstance(v, int | str) else v for k, v in self.mapping.items()}

    def adapt(self, data: Any) -> Any:
        """
        处理业务ID映射

        只处理标记了 _biz_id_mapping_required 的数据
        """
        if not isinstance(data, dict):
            return data

        # 只有当数据被标记为需要映射时才处理
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

            # 移除标记字段
            data.pop("_biz_id_mapping_required", None)

        # 如果没有标记，说明已经在 Export 时映射过了，不做任何处理
        return data


class UserInfoImportAdapter(BaseImportAdapter):
    """
    用户信息导入适配器
    """

    def __init__(self, config: dict):
        super().__init__(config)

    def adapt(self, data: Any) -> Any:
        """
        不做任何处理，直接返回数据

        用户信息已在 Export 阶段处理，这里无需重复操作
        """
        return data


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

        说明：
        - TimestampImportAdapter: 必需，反序列化时间戳
        - BizIDImportAdapter: 处理标记为需要映射的业务ID
        """
        adapters_config = self.config.get("adapters", {})

        # 1. 时间戳适配器（必需，反序列化）
        self.adapters.append(TimestampImportAdapter(adapters_config))

        # 2. 业务ID适配器（处理带标记的数据）
        if adapters_config.get("biz_id_mapping", {}).get("mapping"):
            self.adapters.append(BizIDImportAdapter(adapters_config))

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
