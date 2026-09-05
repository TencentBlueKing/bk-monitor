from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _

from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3DefiniteFailure, NodeManV3PayloadError
from core.errors.collecting import CollectConfigNeedUpgrade
from monitor_web.collecting.deploy.base import BaseInstaller
from monitor_web.collecting.constant import OperationResult, OperationType
from monitor_web.models import CollectConfigMeta, DeploymentConfigVersion
from monitor_web.models.node_man import (
    NodeManIntegrationBinding,
    NodeManResourceType,
    build_nodeman_resource_key,
)

from .orchestrator import NodeManV3Orchestrator
from .reconciler import CollectDeployPolicyReconciler
from .validation import NodeManV3CapabilityBlocked


class NodeManV3Installer(BaseInstaller):
    def __init__(
        self,
        collect_config: CollectConfigMeta,
        topo_tree=None,
        *,
        orchestrator: NodeManV3Orchestrator | None = None,
        reconciler: CollectDeployPolicyReconciler | None = None,
    ):
        super().__init__(collect_config)
        self.topo_tree = topo_tree
        self.orchestrator = orchestrator or NodeManV3Orchestrator()
        self.reconciler = reconciler or CollectDeployPolicyReconciler()

    @transaction.atomic
    def install(self, install_config: dict, operation: str | None) -> dict:
        self._validate_active_collection()
        release_version = self._packaged_release_version()
        current_version = self.collect_config.deployment_config if self.collect_config.deployment_config_id else None
        if current_version and current_version.plugin_version.config_version < release_version.config_version:
            raise CollectConfigNeedUpgrade({"msg": self.collect_config.name})

        is_create = not self.collect_config.pk
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
            "can_rollback": False,
            "id": self.collect_config.pk,
            "deployment_id": new_version.pk,
        }

    @transaction.atomic
    def upgrade(self, params: dict) -> dict:
        self._validate_active_collection()
        release_version = self._packaged_release_version()
        current_version = self.collect_config.deployment_config
        # V2 need_upgrade depends on cached member counts. NodeMan now owns those members.
        if current_version.plugin_version.config_version >= release_version.config_version:
            raise CollectConfigNeedUpgrade({"msg": _("采集配置无需升级")})
        params["collector"]["period"] = current_version.params["collector"]["period"]
        params["collector"]["timeout"] = current_version.params["collector"].get("timeout", 60)
        new_version = self._create_deployment_version(
            plugin_version=release_version,
            target_node_type=current_version.target_node_type,
            target_nodes=current_version.target_nodes,
            params=params,
            remote_collecting_host=current_version.remote_collecting_host,
            parent_id=current_version.pk,
        )
        self._activate_version(new_version, last_operation=OperationType.UPGRADE)
        self._reconcile(trigger="upgrade")
        return {"id": self.collect_config.pk, "deployment_id": new_version.pk}

    def uninstall(self):
        return self.orchestrator.uninstall(collect_config=self.collect_config, topo_tree=self.topo_tree)

    def rollback(self, deployment_config_version: int | DeploymentConfigVersion | None = None):
        del deployment_config_version
        raise NodeManV3CapabilityBlocked(
            "deploy-policy rollback and replacement semantics are absent from the NodeMan V3 protocol"
        )

    def stop(self):
        return self.orchestrator.stop(collect_config=self.collect_config, topo_tree=self.topo_tree)

    def start(self):
        return self.orchestrator.start(collect_config=self.collect_config, topo_tree=self.topo_tree)

    def run(self, action: str | None = None, scope: dict[str, Any] | None = None):
        if scope or (action or "INSTALL").upper() != "INSTALL":
            raise NodeManV3CapabilityBlocked("DeployPolicy execute has no scoped execution or action override protocol")
        return self._reconcile(trigger="run", force=True)

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
            raise NodeManV3PayloadError("the collection plugin has no packaged NodeMan V3 release")
        return release_version

    def _validate_active_collection(self):
        if self.collect_config.last_operation == OperationType.STOP:
            raise NodeManV3CapabilityBlocked(
                "editing or upgrading a stopped collection must preserve its reverse desired state; "
                "the DeployPolicy reverse field is not defined"
            )

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
        return binding

    def _reconcile(self, *, trigger: str, force: bool = False):
        try:
            result = self.reconciler.reconcile(
                binding=self._binding(),
                collect_config=self.collect_config,
                trigger=trigger,
                force=force,
            )
        except NodeManV3DefiniteFailure:
            self.collect_config.operation_result = OperationResult.FAILED
            self.collect_config.save(update_fields=("operation_result", "update_time"))
            raise
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
