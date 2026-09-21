from bk_monitor_base.domains.metric_plugin.define import MetricPluginDeployment
from bk_monitor_base.domains.metric_plugin.installer.base import BaseInstaller
from bk_monitor_base.domains.metric_plugin.installer.job import SQLInstaller
from bk_monitor_base.domains.metric_plugin.installer.k8s import K8sInstaller
from bk_monitor_base.domains.metric_plugin.installer.nodeman import NodemanInstaller
from bk_monitor_base.domains.metric_plugin.models import MetricPluginModel
from bk_monitor_base.nodeman import NodeManBackend, UnsupportedNodeManBackend

INSTALLERS: dict[str, type[BaseInstaller]] = {
    # 目前默认使用 NodemanInstaller，后续可以扩展
    "default": NodemanInstaller,
    "script": NodemanInstaller,
    "datadog": NodemanInstaller,
    "pushgateway": NodemanInstaller,
    "jmx": NodemanInstaller,
    "exporter": NodemanInstaller,
    "job_mysql": SQLInstaller,
    "job_oracle": SQLInstaller,
    "job_db2": SQLInstaller,
    "k8s": K8sInstaller,
    "job_mssql": SQLInstaller,
}

NODEMAN_INSTALLERS: dict[str, type[BaseInstaller]] = {NodeManBackend.V2: NodemanInstaller}


def get_installer(deployment: MetricPluginDeployment, operator: str) -> BaseInstaller:
    """获取安装器

    Args:
        deployment: 部署项
        operator: 操作者

    Returns:
        BaseInstaller: 安装器实例
    """
    # 这里可以根据 deployment 关联 plugin 的 type 来决定使用哪个 installer
    plugin_id = deployment.plugin_id
    plugin = MetricPluginModel.objects.filter(bk_tenant_id=deployment.bk_tenant_id, plugin_id=plugin_id).first()
    if not plugin:
        raise ValueError(f"插件不存在: {plugin_id}")

    installer_class = INSTALLERS.get(plugin.type, INSTALLERS["default"])
    if installer_class is NodemanInstaller:
        # 历史记录无标记时固定解释为 V2，不读取环境级默认值。
        backend = deployment.related_params.get("nodeman_backend", NodeManBackend.V2)
        try:
            installer_class = NODEMAN_INSTALLERS[backend]
        except KeyError:
            raise UnsupportedNodeManBackend(f"采集后端尚未支持: {backend}") from None
    return installer_class(deployment=deployment, operator=operator)
