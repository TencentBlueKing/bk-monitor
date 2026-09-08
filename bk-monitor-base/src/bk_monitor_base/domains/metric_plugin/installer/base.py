import abc
from typing import Any

from bk_monitor_base.domains.metric_plugin.define import (
    MetricPlugin,
    MetricPluginDeployment,
    MetricPluginDeploymentScope,
    MetricPluginDeploymentVersion,
)
from bk_monitor_base.domains.metric_plugin.errors import MetricPluginNotFoundError
from bk_monitor_base.domains.metric_plugin.models import (
    MetricPluginDeploymentModel,
    MetricPluginDeploymentVersionModel,
    MetricPluginModel,
)


class BaseInstaller(abc.ABC):
    """安装器基类"""

    plugin_manager: Any

    def __init__(self, deployment: MetricPluginDeployment, operator: str):
        """
        Args:
            deployment: 指标插件部署项
            operator: 操作者

        Raises:
            MetricPluginNotFoundError: 插件不存在
        """
        self.operator: str = operator
        self.deployment: MetricPluginDeployment = deployment
        self.deployment_version: MetricPluginDeploymentVersion | None = None

        try:
            plugin_model = MetricPluginModel.objects.get(
                bk_tenant_id=deployment.bk_tenant_id,
                plugin_id=deployment.plugin_id,
                is_deleted=False,
            )
        except MetricPluginModel.DoesNotExist as e:
            raise MetricPluginNotFoundError(f"插件不存在: {deployment.bk_tenant_id}/{deployment.plugin_id}") from e

        self.plugin: MetricPlugin = plugin_model.to_plugin()

    def _get_current_deployment_version(self) -> MetricPluginDeploymentVersion | None:
        """获取当前部署项版本"""
        return MetricPluginDeploymentModel.objects.get(id=self.deployment.id).get_current_version()

    def _save(self):
        """部署项保存

        Note:
            1. 保存部署项信息 self.deployment
            2. 保存部署项版本信息 self.deployment_version
        """
        deployment_model = MetricPluginDeploymentModel.objects.get(id=self.deployment.id)
        deployment_model.related_params = self.deployment.related_params
        deployment_model.status = self.deployment.status
        deployment_model.save(update_fields=["related_params", "status"])

        if self.deployment_version:
            remote_scope = self.deployment_version.remote_scope
            plugin_version = (
                f"{self.deployment_version.plugin_version.major}.{self.deployment_version.plugin_version.minor}"
            )
            MetricPluginDeploymentVersionModel.objects.update_or_create(
                bk_tenant_id=self.deployment.bk_tenant_id,
                bk_biz_id=self.deployment.bk_biz_id,
                deployment=deployment_model,
                version=self.deployment_version.version,
                defaults={
                    "plugin_version": plugin_version,
                    "params": self.deployment_version.params,
                    "target_node_type": self.deployment_version.target_scope.node_type,
                    "target_nodes": self.deployment_version.target_scope.nodes,
                    "remote_node_type": remote_scope.node_type if remote_scope else "",
                    "remote_nodes": remote_scope.nodes if remote_scope else [],
                    "target_instances": self.deployment_version.target_instances,
                    "remote_instances": self.deployment_version.remote_instances,
                    "created_by": self.operator,
                },
            )

    @staticmethod
    def get_version_diff(
        current_version: MetricPluginDeploymentVersion | None, new_version: MetricPluginDeploymentVersion
    ) -> tuple[bool, dict[str, Any]]:
        """比对版本差异

        Note:
            1. 插件版本号差异
            2. 部署参数差异
            3. 远程采集范围差异
            4. 采集目标范围差异

        Args:
            current_version: 当前版本，如果为 None，则说明没有当前版本
            new_version: 新版本

        Returns:
            is_modified (bool): 是否存在差异
            diff_result: dict[str, Any] 差异比对结果
                - plugin_version: dict[str, Any] 插件版本号差异
                    - is_modified (bool): 是否存在差异
                    - before (Any): 旧值
                    - after (Any): 新值
                - params: dict[str, Any] 部署参数差异
                    - is_modified (bool): 是否存在差异
                    - before (Any): 旧值
                    - after (Any): 新值
                - remote_scope: dict[str, Any] 远程采集范围差异
                    - is_modified (bool): 是否存在差异
                    - before (Any): 旧值
                    - after (Any): 新值
                - target_scope: dict[str, Any] 采集目标范围差异
                    - is_modified (bool): 是否存在差异
                    - before (Any): 旧值
                    - after (Any): 新值
        """

        diff_result: dict[str, Any] = {
            "plugin_version": {"is_modified": False, "before": None, "after": None},
            "params": {"is_modified": False, "before": None, "after": None},
            "remote_scope": {"is_modified": False, "before": None, "after": None},
            "target_scope": {"is_modified": False, "before": None, "after": None},
        }

        # 插件版本号差异
        if not current_version or current_version.plugin_version != new_version.plugin_version:
            diff_result["plugin_version"]["is_modified"] = True
            diff_result["plugin_version"]["before"] = current_version.plugin_version if current_version else None
            diff_result["plugin_version"]["after"] = new_version.plugin_version

        # 部署参数差异
        if not current_version or current_version.params != new_version.params:
            diff_result["params"]["is_modified"] = True
            diff_result["params"]["before"] = current_version.params if current_version else None
            diff_result["params"]["after"] = new_version.params

        # 远程采集范围差异
        if not current_version or current_version.remote_scope != new_version.remote_scope:
            diff_result["remote_scope"]["is_modified"] = True
            diff_result["remote_scope"]["before"] = current_version.remote_scope if current_version else None
            diff_result["remote_scope"]["after"] = new_version.remote_scope

        # 采集目标范围差异
        if not current_version or current_version.target_scope != new_version.target_scope:
            diff_result["target_scope"]["is_modified"] = True
            diff_result["target_scope"]["before"] = current_version.target_scope if current_version else None
            diff_result["target_scope"]["after"] = new_version.target_scope

        is_modified: bool = any(diff_result[key]["is_modified"] for key in diff_result.keys())

        return is_modified, diff_result

    @abc.abstractmethod
    def install(self, deployment_version: MetricPluginDeploymentVersion) -> Any:
        """安装特定的部署版本

        Note:
            1. 比对当前部署版本与新部署版本，比对差异
            2. 如果相同，则跳过/重试
            3. 如果不同，创建新的部署版本记录，并设置为当前版本
            4. 执行安装/重试操作
            5. 返回差异比对结果

        Args:
            deployment_version: 部署版本
        """

    @abc.abstractmethod
    def uninstall(self):
        """
        卸载
        """

    @abc.abstractmethod
    def stop(self):
        """
        停止
        """

    @abc.abstractmethod
    def start(self):
        """
        启动
        """

    @abc.abstractmethod
    def run(self, action: str | None = None, scope: MetricPluginDeploymentScope | None = None) -> Any:
        """
        主动执行操作

        Args:
            action: 操作类型，根据插件类型自定义
            scope: 操作范围，如果为 None，则为全部
        """

    @abc.abstractmethod
    def retry(self, scope: MetricPluginDeploymentScope | None = None) -> Any:
        """
        重试

        Args:
            scope: 操作范围，如果为 None，则为全部
        """

    @abc.abstractmethod
    def revoke(self, scope: MetricPluginDeploymentScope | None = None) -> Any:
        """
        终止
        """

    @abc.abstractmethod
    def status(self, *args: Any, **kwargs: Any) -> Any:
        """
        状态
        """
