from abc import ABC, abstractmethod
from typing import Any, ClassVar

from typing_extensions import override

from bk_monitor_base.domains.metric_plugin.define import MetricPluginMetricGroup
from bk_monitor_base.domains.metric_plugin.manager.base import BaseMetricPluginManager, OSType


class BuiltInPluginManager(BaseMetricPluginManager, ABC):
    """内置插件管理器基类"""

    type: ClassVar[str] = "built_in"

    @classmethod
    @abstractmethod
    def get_metric_info(cls, **kwargs: Any) -> list[MetricPluginMetricGroup]:
        """获取插件的指标信息

        Args:
            **kwargs: 子类特定的参数，如rules、label等

        Returns:
            指标组列表
        """

    @classmethod
    @abstractmethod
    def create_built_in_plugin(
        cls, bk_tenant_id: str, bk_biz_id: int, operator: str, **kwargs: Any
    ) -> "BuiltInPluginManager":
        """创建内置插件

        Args:
            bk_tenant_id: 租户ID
            bk_biz_id: 业务ID
            operator: 操作人
            **kwargs: 子类特定的额外参数

        Returns:
            BuiltInPluginManager: 内置插件管理器实例
        """
        raise NotImplementedError(f"{cls.__name__} must implement 'create_built_in_plugin' class method.")

    @override
    def get_supported_os_types(self) -> list[OSType]:
        """获取支持的操作系统类型。"""
        # 内置插件不依赖外部插件包，不需要声明 OS 白名单。
        return []

    @override
    def register(self, operator: str) -> list[str]:
        """注册插件。"""
        return []

    @override
    @classmethod
    def _parse_define(
        cls,
        bk_tenant_id: str,
        operator: str,
        extract_dir: Any,
        plugin_id: str,
        meta_data: dict[str, Any],
    ) -> dict[str, Any]:
        """解析插件定义。"""
        raise NotImplementedError("内置插件不支持通过插件包解析 define")

    @override
    def export_package(self, operator: str) -> str:
        """导出插件包。"""
        raise NotImplementedError("内置插件不支持导出插件包")

    @abstractmethod
    def get_deploy_steps_params(
        self,
        bk_biz_id: int,
        collect_task_id: int,
        bk_data_ids: dict[str, int],
        collect_params: dict[str, Any],
        plugin_params: dict[str, Any],
        target_nodes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """获取部署步骤参数

        Args:
            collect_params: 采集参数，如采集周期，超时时间，绑定IP/端口，可以理解为内置参数
            plugin_params: 插件定义参数，用户自定义的参数
            target_nodes: 采集目标节点

        Returns:
            部署步骤参数列表
        """

    @override
    @abstractmethod
    def apply_data_link(self, operator: str) -> dict[str, Any]:
        """申请数据链路

        Args:
            operator: 操作人

        Returns:
            数据链路申请结果，包含申请的数据ID等信息
        """

    def get_data_ids(self, bk_biz_id: int) -> dict[str, int]:  # pyright: ignore[reportUnusedParameter]
        """获取内置插件数据 ID。

        内置插件在发布时会将数据 ID 写入 ``related_params``。部署阶段直接复用这些值，
        避免再次向 metadata 推断或创建。

        Args:
            bk_biz_id: 业务 ID。内置插件当前无需使用，保留参数以兼容统一调用入口。

        Returns:
            dict[str, int]: ``related_params`` 中所有 ``*_data_id`` 字段。

        Raises:
            ValueError: 当插件尚未申请数据链路，找不到任何数据 ID 时抛出。
        """
        data_ids = {
            key: value
            for key, value in self.plugin.related_params.items()
            if key.endswith("_data_id") and isinstance(value, int)
        }
        if not data_ids:
            raise ValueError(f"内置插件缺少数据ID: {self.plugin.id}")
        return data_ids
