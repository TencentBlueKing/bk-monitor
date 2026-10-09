"""监控的节点控制能力；不暴露远端订阅、Workflow 或 API 路由。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PluginOperation:
    """已提交的操作引用，不代表机器安装成功。"""

    operation_id: str


class HostQueries(ABC):
    """监控使用的主机查询能力，输出保持监控现有主机展示字段。"""

    @abstractmethod
    def proxies(self, bk_tenant_id: str, bk_cloud_id: int) -> list[dict[str, Any]]:
        """查询云区域的 Proxy。"""

    @abstractmethod
    def business_proxies(self, bk_tenant_id: str, bk_biz_id: int) -> list[dict[str, Any]]:
        """查询业务使用的云区域中的 Proxy，不按 Proxy 所属业务筛选。"""

    @abstractmethod
    def details(self, bk_tenant_id: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """按监控 IP 选择器的主机和资源范围查询详情与 Agent 状态。"""


class OfficialPlugins(ABC):
    """独立官方插件部署能力，与 V2 采集器 Ensure 分离。"""

    @abstractmethod
    def install(self, bk_tenant_id: str, name: str, version: str, host_ids: list[int]) -> PluginOperation:
        """提交指定主机上的插件安装。"""
