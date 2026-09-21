from abc import ABC, abstractmethod

from bk_monitor_base.domains.metric_plugin.define import MetricPlugin
from bk_monitor_base.domains.metric_plugin.errors import MetricPluginNotFoundError
from bk_monitor_base.domains.metric_plugin.models import MetricPluginModel

PLUGIN_REVERSED_DIMENSION = [
    ("bk_target_ip", "目标IP"),
    ("bk_target_cloud_id", "云区域ID"),
    ("bk_target_topo_level", "拓扑层级"),
    ("bk_target_topo_id", "拓扑ID"),
    ("bk_collect_config_id", "采集配置ID"),
    ("bk_target_host_id", "目标主机ID"),
    ("bk_host_id", "采集主机ID"),
    ("bk_biz_id", "业务ID"),
    ("bk_supplier_id", "开发商ID"),
    ("bk_cloud_id", "采集器云区域ID"),
    ("ip", "采集器IP"),
    ("bk_cmdb_level", "CMDB层级信息"),
    ("bk_agent_id", "Agent ID"),
]


class MetricPluginDataLinker(ABC):
    """指标插件数据链路"""

    def __init__(self, plugin: MetricPlugin, plugin_model: MetricPluginModel | None = None):
        self.plugin: MetricPlugin = plugin
        if not plugin_model:
            plugin_model = MetricPluginModel.objects.filter(
                bk_tenant_id=self.plugin.bk_tenant_id, plugin_id=self.plugin.id
            ).first()
            if not plugin_model:
                raise MetricPluginNotFoundError(f"插件不存在: {self.plugin.bk_tenant_id}/{self.plugin.id}")
        self.plugin_model: MetricPluginModel = plugin_model

    @abstractmethod
    def apply_data_ids(self, operator: str) -> None:
        """申请数据ID"""

    @abstractmethod
    def apply_result_tables(self, operator: str) -> None:
        """申请结果表"""

    @abstractmethod
    def delete_data_ids(self) -> None:
        """删除数据ID"""

    @abstractmethod
    def delete_result_tables(self) -> None:
        """删除结果表"""
