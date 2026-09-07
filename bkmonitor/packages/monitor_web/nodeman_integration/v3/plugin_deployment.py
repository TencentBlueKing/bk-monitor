from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3PayloadError
from monitor_web.models.node_man import NodeManResourceType, build_nodeman_resource_key
from monitor_web.nodeman_integration.v3.policy import (
    DeployPolicySubmission,
    NodeManV3PolicyService,
)


@dataclass(frozen=True)
class PluginHostDeployment:
    bk_host_id: int
    submission: DeployPolicySubmission


class NodeManV3PluginDeploymentService:
    """Ensure one independently managed plugin DeployPolicy per target host."""

    SUPPORTED_RESOURCE_TYPES = {
        NodeManResourceType.PROXY_PLUGIN_DEPLOYMENT,
        NodeManResourceType.OFFICIAL_PLUGIN_DEPLOYMENT,
    }

    def __init__(self, *, policy_service=None):
        self.policy_service = policy_service or NodeManV3PolicyService()

    def ensure_hosts(
        self,
        *,
        resource_type: str,
        owner_bk_tenant_id: str,
        execution_bk_tenant_id: str,
        bk_biz_id: int,
        plugin_name: str,
        plugin_version: str,
        bk_host_ids: list[int],
        bk_cloud_id: int | None = None,
    ) -> list[PluginHostDeployment]:
        resource_type = NodeManResourceType(resource_type)
        if resource_type not in self.SUPPORTED_RESOURCE_TYPES:
            raise NodeManV3PayloadError(f"unsupported plugin deployment resource type: {resource_type}")
        if not plugin_name or not plugin_version:
            raise NodeManV3PayloadError("plugin name and version are required")
        host_ids = sorted({int(host_id) for host_id in bk_host_ids})
        if not host_ids or any(host_id <= 0 for host_id in host_ids):
            raise NodeManV3PayloadError("plugin deployment requires positive host IDs")
        if resource_type == NodeManResourceType.PROXY_PLUGIN_DEPLOYMENT and bk_cloud_id is None:
            raise NodeManV3PayloadError("proxy plugin deployment requires bk_cloud_id")

        with transaction.atomic():
            return self._ensure_hosts_in_transaction(
                resource_type=resource_type,
                owner_bk_tenant_id=owner_bk_tenant_id,
                execution_bk_tenant_id=execution_bk_tenant_id,
                bk_biz_id=bk_biz_id,
                plugin_name=plugin_name,
                plugin_version=plugin_version,
                host_ids=host_ids,
                bk_cloud_id=bk_cloud_id,
            )

    def _ensure_hosts_in_transaction(
        self,
        *,
        resource_type: NodeManResourceType,
        owner_bk_tenant_id: str,
        execution_bk_tenant_id: str,
        bk_biz_id: int,
        plugin_name: str,
        plugin_version: str,
        host_ids: list[int],
        bk_cloud_id: int | None,
    ) -> list[PluginHostDeployment]:
        full_scope = {
            "object_type": "HOST",
            "node_type": "INSTANCE",
            "nodes": [{"bk_host_id": host_id} for host_id in host_ids],
        }
        resolved_scopes = self.policy_service.scope_resolver.resolve(
            owner_bk_tenant_id=owner_bk_tenant_id,
            execution_bk_tenant_id=execution_bk_tenant_id,
            bk_biz_id=bk_biz_id,
            scope=full_scope,
            payload_builder=self.policy_service.payload_builder,
        )
        host_biz_ids = {
            int(host_id): int(item["scope"]["bk_biz_id"])
            for item in resolved_scopes
            for host_id in item["scope"]["instance_ids"]
        }

        deployments = []
        for host_id in host_ids:
            host_scope = {
                "object_type": "HOST",
                "node_type": "INSTANCE",
                "nodes": [{"bk_host_id": host_id}],
            }
            resolved_host_scope = [
                {
                    "type": "instance",
                    "scope": {
                        "granularity": "host",
                        "bk_biz_id": host_biz_ids[host_id],
                        "instance_ids": [host_id],
                    },
                }
            ]
            key_components = {"bk_host_id": host_id, "plugin_name": plugin_name}
            policy_name_parts = ["bkm", "official-plugin", str(host_id), plugin_name]
            if resource_type == NodeManResourceType.PROXY_PLUGIN_DEPLOYMENT:
                assert bk_cloud_id is not None
                key_components["bk_cloud_id"] = bk_cloud_id
                policy_name_parts = ["bkm", "proxy-plugin", str(bk_cloud_id), str(host_id), plugin_name]
            submission = self.policy_service.ensure(
                resource_type=resource_type,
                resource_key=build_nodeman_resource_key(resource_type, **key_components),
                owner_bk_tenant_id=owner_bk_tenant_id,
                execution_bk_tenant_id=execution_bk_tenant_id,
                bk_biz_id=bk_biz_id,
                policy_name="-".join(policy_name_parts),
                description=f"bk-monitor ensures {plugin_name}@{plugin_version} on host {host_id}",
                scope=host_scope,
                steps=[
                    {
                        "type": "PLUGIN",
                        "config": {"plugin_name": plugin_name, "plugin_version": plugin_version},
                        "params": {"context": {}},
                    }
                ],
                resolved_scopes=resolved_host_scope,
            )
            deployments.append(PluginHostDeployment(bk_host_id=host_id, submission=submission))
        return deployments
