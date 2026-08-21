from typing import Any

from monitor_web.collecting.deploy.base import BaseInstaller
from monitor_web.models import CollectConfigMeta, DeploymentConfigVersion

from .orchestrator import NodeManV3Orchestrator


class NodeManV3Installer(BaseInstaller):
    def __init__(
        self,
        collect_config: CollectConfigMeta,
        topo_tree=None,
        *,
        orchestrator: NodeManV3Orchestrator | None = None,
    ):
        super().__init__(collect_config)
        self.topo_tree = topo_tree
        self.orchestrator = orchestrator or NodeManV3Orchestrator()

    def install(self, install_config: dict, operation: str | None) -> dict:
        return self.orchestrator.install(
            collect_config=self.collect_config,
            install_config=install_config,
            operation=operation,
            topo_tree=self.topo_tree,
        )

    def upgrade(self, params: dict) -> dict:
        return self.orchestrator.upgrade(collect_config=self.collect_config, params=params, topo_tree=self.topo_tree)

    def uninstall(self):
        return self.orchestrator.uninstall(collect_config=self.collect_config, topo_tree=self.topo_tree)

    def rollback(self, deployment_config_version: int | DeploymentConfigVersion | None = None):
        return self.orchestrator.rollback(
            collect_config=self.collect_config,
            deployment_config_version=deployment_config_version,
            topo_tree=self.topo_tree,
        )

    def stop(self):
        return self.orchestrator.stop(collect_config=self.collect_config, topo_tree=self.topo_tree)

    def start(self):
        return self.orchestrator.start(collect_config=self.collect_config, topo_tree=self.topo_tree)

    def run(self, action: str | None = None, scope: dict[str, Any] | None = None):
        return self.orchestrator.run(
            collect_config=self.collect_config,
            action=action,
            scope=scope,
            topo_tree=self.topo_tree,
        )

    def retry(self, instance_ids: list[str] | None = None):
        return self.orchestrator.retry(collect_config=self.collect_config, instance_ids=instance_ids)

    def revoke(self, instance_ids: list[int] | None = None):
        return self.orchestrator.revoke(collect_config=self.collect_config, instance_ids=instance_ids)

    def status(self, *args, **kwargs):
        return self.orchestrator.status(collect_config=self.collect_config, args=args, kwargs=kwargs)

    def instance_status(self, instance_id: str):
        return self.orchestrator.instance_status(collect_config=self.collect_config, instance_id=instance_id)
