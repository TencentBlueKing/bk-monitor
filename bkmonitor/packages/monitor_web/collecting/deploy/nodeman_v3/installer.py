from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _

from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3AdapterPending, NodeManV3DefiniteFailure
from core.errors.collecting import CollectConfigNeedUpgrade
from monitor_web.collecting.deploy.base import BaseInstaller
from monitor_web.collecting.constant import OperationResult, OperationType
from monitor_web.models import CollectConfigMeta, DeploymentConfigVersion
from monitor_web.models.node_man import (
    NodeManBindingState,
    NodeManIntegrationBinding,
    NodeManResourceType,
    build_nodeman_resource_key,
)

from .orchestrator import NodeManV3Orchestrator
from .reconciler import CollectTargetReconciler, NodeManV3TargetExecutor


class NodeManV3Installer(BaseInstaller):
    def __init__(
        self,
        collect_config: CollectConfigMeta,
        topo_tree=None,
        *,
        orchestrator: NodeManV3Orchestrator | None = None,
        reconciler: CollectTargetReconciler | None = None,
    ):
        super().__init__(collect_config)
        self.topo_tree = topo_tree
        self.orchestrator = orchestrator or NodeManV3Orchestrator()
        self.reconciler = reconciler or CollectTargetReconciler(
            executor=NodeManV3TargetExecutor(orchestrator=self.orchestrator)
        )

    def install(self, install_config: dict, operation: str | None) -> dict:
        if self.collect_config.pk and self.collect_config.need_upgrade:
            raise CollectConfigNeedUpgrade({"msg": self.collect_config.name})

        is_create = not self.collect_config.pk
        if not is_create:
            raise NodeManV3AdapterPending(
                "deploy-policy edit protocol is available but not wired into the monitor adapter"
            )
        release_version = self._packaged_release_version()
        current_version = self.collect_config.deployment_config if self.collect_config.deployment_config_id else None
        new_version = self._create_deployment_version(
            plugin_version=release_version,
            target_node_type=install_config["target_node_type"],
            target_nodes=install_config["target_nodes"],
            params=install_config["params"],
            remote_collecting_host=install_config.get("remote_collecting_host"),
            parent_id=current_version.pk if current_version else 0,
        )
        diff_node = self._node_diff(current_version, new_version)
        last_operation = operation or (OperationType.CREATE if is_create else OperationType.EDIT)
        self._activate_version(new_version, last_operation=last_operation)
        self._reconcile(trigger=f"install:{last_operation.lower()}")
        return {
            "diff_node": diff_node,
            "can_rollback": last_operation != OperationType.CREATE,
            "id": self.collect_config.pk,
            "deployment_id": new_version.pk,
        }

    def upgrade(self, params: dict) -> dict:
        if not self.collect_config.need_upgrade:
            raise CollectConfigNeedUpgrade({"msg": _("采集配置无需升级")})
        raise NodeManV3AdapterPending(
            "deploy-policy upgrade protocol is available but not wired into the monitor adapter"
        )

    def uninstall(self):
        return self.orchestrator.uninstall(collect_config=self.collect_config, topo_tree=self.topo_tree)

    def rollback(self, deployment_config_version: int | DeploymentConfigVersion | None = None):
        del deployment_config_version
        raise NodeManV3AdapterPending(
            "deploy-policy update protocol is available but rollback is not wired into the monitor adapter"
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

    def _packaged_release_version(self):
        release_version = self.plugin.packaged_release_version
        if not release_version or not release_version.is_packaged:
            raise NodeManV3AdapterPending(
                "NodeMan V3 package import protocol is available but not wired into the collecting adapter"
            )
        return release_version

    def _create_deployment_version(
        self,
        *,
        plugin_version,
        target_node_type,
        target_nodes,
        params,
        remote_collecting_host,
        parent_id,
    ) -> DeploymentConfigVersion:
        return DeploymentConfigVersion.objects.create(
            plugin_version=plugin_version,
            target_node_type=target_node_type,
            target_nodes=target_nodes,
            params=params,
            remote_collecting_host=remote_collecting_host,
            config_meta_id=self.collect_config.pk or 0,
            parent_id=parent_id,
            subscription_id=0,
            task_ids=[],
        )

    def _activate_version(self, deployment, *, last_operation: str) -> None:
        with transaction.atomic():
            self.collect_config.deployment_config = deployment
            self.collect_config.last_operation = last_operation
            self.collect_config.operation_result = OperationResult.PREPARING
            self.collect_config.save()
            if not deployment.config_meta_id:
                deployment.config_meta_id = self.collect_config.pk
                deployment.save(update_fields=("config_meta_id", "update_time"))

    def _binding(self) -> NodeManIntegrationBinding:
        resource_key = build_nodeman_resource_key(
            NodeManResourceType.COLLECT_CONFIG,
            object_id=self.collect_config.pk,
        )
        binding, _ = NodeManIntegrationBinding.objects.get_or_create(
            resource_type=NodeManResourceType.COLLECT_CONFIG,
            resource_key=resource_key,
            owner_bk_tenant_id=self.collect_config.bk_tenant_id,
            execution_bk_tenant_id=self.collect_config.bk_tenant_id,
            bk_biz_id=self.collect_config.bk_biz_id,
        )
        if binding.state != NodeManBindingState.ACTIVE:
            binding.state = NodeManBindingState.ACTIVE
            binding.save(update_fields=("state", "updated_at"))
        return binding

    def _reconcile(self, *, trigger: str):
        try:
            result = self.reconciler.reconcile(
                binding=self._binding(),
                collect_config=self.collect_config,
                trigger=trigger,
            )
        except NodeManV3DefiniteFailure:
            self.collect_config.operation_result = OperationResult.FAILED
            self.collect_config.save(update_fields=("operation_result", "update_time"))
            raise
        if not (result.added or result.changed or result.removed or result.inflight):
            self.collect_config.operation_result = OperationResult.SUCCESS
            self.collect_config.cache_data = {"error_instance_count": 0, "total_instance_count": 0}
            self.collect_config.save(update_fields=("operation_result", "cache_data", "update_time"))
        return result

    @staticmethod
    def _node_diff(current_version, target_version) -> dict:
        if current_version:
            return current_version.show_diff(target_version)["nodes"]
        return {
            "is_modified": True,
            "added": target_version.target_nodes,
            "removed": [],
            "unchanged": [],
            "updated": [],
        }
